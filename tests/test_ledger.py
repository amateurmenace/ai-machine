"""Tests for the constitution ledger.

The chain's whole job is to make three things impossible to do quietly: edit an
adopted version, forge a ratification, and break the link between versions.
Each gets a test.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

from community.constitution import load_constitution
from community.ledger import (
    GENESIS_PREV, LedgerError, add_anchor, add_signature, generate_keypair,
    hash_text, key_id, load_ledger, parse_ssh_public_key, seal_version,
    sign_bytes, verify_bytes,
)

PASS: List[str] = []
FAIL: List[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  -> {detail}" if not condition else ""))


def build_community(tmp: str, threshold: int = 2):
    """A scratch constitution directory with three ratifiers."""
    d = Path(tmp)
    (d / "constitution-v1.0.md").write_text(
        "# Constitution\n\n## 1. Evidence\nCite sources.\n", encoding="utf-8")
    (d / "constitution-v1.1.md").write_text(
        "# Constitution\n\n## 1. Evidence\nCite sources.\n\n"
        "## 2. Time\nDate your claims.\n", encoding="utf-8")

    keys: Dict[str, str] = {}
    signers = []
    for name, role in [("A. Chen", "Chair"), ("B. Okafor", "Member"),
                       ("C. Ramos", "Clerk")]:
        private, public = generate_keypair()
        keys[name] = private
        signers.append({"name": name, "role": role, "public_key": public})
    (d / "signers.json").write_text(json.dumps({"signers": signers}, indent=2),
                                    encoding="utf-8")
    return d, keys


def test_crypto_primitives() -> None:
    print("\nsignature primitives")
    private, public = generate_keypair()
    signature = sign_bytes(private, b"payload")

    check("a valid signature verifies", verify_bytes(public, signature, b"payload"))
    check("a different payload is rejected",
          not verify_bytes(public, signature, b"tampered"))

    other_private, other_public = generate_keypair()
    check("a different key is rejected",
          not verify_bytes(other_public, signature, b"payload"))
    check("a garbage signature is rejected",
          not verify_bytes(public, "bm90LWEtc2lnbmF0dXJl", b"payload"))

    raw = parse_ssh_public_key(public)
    check("ssh public key parses to 32 bytes", len(raw) == 32, str(len(raw)))
    check("fingerprint looks like ssh's", key_id(raw).startswith("SHA256:"))

    try:
        parse_ssh_public_key("ssh-rsa AAAAB3NzaC1yc2E")
        check("non-ed25519 keys are refused", False, "accepted an RSA key")
    except LedgerError:
        check("non-ed25519 keys are refused", True)


def test_canonical_hashing() -> None:
    print("\nhashing survives harmless edits")
    base = "# Rules\n\n## 1. Evidence\nCite sources.\n"
    check("trailing newlines do not change the hash",
          hash_text(base) == hash_text(base + "\n\n"))
    check("windows line endings do not change the hash",
          hash_text(base) == hash_text(base.replace("\n", "\r\n")))
    check("trailing spaces do not change the hash",
          hash_text(base) == hash_text("# Rules  \n\n## 1. Evidence  \nCite sources.\n"))
    check("a real edit does change the hash",
          hash_text(base) != hash_text(base.replace("Cite sources.", "Cite sources sometimes.")))
    check("hashes are labeled with their algorithm",
          hash_text(base).startswith("sha256:"))


def test_chain_construction() -> None:
    print("\nbuilding the chain")
    with tempfile.TemporaryDirectory() as tmp:
        d, _ = build_community(tmp)

        genesis = seal_version("1.0", d, status="draft", adopted="2026-09-20")
        check("genesis is block zero", genesis.index == 0)
        check("genesis points at the zero hash", genesis.prev_hash == GENESIS_PREV)
        check("genesis is flagged as genesis", genesis.is_genesis)

        second = seal_version("1.1", d, status="draft", adopted="2026-10-14")
        check("the second block is index one", second.index == 1)
        check("it links to the genesis block hash",
              second.prev_hash == genesis.compute_hash(), second.prev_hash)

        ledger = load_ledger(d)
        check("the chain verifies", ledger.valid, str(ledger.problems))
        check("head is the newest block", ledger.head.version == "1.1")

        try:
            seal_version("1.0", d)
            check("a version cannot be sealed twice", False, "re-seal succeeded")
        except LedgerError:
            check("a version cannot be sealed twice", True)


def test_editing_an_adopted_version_is_caught() -> None:
    print("\nediting an adopted version")
    with tempfile.TemporaryDirectory() as tmp:
        d, _ = build_community(tmp)
        seal_version("1.0", d, status="draft")
        check("clean chain verifies", load_ledger(d).valid)

        (d / "constitution-v1.0.md").write_text(
            "# Constitution\n\n## 1. Evidence\nCite sources when convenient.\n",
            encoding="utf-8")

        ledger = load_ledger(d)
        check("the edit breaks verification", not ledger.valid)
        check("the problem names the file and both hashes",
              any("has changed since it was sealed" in p for p in ledger.problems),
              str(ledger.problems))
        check("the problem says what to do instead",
              any("adopt a new version" in p for p in ledger.problems),
              str(ledger.problems))


def test_broken_link_is_caught() -> None:
    print("\ntampering with the chain itself")
    with tempfile.TemporaryDirectory() as tmp:
        d, _ = build_community(tmp)
        seal_version("1.0", d)
        seal_version("1.1", d)

        # Rewrite the second block to point somewhere else, as an attacker
        # splicing a version out of the history would.
        path = d / "ledger.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["blocks"][1]["prev_hash"] = "sha256:" + "ab" * 32
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        ledger = load_ledger(d)
        check("a broken link fails verification", not ledger.valid)
        check("the problem names the expected hash",
              any("does not link to block" in p for p in ledger.problems),
              str(ledger.problems))


def test_multisig_ratification() -> None:
    print("\nratification by multi-signature")
    with tempfile.TemporaryDirectory() as tmp:
        d, keys = build_community(tmp)
        seal_version("1.0", d, status="adopted", threshold=2)

        add_signature("1.0", "A. Chen", keys["A. Chen"], d)
        ledger = load_ledger(d)
        block = ledger.block_for_version("1.0")
        check("one signature is below the threshold", not block.ratified)
        check("an adopted block below threshold is a problem", not ledger.valid)

        add_signature("1.0", "B. Okafor", keys["B. Okafor"], d)
        ledger = load_ledger(d)
        block = ledger.block_for_version("1.0")
        check("two signatures reach the threshold", block.ratified)
        check("both verify", sum(1 for s in block.signatures if s.verified) == 2)
        check("the chain now verifies", ledger.valid, str(ledger.problems))

        # Signing again replaces rather than duplicates.
        add_signature("1.0", "A. Chen", keys["A. Chen"], d)
        block = load_ledger(d).block_for_version("1.0")
        check("re-signing does not double-count",
              len(block.signatures) == 2, str(len(block.signatures)))


def test_forged_signatures_are_rejected() -> None:
    print("\nforgery")
    with tempfile.TemporaryDirectory() as tmp:
        d, keys = build_community(tmp)
        seal_version("1.0", d, status="adopted", threshold=1)

        stranger_private, _ = generate_keypair()
        try:
            add_signature("1.0", "A. Chen", stranger_private, d)
            check("signing as someone else is refused", False, "forgery accepted")
        except LedgerError as exc:
            check("signing as someone else is refused", True)
            check("the refusal says the key does not match",
                  "does not verify" in str(exc), str(exc))

        try:
            add_signature("1.0", "Nobody", keys["A. Chen"], d)
            check("an unknown signer is refused", False, "stranger accepted")
        except LedgerError as exc:
            check("an unknown signer is refused", True)
            check("the refusal points at the roster",
                  "signers.json" in str(exc), str(exc))


def test_signature_tampering_is_caught() -> None:
    print("\ntampered signature bytes")
    with tempfile.TemporaryDirectory() as tmp:
        d, keys = build_community(tmp)
        seal_version("1.0", d, status="adopted", threshold=1)
        add_signature("1.0", "A. Chen", keys["A. Chen"], d)
        check("valid before tampering", load_ledger(d).valid)

        path = d / "ledger.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        signature = data["blocks"][0]["signatures"][0]["signature"]
        data["blocks"][0]["signatures"][0]["signature"] = (
            ("B" if signature[0] != "B" else "C") + signature[1:]
        )
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        ledger = load_ledger(d)
        check("a tampered signature fails", not ledger.valid)
        check("the signer is named",
              any("A. Chen" in p for p in ledger.problems), str(ledger.problems))


def test_signatures_survive_later_signatures() -> None:
    print("\nsignatures cover the header, not each other")
    with tempfile.TemporaryDirectory() as tmp:
        d, keys = build_community(tmp)
        seal_version("1.0", d, status="adopted", threshold=3)
        add_signature("1.0", "A. Chen", keys["A. Chen"], d)
        add_signature("1.0", "B. Okafor", keys["B. Okafor"], d)
        add_signature("1.0", "C. Ramos", keys["C. Ramos"], d)

        block = load_ledger(d).block_for_version("1.0")
        check("all three still verify after the others were added",
              sum(1 for s in block.signatures if s.verified) == 3,
              str([(s.signer, s.verified) for s in block.signatures]))

        add_anchor("1.0", "minutes", "Select Board minutes 2026-09-20, item 4",
                   "Block hash read into the record", d)
        block = load_ledger(d).block_for_version("1.0")
        check("signatures survive anchoring too",
              sum(1 for s in block.signatures if s.verified) == 3)
        check("the anchor is recorded", block.anchors[0].kind == "minutes")
        check("the anchor keeps its reference",
              "minutes 2026-09-20" in block.anchors[0].reference)


def test_constitution_carries_its_hash() -> None:
    print("\nthe running constitution knows its own hash")
    constitution = load_constitution()
    check("a hash is computed", constitution.content_hash.startswith("sha256:"),
          constitution.content_hash)
    check("a short form is available for display",
          len(constitution.short_hash) == 8, constitution.short_hash)
    check("it found its block in the ledger", constitution.block_index == 0,
          str(constitution.block_index))
    check("the shipped ledger verifies", constitution.ledger_verified is True,
          str(constitution.ledger_problems))
    check("the shipped constitution is honestly unratified",
          constitution.ratified is False)

    rendered = constitution.render_for_prompt("Brookline, MA")
    check("the rules state their own hash to the model",
          constitution.short_hash in rendered.split("\n")[0],
          rendered.split("\n")[0])

    summary = constitution.summary()
    check("the summary carries the hash", summary["content_hash_short"] == constitution.short_hash)
    check("the summary reports ratification", summary["ratified"] is False)


def test_missing_ledger_is_not_an_error() -> None:
    print("\na community that has not sealed anything")
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "constitution-v1.0.md").write_text("# Rules\n\n## 1. Evidence\nCite.\n",
                                                encoding="utf-8")
        ledger = load_ledger(d)
        check("an empty ledger is valid, not broken", ledger.valid)
        check("it has no blocks", ledger.blocks == [])
        check("and no head", ledger.head is None)

        constitution = load_constitution(directory=d)
        check("the constitution still loads", constitution.version == "1.0")
        check("and still gets a hash", constitution.content_hash.startswith("sha256:"))
        check("with no block index", constitution.block_index is None)


def main() -> int:
    print("=" * 62)
    print("Constitution ledger tests")
    print("=" * 62)
    for fn in [
        test_crypto_primitives,
        test_canonical_hashing,
        test_chain_construction,
        test_editing_an_adopted_version_is_caught,
        test_broken_link_is_caught,
        test_multisig_ratification,
        test_forged_signatures_are_rejected,
        test_signature_tampering_is_caught,
        test_signatures_survive_later_signatures,
        test_constitution_carries_its_hash,
        test_missing_ledger_is_not_an_error,
    ]:
        fn()
    print("\n" + "=" * 62)
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    for name in FAIL:
        print(f"  FAILED: {name}")
    return 1 if FAIL else 0


def test_all() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
