"""
Build a constitution-following training set.

Section 9 of the guide: the strongest examples carry the user question, an
incorrect answer, a critique tied to one or more principles, and a corrected
answer. That structure teaches civic epistemology rather than facts, which is
the whole reason to fine-tune at all when facts belong in RAG.

Two output formats:

* ``sft`` (default) — supervised chat examples, system + user + assistant, with
  the constitution rendered exactly as the serving pipeline renders it. Training
  on a different prompt layout than you serve loses the gains at inference.
* ``dpo`` — preference pairs (chosen = corrected answer, rejected = incorrect
  answer), for the preference methods section 11 mentions.

    python3 -m training.build_dataset --stats
    python3 -m training.build_dataset --out training/datasets/constitution-v1.jsonl
    python3 -m training.build_dataset --format dpo --out training/datasets/prefs-v1.jsonl
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from community.constitution import load_constitution  # noqa: E402

SEED_FILE = Path(__file__).resolve().parent / "seed_examples.jsonl"

CRITIQUE_INSTRUCTION = (
    "Below is a question, the community records retrieved for it, and a draft "
    "answer. Critique the draft against the community constitution, naming the "
    "principles it violates, then write a corrected answer."
)


def load_seeds(path: Path = SEED_FILE) -> List[Dict[str, Any]]:
    if not path.is_file():
        raise SystemExit(f"No seed examples at {path}")
    seeds = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            seeds.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{line_no}: {exc}")
    return seeds


def build_sft(seeds: List[Dict[str, Any]], constitution, community: str,
              include_critique: bool = True) -> Iterator[Dict[str, Any]]:
    """Emit supervised chat examples.

    Each seed yields two examples:

    1. The plain task: question plus records, answered correctly. This is the
       shape the model sees at serving time.
    2. The critique task: question, records and the bad draft, answered with a
       principle-cited critique and a correction. This is what teaches the model
       to recognize the failure rather than merely avoid one instance of it.
    """
    constitution_text = constitution.render_for_prompt(community)

    for seed in seeds:
        context = seed.get("context", "")

        yield {
            "id": f"{seed['id']}-answer",
            "principles": seed.get("principles", []),
            "messages": [
                {"role": "system", "content": constitution_text},
                {"role": "system", "content": context},
                {"role": "user", "content": seed["question"]},
                {"role": "assistant", "content": seed["good_answer"]},
            ],
        }

        if include_critique and seed.get("bad_answer") and seed.get("critique"):
            principle_refs = ", ".join(
                p.ref for p in (
                    constitution.principle(n) for n in seed.get("principles", [])
                ) if p
            )
            critique_body = seed["critique"]
            if principle_refs and principle_refs not in critique_body:
                critique_body = f"{critique_body}\n\nPrinciples at stake: {principle_refs}."

            yield {
                "id": f"{seed['id']}-critique",
                "principles": seed.get("principles", []),
                "messages": [
                    {"role": "system", "content": constitution_text},
                    {"role": "user", "content":
                        f"{CRITIQUE_INSTRUCTION}\n\n"
                        f"QUESTION:\n{seed['question']}\n\n"
                        f"RETRIEVED RECORDS:\n{context}\n\n"
                        f"DRAFT ANSWER:\n{seed['bad_answer']}"},
                    {"role": "assistant", "content":
                        f"CRITIQUE:\n{critique_body}\n\n"
                        f"CORRECTED ANSWER:\n{seed['good_answer']}"},
                ],
            }


def build_dpo(seeds: List[Dict[str, Any]], constitution, community: str
              ) -> Iterator[Dict[str, Any]]:
    """Emit preference pairs for DPO-style training."""
    constitution_text = constitution.render_for_prompt(community)
    for seed in seeds:
        if not seed.get("bad_answer"):
            continue
        yield {
            "id": f"{seed['id']}-pref",
            "principles": seed.get("principles", []),
            "system": constitution_text,
            "context": seed.get("context", ""),
            "prompt": seed["question"],
            "chosen": seed["good_answer"],
            "rejected": seed["bad_answer"],
            "reason": seed.get("critique", ""),
        }


def print_stats(seeds: List[Dict[str, Any]], constitution) -> None:
    counts: collections.Counter = collections.Counter()
    for seed in seeds:
        for number in seed.get("principles", []):
            counts[number] += 1

    print(f"Seed examples:      {len(seeds)}")
    print(f"Constitution:       v{constitution.version} "
          f"({len(constitution.principles)} principles)")
    print(f"SFT examples built: {len(seeds) * 2} (answer + critique per seed)")
    print()
    print("Principle coverage:")
    for principle in constitution.principles:
        n = counts.get(principle.number, 0)
        marker = "     " if n else "  <-- "
        print(f"  {principle.number:>2}. {principle.title:<26} {n:>3}{marker}"
              f"{'no examples' if not n else ''}")

    uncovered = [p.number for p in constitution.principles if not counts.get(p.number)]
    print()
    print(f"{len(uncovered)} of {len(constitution.principles)} principles have no "
          f"training example.")
    if uncovered:
        print("A principle with no example is a principle the adapter cannot learn.")
        print("Section 9 asks for several thousand high-quality examples before")
        print("training; this seed set is a starting shape, not a dataset.")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", help="output JSONL path")
    parser.add_argument("--format", choices=["sft", "dpo"], default="sft")
    parser.add_argument("--community", default="this community")
    parser.add_argument("--constitution-version", default="latest")
    parser.add_argument("--no-critique", action="store_true",
                        help="emit only the plain answer examples")
    parser.add_argument("--stats", action="store_true",
                        help="report principle coverage and exit")
    args = parser.parse_args(argv)

    constitution = load_constitution(version=args.constitution_version)
    if not constitution:
        raise SystemExit(
            "No constitution found. Training examples are defined against the "
            "constitution; create constitution/constitution-v1.0.md first."
        )

    seeds = load_seeds()

    if args.stats or not args.out:
        print_stats(seeds, constitution)
        if not args.out:
            print("\nPass --out to write a dataset.")
        return 0

    if args.format == "sft":
        records = list(build_sft(seeds, constitution, args.community,
                                 include_critique=not args.no_critique))
    else:
        records = list(build_dpo(seeds, constitution, args.community))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Wrote {len(records)} {args.format} examples to {out}")
    print(f"Constitution v{constitution.version} embedded in every example.")
    print()
    print("Before training, re-read training/README.md: the gate is a frozen")
    print("evaluation set and a passing retrieval-only run, not a dataset.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
