"""Tests for the platform layer: record status, tenancy, precompute, second opinion.

No network, no model, no database.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from knowledge.schemas import RecordStatus, SourceType
from knowledge.status import classify_status, describe_for_context, detect_vote
from models import AIProvider, ProjectConfig
from precompute import (
    AnswerCache, CacheKey, STARTER_QUESTIONS, mine_questions_from_logs,
    normalize_question, question_list, run_precompute, save_question_list,
)
from second_opinion import PROVIDER_RECIPIENTS, available_options, ask, compare
from tenancy import (
    IsolationError, Tenant, TenantRegistry, TenancyError, load_registry,
    scaffold_tenant, tenant_constitution, tenant_eval_files,
)

PASS: List[str] = []
FAIL: List[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  -> {detail}" if not condition else ""))


# --- record status --------------------------------------------------------

MEETING = {"source_type": SourceType.MEETING_TRANSCRIPT}


def test_discussion_is_never_mistaken_for_a_decision() -> None:
    print("\ndiscussion is not a decision")
    a = classify_status(
        "Several members expressed support for the redesign, and the board asked "
        "staff to return with cost figures. No motion was made.", MEETING)
    check("classified as discussion", a.status == RecordStatus.DISCUSSION, a.status)
    check("no vote recorded", a.vote.vote_taken is False)
    check("explicit absence is high confidence", a.confidence >= 0.85, str(a.confidence))
    check("the context line tells the model outright",
          "no vote was taken" in describe_for_context(a), describe_for_context(a))

    a = classify_status("The board discussed parking for about forty minutes.", MEETING)
    check("silence about a vote still means discussion",
          a.status == RecordStatus.DISCUSSION, a.status)
    check("and is never adopted", a.status != RecordStatus.ADOPTED)


def test_votes_are_detected_with_their_tally() -> None:
    print("\nvotes")
    a = classify_status(
        "I move that we approve the site plan. Seconded. All those in favor? "
        "The motion carries 4-1.", MEETING)
    check("classified as adopted", a.status == RecordStatus.ADOPTED, a.status)
    check("vote recorded", a.vote.vote_taken is True)
    check("outcome is passed", a.vote.outcome == "passed", a.vote.outcome)
    check("tally captured", a.vote.tally == "4-1", a.vote.tally)
    check("yes and no counts parsed", (a.vote.yes, a.vote.no) == (4, 1),
          str((a.vote.yes, a.vote.no)))
    check("the context line states the tally",
          "4-1" in describe_for_context(a), describe_for_context(a))

    a = classify_status(
        "On a motion duly made and seconded, it was voted unanimously to adopt "
        "the amended budget.", MEETING)
    check("unanimous votes are adopted", a.status == RecordStatus.ADOPTED)
    check("unanimous recorded as the tally", a.vote.tally == "unanimous", a.vote.tally)

    a = classify_status("The motion failed for lack of a second.", MEETING)
    check("a failed motion is not adopted", a.status != RecordStatus.ADOPTED, a.status)
    check("the failure is recorded as a vote outcome",
          a.vote.outcome == "failed", a.vote.outcome)

    a = classify_status("The article was tabled and continued to the May meeting.", MEETING)
    check("tabled is not adopted", a.status == RecordStatus.DISCUSSION)
    check("tabled is recorded", a.vote.outcome == "tabled", a.vote.outcome)


def test_a_vote_said_out_loud_is_read_as_a_vote() -> None:
    """Minutes write "4-1". Transcripts are people talking, and this archive
    is mostly transcripts. Every case here was classified as discussion before
    the patterns learned to hear a sentence rather than a phrase."""
    print("\nvotes as spoken, not as written")

    a = classify_status(
        "The motion to approve the minutes carries, five to zero.", MEETING)
    check("a subject separated from its verb is still a vote",
          a.status == RecordStatus.ADOPTED, a.status)
    check("and the spoken tally is read", a.vote.tally == "5-0", a.vote.tally)

    a = classify_status(
        "The committee voted unanimously to adopt the budget.", MEETING)
    check("an adverb between the verb and the object does not hide the vote",
          a.status == RecordStatus.ADOPTED, a.status)
    check("recorded as unanimous", a.vote.tally == "unanimous", a.vote.tally)

    a = classify_status("The motion to accept the gift was adopted unanimously.", MEETING)
    check("adopted, with the motion spelled out in between",
          a.status == RecordStatus.ADOPTED, a.status)

    a = classify_status(
        "The motion to rezone the parcel failed, two to three.", MEETING)
    check("a failed vote is recorded as a vote", a.vote.vote_taken is True)
    check("with its outcome", a.vote.outcome == "failed", a.vote.outcome)
    check("and its spoken tally", a.vote.tally == "2-3", a.vote.tally)
    check("but is not adopted", a.status != RecordStatus.ADOPTED, a.status)

    a = classify_status(
        "The motion carries, four to one with one abstaining.", MEETING)
    check("an abstention is counted", a.vote.tally == "4-1-1", a.vote.tally)
    check("and parsed", a.vote.abstain == 1, str(a.vote.abstain))


def test_a_negated_vote_is_not_a_vote() -> None:
    """The loosened patterns are the risk. A sentence that says a thing did
    not happen must not read as the thing happening: that is the same failure
    as reporting discussion as a decision, pointed the other way."""
    print("\nnegation")

    a = classify_status("The board never voted to approve the plan.", MEETING)
    check("never voted to approve is not an approval",
          a.status != RecordStatus.ADOPTED, a.status)
    check("and no vote is recorded", a.vote.vote_taken is False)

    a = classify_status("The motion to approve the contract was not passed.", MEETING)
    check("was not passed is not passed", a.vote.outcome != "passed", a.vote.outcome)

    a = classify_status("The board declined to approve the contract.", MEETING)
    check("declined to approve is not adopted", a.status != RecordStatus.ADOPTED, a.status)

    vote = detect_vote("The project will cost four to five million dollars.")
    check("a spoken number range with no vote language is not a tally",
          vote.tally == "" and vote.vote_taken is False, vote.tally)

    vote = detect_vote("We met from four to six on Tuesday.")
    check("nor is a time range", vote.tally == "", vote.tally)


def test_talk_about_a_vote_is_not_a_vote() -> None:
    """Every sentence here was said at a Brookline meeting, is copied from the
    automatic captions as they came, and was filed as "a vote was taken and it
    passed". The earlier tests were written in the grammar of minutes. A
    meeting is mostly the future and the conditional, and this is that."""
    print("\nwhat boards actually say, from the first night of the real archive")

    for said, why in [
        ("I'm pleased to come in front of the board to ask that the board vote to accept "
         "funding under the Charles Shannon grant", "asking for a vote"),
        ("we recommend that this board vote to accept them as well", "recommending one"),
        ("designed to operate such that article 5 would be passed that is the one that "
         "presents the overall concept", "a vote that might happen"),
        ("article 5 which has passed we think will really give the town the most effective "
         "tool", "an article described in passing"),
        ("and so warrant article 23 of 1946 of the laws passed by town meeting at the time "
         "includes the agreement", "history"),
        ("implement the warrant article if it's passed", "a condition"),
        ("we have a second reading and vote tonight on the legislative priorities",
         "a second reading is not a second"),
        ("give me just a second to find the page all in favor of moving on",
         "nor is just a second"),
    ]:
        a = classify_status(said, MEETING)
        check(f"{why}: not adopted", a.status != RecordStatus.ADOPTED,
              f"{a.status} on {a.evidence}")

    print("\nand the votes among them, which are still votes")
    a = classify_status("any other questions then I move that we approve the minutes of "
                        "December 11th as amended all in favor please say aye selectman "
                        "Daly aye selectman Mermell aye", MEETING)
    check("the chair's motion and the vote on it", a.status == RecordStatus.ADOPTED, a.status)
    check("without a tally nobody announced: a vote that was called is not thereby "
          "unanimous", a.vote.tally == "", a.vote.tally)
    check("and the words that decided it are kept", bool(a.evidence), str(a.evidence))

    a = classify_status("Do we have a motion to accept the capital projects? So moved. "
                        "Second. We have a second. All those in favor? Aye. That's unanimous.",
                        MEETING)
    check("unanimous when somebody says unanimous",
          a.status == RecordStatus.ADOPTED and a.vote.tally == "unanimous",
          f"{a.status} {a.vote.tally}")

    for said, what in [
        ("ready to vote I move that we award and execute contract number pw1 13-16 pavement "
         "management system all in favor please say aye", "a contract number"),
        ("I move that we approve amendment number four to contract PW 06-08 professional "
         "design services all in favor please say aye", "another, which read as losing 6-8"),
        ("I move that we grant the licence for liquor also 11 12 to9 Friday and Saturday "
         "all in favor please say aye", "the hours on a liquor licence"),
        ("I move that we correct this just by changing Monday to Sunday on the vote Sunday "
         "would be 11 to9 and then 12 to 9 for the liquor all in favor please say aye",
         "hours again, this time with the word vote nearby"),
    ]:
        a = classify_status(said, MEETING)
        check(f"{what} is not a tally", a.vote.tally == "", a.vote.tally)
        check("and the vote beside it is still a vote", a.status == RecordStatus.ADOPTED)
    a = classify_status("I move that we approve the contract. The motion carries on a 3-2 "
                        "vote.", MEETING)
    check("a tally said beside the result is still read", a.vote.tally == "3-2", a.vote.tally)
    for said, tally in [("The board voted 4 to 1 to approve the licence.", "4-1"),
                        ("The motion passed by a vote of three to two.", "3-2"),
                        ("The motion carries, as amended, four to one.", "4-1")]:
        check(f"and so is {said[:38]!r}", detect_vote(said).tally == tally,
              detect_vote(said).tally)

    a = classify_status("the audit committee voted unanimously to accept the audit reports",
                        MEETING)
    check("a vote reported in the past tense is a vote", a.status == RecordStatus.ADOPTED)


def test_the_words_that_decided_a_status_ride_along_on_the_passage() -> None:
    print("\nevidence, which the guide promises and the chunk used to drop")
    from knowledge.schemas import meeting_chunks

    chunks = meeting_chunks(
        [{"text": "I move that we approve the contract all in favor please say aye", "start": 12.0}],
        community="Brookline, MA", body="Select Board", meeting_date="2013-01-15",
        video_url="https://youtube.com/watch?v=x")
    payload = chunks[0].to_payload()
    check("the label", payload.get("status") == RecordStatus.ADOPTED, str(payload.get("status")))
    check("and why", "move that" in payload.get("status_evidence", "").lower(),
          str(payload.get("status_evidence")))


def test_a_bare_number_is_not_a_tally() -> None:
    print("\nnumbers that look like tallies")
    vote = detect_vote("The project runs from 2024-2026 and costs 4-5 million dollars.")
    check("a cost range is not a vote", vote.vote_taken is False)
    check("and no tally is invented", vote.tally == "", vote.tally)

    vote = detect_vote("The motion carries 5-0.")
    check("a tally beside vote language is a vote", vote.vote_taken is True)
    check("and is parsed", vote.tally == "5-0", vote.tally)


def test_document_type_decides_when_it_knows() -> None:
    print("\ndocuments")
    a = classify_status("Article 8.4 permits accessory dwelling units by right.",
                        {"source_type": SourceType.MUNICIPAL_DOCUMENT,
                         "document_type": "bylaw"})
    check("bylaw text is adopted", a.status == RecordStatus.ADOPTED, a.status)

    a = classify_status("Seeks to appropriate $5,000,000 for roof repair.",
                        {"source_type": SourceType.MUNICIPAL_DOCUMENT,
                         "document_type": "warrant_article"})
    check("a warrant article is a proposal", a.status == RecordStatus.PROPOSED, a.status)

    a = classify_status("Anything at all.",
                        {"source_type": SourceType.MUNICIPAL_DOCUMENT,
                         "status": "superseded"})
    check("a declared status wins over any guess",
          a.status == "superseded", a.status)
    check("and is high confidence", a.confidence >= 0.9)


def test_classification_shows_its_evidence() -> None:
    print("\nevidence")
    a = classify_status("The motion carries 4-1.", MEETING)
    check("the triggering phrase is recorded", bool(a.vote.phrases), str(a.vote.phrases))
    check("metadata carries status and confidence",
          {"status", "status_confidence"} <= set(a.to_metadata()))
    check("metadata carries the tally for a vote",
          a.to_metadata().get("vote_tally") == "4-1", str(a.to_metadata()))


# --- tenancy --------------------------------------------------------------


def _two_towns(tmp: str) -> Path:
    root = Path(tmp) / "data"
    for pid, community in [("brookline-ma", "Brookline, MA"),
                           ("cambridge-ma", "Cambridge, MA")]:
        d = root / pid
        d.mkdir(parents=True)
        (d / "config.json").write_text(json.dumps({"municipality_name": community}))
    return root


def test_tenants_are_discovered_without_configuration() -> None:
    print("\ntenancy discovery")
    with tempfile.TemporaryDirectory() as tmp:
        root = _two_towns(tmp)
        registry = load_registry(path="/nonexistent.yaml", data_root=str(root))
        check("both projects became tenants", len(registry) == 2, str(len(registry)))
        check("community name carried over",
              registry.get("brookline-ma").community == "Brookline, MA")
        check("no configuration was required", registry.problems == [],
              str(registry.problems))


def test_tenant_isolation_fails_closed() -> None:
    print("\ntenancy isolation")
    with tempfile.TemporaryDirectory() as tmp:
        root = _two_towns(tmp)
        registry = load_registry(path="/nonexistent.yaml", data_root=str(root))
        brookline = registry.get("brookline-ma")
        cambridge = registry.get("cambridge-ma")

        check("own directory allowed",
              brookline.contains(brookline.data_root(str(root)) / "qdrant", str(root)))
        check("another community's directory refused",
              not brookline.contains(cambridge.data_root(str(root)), str(root)))

        for label, path in [
            ("another tenant's config", cambridge.data_root(str(root)) / "config.json"),
            ("a traversal out of the data root", root / ".." / ".." / "etc" / "passwd"),
            ("an absolute path elsewhere", Path("/etc/hosts")),
        ]:
            try:
                brookline.assert_contains(path, str(root))
                check(f"raises on {label}", False, "allowed")
            except IsolationError:
                check(f"raises on {label}", True)


def test_each_community_governs_itself() -> None:
    print("\nper-community governance")
    with tempfile.TemporaryDirectory() as tmp:
        root = _two_towns(tmp)
        registry = load_registry(path="/nonexistent.yaml", data_root=str(root))
        brookline = registry.get("brookline-ma")

        check("starts without its own constitution",
              not brookline.has_own_constitution(str(root)))
        borrowed = tenant_constitution(brookline, data_root=str(root))
        check("falls back to the deployment default", borrowed.version == "1.0")
        check("and says so rather than hiding it",
              any("has not adopted its own" in p for p in borrowed.ledger_problems),
              str(borrowed.ledger_problems))

        scaffold_tenant(brookline, data_root=str(root))
        check("scaffolding gives it its own copy",
              brookline.has_own_constitution(str(root)))
        own = tenant_constitution(brookline, data_root=str(root))
        check("the fallback warning is gone",
              not any("has not adopted" in p for p in own.ledger_problems),
              str(own.ledger_problems))

        cambridge = registry.get("cambridge-ma")
        check("the other community is untouched",
              not cambridge.has_own_constitution(str(root)))

        check("evaluation sets fall back to the seed set",
              len(tenant_eval_files(cambridge, str(root))) > 0)


def test_tenant_resolution() -> None:
    print("\ntenancy resolution")
    registry = TenantRegistry(data_root="./data")
    registry.register(Tenant(tenant_id="brookline", project_id="brookline-ma",
                             hostnames=["brookline.civicai.org", "*.bkl.test"],
                             path_prefix="/brookline"))
    registry.register(Tenant(tenant_id="cambridge", project_id="cambridge-ma",
                             hostnames=["cambridge.civicai.org"]))

    check("hostname resolves",
          registry.resolve(hostname="brookline.civicai.org").tenant_id == "brookline")
    check("port is ignored",
          registry.resolve(hostname="brookline.civicai.org:8443").tenant_id == "brookline")
    check("wildcard hostname resolves",
          registry.resolve(hostname="anything.bkl.test").tenant_id == "brookline")
    check("path prefix resolves",
          registry.resolve(path="/brookline/community/ask").tenant_id == "brookline")
    check("project id resolves",
          registry.resolve(project_id="cambridge-ma").tenant_id == "cambridge")
    check("an explicit id wins over the hostname",
          registry.resolve(hostname="cambridge.civicai.org",
                           explicit="brookline").tenant_id == "brookline")
    check("an unknown host resolves to nothing when several tenants exist",
          registry.resolve(hostname="stranger.example.com") is None)

    single = TenantRegistry(data_root="./data")
    single.register(Tenant(tenant_id="only", project_id="only"))
    check("one community serves every request",
          single.resolve(hostname="whatever.example.com").tenant_id == "only")


def test_conflicting_tenants_are_refused() -> None:
    print("\ntenancy conflicts")
    registry = TenantRegistry(data_root="./data")
    registry.register(Tenant(tenant_id="a", hostnames=["shared.example.org"]))
    for label, tenant in [
        ("a duplicate hostname", Tenant(tenant_id="b", hostnames=["shared.example.org"])),
        ("a duplicate id", Tenant(tenant_id="a")),
    ]:
        try:
            registry.register(tenant)
            check(f"{label} is refused", False, "accepted")
        except TenancyError:
            check(f"{label} is refused", True)

    try:
        Tenant(tenant_id="Has Spaces")
        check("an unusable tenant id is refused", False, "accepted")
    except TenancyError:
        check("an unusable tenant id is refused", True)


# --- precompute -----------------------------------------------------------


class FakeAgent:
    """Just enough agent for a precompute pass."""

    def __init__(self, documents: int = 100, constitution_hash: str = "sha256:aaa",
                 answers: Dict[str, Dict[str, Any]] | None = None) -> None:
        self.config = ProjectConfig(project_id="p", municipality_name="X",
                                    project_name="Y", model_name="gemma-4-26b-a4b")
        self.client_type = "lmstudio"
        self.constitution = type("C", (), {"content_hash": constitution_hash})()
        self.vector_store = type("V", (), {
            "get_stats": staticmethod(lambda: {"total_documents": documents,
                                               "embedding_model": "all-MiniLM-L6-v2"})
        })()
        self.answers = answers or {}
        self.calls: List[str] = []

    def chat(self, question, conversation_history=None, filters=None):
        self.calls.append(question)
        if question in self.answers:
            return self.answers[question]
        return {"answer": f"answer to {question}", "sources": [{"id": "s1", "used": True}],
                "provenance": {"sources_used": 1, "model": "gemma-4-26b-a4b"}}


def test_cache_key_covers_what_changes_an_answer() -> None:
    print("\nprecompute cache keys")
    base = CacheKey("When is trash day?", "c1", "h1", "m", "p")
    check("wording differences collapse",
          base.digest() == CacheKey("when is TRASH day", "c1", "h1", "m", "p").digest())
    check("a changed corpus invalidates",
          base.digest() != CacheKey("When is trash day?", "c2", "h1", "m", "p").digest())
    check("an amended constitution invalidates",
          base.digest() != CacheKey("When is trash day?", "c1", "h2", "m", "p").digest())
    check("a different model invalidates",
          base.digest() != CacheKey("When is trash day?", "c1", "h1", "m2", "p").digest())


def test_precompute_pass() -> None:
    print("\nprecompute pass")
    with tempfile.TemporaryDirectory() as tmp:
        agent = FakeAgent()
        questions = ["When is trash day?", "How do I get a permit?"]
        result = run_precompute("p", agent, questions=questions, data_root=tmp)
        check("both computed", result.computed == 2, str(result.computed))
        check("model was called twice", len(agent.calls) == 2, str(len(agent.calls)))

        agent.calls.clear()
        again = run_precompute("p", agent, questions=questions, data_root=tmp)
        check("second pass reuses the cache", again.reused == 2, str(again.reused))
        check("and calls the model zero times", agent.calls == [], str(agent.calls))

        from precompute import lookup
        hit = lookup("p", "when is TRASH day", agent, data_root=tmp)
        check("a resident's question hits the cache", hit is not None)
        check("and the answer says it was prepared earlier",
              hit["provenance"].get("precomputed") is True, str(hit["provenance"]))

        # Amending the constitution must invalidate everything.
        agent.constitution = type("C", (), {"content_hash": "sha256:bbb"})()
        check("an amended constitution is a cache miss",
              lookup("p", "When is trash day?", agent, data_root=tmp) is None)
        third = run_precompute("p", agent, questions=questions, data_root=tmp)
        check("and forces a recompute", third.computed == 2, str(third.computed))
        check("stale entries are pruned", third.pruned == 2, str(third.pruned))


def test_answers_without_sources_are_not_cached() -> None:
    print("\nwhat not to cache")
    with tempfile.TemporaryDirectory() as tmp:
        agent = FakeAgent(answers={
            "What is the poet laureate's name?": {
                "answer": "I do not have a record of that.",
                "sources": [], "provenance": {"sources_used": 0},
            }})
        result = run_precompute("p", agent,
                                questions=["What is the poet laureate's name?"],
                                data_root=tmp)
        check("an answer with no sources is not cached", result.computed == 0)
        check("and is reported rather than silently dropped",
              any("not cached" in e for e in result.errors), str(result.errors))


def test_question_list_and_log_mining() -> None:
    print("\nwhere questions come from")
    with tempfile.TemporaryDirectory() as tmp:
        questions, source = question_list("p", tmp)
        check("falls back to the starter list",
              questions == STARTER_QUESTIONS, source)

        save_question_list("p", ["When is trash day?"], tmp)
        questions, source = question_list("p", tmp)
        check("an operator's list wins", questions == ["When is trash day?"])

        check("mining finds nothing without logs",
              mine_questions_from_logs("p", data_root=tmp) == [])

        logs = Path(tmp) / "p" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        from datetime import datetime as dt
        today = dt.now().strftime("%Y-%m-%d")
        lines = []
        for _ in range(4):
            lines.append(json.dumps({"question": "When is trash day?"}))
        lines.append(json.dumps({"question_hash": "abc"}))  # no text: privacy default
        (logs / f"requests-{today}.jsonl").write_text("\n".join(lines))

        mined = mine_questions_from_logs("p", data_root=tmp, minimum=3)
        check("a repeated question is mined", mined and mined[0][1] == 4, str(mined))
        check("a hashed-only record contributes nothing",
              len(mined) == 1, str(mined))


# --- second opinion -------------------------------------------------------


def test_second_opinion_options() -> None:
    print("\nsecond opinion")
    project = ProjectConfig(project_id="t", municipality_name="Brookline, MA",
                            project_name="B", ai_provider=AIProvider.LMSTUDIO)
    options = available_options(project)
    check("three frontier options offered", len(options) == 3, str(len(options)))
    check("each names who receives the question",
          all(o.recipient for o in options))
    check("Gemini discloses Google, not Gemini",
          next(o for o in options if o.provider == "gemini").recipient == "Google")

    anthropic_primary = ProjectConfig(project_id="t2", municipality_name="X",
                                      project_name="Y",
                                      ai_provider=AIProvider.ANTHROPIC)
    check("a provider is not offered as a second opinion on itself",
          "anthropic" not in [o.provider for o in available_options(anthropic_primary)])

    check("local providers are described as sending nothing out",
          "nobody" in PROVIDER_RECIPIENTS["lmstudio"])


def test_second_opinion_refuses_cleanly() -> None:
    print("\nsecond opinion failures")
    import os
    saved = {k: os.environ.pop(k, None) for k in
             ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY")}
    try:
        project = ProjectConfig(project_id="t", municipality_name="X",
                                project_name="Y", ai_provider=AIProvider.LMSTUDIO)
        result = ask(project, None, "a question", "anthropic")
        check("a missing key is an error, not a crash", result.error is not None)
        check("the disclosure is set even on failure",
              "Anthropic" in result.disclosure, result.disclosure)

        result = ask(project, None, "a question", "not-a-provider")
        check("an unknown provider is refused", result.error is not None)
        check("and the refusal lists the real options",
              "anthropic" in (result.error or ""), str(result.error))
    finally:
        for key, value in saved.items():
            if value:
                os.environ[key] = value


def test_comparison_is_mechanical() -> None:
    print("\ncomparing two answers")
    from second_opinion import SecondOpinion
    local = {"answer": "Local answer.", "sources": [{"id": "a", "used": True}],
             "provenance": {"model": "gemma", "provider": "lmstudio", "sources_used": 1}}
    other = SecondOpinion(provider="anthropic", model="claude-opus-5",
                          recipient="Anthropic", answer="A longer frontier answer.",
                          sources=[{"id": "b", "used": True}],
                          provenance={"sources_used": 1})
    result = compare(local, other)
    check("both sides described", result["local"]["model"] == "gemma"
          and result["second_opinion"]["model"] == "claude-opus-5")
    check("differing citations are surfaced",
          result["sources_only_local_used"] == ["a"]
          and result["sources_only_other_used"] == ["b"], str(result))
    check("no verdict is rendered",
          not any(k in result for k in ("winner", "better", "score")), str(result.keys()))


def main() -> int:
    print("=" * 62)
    print("Platform tests: status, tenancy, precompute, second opinion")
    print("=" * 62)
    for fn in [
        test_discussion_is_never_mistaken_for_a_decision,
        test_votes_are_detected_with_their_tally,
        test_a_vote_said_out_loud_is_read_as_a_vote,
        test_a_negated_vote_is_not_a_vote,
        test_talk_about_a_vote_is_not_a_vote,
        test_the_words_that_decided_a_status_ride_along_on_the_passage,
        test_a_bare_number_is_not_a_tally,
        test_document_type_decides_when_it_knows,
        test_classification_shows_its_evidence,
        test_tenants_are_discovered_without_configuration,
        test_tenant_isolation_fails_closed,
        test_each_community_governs_itself,
        test_tenant_resolution,
        test_conflicting_tenants_are_refused,
        test_cache_key_covers_what_changes_an_answer,
        test_precompute_pass,
        test_answers_without_sources_are_not_cached,
        test_question_list_and_log_mining,
        test_second_opinion_options,
        test_second_opinion_refuses_cleanly,
        test_comparison_is_mechanical,
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
