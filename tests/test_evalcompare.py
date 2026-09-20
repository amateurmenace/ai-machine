"""Tests for the provider comparison and the retrieval diversity pass.

Two claims are being defended here. The comparison's claim is that the table it
publishes is arithmetic anyone can check, produced from one retrieval shown to
every provider, with a stated margin for calling a category level. The diversity
pass's claim is that when three retrieved passages agree, it finds the fourth
one that does not.

No network and no model: the providers are scripted, so a run costs nothing and
an unreachable frontier API cannot make this suite flap.
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional, Tuple

from evals.compare_providers import (
    DEFAULT_PARITY_MARGIN, ProjectRunner, ProviderRun, SharedEvidence, assign_labels,
    build_rows, parse_spec, plan, rate, render_table, run_comparison,
)
from evals.run_evals import CaseResult, score_case
from knowledge.schemas import CivicChunk, RecordStatus, SourceType
from models import AIProvider, ProjectConfig
from providers import BaseProvider, ChatTurn, GenerationSettings
from rag.diversity import (
    lexical_similarity, passage_similarity, provenance_similarity, select_diverse,
)
from rag.hybrid import HybridRetriever, RetrievedChunk
from rag.pipeline import PromptBundle
from tests.fakes import FakeVectorStore

PASS: List[str] = []
FAIL: List[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  -> {detail}" if not condition else ""))


class ScriptedProvider(BaseProvider):
    """Answers from a script, recording every prompt it was sent.

    Keyed by the question so one script can serve a whole eval set, and able to
    raise on demand, which is how an unconfigured frontier provider behaves.
    """

    name = "scripted"
    protocol = "openai"

    def __init__(self, answers: Dict[str, str],
                 raises: Optional[Exception] = None) -> None:
        super().__init__(GenerationSettings(model="test-model"))
        self.answers = answers
        self.raises = raises
        self.prompts: List[List[Dict[str, Any]]] = []

    def chat(self, messages, tools=None, max_tokens=None) -> ChatTurn:
        if self.raises is not None:
            raise self.raises
        self.prompts.append(list(messages))
        question = str(messages[-1].get("content", ""))
        return ChatTurn(text=self.answers.get(question, "I do not have a record of that."))


# --- a small frozen set, scored the way the real one is --------------------

SPEC_TEXTS = ["lmstudio:gemma-4-26b-a4b", "anthropic:claude-opus-5",
              "gemini:gemini-3.1-pro"]

# category -> (cases, {column label -> how many of them that column gets right})
SCRIPT = {
    "local_factual": (4, {"local": 4, "Claude": 4, "Gemini": 4}),
    "ambiguous": (5, {"local": 3, "Claude": 5, "Gemini": 4}),
    "general_ai": (4, {"local": 2, "Claude": 4, "Gemini": 4}),
}


def build_set() -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, bool]]]:
    """Cases plus a lookup of which column is supposed to pass each one."""
    cases: List[Dict[str, Any]] = []
    correct: Dict[str, Dict[str, bool]] = {}
    for category, (count, per_column) in SCRIPT.items():
        for i in range(count):
            case_id = f"{category}-{i}"
            cases.append({
                "id": case_id,
                "category": category,
                "question": f"Question {case_id}?",
                "expect_sources": ["Coolidge Corner"],
                "must_include": ["no vote"],
                "must_cite": True,
            })
            correct[case_id] = {
                label: i < passes for label, passes in per_column.items()
            }
    # One case that scores retrieval only, to prove a case with nothing to say
    # about the answer is never sent to a model.
    cases.append({
        "id": "retrieval-only-0",
        "category": "local_factual",
        "question": "Question retrieval-only-0?",
        "expect_sources": ["Coolidge Corner"],
    })
    return cases, correct


def scripted_comparison(margin: float = DEFAULT_PARITY_MARGIN):
    """Run the whole comparison against scripted providers."""
    cases, correct = build_set()
    specs = assign_labels([parse_spec(text) for text in SPEC_TEXTS])

    evidence_built: List[str] = []

    def retrieve(case: Dict[str, Any]) -> SharedEvidence:
        evidence_built.append(case["id"])
        citation = {"number": 1, "title": "Coolidge Corner redesign",
                    "excerpt": "no vote was taken", "used": False}
        return SharedEvidence(
            citations=[citation],
            texts=["The board discussed the Coolidge Corner redesign; no vote was taken."],
            prompt=PromptBundle(
                identity="You are a community assistant.",
                constitution_text="COMMUNITY CONSTITUTION",
                context_block="[1] Coolidge Corner redesign: no vote was taken.",
                question=case["question"],
            ),
        )

    scripts = {
        spec.key: ScriptedProvider({
            f"Question {case_id}?":
                ("The board discussed it and there was no vote [1]."
                 if columns[spec.label] else "The board approved it.")
            for case_id, columns in correct.items()
        })
        for spec in specs
    }

    def generate(spec, case, evidence) -> str:
        return scripts[spec.key].complete(evidence.prompt)

    comparison = run_comparison(cases, specs, retrieve=retrieve, generate=generate,
                                margin=margin)
    return comparison, specs, scripts, evidence_built


def provider_run(spec_text: str, scores: Dict[str, Tuple[int, int]]) -> ProviderRun:
    """A finished run with ``passed of scored`` per category, no model involved."""
    run = ProviderRun(spec=parse_spec(spec_text))
    for category, (passed, scored) in scores.items():
        for i in range(scored):
            run.results.append(CaseResult(
                id=f"{category}-{i}", category=category, question="q",
                generation_scored=True, generation_passed=i < passed))
    return run


# --- tests ----------------------------------------------------------------


def test_provider_specs() -> None:
    print("\nreading the provider list")
    spec = parse_spec("lmstudio:gemma-4-26b-a4b")
    check("provider and model split apart",
          (spec.provider, spec.model) == ("lmstudio", "gemma-4-26b-a4b"), spec.key)
    check("lmstudio counts as local", spec.is_local and not spec.is_frontier)
    check("anthropic counts as frontier", parse_spec("anthropic:claude-opus-5").is_frontier)

    ollama = parse_spec("ollama:llama3.3:70b")
    check("an ollama tag keeps its own colon", ollama.model == "llama3.3:70b", ollama.model)

    check("a provider with no model falls back to its listed one",
          bool(parse_spec("anthropic").model), parse_spec("anthropic").model)

    try:
        parse_spec("skynet:v1")
        check("an unknown provider is refused", False, "accepted skynet")
    except SystemExit as exc:
        check("an unknown provider is refused", True)
        check("the refusal lists the real providers", "lmstudio" in str(exc), str(exc))

    labels = [s.label for s in assign_labels(
        [parse_spec(t) for t in ["lmstudio:gemma-4-26b-a4b", "anthropic:claude-opus-5"]])]
    check("columns are headed local and Claude", labels == ["local", "Claude"], str(labels))

    both_local = [s.label for s in assign_labels(
        [parse_spec("lmstudio:gemma-4-26b-a4b"), parse_spec("ollama:qwen3:30b-a3b")])]
    check("two local models do not both get the same heading",
          len(set(both_local)) == 2, str(both_local))


def test_comparison_table_maths() -> None:
    print("\nthe table is arithmetic, not vibes")
    comparison, specs, _, _ = scripted_comparison()
    by_key = {run.spec.key: run for run in comparison.runs}
    local = by_key["lmstudio:gemma-4-26b-a4b"]
    claude = by_key["anthropic:claude-opus-5"]

    check("every provider answered every generation-scored case",
          all(run.counts()[0] == 13 for run in comparison.runs),
          str([run.counts() for run in comparison.runs]))
    check("the retrieval-only case was never sent to a model",
          all("retrieval-only-0" not in [r.id for r in run.results]
              for run in comparison.runs))

    check("local scores 3 of 5 on ambiguous",
          local.counts("ambiguous") == (5, 3), str(local.counts("ambiguous")))
    check("that prints as 60%", local.category_rate("ambiguous") == 60.0,
          str(local.category_rate("ambiguous")))
    check("Claude scores 5 of 5 on ambiguous",
          claude.category_rate("ambiguous") == 100.0,
          str(claude.category_rate("ambiguous")))
    check("local scores 50% on general capability",
          local.category_rate("general_ai") == 50.0, str(local.category_rate("general_ai")))
    check("the overall rate is every scored case, not the mean of the rows",
          local.category_rate() == 9 / 13 * 100, str(local.category_rate()))

    check("nothing scored is reported as no result, not as zero",
          rate(0, 0) is None and rate(0, 4) == 0.0)

    rows = {row.category: row for row in comparison.rows}
    check("a row exists per category", set(rows) == {"local_factual", "ambiguous",
                                                     "general_ai"}, str(set(rows)))
    check("rows are headed in plain words",
          rows["ambiguous"].label == "ambiguous (vote vs talk)"
          and rows["general_ai"].label == "general capability",
          rows["general_ai"].label)
    check("civic categories are listed before general capability",
          [r.category for r in comparison.rows].index("general_ai") == len(rows) - 1)

    table = render_table(comparison)
    check("the header carries every column",
          all(label in table[0] for label in ("local", "Claude", "Gemini")), table[0])
    check("the ambiguous row prints the three percentages",
          "60%" in table[2] and "100%" in table[2] and "80%" in table[2], table[2])


def test_parity_detection() -> None:
    print("\ncalling a category level")
    runs = [
        provider_run("lmstudio:gemma-4-26b-a4b",
                     {"local_factual": (18, 20), "ambiguous": (14, 20)}),
        provider_run("anthropic:claude-opus-5",
                     {"local_factual": (19, 20), "ambiguous": (18, 20)}),
    ]
    assign_labels([run.spec for run in runs])
    rows = {row.category: row for row in build_rows(runs)}

    factual = rows["local_factual"]
    check("local 90% against Claude 95% is a five point gap",
          factual.gap == -5.0, str(factual.gap))
    check("exactly at the margin counts as parity", factual.at_parity is True)
    check("the frontier column it was compared against is named",
          factual.best_frontier_label == "Claude", factual.best_frontier_label)

    ambiguous = rows["ambiguous"]
    check("local 70% against Claude 90% is not parity", ambiguous.at_parity is False)
    check("the gap is reported as twenty points", ambiguous.gap == -20.0, str(ambiguous.gap))

    wider = {row.category: row for row in build_rows(runs, margin=25)}
    check("the margin is configurable", wider["ambiguous"].at_parity is True)
    tighter = {row.category: row for row in build_rows(runs, margin=1)}
    check("a tighter margin un-calls the close one", tighter["local_factual"].at_parity is False)

    print("\nparity compares against the best frontier model, not the average")
    three = [
        provider_run("lmstudio:gemma-4-26b-a4b", {"reasoning": (17, 20)}),
        provider_run("anthropic:claude-opus-5", {"reasoning": (16, 20)}),
        provider_run("gemini:gemini-3.1-pro", {"reasoning": (19, 20)}),
    ]
    assign_labels([run.spec for run in three])
    row = build_rows(three)[0]
    check("the better frontier result is the one to beat",
          row.best_frontier == 95.0 and row.best_frontier_label == "Gemini",
          f"{row.best_frontier} {row.best_frontier_label}")
    check("local 85% against the best 95% is behind", row.at_parity is False)

    print("\nnothing to compare against")
    alone = [provider_run("lmstudio:gemma-4-26b-a4b", {"writing": (5, 10)})]
    assign_labels([run.spec for run in alone])
    lonely = build_rows(alone)[0]
    check("a local-only run does not claim parity", lonely.at_parity is None)
    check("and still reports its own rate", lonely.local == 50.0, str(lonely.local))


def test_retrieval_is_shared() -> None:
    print("\none retrieval, every provider")
    comparison, specs, scripts, evidence_built = scripted_comparison()
    cases, _ = build_set()

    check("retrieval ran once per case, not once per case per provider",
          len(evidence_built) == len(cases) == comparison.retrievals,
          f"{len(evidence_built)} retrievals for {len(cases)} cases "
          f"and {len(specs)} providers")
    check("no case was searched twice",
          len(set(evidence_built)) == len(evidence_built), str(evidence_built))

    contexts = {
        tuple(m["content"] for m in prompt if m["role"] == "system")
        for provider in scripts.values() for prompt in provider.prompts
    }
    check("every provider was shown the same passages",
          len(contexts) == 1, f"{len(contexts)} distinct context blocks")

    retrieval = comparison.retrieval_summary()
    check("retrieval is scored once for the whole comparison",
          retrieval["scored"] == len(cases), str(retrieval))
    check("the shared retrieval score appears once in the json",
          isinstance(comparison.to_dict()["retrieval"], dict)
          and len(comparison.to_dict()["providers"]) == 3)


def test_a_missing_passage_is_not_blamed_on_the_model() -> None:
    print("\nthe section 16 split survives the comparison")
    cases = [
        {"id": "found", "category": "local_factual", "question": "Question found?",
         "expect_sources": ["Coolidge Corner"], "must_include": ["no vote"]},
        # The archive has nothing to match, so retrieval fails. The model is
        # still shown what there was and still answers it correctly.
        {"id": "missed", "category": "local_factual", "question": "Question missed?",
         "expect_sources": ["Never Ingested"], "must_include": ["no vote"]},
    ]
    specs = assign_labels([parse_spec(t) for t in SPEC_TEXTS[:2]])

    def retrieve(case):
        return SharedEvidence(
            citations=[{"number": 1, "title": "Coolidge Corner", "used": False}],
            texts=["no vote was taken"],
            prompt=PromptBundle(identity="", constitution_text="", context_block="",
                                question=case["question"]))

    def generate(spec, case, evidence):
        return "The record shows no vote was taken [1]."

    comparison = run_comparison(cases, specs, retrieve=retrieve, generate=generate)
    retrieval = comparison.retrieval_summary()
    check("the missing passage is counted as a retrieval failure",
          (retrieval["passed"], retrieval["failed"]) == (1, 1), str(retrieval))

    for run in comparison.runs:
        check(f"{run.spec.label} is still credited with both answers",
              run.counts() == (2, 2), str(run.counts()))
    missed = [r for r in comparison.runs[0].results if r.id == "missed"][0]
    check("the case records both verdicts separately",
          missed.retrieval_passed is False and missed.generation_passed is True,
          f"retrieval={missed.retrieval_passed} generation={missed.generation_passed}")


def test_dry_run_counts_the_bill() -> None:
    print("\ndry run")
    cases, _ = build_set()
    specs = assign_labels([parse_spec(text) for text in SPEC_TEXTS])
    estimate = plan(cases, specs)

    check("every case is counted", estimate["cases"] == 14, str(estimate["cases"]))
    check("cases that score an answer are counted apart from the rest",
          (estimate["generation_cases"], estimate["retrieval_only_cases"]) == (13, 1),
          str(estimate))
    check("retrieval is counted once per case",
          estimate["retrievals"] == len(cases), str(estimate["retrievals"]))
    check("model calls are cases times providers",
          estimate["model_calls"] == 13 * 3, str(estimate["model_calls"]))
    check("only the frontier calls are billed",
          estimate["billed_model_calls"] == 13 * 2, str(estimate["billed_model_calls"]))
    check("the billed providers are named",
          estimate["billed_providers"] == ["anthropic:claude-opus-5",
                                           "gemini:gemini-3.1-pro"],
          str(estimate["billed_providers"]))

    local_only = plan(cases, assign_labels([parse_spec("lmstudio:gemma-4-26b-a4b")]))
    check("a local-only comparison is free",
          local_only["billed_model_calls"] == 0, str(local_only["billed_model_calls"]))

    comparison, _, _, _ = scripted_comparison()
    check("the estimate matches what the run actually spends",
          [run.calls for run in comparison.runs] == [13, 13, 13],
          str([run.calls for run in comparison.runs]))


def test_an_unreachable_provider_does_not_sink_the_run() -> None:
    print("\na provider that is not configured")
    cases, correct = build_set()
    specs = assign_labels([parse_spec(t) for t in SPEC_TEXTS[:2]])

    working = ScriptedProvider({f"Question {cid}?": "no vote was taken [1]."
                                for cid in correct})
    broken = ScriptedProvider({}, raises=RuntimeError("no API key configured"))
    scripts = {specs[0].key: working, specs[1].key: broken}

    def retrieve(case):
        return SharedEvidence(
            citations=[{"number": 1, "title": "Coolidge Corner", "used": False}],
            texts=["no vote was taken"],
            prompt=PromptBundle(identity="", constitution_text="", context_block="",
                                question=case["question"]))

    def generate(spec, case, evidence):
        return scripts[spec.key].complete(evidence.prompt)

    comparison = run_comparison(cases, specs, retrieve=retrieve, generate=generate)
    local, missing = comparison.runs

    check("the working provider still produced a column",
          local.counts()[0] == 13, str(local.counts()))
    check("the unreachable one is marked unavailable",
          missing.unavailable is not None, str(missing.unavailable))
    check("the reason names what the operator has to fix",
          "no API key configured" in (missing.unavailable or ""), str(missing.unavailable))
    check("it gave up after the first failure instead of billing the whole set",
          missing.calls == 0 and len(missing.errors) == 1, str(missing.errors))
    check("an unavailable column is empty, not zero",
          missing.category_rate("ambiguous") is None)
    check("parity is not claimed against a provider that never ran",
          all(row.at_parity is None for row in comparison.rows),
          str([(r.category, r.at_parity) for r in comparison.rows]))


def test_the_real_retrieval_path_builds_one_prompt() -> None:
    print("\nthe production path, with only the model and the database replaced")
    project = ProjectConfig(
        project_id="compare-providers-test", municipality_name="Brookline, MA",
        project_name="Brookline AI", ai_provider=AIProvider.LMSTUDIO,
        model_name="gemma-4-26b-a4b",
    )
    corpus = [{
        "text": "Several members expressed support for the Coolidge Corner redesign "
                "during discussion. No motion was made and the board took no vote.",
        "source_type": SourceType.MEETING_TRANSCRIPT, "body": "Select Board",
        "meeting_date": "2026-05-12", "start_time": 4422.0,
        "title": "Select Board May 12", "url": "https://www.youtube.com/watch?v=abc123",
    }]
    runner = ProjectRunner(project, vector_store=FakeVectorStore(corpus, "compare-real"))

    case = {"id": "ambiguous-real", "category": "ambiguous",
            "question": "Did the Select Board approve the Coolidge Corner redesign?",
            "expect_sources": ["Coolidge Corner"], "must_include": ["no vote"],
            "must_cite": True}
    evidence = runner.retrieve(case)

    check("the real pipeline found the passage", len(evidence.citations) == 1,
          str(len(evidence.citations)))
    check("the prompt carries the constitution",
          any("CONSTITUTION" in block for block in evidence.prompt.system_blocks()))
    check("the prompt carries the numbered passage",
          "[1]" in evidence.prompt.context_block, evidence.prompt.context_block[:60])
    check("the question asked is the question the resident asked",
          evidence.prompt.question == case["question"])

    # Seed the provider cache so that nothing leaves the building.
    specs = assign_labels([parse_spec(t) for t in SPEC_TEXTS[:2]])
    for spec in specs:
        runner._providers[spec.key] = ScriptedProvider(
            {case["question"]: "The board discussed it; no vote was taken [1]. Also [9]."})

    answers = {spec.key: runner.generate(spec, case, evidence) for spec in specs}
    check("both providers answered from the one prompt", len(answers) == 2)
    check("a citation pointing at nothing is stripped before scoring",
          all("[9]" not in answer for answer in answers.values()), str(answers))
    check("the real citation survives",
          all("[1]" in answer for answer in answers.values()), str(answers))

    result = score_case(case, evidence.citations, evidence.texts,
                        answer=answers[specs[0].key])
    check("retrieval and generation both pass on the real path",
          result.retrieval_passed is True and result.generation_passed is True,
          str(result.failures))


# --- retrieval diversity ---------------------------------------------------


AGREEING = [
    ("Members spoke in favor of the Harvard Street bike lane and asked staff "
     "to proceed with the design.", "Select Board", "2026-05-12",
     RecordStatus.DISCUSSION, "https://example.org/sb-may"),
    ("Members spoke in favor of the Harvard Street bike lane design and asked "
     "staff to continue.", "Select Board", "2026-05-12",
     RecordStatus.DISCUSSION, "https://example.org/sb-may"),
    ("Members spoke in favor of the Harvard Street bike lane and thanked staff "
     "for the design work.", "Select Board", "2026-05-12",
     RecordStatus.DISCUSSION, "https://example.org/sb-may"),
]
DISSENTING = (
    "The Transportation Board found the Harvard Street proposal unsafe for "
    "cyclists and voted to reject it.", "Transportation Board", "2026-07-09",
    RecordStatus.ADOPTED, "https://example.org/tb-july",
)


def candidates() -> List[RetrievedChunk]:
    """Three passages that agree, then the one that does not."""
    out = []
    for i, (text, body, date, status, url) in enumerate(AGREEING + [DISSENTING]):
        chunk = CivicChunk(text=text, body=body, meeting_date=date, status=status,
                           url=url, source_type=SourceType.MEETING_TRANSCRIPT)
        out.append(RetrievedChunk(chunk=chunk, chunk_id=f"c{i}",
                                  fused_score=0.9 - 0.05 * i, rerank_score=5.0 - i))
    return out


def test_similarity_needs_no_embeddings() -> None:
    print("\nsimilarity from words and provenance alone")
    items = candidates()
    same_meeting = passage_similarity(items[0].chunk, items[1].chunk)
    different_board = passage_similarity(items[0].chunk, items[3].chunk)
    check("two passages from one meeting look alike",
          same_meeting > 0.5, f"{same_meeting:.2f}")
    check("the dissenting passage does not",
          different_board < 0.3, f"{different_board:.2f}")

    check("the civic tokenizer keeps article numbers apart",
          lexical_similarity("Article 8.4 permits accessory dwelling units",
                             "Article 8.1 permits accessory dwelling units") < 1.0)
    check("identical text is identical", lexical_similarity("a vote", "a vote") == 1.0)
    check("empty text is not similar to anything", lexical_similarity("", "text") == 0.0)

    check("same board, date, status and document scores 1.0",
          provenance_similarity(items[0].chunk, items[1].chunk) == 1.0,
          str(provenance_similarity(items[0].chunk, items[1].chunk)))
    check("a different board, date, status and document scores 0.0",
          provenance_similarity(items[0].chunk, items[3].chunk) == 0.0,
          str(provenance_similarity(items[0].chunk, items[3].chunk)))

    bare = CivicChunk(text="Curbside collection shifts one day during holiday weeks.")
    other = CivicChunk(text="Parking permits are issued at Town Hall.")
    check("a chunk with no metadata is not judged on metadata",
          provenance_similarity(bare, other) is None)
    check("and falls back to wording alone",
          passage_similarity(bare, other) == lexical_similarity(bare.text, other.text))

    unknown = CivicChunk(text="a", status=RecordStatus.UNKNOWN)
    unknown2 = CivicChunk(text="b", status=RecordStatus.UNKNOWN)
    check("two unknown statuses are not treated as the same status",
          provenance_similarity(unknown, unknown2) is None)


def test_diversity_surfaces_the_dissenting_passage() -> None:
    print("\nthe passage that disagrees")
    items = candidates()

    naive = select_diverse(items, top_k=3, diversity=0.0)
    check("naive top-k takes the three most relevant",
          [c.chunk_id for c in naive] == ["c0", "c1", "c2"],
          str([c.chunk_id for c in naive]))
    check("and they all come from the same board on the same day",
          len({(c.chunk.body, c.chunk.record_date) for c in naive}) == 1)
    check("so the objection never reaches the model",
          "c3" not in [c.chunk_id for c in naive])

    diverse = select_diverse(items, top_k=3, diversity=0.5)
    ids = [c.chunk_id for c in diverse]
    check("with diversity on, the dissenting passage is retrieved", "c3" in ids, str(ids))
    check("the most relevant passage is still first", ids[0] == "c0", str(ids))
    check("the same number of passages is returned", len(diverse) == 3, str(len(diverse)))
    check("no passage is returned twice", len(set(ids)) == 3, str(ids))
    check("both sides are now present",
          {c.chunk.body for c in diverse} == {"Select Board", "Transportation Board"},
          str([c.chunk.body for c in diverse]))

    print("\nthe dial")
    check("a full dial still returns top_k passages",
          len(select_diverse(items, top_k=3, diversity=1.0)) == 3)
    check("asking for more than exists returns what exists",
          len(select_diverse(items, top_k=99, diversity=0.5)) == 4)
    check("an empty candidate list is survivable",
          select_diverse([], top_k=3, diversity=0.5) == [])
    check("one candidate is survivable",
          len(select_diverse(items[:1], top_k=3, diversity=0.5)) == 1)


def test_diversity_off_changes_nothing() -> None:
    print("\noff by default")
    items = candidates()
    check("zero returns the ranking untouched",
          select_diverse(items, top_k=4, diversity=0.0) == items)
    check("and the objects are the same objects, not copies",
          all(a is b for a, b in zip(select_diverse(items, top_k=4), items)))
    check("a negative dial is treated as off",
          select_diverse(items, top_k=4, diversity=-1.0) == items)

    corpus = [
        {"text": c.chunk.text, "body": c.chunk.body, "meeting_date": c.chunk.record_date,
         "status": c.chunk.status, "url": c.chunk.url, "source_type": c.chunk.source_type}
        for c in items
    ]
    retriever = HybridRetriever(FakeVectorStore(corpus), cache_key="diversity-default")
    default = retriever.retrieve("Harvard Street bike lane", top_k=3, use_reranker=False)
    explicit_off = retriever.retrieve("Harvard Street bike lane", top_k=3,
                                      use_reranker=False, diversity=0.0)
    check("the retriever defaults to no diversity pass",
          default.diagnostics()["diversity"] == 0.0)
    check("passing zero is the same as not passing it",
          [c.chunk_id for c in default.chunks] == [c.chunk_id for c in explicit_off.chunks])
    check("no note is added when it did not run",
          not any("diversity" in note for note in default.notes), str(default.notes))

    on = retriever.retrieve("Harvard Street bike lane", top_k=3, use_reranker=False,
                            diversity=0.7)
    check("turning it on is reported in the diagnostics",
          on.diagnostics()["diversity"] == 0.7, str(on.diagnostics()["diversity"]))
    check("and noted for the transparency panel",
          any("diversity" in note for note in on.notes), str(on.notes))
    check("the same number of passages still comes back",
          len(on.chunks) == len(default.chunks), f"{len(on.chunks)} vs {len(default.chunks)}")


def main() -> int:
    print("=" * 62)
    print("Provider comparison and retrieval diversity tests")
    print("=" * 62)
    for fn in [
        test_provider_specs,
        test_comparison_table_maths,
        test_parity_detection,
        test_retrieval_is_shared,
        test_a_missing_passage_is_not_blamed_on_the_model,
        test_dry_run_counts_the_bill,
        test_an_unreachable_provider_does_not_sink_the_run,
        test_the_real_retrieval_path_builds_one_prompt,
        test_similarity_needs_no_embeddings,
        test_diversity_surfaces_the_dissenting_passage,
        test_diversity_off_changes_nothing,
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
