"""
Compare two evaluation runs.

Section 19 of the guide asks whether a fine-tune "measurably improves the
desired behavior without damaging general capability". That is a comparison, not
a score: a run that gains four civic cases and loses three general-capability
cases has not improved anything, and a single aggregate number hides it.

    python3 -m evals.compare results/before.json results/after.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict


def verdicts(run: Dict[str, Any]) -> Dict[str, str]:
    out = {}
    for result in run.get("results", []):
        retrieval_failed = result.get("retrieval_scored") and not result.get("retrieval_passed")
        generation_failed = result.get("generation_scored") and not result.get("generation_passed")
        if retrieval_failed:
            out[result["id"]] = "retrieval_problem"
        elif generation_failed:
            out[result["id"]] = "generation_problem"
        elif result.get("retrieval_scored") or result.get("generation_scored"):
            out[result["id"]] = "pass"
        else:
            out[result["id"]] = "not_scored"
    return out


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    if len(argv) != 2:
        print(__doc__)
        return 2

    before = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    after = json.loads(Path(argv[1]).read_text(encoding="utf-8"))

    before_v, after_v = verdicts(before), verdicts(after)
    categories = {r["id"]: r.get("category", "") for r in after.get("results", [])}

    print(f"before: {before.get('model')} / constitution v{before.get('constitution_version')} "
          f"({before.get('run_at')})")
    print(f"after:  {after.get('model')} / constitution v{after.get('constitution_version')} "
          f"({after.get('run_at')})")
    print()

    fixed, broken, still = [], [], []
    for case_id in sorted(set(before_v) | set(after_v)):
        b, a = before_v.get(case_id), after_v.get(case_id)
        if b is None or a is None:
            continue
        if b != "pass" and a == "pass":
            fixed.append(case_id)
        elif b == "pass" and a != "pass":
            broken.append((case_id, a))
        elif b != "pass" and a != "pass":
            still.append(case_id)

    print(f"FIXED    {len(fixed)}")
    for case_id in fixed:
        print(f"   + {case_id}  ({categories.get(case_id, '')})")

    print(f"\nBROKEN   {len(broken)}")
    for case_id, verdict in broken:
        print(f"   - {case_id}  ({categories.get(case_id, '')})  now {verdict}")

    print(f"\nSTILL FAILING  {len(still)}")

    only_in_after = set(after_v) - set(before_v)
    if only_in_after:
        print(f"\nNEW CASES (not in the earlier run): {len(only_in_after)}")
        print("   A frozen set should only grow. Cases present before and absent")
        print("   now would mean the set was edited, which invalidates comparison.")

    missing = set(before_v) - set(after_v)
    if missing:
        print(f"\nWARNING: {len(missing)} cases from the earlier run are missing:")
        for case_id in sorted(missing):
            print(f"   ? {case_id}")

    print()
    if broken:
        print("Verdict: this change breaks cases that previously passed.")
        return 1
    if fixed:
        print("Verdict: strict improvement.")
        return 0
    print("Verdict: no change in pass/fail.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
