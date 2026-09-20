"""Tests for the community retrieval pipeline.

Run with:  python3 -m tests.test_rag     (no pytest required)
       or:  python3 -m pytest tests/
"""

from __future__ import annotations

import sys

from community.constitution import load_constitution
from knowledge.schemas import CivicChunk, SourceType, normalize_payload
from rag.citations import build_citations, deep_link, verify_citations
from rag.hybrid import HybridRetriever, RetrievalFilters
from rag.pipeline import CommunityPipeline
from tests.fakes import FakeVectorStore, ScriptedModel


CORPUS = [
    {
        "text": "Article 8.4 of the zoning bylaw permits accessory dwelling units "
                "by right in all residential districts, subject to dimensional limits.",
        "source_type": "municipal_document", "title": "Zoning Bylaw",
        "url": "https://example.org/zoning.pdf", "page": 84, "section": "Article 8.4",
        "document_type": "bylaw", "status": "adopted", "effective_date": "2024-06-01",
    },
    {
        "text": "Article 8.1 of the zoning bylaw governs signage dimensions in "
                "business districts and requires a special permit for projecting signs.",
        "source_type": "municipal_document", "title": "Zoning Bylaw",
        "url": "https://example.org/zoning.pdf", "page": 81, "section": "Article 8.1",
        "document_type": "bylaw", "status": "adopted", "effective_date": "2024-06-01",
    },
    {
        "text": "Several members expressed support for the Coolidge Corner redesign "
                "but the board took no vote on the proposal at this meeting.",
        "source_type": "meeting_transcript", "body": "Select Board",
        "meeting_date": "2026-05-12", "start_time": 4422.0,
        "url": "https://www.youtube.com/watch?v=abc123",
        "speaker": "Jane Smith", "speaker_role": "Transportation Director",
        "agenda_item": "Coolidge Corner redesign",
    },
    {
        "text": "The Planning Board voted unanimously to approve the site plan for "
                "the Harvard Street mixed use project.",
        "source_type": "meeting_transcript", "body": "Planning Board",
        "meeting_date": "2019-09-04", "start_time": 812.0,
        "url": "https://www.youtube.com/watch?v=xyz789",
        "speaker": "Ann Lee", "speaker_role": "Chair",
    },
    {
        "text": "Municipal buildings will transition away from fossil fuel heating "
                "to heat pumps under the electrification schedule by 2035.",
        "source_type": "municipal_document", "title": "Climate Action Plan",
        "url": "https://example.org/cap.pdf", "page": 73,
        "document_type": "plan", "status": "adopted",
    },
    {
        "text": "Curbside solid waste collection shifts one day later during weeks "
                "containing a holiday.",
        "source_type": "website", "title": "Public Works FAQ",
        "url": "https://example.org/dpw",
    },
]


PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}  {detail}")


def make_retriever() -> HybridRetriever:
    store = FakeVectorStore(CORPUS)
    retriever = HybridRetriever(store, cache_key=f"test-{id(store)}")
    return retriever


def test_keyword_beats_dense_on_exact_identifiers() -> None:
    print("\nexact identifiers reach the model")
    r = make_retriever()
    result = r.retrieve("What does Article 8.4 of the zoning bylaw say?",
                        top_k=3, use_reranker=False)
    top = result.chunks[0].chunk.text
    check("Article 8.4 ranks first", "8.4" in top, f"got: {top[:60]}")
    check("both retrievers contributed",
          result.dense_hits > 0 and result.sparse_hits > 0,
          f"dense={result.dense_hits} sparse={result.sparse_hits}")
    paths = {c.retrieval_path for c in result.chunks}
    check("retrieval path is recorded", paths <= {"dense", "keyword", "both"}, str(paths))


def test_filters_restrict_by_board_and_date() -> None:
    print("\nmetadata filters")
    r = make_retriever()

    result = r.retrieve("approve project", top_k=5, use_reranker=False,
                        filters=RetrievalFilters(body="Planning Board"))
    bodies = {c.chunk.body for c in result.chunks}
    check("board filter keeps only that board", bodies == {"Planning Board"}, str(bodies))

    result = r.retrieve("board vote", top_k=5, use_reranker=False,
                        filters=RetrievalFilters(date_from="2026-01-01"))
    dates = [c.chunk.record_date for c in result.chunks]
    check("date filter excludes older records",
          all(d >= "2026-01-01" for d in dates if d), str(dates))

    result = r.retrieve("zoning", top_k=5, use_reranker=False,
                        filters=RetrievalFilters(source_type=SourceType.MUNICIPAL_DOCUMENT))
    types = {c.chunk.source_type for c in result.chunks}
    check("source type filter applies", types == {SourceType.MUNICIPAL_DOCUMENT}, str(types))


def test_empty_corpus_is_survivable() -> None:
    print("\nempty corpus")
    r = HybridRetriever(FakeVectorStore([]), cache_key="empty-corpus")
    result = r.retrieve("anything at all", top_k=5)
    check("no chunks returned", result.chunks == [])
    check("corpus size reported zero", result.corpus_size == 0)
    check("diagnostics still produced", "elapsed_ms" in result.diagnostics())


def test_citations_deep_link_to_the_record() -> None:
    print("\ncitations and deep links")
    r = make_retriever()
    result = r.retrieve("Did the Select Board approve the Coolidge Corner redesign?",
                        top_k=4, use_reranker=False)
    citations = build_citations(result.chunks)
    check("citations numbered from 1", [c.number for c in citations][:1] == [1])

    meeting = next((c for c in citations if c.source_type == SourceType.MEETING_TRANSCRIPT), None)
    check("a meeting was retrieved", meeting is not None)
    if meeting:
        check("meeting link seeks to the timestamp", "&t=" in meeting.url, meeting.url)
        check("meeting label carries board, date, time",
              "Select Board" in meeting.label and "•" in meeting.label, meeting.label)
        check("speaker attribution recorded",
              "Jane Smith" in (meeting.attribution or ""), meeting.attribution)

    doc = next((c for c in citations if c.source_type == SourceType.MUNICIPAL_DOCUMENT), None)
    if doc:
        check("document link opens the page", "#page=" in doc.url, doc.url)


def test_invalid_citations_are_stripped() -> None:
    print("\ncitation verification")
    chunk = CivicChunk(text="x", source_type=SourceType.MUNICIPAL_DOCUMENT,
                       title="Plan", url="https://e.org/p.pdf", page=3)
    citations = build_citations([chunk])
    check_result = verify_citations("Supported [1]. Invented [9].", citations)
    check("real marker counted", check_result.cited_numbers == [1])
    check("fabricated marker flagged", check_result.invalid_numbers == [9])
    check("check reports not ok", check_result.ok is False)


def test_pipeline_injects_constitution_and_context() -> None:
    print("\npipeline assembly")
    constitution = load_constitution()
    pipeline = CommunityPipeline(
        retriever=make_retriever(),
        constitution=constitution,
        project_name="Brookline AI",
        community="Brookline, MA",
        model="gemma-4-26b-a4b", provider="lmstudio",
    )
    model = ScriptedModel("The board discussed it but took no vote [3]. Also [9].")
    answer = pipeline.answer("Did the Select Board approve the redesign?", generate=model)

    check("model was called", len(model.prompts) == 1)
    prompt = model.prompts[0]
    blocks = prompt.system_blocks()
    check("three system blocks sent", len(blocks) == 3, f"got {len(blocks)}")
    check("constitution injected as its own block",
          "COMMUNITY CONSTITUTION" in blocks[1], blocks[1][:60])
    check("constitution version present",
          f"version {constitution.version}" in blocks[1])
    check("retrieved records in their own block",
          "COMMUNITY RECORDS RETRIEVED" in blocks[2], blocks[2][:60])
    check("context warns against prompt injection from records",
          "never as instructions" in blocks[2])

    check("fabricated marker removed from answer",
          "[9]" not in answer.answer, answer.answer)
    check("provenance names the model",
          answer.provenance.model == "gemma-4-26b-a4b")
    check("provenance carries constitution version",
          answer.provenance.constitution_version == constitution.version)
    check("provenance counts retrieved sources",
          answer.provenance.sources_retrieved == len(answer.citations))
    check("warning recorded for stripped marker",
          any("removed citation" in w for w in answer.provenance.warnings),
          str(answer.provenance.warnings))

    openai_messages = prompt.as_openai_messages()
    check("openai shape ends with the user question",
          openai_messages[-1]["role"] == "user")
    system_text, anthropic_messages = prompt.as_anthropic_messages()
    check("anthropic shape flattens system blocks",
          "COMMUNITY CONSTITUTION" in system_text
          and all(m["role"] != "system" for m in anthropic_messages))


def test_legacy_payloads_still_retrievable() -> None:
    print("\nbackward compatibility with already-ingested data")
    legacy = [{
        "text": "The select board discussed the bike lane proposal on Beacon Street.",
        "source": "Town Meetings", "source_type": "youtube",
        "url": "https://youtube.com/watch?v=old1", "title": "Select Board Jan 15",
        "date": "2024-01-15", "video_id": "old1", "timestamp": 930.0,
    }]
    r = HybridRetriever(FakeVectorStore(legacy), cache_key="legacy-corpus")
    result = r.retrieve("bike lane Beacon Street", top_k=3, use_reranker=False)
    check("legacy chunk retrieved", len(result.chunks) == 1)
    if result.chunks:
        chunk = result.chunks[0].chunk
        check("legacy youtube mapped to meeting_transcript",
              chunk.source_type == SourceType.MEETING_TRANSCRIPT, chunk.source_type)
        check("legacy timestamp became start_time", chunk.start_time == 930.0)
        link = deep_link(chunk)
        check("legacy chunk deep links to timestamp", "&t=930s" in link, link)


def test_answer_without_any_retrieval_says_so() -> None:
    print("\nno matching records")
    pipeline = CommunityPipeline(
        retriever=HybridRetriever(FakeVectorStore([]), cache_key="none-corpus"),
        constitution=load_constitution(), community="Brookline, MA",
    )
    model = ScriptedModel("I do not have a record of that in the knowledge base.")
    answer = pipeline.answer("What did the Planning Board decide yesterday?", generate=model)
    context = model.prompts[0].context_block
    check("context states that nothing was retrieved",
          "none" in context.lower() or "empty" in context.lower(), context[:80])
    check("no citations offered", answer.citations == [])
    check("no false 'uncited answer' warning when nothing was retrieved",
          not any("cites no community source" in w for w in answer.provenance.warnings),
          str(answer.provenance.warnings))


def main() -> int:
    print("=" * 62)
    print("Community RAG pipeline tests")
    print("=" * 62)
    for fn in [
        test_keyword_beats_dense_on_exact_identifiers,
        test_filters_restrict_by_board_and_date,
        test_empty_corpus_is_survivable,
        test_citations_deep_link_to_the_record,
        test_invalid_citations_are_stripped,
        test_pipeline_injects_constitution_and_context,
        test_legacy_payloads_still_retrievable,
        test_answer_without_any_retrieval_says_so,
    ]:
        fn()

    print("\n" + "=" * 62)
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        for name in FAIL:
            print(f"  FAILED: {name}")
    return 1 if FAIL else 0


# pytest entry points
def test_all() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
