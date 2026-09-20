"""
Run the frozen evaluation set.

The central discipline from section 16 of the guide: when an answer is wrong,
first determine whether retrieval found the right passage. If the correct
evidence never reached the model, the problem is search, chunking, metadata, or
ranking. If the evidence was there and the answer is still wrong, the problem is
generation, prompting, or policy adherence.

This runner therefore scores two things and never averages them together.

Usage:

    python3 -m evals.run_evals --project brookline-ma --retrieval-only
    python3 -m evals.run_evals --project brookline-ma
    python3 -m evals.run_evals --project brookline-ma --category ambiguous
    python3 -m evals.run_evals --project brookline-ma --json results/v0.1.json
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

EVAL_DIR = Path(__file__).resolve().parent

# Phrases that count as the assistant declining to state a local fact it does
# not have. Matching on phrasing is crude; it is checked only for cases that
# explicitly set `must_abstain`, where the expected behavior is narrow.
ABSTENTION_MARKERS = (
    "do not have", "don't have", "no record", "not in the", "could not find",
    "cannot find", "unable to find", "not available in", "is not something i have",
    "knowledge base does not", "knowledge base doesn't", "nothing in the",
    "no information", "not been ingested", "i cannot reliably", "can't reliably",
    "does not appear in", "no such record",
)


@dataclass
class CaseResult:
    id: str
    category: str
    question: str
    retrieval_scored: bool = False
    retrieval_passed: Optional[bool] = None
    generation_scored: bool = False
    generation_passed: Optional[bool] = None
    failures: List[str] = field(default_factory=list)
    sources_retrieved: int = 0
    sources_used: int = 0
    answer: str = ""
    principles: List[int] = field(default_factory=list)
    elapsed_ms: float = 0.0

    @property
    def verdict(self) -> str:
        """The section 16 triage: which subsystem owns this failure."""
        if self.retrieval_scored and self.retrieval_passed is False:
            return "retrieval_problem"
        if self.generation_scored and self.generation_passed is False:
            return "generation_problem"
        if self.generation_scored or self.retrieval_scored:
            return "pass"
        return "not_scored"


def load_cases(category: Optional[str] = None,
               files: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    paths = files or sorted(glob.glob(str(EVAL_DIR / "*.jsonl")))
    cases: List[Dict[str, Any]] = []
    seen_ids = set()

    for path in paths:
        with open(path, "r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    case = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}")

                if "id" not in case or "question" not in case:
                    raise SystemExit(f"{path}:{line_no}: case needs 'id' and 'question'")
                if case["id"] in seen_ids:
                    raise SystemExit(f"{path}:{line_no}: duplicate case id {case['id']!r}")
                seen_ids.add(case["id"])

                if category and case.get("category") != category:
                    continue
                case.setdefault("_file", os.path.basename(path))
                cases.append(case)

    return cases


def _source_text(citation: Dict[str, Any], chunk_text: str = "") -> str:
    return " ".join(str(citation.get(k, "")) for k in
                    ("title", "label", "url", "body", "speaker", "agenda_item")) + " " + chunk_text


def score_retrieval(case: Dict[str, Any], citations: List[Dict[str, Any]],
                    texts: List[str]) -> tuple[bool, Optional[bool], List[str]]:
    """Did the passage the answer needs actually reach the model?"""
    expected = case.get("expect_sources") or []
    if not expected:
        return False, None, []

    haystacks = [
        _source_text(citation, text).lower()
        for citation, text in zip(citations, texts + [""] * len(citations))
    ]
    for needle in expected:
        if any(needle.lower() in haystack for haystack in haystacks):
            return True, True, []

    return True, False, [
        f"no retrieved passage matched any of {expected}"
    ]


def score_generation(case: Dict[str, Any], answer: str,
                     has_citations: bool) -> tuple[bool, Optional[bool], List[str]]:
    """Did the answer follow the constitution given what it was shown?"""
    checks_present = any(
        key in case for key in
        ("must_include", "must_not_include", "must_abstain", "must_cite")
    )
    if not checks_present:
        return False, None, []

    failures: List[str] = []
    lowered = (answer or "").lower()

    for needle in case.get("must_include") or []:
        if needle.lower() not in lowered:
            failures.append(f"missing required text: {needle!r}")

    for needle in case.get("must_not_include") or []:
        if needle.lower() in lowered:
            failures.append(f"contains forbidden text: {needle!r}")

    if case.get("must_abstain"):
        if not any(marker in lowered for marker in ABSTENTION_MARKERS):
            failures.append("did not say the record is missing")

    if case.get("must_cite") and not has_citations:
        failures.append("answer carries no citation")

    return True, not failures, failures


def run(project_id: str, category: Optional[str] = None,
        retrieval_only: bool = False, top_k: int = 8,
        limit: Optional[int] = None, verbose: bool = False) -> Dict[str, Any]:
    """Run the set against one project."""
    # Imported here so --help works without the inference stack installed.
    sys.path.insert(0, str(EVAL_DIR.parent))
    from agent import NeighborhoodAgent
    from rag.citations import build_citations, extract_citation_numbers

    config_path = Path("./data") / project_id / "config.json"
    if not config_path.is_file():
        raise SystemExit(f"No project at {config_path}. Create it first.")

    from models import ProjectConfig

    project = ProjectConfig(**json.loads(config_path.read_text(encoding="utf-8")))
    agent = NeighborhoodAgent(project)

    cases = load_cases(category=category)
    if limit:
        cases = cases[:limit]
    if not cases:
        raise SystemExit("No evaluation cases matched.")

    print(f"Running {len(cases)} cases against {project.project_name} "
          f"({project.municipality_name})")
    print(f"  model:        {project.model_name} via {agent.client_type}")
    print(f"  constitution: v{agent.constitution.version} "
          f"({len(agent.constitution.principles)} principles, {agent.constitution.status})")
    print(f"  mode:         {'retrieval only' if retrieval_only else 'retrieval + generation'}")
    print()

    results: List[CaseResult] = []

    for case in cases:
        started = time.perf_counter()
        result = CaseResult(
            id=case["id"],
            category=case.get("category", "uncategorized"),
            question=case["question"],
            principles=case.get("principles", []),
        )

        if retrieval_only:
            retrieval = agent.retriever.retrieve(
                case["question"], top_k=top_k,
                use_reranker=getattr(project, "enable_reranking", True),
            )
            citations = [c.to_dict() for c in build_citations(retrieval.chunks)]
            texts = [c.chunk.text for c in retrieval.chunks]
            result.sources_retrieved = len(citations)
        else:
            response = agent.chat(case["question"])
            citations = response.get("sources", [])
            texts = [c.get("excerpt", "") for c in citations]
            result.answer = response.get("answer", "")
            provenance = response.get("provenance", {}) or {}
            result.sources_retrieved = provenance.get("sources_retrieved", len(citations))
            result.sources_used = provenance.get("sources_used", 0)

        scored, passed, failures = score_retrieval(case, citations, texts)
        result.retrieval_scored, result.retrieval_passed = scored, passed
        result.failures.extend(failures)

        if not retrieval_only:
            has_citations = bool(extract_citation_numbers(result.answer)) or \
                any(c.get("used") for c in citations)
            scored, passed, failures = score_generation(case, result.answer, has_citations)
            result.generation_scored, result.generation_passed = scored, passed
            result.failures.extend(failures)

        result.elapsed_ms = (time.perf_counter() - started) * 1000
        results.append(result)

        mark = {"pass": "PASS", "retrieval_problem": "RAG ", "generation_problem": "GEN ",
                "not_scored": "  - "}[result.verdict]
        print(f"  {mark}  {result.id:<20} {result.category:<24} "
              f"{result.sources_retrieved} src  {result.elapsed_ms:6.0f}ms")
        if verbose and result.failures:
            for failure in result.failures:
                print(f"           {failure}")

    return summarize(results, project_id, project, agent, retrieval_only)


def summarize(results: List[CaseResult], project_id: str, project: Any,
              agent: Any, retrieval_only: bool) -> Dict[str, Any]:
    retrieval_scored = [r for r in results if r.retrieval_scored]
    generation_scored = [r for r in results if r.generation_scored]

    by_category: Dict[str, Dict[str, int]] = {}
    for result in results:
        entry = by_category.setdefault(
            result.category, {"total": 0, "pass": 0, "retrieval_problem": 0,
                              "generation_problem": 0, "not_scored": 0})
        entry["total"] += 1
        entry[result.verdict] += 1

    summary = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "project_id": project_id,
        "community": project.municipality_name,
        "model": project.model_name,
        "provider": agent.client_type,
        "constitution_version": agent.constitution.version,
        "corpus_passages": agent.vector_store.get_stats().get("total_documents", 0),
        "mode": "retrieval_only" if retrieval_only else "full",
        "cases": len(results),
        "retrieval": {
            "scored": len(retrieval_scored),
            "passed": sum(1 for r in retrieval_scored if r.retrieval_passed),
            "failed": sum(1 for r in retrieval_scored if r.retrieval_passed is False),
        },
        "generation": {
            "scored": len(generation_scored),
            "passed": sum(1 for r in generation_scored if r.generation_passed),
            "failed": sum(1 for r in generation_scored if r.generation_passed is False),
        },
        "by_category": by_category,
        "results": [asdict(r) for r in results],
    }

    print()
    print("=" * 66)
    print("RESULTS")
    print("=" * 66)

    retrieval = summary["retrieval"]
    generation = summary["generation"]

    if retrieval["scored"]:
        rate = retrieval["passed"] / retrieval["scored"] * 100
        print(f"  Retrieval    {retrieval['passed']}/{retrieval['scored']} ({rate:.0f}%)"
              f"   <- chunking, metadata, ranking, filters")
    else:
        print("  Retrieval    not scored (no cases declare expect_sources)")

    if generation["scored"]:
        rate = generation["passed"] / generation["scored"] * 100
        print(f"  Generation   {generation['passed']}/{generation['scored']} ({rate:.0f}%)"
              f"   <- prompt, constitution, model")
    else:
        print("  Generation   not scored (retrieval-only run)")

    print()
    print(f"  {'category':<26} {'total':>6} {'pass':>6} {'RAG':>6} {'GEN':>6}")
    for category, entry in sorted(by_category.items()):
        print(f"  {category:<26} {entry['total']:>6} {entry['pass']:>6} "
              f"{entry['retrieval_problem']:>6} {entry['generation_problem']:>6}")

    failures = [r for r in results if r.verdict != "pass" and r.verdict != "not_scored"]
    if failures:
        print()
        print(f"  {len(failures)} failing cases:")
        for result in failures:
            owner = "RETRIEVAL" if result.verdict == "retrieval_problem" else "GENERATION"
            print(f"    [{owner}] {result.id}: {result.question[:60]}")
            for failure in result.failures:
                print(f"        {failure}")
            if result.principles:
                print(f"        principles at stake: {result.principles}")

    return summary


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", required=True, help="project id, e.g. brookline-ma")
    parser.add_argument("--category", help="run only one category")
    parser.add_argument("--retrieval-only", action="store_true",
                        help="skip generation; no inference cost")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--limit", type=int, help="run only the first N cases")
    parser.add_argument("--json", dest="json_out", help="write full results to this path")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    summary = run(
        project_id=args.project,
        category=args.category,
        retrieval_only=args.retrieval_only,
        top_k=args.top_k,
        limit=args.limit,
        verbose=args.verbose,
    )

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        print(f"\nWrote {out}")

    failed = summary["retrieval"]["failed"] + summary["generation"]["failed"]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
