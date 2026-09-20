"""
The constitution ledger.

A hash chain over the community's constitution, signed at ratification.

The vocabulary is borrowed from cryptocurrency on purpose, and only where it is
literally accurate. Each adopted version is a **block**. Each block records the
**hash** of its own text and the hash of the block before it, so the versions
form a **chain** starting from a **genesis block**. Ratification is an
**N-of-M multi-signature**: a threshold of named officials sign the block, and
the signatures are verified here rather than asserted. A block may carry
**anchors**: external witnesses that prove the block existed by a certain time.

What this is not, said plainly because the difference matters: there is no
distributed consensus, no mining, no token, and no decentralization. One
operator runs one server. The chain makes tampering **detectable**, not
impossible. Detectable is the guarantee that actually addresses the threat here,
which is not a cryptographic attacker but a quiet edit, a vendor's denial, and a
dispute a year later about what the rules said in March.

Design notes:

* **Hashes live in ledger.json, never in the constitution file.** Putting a
  file's hash inside the file is circular. The markdown stays pure text.
* **Signatures sign the block header, not the signature list.** Otherwise each
  new signature would change what the others signed.
* **Verification runs on load.** An edited adopted version fails loudly instead
  of quietly governing answers under a version number that no longer describes it.

Keys are Ed25519 and public keys are stored in the familiar
``ssh-ed25519 AAAA...`` one-line format, so a roster is diffable in a pull
request and recognizable to anyone who has used SSH.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import struct
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONSTITUTION_DIR = REPO_ROOT / "constitution"

LEDGER_FILENAME = "ledger.json"
SIGNERS_FILENAME = "signers.json"

# The genesis block's predecessor. Sixty-four zeros, the same convention a
# blockchain uses for the first block.
GENESIS_PREV = "sha256:" + "0" * 64

_VERSION_FILE_RE = re.compile(r"^constitution-v(?P<version>\d+(?:\.\d+)*)\.md$")


class LedgerError(RuntimeError):
    """A ledger problem an operator needs to see."""


# --- hashing --------------------------------------------------------------


def canonical_text(raw: str) -> str:
    """Normalize text so a hash survives harmless editor differences.

    Line endings and trailing whitespace are normalized; nothing else is
    touched. A hash that changed because someone's editor added a final newline
    would train people to ignore verification failures, which is worse than
    having none.
    """
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def hash_text(raw: str) -> str:
    digest = hashlib.sha256(canonical_text(raw).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def hash_file(path: Path) -> str:
    return hash_text(path.read_text(encoding="utf-8"))


def short(digest: str) -> str:
    """The first eight hex characters, for display. Like a git short hash."""
    return digest.split(":")[-1][:8]


# --- ssh-format Ed25519 keys ---------------------------------------------


def parse_ssh_public_key(line: str) -> bytes:
    """Extract the raw 32-byte Ed25519 key from an ``ssh-ed25519 AAAA...`` line."""
    parts = line.strip().split()
    blob_b64 = next((p for p in parts if p.startswith("AAAA")), None)
    if blob_b64 is None:
        raise LedgerError(f"not an SSH public key line: {line[:40]!r}")

    try:
        blob = base64.b64decode(blob_b64)
    except Exception as exc:
        raise LedgerError(f"could not decode the key blob: {exc}") from exc

    offset = 0
    fields: List[bytes] = []
    while offset + 4 <= len(blob):
        (length,) = struct.unpack(">I", blob[offset:offset + 4])
        offset += 4
        if offset + length > len(blob):
            break
        fields.append(blob[offset:offset + length])
        offset += length

    if len(fields) < 2 or fields[0] != b"ssh-ed25519":
        raise LedgerError(
            "only ssh-ed25519 keys are supported. Generate one with "
            "`ssh-keygen -t ed25519`, or use `python3 -m community.ledger keygen`."
        )
    if len(fields[1]) != 32:
        raise LedgerError("the Ed25519 public key is not 32 bytes")
    return fields[1]


def format_ssh_public_key(raw: bytes, comment: str = "") -> str:
    blob = (struct.pack(">I", len(b"ssh-ed25519")) + b"ssh-ed25519"
            + struct.pack(">I", len(raw)) + raw)
    line = f"ssh-ed25519 {base64.b64encode(blob).decode('ascii')}"
    return f"{line} {comment}".strip()


def key_id(raw_public_key: bytes) -> str:
    """A short fingerprint, the way SSH shows one."""
    digest = hashlib.sha256(raw_public_key).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def _ed25519():
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
        return ed25519
    except Exception as exc:
        raise LedgerError(
            "Ed25519 support needs the 'cryptography' package. "
            "Install it with: pip install cryptography"
        ) from exc


def generate_keypair() -> Tuple[str, str]:
    """Create a ratifier keypair. Returns ``(private_b64, ssh_public_line)``."""
    ed25519 = _ed25519()
    private = ed25519.Ed25519PrivateKey.generate()
    from cryptography.hazmat.primitives import serialization

    raw_private = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    raw_public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return (base64.b64encode(raw_private).decode("ascii"),
            format_ssh_public_key(raw_public))


def sign_bytes(private_b64: str, payload: bytes) -> str:
    ed25519 = _ed25519()
    raw = base64.b64decode(private_b64)
    key = ed25519.Ed25519PrivateKey.from_private_bytes(raw)
    return base64.b64encode(key.sign(payload)).decode("ascii")


def verify_bytes(ssh_public_line: str, signature_b64: str, payload: bytes) -> bool:
    ed25519 = _ed25519()
    try:
        raw_public = parse_ssh_public_key(ssh_public_line)
        key = ed25519.Ed25519PublicKey.from_public_bytes(raw_public)
        key.verify(base64.b64decode(signature_b64), payload)
        return True
    except Exception:
        return False


# --- blocks ---------------------------------------------------------------


@dataclass
class Signature:
    signer: str
    key_id: str
    signature: str
    signed_at: str = ""
    role: str = ""
    verified: Optional[bool] = None   # filled in by verification, not stored

    def to_stored(self) -> Dict[str, Any]:
        return {"signer": self.signer, "key_id": self.key_id,
                "signature": self.signature, "signed_at": self.signed_at,
                "role": self.role}


@dataclass
class Anchor:
    """An external witness that the block existed by a certain time.

    ``kind`` is one of:
      * ``minutes``   published in the community's own meeting minutes. The most
                      civically appropriate witness a town has, and the one that
                      outlives this software.
      * ``rekor``     an entry in Sigstore's public transparency log.
      * ``ots``       an OpenTimestamps proof anchored into Bitcoin.
      * ``rfc3161``   a timestamp authority's signed token.
    """

    kind: str
    reference: str
    anchored_at: str = ""
    note: str = ""

    def to_stored(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Block:
    """One adopted constitution version."""

    index: int
    version: str
    content_hash: str
    prev_hash: str
    adopted: str = ""
    status: str = "draft"
    summary: str = ""
    threshold: int = 0
    signatures: List[Signature] = field(default_factory=list)
    anchors: List[Anchor] = field(default_factory=list)

    # Computed, never stored: storing a block's own hash invites it drifting
    # from the header it is supposed to summarize.
    block_hash: str = ""
    verification: Dict[str, Any] = field(default_factory=dict)

    def header(self) -> Dict[str, Any]:
        """The fields the block hash covers, and that signatures sign.

        Signatures and anchors are excluded on purpose. Both are added *after*
        ratification begins, and a header that changed with each new signature
        would invalidate the signatures already collected.
        """
        return {
            "index": self.index,
            "version": self.version,
            "content_hash": self.content_hash,
            "prev_hash": self.prev_hash,
            "adopted": self.adopted,
        }

    def compute_hash(self) -> str:
        canonical = json.dumps(self.header(), sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def signing_payload(self) -> bytes:
        """What a ratifier signs: a domain-separated block hash.

        The prefix keeps a constitution signature from being replayed as a
        signature over anything else this project might sign later.
        """
        return b"community-ai/constitution-block/v1\n" + self.compute_hash().encode()

    @property
    def is_genesis(self) -> bool:
        return self.index == 0

    @property
    def ratified(self) -> bool:
        if self.status != "adopted":
            return False
        valid = sum(1 for s in self.signatures if s.verified)
        return self.threshold > 0 and valid >= self.threshold

    def to_stored(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "version": self.version,
            "content_hash": self.content_hash,
            "prev_hash": self.prev_hash,
            "adopted": self.adopted,
            "status": self.status,
            "summary": self.summary,
            "threshold": self.threshold,
            "signatures": [s.to_stored() for s in self.signatures],
            "anchors": [a.to_stored() for a in self.anchors],
        }

    def to_public(self) -> Dict[str, Any]:
        valid = sum(1 for s in self.signatures if s.verified)
        return {
            "index": self.index,
            "version": self.version,
            "content_hash": self.content_hash,
            "content_hash_short": short(self.content_hash),
            "prev_hash": self.prev_hash,
            "prev_hash_short": short(self.prev_hash),
            "block_hash": self.block_hash or self.compute_hash(),
            "block_hash_short": short(self.block_hash or self.compute_hash()),
            "adopted": self.adopted,
            "status": self.status,
            "summary": self.summary,
            "genesis": self.is_genesis,
            "ratified": self.ratified,
            "threshold": self.threshold,
            "signatures_valid": valid,
            "signatures": [
                {"signer": s.signer, "role": s.role, "key_id": s.key_id,
                 "signed_at": s.signed_at, "verified": s.verified}
                for s in self.signatures
            ],
            "anchors": [a.to_stored() for a in self.anchors],
            "verification": self.verification,
        }


# --- the chain ------------------------------------------------------------


@dataclass
class Ledger:
    directory: Path
    blocks: List[Block] = field(default_factory=list)
    signers: Dict[str, Dict[str, str]] = field(default_factory=dict)
    problems: List[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.problems

    @property
    def head(self) -> Optional[Block]:
        return self.blocks[-1] if self.blocks else None

    def block_for_version(self, version: str) -> Optional[Block]:
        for block in self.blocks:
            if block.version == version:
                return block
        return None

    def to_public(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "problems": self.problems,
            "block_count": len(self.blocks),
            "head": self.head.to_public() if self.head else None,
            "signers": [
                {"name": name, "role": info.get("role", ""),
                 "key_id": info.get("key_id", "")}
                for name, info in sorted(self.signers.items())
            ],
            "blocks": [b.to_public() for b in self.blocks],
        }


def ledger_path(directory: Optional[Path] = None) -> Path:
    return (Path(directory) if directory else DEFAULT_CONSTITUTION_DIR) / LEDGER_FILENAME


def signers_path(directory: Optional[Path] = None) -> Path:
    return (Path(directory) if directory else DEFAULT_CONSTITUTION_DIR) / SIGNERS_FILENAME


def load_signers(directory: Optional[Path] = None) -> Dict[str, Dict[str, str]]:
    path = signers_path(directory)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    signers: Dict[str, Dict[str, str]] = {}
    for entry in data.get("signers", []):
        name = entry.get("name")
        public_key = entry.get("public_key", "")
        if not name or not public_key:
            continue
        try:
            fingerprint = key_id(parse_ssh_public_key(public_key))
        except LedgerError:
            fingerprint = ""
        signers[name] = {
            "public_key": public_key,
            "role": entry.get("role", ""),
            "key_id": fingerprint,
        }
    return signers


def load_ledger(directory: Optional[Path] = None, verify: bool = True) -> Ledger:
    """Read the chain and, by default, check it."""
    directory = Path(directory) if directory else DEFAULT_CONSTITUTION_DIR
    ledger = Ledger(directory=directory, signers=load_signers(directory))

    path = ledger_path(directory)
    if not path.is_file():
        return ledger

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        ledger.problems.append(f"{LEDGER_FILENAME} could not be read: {exc}")
        return ledger

    for raw in data.get("blocks", []):
        block = Block(
            index=int(raw.get("index", 0)),
            version=str(raw.get("version", "")),
            content_hash=raw.get("content_hash", ""),
            prev_hash=raw.get("prev_hash", GENESIS_PREV),
            adopted=raw.get("adopted", ""),
            status=raw.get("status", "draft"),
            summary=raw.get("summary", ""),
            threshold=int(raw.get("threshold", 0) or 0),
            signatures=[
                Signature(
                    signer=s.get("signer", ""), key_id=s.get("key_id", ""),
                    signature=s.get("signature", ""), signed_at=s.get("signed_at", ""),
                    role=s.get("role", ""),
                )
                for s in raw.get("signatures", [])
            ],
            anchors=[
                Anchor(kind=a.get("kind", ""), reference=a.get("reference", ""),
                       anchored_at=a.get("anchored_at", ""), note=a.get("note", ""))
                for a in raw.get("anchors", [])
            ],
        )
        block.block_hash = block.compute_hash()
        ledger.blocks.append(block)

    ledger.blocks.sort(key=lambda b: b.index)

    if verify:
        verify_ledger(ledger)
    return ledger


def verify_ledger(ledger: Ledger) -> Ledger:
    """Check every link, every file hash, and every signature."""
    previous: Optional[Block] = None

    for block in ledger.blocks:
        checks: Dict[str, Any] = {}

        # 1. The file on disk still hashes to what the block recorded.
        file_path = ledger.directory / f"constitution-v{block.version}.md"
        if not file_path.is_file():
            checks["file_present"] = False
            ledger.problems.append(
                f"block {block.index} (v{block.version}): "
                f"constitution-v{block.version}.md is missing"
            )
        else:
            checks["file_present"] = True
            actual = hash_file(file_path)
            checks["content_hash_matches"] = actual == block.content_hash
            if not checks["content_hash_matches"]:
                ledger.problems.append(
                    f"block {block.index} (v{block.version}): the file has changed "
                    f"since it was sealed. Ledger says {short(block.content_hash)}, "
                    f"the file is {short(actual)}. An adopted version must never be "
                    f"edited in place; adopt a new version instead."
                )

        # 2. The chain links.
        if previous is None:
            checks["links_to_genesis"] = block.prev_hash == GENESIS_PREV
            if not checks["links_to_genesis"]:
                ledger.problems.append(
                    f"block {block.index}: the first block must point at the "
                    f"genesis hash"
                )
        else:
            expected = previous.compute_hash()
            checks["links_to_previous"] = block.prev_hash == expected
            if not checks["links_to_previous"]:
                ledger.problems.append(
                    f"block {block.index} (v{block.version}): does not link to "
                    f"block {previous.index}. Expected prev_hash "
                    f"{short(expected)}, found {short(block.prev_hash)}."
                )
            if block.index != previous.index + 1:
                ledger.problems.append(
                    f"block index jumps from {previous.index} to {block.index}"
                )

        # 3. Signatures.
        payload = block.signing_payload()
        valid = 0
        for signature in block.signatures:
            signer = ledger.signers.get(signature.signer)
            if not signer:
                signature.verified = False
                ledger.problems.append(
                    f"block {block.index}: signature from {signature.signer!r}, "
                    f"who is not in {SIGNERS_FILENAME}"
                )
                continue
            signature.verified = verify_bytes(
                signer["public_key"], signature.signature, payload
            )
            if signature.verified:
                valid += 1
            else:
                ledger.problems.append(
                    f"block {block.index}: signature from {signature.signer!r} "
                    f"does not verify against their recorded key"
                )
        checks["signatures_valid"] = valid
        checks["threshold"] = block.threshold

        if block.status == "adopted":
            checks["threshold_met"] = block.threshold > 0 and valid >= block.threshold
            if not checks["threshold_met"]:
                ledger.problems.append(
                    f"block {block.index} (v{block.version}) is marked adopted but "
                    f"has {valid} valid signature(s) against a threshold of "
                    f"{block.threshold}"
                )

        checks["anchored"] = bool(block.anchors)
        block.verification = checks
        previous = block

    return ledger


def save_ledger(ledger: Ledger) -> None:
    payload = {
        "$schema": "community-ai/constitution-ledger/v1",
        "description": (
            "A hash chain of adopted constitution versions. Each block records "
            "the hash of its text and of the block before it. Ratification is an "
            "N-of-M multi-signature over the block header. Verify with: "
            "python3 -m community.ledger verify"
        ),
        "blocks": [b.to_stored() for b in ledger.blocks],
    }
    path = ledger_path(ledger.directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def seal_version(version: str, directory: Optional[Path] = None,
                 status: str = "draft", adopted: str = "",
                 summary: str = "", threshold: int = 0) -> Block:
    """Add a version to the chain as a new block.

    Sealing records what the text *is*. Ratifying, which happens afterwards
    through signatures, records that the community *adopted* it.
    """
    directory = Path(directory) if directory else DEFAULT_CONSTITUTION_DIR
    file_path = directory / f"constitution-v{version}.md"
    if not file_path.is_file():
        raise LedgerError(f"no such constitution file: {file_path}")

    ledger = load_ledger(directory, verify=False)
    if ledger.block_for_version(version):
        raise LedgerError(
            f"version {version} is already in the ledger. An adopted version is "
            f"never re-sealed; create a new version instead."
        )

    head = ledger.head
    block = Block(
        index=(head.index + 1) if head else 0,
        version=version,
        content_hash=hash_file(file_path),
        prev_hash=head.compute_hash() if head else GENESIS_PREV,
        adopted=adopted or datetime.now().strftime("%Y-%m-%d"),
        status=status,
        summary=summary,
        threshold=threshold,
    )
    block.block_hash = block.compute_hash()
    ledger.blocks.append(block)
    save_ledger(ledger)
    return block


def add_signature(version: str, signer: str, private_key_b64: str,
                  directory: Optional[Path] = None) -> Block:
    """Sign a block as a named ratifier."""
    directory = Path(directory) if directory else DEFAULT_CONSTITUTION_DIR
    ledger = load_ledger(directory, verify=False)
    block = ledger.block_for_version(version)
    if not block:
        raise LedgerError(f"version {version} is not in the ledger. Seal it first.")

    signers = ledger.signers
    if signer not in signers:
        raise LedgerError(
            f"{signer!r} is not in {SIGNERS_FILENAME}. Add their public key "
            f"first, in a commit, so the roster is part of the record."
        )

    signature = sign_bytes(private_key_b64, block.signing_payload())
    if not verify_bytes(signers[signer]["public_key"], signature, block.signing_payload()):
        raise LedgerError(
            f"the signature does not verify against the public key recorded for "
            f"{signer!r}. The private key does not match the roster."
        )

    block.signatures = [s for s in block.signatures if s.signer != signer]
    block.signatures.append(Signature(
        signer=signer,
        key_id=signers[signer].get("key_id", ""),
        signature=signature,
        signed_at=datetime.now().strftime("%Y-%m-%d"),
        role=signers[signer].get("role", ""),
    ))
    save_ledger(ledger)
    return block


def add_anchor(version: str, kind: str, reference: str, note: str = "",
               directory: Optional[Path] = None) -> Block:
    """Record an external witness to when this block existed."""
    directory = Path(directory) if directory else DEFAULT_CONSTITUTION_DIR
    ledger = load_ledger(directory, verify=False)
    block = ledger.block_for_version(version)
    if not block:
        raise LedgerError(f"version {version} is not in the ledger")

    block.anchors.append(Anchor(
        kind=kind, reference=reference, note=note,
        anchored_at=datetime.now().strftime("%Y-%m-%d"),
    ))
    save_ledger(ledger)
    return block


# --- command line ---------------------------------------------------------


def _cmd_verify(args) -> int:
    ledger = load_ledger(args.directory)
    print(f"Constitution ledger: {len(ledger.blocks)} block(s)")
    print()
    for block in ledger.blocks:
        marker = "genesis" if block.is_genesis else f"<- {short(block.prev_hash)}"
        valid = sum(1 for s in block.signatures if s.verified)
        state = "RATIFIED" if block.ratified else block.status
        print(f"  [{block.index}] v{block.version:<6} {short(block.content_hash)} "
              f"{marker:<16} {state:<10} {valid}/{block.threshold or '-'} sigs"
              f"{'  anchored' if block.anchors else ''}")
    print()
    if ledger.valid:
        print("Chain verified. Every block links, every file matches its hash,")
        print("and every signature checks out.")
        return 0
    print(f"{len(ledger.problems)} problem(s):")
    for problem in ledger.problems:
        print(f"  - {problem}")
    return 1


def _cmd_seal(args) -> int:
    block = seal_version(args.version, args.directory, status=args.status,
                         adopted=args.adopted or "", summary=args.summary or "",
                         threshold=args.threshold)
    print(f"Sealed v{block.version} as block {block.index}")
    print(f"  content hash: {block.content_hash}")
    print(f"  prev hash:    {block.prev_hash}")
    print(f"  block hash:   {block.compute_hash()}")
    print()
    print("Ratifiers sign this block hash. Read it into the minutes:")
    print(f"  {short(block.compute_hash())}")
    return 0


def _cmd_keygen(args) -> int:
    private_b64, public_line = generate_keypair()
    print("Private key (keep this secret, it is how you sign):")
    print(f"  {private_b64}")
    print()
    print(f"Public key (commit this to {SIGNERS_FILENAME}):")
    print(f"  {public_line} {args.name or ''}".rstrip())
    return 0


def _cmd_sign(args) -> int:
    private_b64 = args.key
    if private_b64 and os.path.isfile(private_b64):
        private_b64 = Path(private_b64).read_text(encoding="utf-8").strip()
    block = add_signature(args.version, args.signer, private_b64, args.directory)
    valid = sum(1 for s in block.signatures if s.verified is not False)
    print(f"Signed block {block.index} (v{block.version}) as {args.signer}")
    print(f"  {len(block.signatures)} signature(s) recorded, threshold "
          f"{block.threshold or 'not set'}")
    return 0


def _cmd_anchor(args) -> int:
    block = add_anchor(args.version, args.kind, args.reference, args.note or "",
                       args.directory)
    print(f"Anchored block {block.index} (v{block.version}) via {args.kind}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="The constitution ledger: a signed hash chain of adopted versions.",
    )
    parser.add_argument("--directory", type=Path, default=None,
                        help="constitution directory (default: ./constitution)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("verify", help="check the whole chain")
    p.set_defaults(func=_cmd_verify)

    p = sub.add_parser("seal", help="add a version to the chain")
    p.add_argument("version")
    p.add_argument("--status", default="draft", choices=["draft", "adopted", "superseded"])
    p.add_argument("--adopted", help="date, YYYY-MM-DD")
    p.add_argument("--summary", help="one line on what changed")
    p.add_argument("--threshold", type=int, default=0,
                   help="signatures required to ratify")
    p.set_defaults(func=_cmd_seal)

    p = sub.add_parser("keygen", help="create a ratifier keypair")
    p.add_argument("--name", help="comment for the public key line")
    p.set_defaults(func=_cmd_keygen)

    p = sub.add_parser("sign", help="sign a block as a ratifier")
    p.add_argument("version")
    p.add_argument("--signer", required=True, help="name as it appears in signers.json")
    p.add_argument("--key", required=True, help="private key, or a path to it")
    p.set_defaults(func=_cmd_sign)

    p = sub.add_parser("anchor", help="record an external timestamp")
    p.add_argument("version")
    p.add_argument("--kind", required=True,
                   choices=["minutes", "rekor", "ots", "rfc3161"])
    p.add_argument("--reference", required=True)
    p.add_argument("--note")
    p.set_defaults(func=_cmd_anchor)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except LedgerError as exc:
        print(f"error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
