"""
Run the frozen evaluation set against several providers and publish the gap.

The project's claim is that a community can run an open model and not feel it
got the cheap version. That is a claim, not a slogan, and the only honest way to
settle it is to put the same questions to a local model and to a frontier one
and print both columns. A town that can say "we use an open model and here is
exactly what it costs us" is in a far stronger position than one arguing either
that open models are just as good or that the expensive one is necessary.

Two properties make the comparison fair rather than merely cheap.

**Retrieval runs once.** Searching the archive does not involve the language
model at all, so every provider is shown exactly the same passages. Re-running
it per provider would be slower, would spend money to learn nothing, and would
let an unlucky reranker pass one model a better passage than another and call
the difference capability. The retrieval score is therefore reported once, on
its own, and never folded into a provider's column.

**The columns are generation only.** Section 16's discipline is that a failure
belongs either to retrieval or to generation and never to both. A passage that
never arrived is the same missing passage for every provider, so blaming a model
for it would be wrong twice over.

What comes out is the table from roadmap 1.1: a pass rate per category per
provider, and a note saying where the local model is at parity. The finding is
usually that local is level on source-grounded civic questions, where the answer
is in the retrieved passage either way, and behind on general capability. Those
are different problems with different fixes, and one aggregate number hides both.

    python3 -m evals.compare_providers --project brookline-ma \\
        --providers lmstudio:gemma-4-26b-a4b anthropic:claude-opus-5 \\
                    gemini:gemini-3.1-pro
    python3 -m evals.compare_providers --project brookline-ma \\
        --providers lmstudio:gemma-4-26b-a4b anthropic:claude-opus-5 --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL_DIR.parent))

from evals.run_evals import (  # noqa: E402  (after the path fix, deliberately)
    CaseResult, load_cases, load_project, score_case, scores_generation,
)
from models import FRONTIER_PROVIDERS, LOCAL_PROVIDERS  # noqa: E402

# Within this many points, local and frontier are called level. Five is a
# judgment, not a statistic: on a set of a few hundred cases it is roughly the
# width of the noise, and a town choosing between a machine in a closet and a
# monthly bill is not served by treating 92% against 94% as a defeat.
DEFAULT_PARITY_MARGIN = 5.0

KNOWN_PROVIDERS = tuple(LOCAL_PROVIDERS) + tuple(FRONTIER_PROVIDERS)

# Short column headings. "local" rather than a model name, because that is the
# distinction the table exists to make.
COLUMN_LABELS = {
    "lmstudio": "local",
    "ollama": "local",
    "anthropic": "Claude",
    "openai": "OpenAI",
    "gemini": "Gemini",
}

# Row headings. The eval set's category ids are written for a machine; a
# published table is read by residents and a select board.
CATEGORY_LABELS = {
    "local_factual": "local factual",
    "temporal": "temporal (what is current)",
    "historical": "historical",
    "ambiguous": "ambiguous (vote vs talk)",
    "conflicting_evidence": "conflicting evidence",
    "source_absence": "source absence",
    "community_disagreement": "community disagreement",
    "attribution": "attribution",
    "general_ai": "general capability",
    "writing": "writing",
    "reasoning": "reasoning",
    "multilingual": "multilingual",
}

# The order the guide's own table uses: civic categories first, general
# capability last, so the shape of the gap is visible reading down the page.
CATEGORY_ORDER = list(CATEGORY_LABELS)


# --- providers under test -------------------------------------------------


@dataclass
class ProviderSpec:
    """One column of the table: a provider and the model it serves."""

    provider: str
    model: str
    label: str = ""

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.model}"

    @property
    def is_local(self) -> bool:
        return self.provider in LOCAL_PROVIDERS

    @property
    def is_frontier(self) -> bool:
        return self.provider in FRONTIER_PROVIDERS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key, "provider": self.provider, "model": self.model,
            "label": self.label, "local": self.is_local, "billed": self.is_frontier,
        }


def default_model_for(provider: str) -> str:
    """The model a provider is listed with, when the spec names only a provider."""
    try:
        from models import AVAILABLE_MODELS
    except Exception:
        return ""
    for entry in AVAILABLE_MODELS.get(provider, []):
        if entry.get("name") and entry["name"] != "custom":
            return str(entry["name"])
    return ""


def parse_spec(raw: str) -> ProviderSpec:
    """Parse ``provider:model``.

    Split on the first colon only: an Ollama model identifier is itself
    ``name:tag``, so ``ollama:llama3.3:70b`` has to mean the 70b tag rather than
    a syntax error.
    """
    text = (raw or "").strip()
    provider, _, model = text.partition(":")
    provider = provider.strip().lower()
    model = model.strip()

    if provider not in KNOWN_PROVIDERS:
        raise SystemExit(
            f"Unknown provider {provider!r} in {raw!r}. "
            f"Expected one of: {', '.join(KNOWN_PROVIDERS)}."
        )
    if not model:
        model = default_model_for(provider)
        if not model:
            raise SystemExit(
                f"No model given for {provider!r}. Write it as {provider}:model-name."
            )
    return ProviderSpec(provider=provider, model=model)


def assign_labels(specs: Sequence[ProviderSpec]) -> List[ProviderSpec]:
    """Give every column a short heading, keeping them distinct.

    Two local models compared against each other would both be headed "local",
    which would make the table unreadable, so a repeated heading falls back to
    the model name.
    """
    counts: Dict[str, int] = {}
    for spec in specs:
        label = COLUMN_LABELS.get(spec.provider, spec.provider)
        counts[label] = counts.get(label, 0) + 1

    for spec in specs:
        label = COLUMN_LABELS.get(spec.provider, spec.provider)
        spec.label = label if counts[label] == 1 else spec.model[:12]
    return list(specs)


# --- shared evidence ------------------------------------------------------


@dataclass
class SharedEvidence:
    """What one question retrieved, handed unchanged to every provider.

    ``citations`` and ``texts`` are what the scorer reads; ``prompt`` is what
    the model is sent. Built once per case: see the module docstring for why
    that is a fairness property and not only a speed one.
    """

    citations: List[Dict[str, Any]] = field(default_factory=list)
    texts: List[str] = field(default_factory=list)
    prompt: Any = None
    citation_objects: List[Any] = field(default_factory=list)


# --- results --------------------------------------------------------------


def rate(passed: int, scored: int) -> Optional[float]:
    """A percentage, or None when nothing was scored.

    None is not zero. A category with no scored cases has no result, and
    printing 0% for it would report a failure that never happened.
    """
    if scored <= 0:
        return None
    return passed / scored * 100.0


@dataclass
class ProviderRun:
    """Every case one provider answered."""

    spec: ProviderSpec
    results: List[CaseResult] = field(default_factory=list)
    calls: int = 0
    errors: List[str] = field(default_factory=list)
    unavailable: Optional[str] = None
    elapsed_ms: float = 0.0

    @property
    def ran(self) -> bool:
        return self.unavailable is None and bool(self.results)

    def counts(self, category: Optional[str] = None) -> Tuple[int, int]:
        """Scored and passed generations, for one category or for all."""
        scored = passed = 0
        for result in self.results:
            if category is not None and result.category != category:
                continue
            if not result.generation_scored:
                continue
            scored += 1
            passed += 1 if result.generation_passed else 0
        return scored, passed

    def category_rate(self, category: Optional[str] = None) -> Optional[float]:
        scored, passed = self.counts(category)
        return rate(passed, scored)

    def to_dict(self) -> Dict[str, Any]:
        scored, passed = self.counts()
        by_category: Dict[str, Dict[str, Any]] = {}
        for category in sorted({r.category for r in self.results}):
            in_category, passed_in_category = self.counts(category)
            by_category[category] = {
                "scored": in_category,
                "passed": passed_in_category,
                "rate": rate(passed_in_category, in_category),
            }

        return {
            **self.spec.to_dict(),
            "unavailable": self.unavailable,
            "model_calls": self.calls,
            "errors": self.errors,
            "elapsed_ms": round(self.elapsed_ms, 1),
            "generation": {"scored": scored, "passed": passed,
                           "failed": scored - passed, "rate": rate(passed, scored)},
            "by_category": by_category,
            "results": [asdict(r) for r in self.results],
        }


@dataclass
class CategoryRow:
    """One row of the published table."""

    category: str
    label: str
    rates: Dict[str, Optional[float]] = field(default_factory=dict)
    local: Optional[float] = None
    best_frontier: Optional[float] = None
    best_frontier_label: str = ""
    gap: Optional[float] = None
    at_parity: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_rows(runs: Sequence[ProviderRun],
               margin: float = DEFAULT_PARITY_MARGIN) -> List[CategoryRow]:
    """Turn the per-provider results into the table, and judge parity.

    Parity compares the first local column against the *best* frontier column,
    not the average of them: the question a community is actually deciding is
    whether to run its own model instead of the best one it could buy.
    """
    seen = {result.category for run in runs for result in run.results}
    ordered = [c for c in CATEGORY_ORDER if c in seen]
    ordered += sorted(c for c in seen if c not in CATEGORY_ORDER)

    local_run = next((r for r in runs if r.spec.is_local and r.ran), None)
    frontier_runs = [r for r in runs if r.spec.is_frontier and r.ran]

    rows: List[CategoryRow] = []
    for category in ordered:
        row = CategoryRow(
            category=category,
            label=CATEGORY_LABELS.get(category, category.replace("_", " ")),
            rates={run.spec.key: run.category_rate(category) for run in runs},
        )

        if local_run is not None:
            row.local = local_run.category_rate(category)

        scored_frontier = [
            (run.category_rate(category), run.spec.label) for run in frontier_runs
            if run.category_rate(category) is not None
        ]
        if scored_frontier:
            row.best_frontier, row.best_frontier_label = max(scored_frontier)

        if row.local is not None and row.best_frontier is not None:
            row.gap = row.local - row.best_frontier
            row.at_parity = row.gap >= -abs(margin)

        rows.append(row)

    return rows


@dataclass
class Comparison:
    """Everything one comparison produced."""

    runs: List[ProviderRun] = field(default_factory=list)
    retrieval: List[CaseResult] = field(default_factory=list)
    rows: List[CategoryRow] = field(default_factory=list)
    margin: float = DEFAULT_PARITY_MARGIN
    retrievals: int = 0
    cases: int = 0

    def retrieval_summary(self) -> Dict[str, Any]:
        scored = [r for r in self.retrieval if r.retrieval_scored]
        passed = sum(1 for r in scored if r.retrieval_passed)
        return {"scored": len(scored), "passed": passed,
                "failed": len(scored) - passed, "rate": rate(passed, len(scored))}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cases": self.cases,
            "retrievals": self.retrievals,
            "parity_margin": self.margin,
            # Scored once, because retrieval does not involve the model.
            "retrieval": self.retrieval_summary(),
            "retrieval_results": [asdict(r) for r in self.retrieval],
            "providers": [run.to_dict() for run in self.runs],
            "by_category": [row.to_dict() for row in self.rows],
        }


# --- the comparison -------------------------------------------------------

Retrieve = Callable[[Dict[str, Any]], SharedEvidence]
Generate = Callable[[ProviderSpec, Dict[str, Any], SharedEvidence], str]


def run_comparison(
    cases: Sequence[Dict[str, Any]],
    specs: Sequence[ProviderSpec],
    retrieve: Retrieve,
    generate: Generate,
    margin: float = DEFAULT_PARITY_MARGIN,
    verbose: bool = False,
) -> Comparison:
    """Score one frozen set against several providers over shared passages.

    Retrieval and generation are injected rather than imported, the same way
    :mod:`rag.pipeline` injects its generator, so the comparison arithmetic can
    be tested without a corpus, a model, or an invoice.
    """
    comparison = Comparison(margin=margin, cases=len(cases))

    # --- retrieve once, for everybody ---
    evidence: List[Tuple[Dict[str, Any], SharedEvidence]] = []
    for case in cases:
        try:
            found = retrieve(case)
        except Exception as exc:
            # One unsearchable question should not end the run; it is recorded
            # as a retrieval failure, which is what it is.
            found = SharedEvidence()
            print(f"  retrieval failed for {case['id']}: {type(exc).__name__}: {exc}")
        comparison.retrievals += 1
        evidence.append((case, found))
        comparison.retrieval.append(score_case(case, found.citations, found.texts))

    # --- generate per provider ---
    for spec in specs:
        run = ProviderRun(spec=spec)
        started = time.perf_counter()
        print(f"\n  {spec.key}")

        for case, found in evidence:
            # A case with no generation checks cannot tell two models apart, so
            # paying a frontier provider to answer it would buy nothing.
            if not scores_generation(case):
                continue

            try:
                answer = generate(spec, case, found)
            except Exception as exc:
                detail = f"{case['id']}: {type(exc).__name__}: {exc}"
                run.errors.append(detail)
                if not run.results:
                    # Failing on the very first case means the provider is not
                    # configured or not reachable, not that the model is bad.
                    # Stop rather than burn the whole set into the same error.
                    run.unavailable = f"{type(exc).__name__}: {exc}"
                    print(f"    SKIPPED  {spec.key} is unavailable: {exc}")
                    break
                print(f"    ERROR    {detail}")
                continue

            run.calls += 1
            result = score_case(case, found.citations, found.texts, answer=answer)
            run.results.append(result)

            mark = "PASS" if result.generation_passed else "FAIL"
            print(f"    {mark}  {result.id:<20} {result.category:<24} "
                  f"{result.sources_retrieved} src")
            if verbose and result.failures:
                for failure in result.failures:
                    print(f"             {failure}")

        run.elapsed_ms = (time.perf_counter() - started) * 1000
        comparison.runs.append(run)

    comparison.rows = build_rows(comparison.runs, margin=margin)
    return comparison


# --- planning and cost ----------------------------------------------------


def plan(cases: Sequence[Dict[str, Any]],
         specs: Sequence[ProviderSpec]) -> Dict[str, Any]:
    """What a run would cost, before it costs it.

    Frontier providers bill per call, so the number of calls is a number an
    operator is entitled to see before committing to it rather than after.
    """
    generation_cases = [c for c in cases if scores_generation(c)]
    billed = [s for s in specs if s.is_frontier]
    return {
        "cases": len(cases),
        "generation_cases": len(generation_cases),
        "retrieval_only_cases": len(cases) - len(generation_cases),
        # Once per case, not once per case per provider.
        "retrievals": len(cases),
        "model_calls": len(generation_cases) * len(specs),
        "billed_model_calls": len(generation_cases) * len(billed),
        "billed_providers": [s.key for s in billed],
        "providers": [
            {**spec.to_dict(), "model_calls": len(generation_cases)} for spec in specs
        ],
    }


def print_plan(the_plan: Dict[str, Any], project_id: str) -> None:
    print("=" * 66)
    print("DRY RUN: nothing is sent to any model")
    print("=" * 66)
    print(f"  project            {project_id}")
    print(f"  cases              {the_plan['cases']} "
          f"({the_plan['generation_cases']} score the answer, "
          f"{the_plan['retrieval_only_cases']} score retrieval only)")
    print(f"  retrievals         {the_plan['retrievals']} "
          f"(run once and shared by every provider)")
    print(f"  model calls        {the_plan['model_calls']} = "
          f"{the_plan['generation_cases']} x {len(the_plan['providers'])} providers")
    print()
    for entry in the_plan["providers"]:
        cost = "billed per call" if entry["billed"] else "local, no charge"
        print(f"    {entry['key']:<34} {entry['model_calls']:>4} calls   {cost}")
    print()
    if the_plan["billed_model_calls"]:
        print(f"  {the_plan['billed_model_calls']} of those calls are billed: "
              f"{', '.join(the_plan['billed_providers'])}.")
    else:
        print("  No frontier providers selected; this run would cost nothing.")


def print_cost_warning(the_plan: Dict[str, Any]) -> None:
    """Say what this will spend, in plain words, before spending it."""
    if not the_plan["billed_model_calls"]:
        return
    print()
    print("=" * 66)
    print("COST WARNING")
    print("=" * 66)
    print(f"  This run sends {the_plan['billed_model_calls']} requests to providers "
          f"that bill per request:")
    for key in the_plan["billed_providers"]:
        print(f"    {key}")
    print("  Each request carries the retrieved passages and the constitution, so")
    print("  it is not a short prompt.")
    print("  Local providers and retrieval cost nothing. Use --dry-run to see the")
    print("  plan without spending anything, or --limit N to try a few cases first.")
    print("=" * 66)


def confirm(the_plan: Dict[str, Any], assume_yes: bool) -> bool:
    """Ask before spending money, but only when someone is there to answer.

    A scheduled run has no one at the keyboard, and blocking it on a prompt it
    cannot answer would hang the job rather than protect anybody.
    """
    if assume_yes or not the_plan["billed_model_calls"]:
        return True
    if not sys.stdin.isatty():
        return True
    try:
        reply = input("\nContinue and send these requests? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return reply in ("y", "yes")


# --- rendering ------------------------------------------------------------


def format_rate(value: Optional[float]) -> str:
    return "-" if value is None else f"{value:.0f}%"


def corpus_size(agent: Any) -> int:
    """How many passages the archive holds, or 0 if it will not say."""
    try:
        return int(agent.vector_store.get_stats().get("total_documents", 0))
    except Exception:
        return 0


def render_table(comparison: Comparison) -> List[str]:
    """The table from roadmap 1.1, as lines."""
    runs = comparison.runs
    label_width = max([26] + [len(row.label) for row in comparison.rows]) + 2

    lines = [
        " " * label_width + "".join(f"{run.spec.label:>10}" for run in runs)
    ]
    for row in comparison.rows:
        cells = "".join(format_rate(row.rates.get(run.spec.key)).rjust(10) for run in runs)
        marker = ""
        if row.at_parity is True:
            marker = "   <- at parity"
        elif row.at_parity is False and row.gap is not None:
            marker = f"   <- {abs(row.gap):.0f} pts behind {row.best_frontier_label}"
        lines.append(f"{row.label:<{label_width}}{cells}{marker}")

    overall = "".join(format_rate(run.category_rate()).rjust(10) for run in runs)
    lines.append("")
    lines.append(f"{'all scored answers':<{label_width}}{overall}")
    return lines


def print_report(comparison: Comparison) -> None:
    print()
    print("=" * 66)
    print("RESULTS")
    print("=" * 66)

    retrieval = comparison.retrieval_summary()
    if retrieval["scored"]:
        print(f"  Retrieval    {retrieval['passed']}/{retrieval['scored']} "
              f"({format_rate(retrieval['rate'])})   <- chunking, metadata, ranking")
    else:
        print("  Retrieval    not scored (no cases declare expect_sources)")
    print(f"               scored once: retrieval does not involve the model, so it "
          f"ran")
    print(f"               {comparison.retrievals} times and every provider below saw "
          f"the same passages")
    print()

    for line in render_table(comparison):
        print(f"  {line}".rstrip())

    unavailable = [run for run in comparison.runs if run.unavailable]
    if unavailable:
        print()
        for run in unavailable:
            print(f"  {run.spec.key} did not run: {run.unavailable}")

    at_parity = [row for row in comparison.rows if row.at_parity is True]
    behind = [row for row in comparison.rows if row.at_parity is False]

    print()
    if at_parity:
        print(f"  At parity (local within {comparison.margin:.0f} points of the best "
              f"frontier result):")
        for row in at_parity:
            print(f"    {row.label:<28} {format_rate(row.local)} vs "
                  f"{format_rate(row.best_frontier)}")
    if behind:
        print(f"  Behind by more than {comparison.margin:.0f} points:")
        for row in behind:
            print(f"    {row.label:<28} {format_rate(row.local)} vs "
                  f"{format_rate(row.best_frontier)} ({row.best_frontier_label}), "
                  f"{abs(row.gap or 0):.0f} pts")
    if not at_parity and not behind:
        print("  No local and frontier pair to compare; parity was not assessed.")

    print()
    print("  Publish this per release. Naming what an open model costs a community")
    print("  is a stronger civic position than claiming it costs nothing.")


# --- the real project -----------------------------------------------------


class ProjectRunner:
    """Retrieval and generation against one real project.

    Holds the agent, which owns the corpus, the constitution, and the retrieval
    path, and builds one provider per column on first use. Kept apart from
    :func:`run_comparison` so that the comparison itself needs neither.
    """

    def __init__(self, project: Any, top_k: Optional[int] = None,
                 vector_store: Any = None) -> None:
        from agent import CivicAgent

        self.project = project
        # ``vector_store`` is the same seam CivicAgent offers: tests hand it a
        # corpus in memory so this class can be exercised without a database.
        self.agent = CivicAgent(project, vector_store=vector_store)
        self.pipeline = self.agent.pipeline
        self.top_k = top_k
        self._providers: Dict[str, Any] = {}

    def retrieve(self, case: Dict[str, Any]) -> SharedEvidence:
        from rag.citations import build_citations

        _, retrieval = self.pipeline.retrieve(
            case["question"],
            top_k=self.top_k,
            use_reranker=getattr(self.project, "enable_reranking", True),
            expand=getattr(self.project, "enable_query_expansion", True),
            # No model-backed rewriter, even when the project enables one: a
            # rewrite by the model under test would make retrieval differ per
            # provider, and the shared-passage property is the whole point.
            rewriter=None,
        )
        citations = build_citations(retrieval.chunks)
        return SharedEvidence(
            citations=[c.to_dict() for c in citations],
            texts=[c.chunk.text for c in retrieval.chunks],
            prompt=self.pipeline.build_prompt(case["question"], retrieval, citations),
            citation_objects=citations,
        )

    def provider_for(self, spec: ProviderSpec) -> Any:
        from providers import build_provider

        if spec.key in self._providers:
            return self._providers[spec.key]

        own = str(getattr(self.project.ai_provider, "value", self.project.ai_provider))
        provider = build_provider(
            provider=spec.provider,
            model=spec.model,
            temperature=self.project.temperature,
            max_tokens=self.project.max_tokens,
            context_window=self.project.context_window,
            # The project's key belongs to the project's own provider. Every
            # other column reads its key from the environment, which is where a
            # comparison key belongs: it is an operator's key, not the town's
            # service configuration.
            api_key=self.project.api_key if spec.provider == own else None,
            base_url=getattr(self.project, "lmstudio_base_url", None)
            if spec.provider == own else None,
            auth_header=getattr(self.project, "local_auth_header", None)
            if spec.provider == own else None,
            verify_tls=getattr(self.project, "local_verify_tls", True),
        )
        self._providers[spec.key] = provider
        return provider

    def generate(self, spec: ProviderSpec, case: Dict[str, Any],
                 evidence: SharedEvidence) -> str:
        from rag.citations import strip_invalid_markers, verify_citations

        raw = (self.provider_for(spec).complete(evidence.prompt) or "").strip()

        # The same citation check the live answer path applies, so a model is
        # not credited for a marker pointing at a passage nobody supplied. The
        # check re-marks every citation from scratch, so one provider's answer
        # leaves nothing behind on the shared evidence for the next one.
        check = verify_citations(raw, evidence.citation_objects)
        if check.invalid_numbers:
            raw = strip_invalid_markers(
                raw, [c.number for c in evidence.citation_objects])
        return raw


# --- cli ------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", required=True, help="project id, e.g. brookline-ma")
    parser.add_argument("--providers", required=True, nargs="+", metavar="PROVIDER:MODEL",
                        help="one or more, e.g. lmstudio:gemma-4-26b-a4b anthropic:claude-opus-5")
    parser.add_argument("--category", help="run only one category")
    parser.add_argument("--limit", type=int, help="run only the first N cases")
    parser.add_argument("--top-k", type=int, help="passages to retrieve per question")
    parser.add_argument("--margin", type=float, default=DEFAULT_PARITY_MARGIN,
                        help=f"points within which local counts as at parity "
                             f"(default {DEFAULT_PARITY_MARGIN:.0f})")
    parser.add_argument("--dry-run", action="store_true",
                        help="list what would run and how many model calls it would take")
    parser.add_argument("--yes", action="store_true",
                        help="do not ask before sending billed requests")
    parser.add_argument("--json", dest="json_out", help="write full results to this path")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    specs = assign_labels([parse_spec(raw) for raw in args.providers])
    cases = load_cases(category=args.category)
    if args.limit:
        cases = cases[:args.limit]
    if not cases:
        raise SystemExit("No evaluation cases matched.")

    the_plan = plan(cases, specs)

    if args.dry_run:
        print_plan(the_plan, args.project)
        return 0

    project = load_project(args.project)
    print(f"Comparing {len(specs)} providers on {len(cases)} cases from "
          f"{project.project_name} ({project.municipality_name})")
    for spec in specs:
        kind = "local" if spec.is_local else "frontier, billed"
        print(f"  {spec.label:<10} {spec.key}  ({kind})")

    print_cost_warning(the_plan)
    if not confirm(the_plan, args.yes):
        print("Stopped. Nothing was sent.")
        return 0

    runner = ProjectRunner(project, top_k=args.top_k)
    print(f"\n  constitution: v{runner.agent.constitution.version} "
          f"({runner.agent.constitution.status})")
    print(f"  corpus:       {corpus_size(runner.agent)} passages")

    comparison = run_comparison(
        cases, specs, retrieve=runner.retrieve, generate=runner.generate,
        margin=args.margin, verbose=args.verbose,
    )
    print_report(comparison)

    if args.json_out:
        summary = {
            "run_at": datetime.now().isoformat(timespec="seconds"),
            "project_id": args.project,
            "community": project.municipality_name,
            "constitution_version": runner.agent.constitution.version,
            "constitution_hash": runner.agent.constitution.content_hash,
            "corpus_passages": corpus_size(runner.agent),
            "plan": the_plan,
            **comparison.to_dict(),
        }
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        print(f"\nWrote {out}")

    # A provider that could not be reached is an operator problem and should
    # not read as a passing comparison.
    return 1 if any(run.unavailable for run in comparison.runs) else 0


if __name__ == "__main__":
    sys.exit(main())
