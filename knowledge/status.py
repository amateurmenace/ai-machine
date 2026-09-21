"""
Telling discussion apart from a decision.

The signature failure of a civic assistant is answering "did the board approve
it?" with "yes" when the record shows a conversation. The guide's evaluation set
calls this the `ambiguous` category, Principle 4 forbids it, and it is the
failure most likely to end up in a newspaper.

The usual fix is to prompt harder. That does not work well, because at answer
time the model is reading a transcript passage and inferring the parliamentary
state of a meeting from prose. Inference is the wrong tool: a meeting announces
its own state out loud, in a small and highly conventional vocabulary. "I move
that", "is there a second", "all those in favor", "the motion carries four to
one" are not ambiguous English. They are a protocol.

So this classifies at **ingestion**, once, and stores the result. By the time
the model sees the passage it does not have to infer whether a vote happened; it
is told, with the phrase that says so. That moves the problem from generation,
where it is hard, to retrieval metadata, where it is mostly regular expressions.

Two things are deliberately conservative:

* **Silence is not a decision.** A passage with no vote language is classified
  `discussion`, never `adopted`. The cost of under-claiming is an assistant that
  says "the record does not show a vote", which is correct and useful. The cost
  of over-claiming is an assistant that invents a decision.
* **Every classification carries the evidence.** The phrase that triggered it is
  recorded, so a maintainer reviewing a wrong answer can see what the classifier
  saw, and a resident can be shown it.

Pure stdlib. Ingestion should not need a model to read a motion.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from knowledge.schemas import RecordStatus, SourceType


@dataclass
class VoteEvidence:
    """What the passage says about a vote."""

    vote_taken: bool = False
    outcome: str = ""            # passed | failed | tabled | withdrawn | unclear
    tally: str = ""              # "4-1", "unanimous", "5-0-1"
    yes: Optional[int] = None
    no: Optional[int] = None
    abstain: Optional[int] = None
    motion_made: bool = False
    seconded: bool = False
    phrases: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vote_taken": self.vote_taken,
            "outcome": self.outcome,
            "tally": self.tally,
            "yes": self.yes,
            "no": self.no,
            "abstain": self.abstain,
            "motion_made": self.motion_made,
            "seconded": self.seconded,
            "phrases": self.phrases[:6],
        }


@dataclass
class StatusAssessment:
    status: str = RecordStatus.UNKNOWN
    confidence: float = 0.0
    vote: VoteEvidence = field(default_factory=VoteEvidence)
    reason: str = ""
    evidence: List[str] = field(default_factory=list)

    def to_metadata(self) -> Dict[str, Any]:
        """The fields that ride along on a chunk."""
        data: Dict[str, Any] = {
            "status": self.status,
            "status_confidence": round(self.confidence, 2),
        }
        if self.evidence:
            data["status_evidence"] = self.evidence[:3]
        if self.vote.vote_taken:
            data["vote_taken"] = True
            if self.vote.outcome:
                data["vote_outcome"] = self.vote.outcome
            if self.vote.tally:
                data["vote_tally"] = self.vote.tally
        return data


# --- the parliamentary vocabulary ----------------------------------------
#
# Ordered from strongest to weakest signal. A tally is near-conclusive; "moved
# and seconded" says a motion existed but not that it passed.

_TALLY_RE = re.compile(
    r"\b(?P<yes>\d{1,2})\s*(?:-|to|–|—)\s*(?P<no>\d{1,2})"
    r"(?:\s*(?:-|to|–|—)\s*(?P<abstain>\d{1,2}))?\b"
)

# Minutes write "4-1". People say "four to one", and this archive is built out
# of what people said. A classifier that only reads the written form misses
# every tally in every transcript, which is most of the record.
_NUMBER_WORDS = {
    "zero": 0, "none": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12,
}
_WORD_TALLY_RE = re.compile(
    r"\b(?P<yes>" + "|".join(_NUMBER_WORDS) + r")"
    r"\s+(?:to|-)\s+"
    r"(?P<no>" + "|".join(_NUMBER_WORDS) + r")"
    r"(?:\s+(?:to|-|with)\s+(?P<abstain>" + "|".join(_NUMBER_WORDS) + r")"
    r"\s+abstain(?:ing|ed|tions?)?)?\b",
    re.I,
)

# Somebody saying the vote was unanimous.
_UNANIMOUS_RE = re.compile(
    r"\b(?:unanimous(?:ly)?|without objection|nem(?:ine)?\.? con)\b", re.I
)

# The chair calling the vote, which is not the same thing. "All in favor please
# say aye" is how nearly every Select Board vote in the archive is taken, and
# it is how a 3-2 vote is taken too. It used to be read as "unanimous", so the
# model was told a tally nobody had announced.
_VOTE_CALLED_RE = re.compile(
    r"\b(?:all (?:those )?in favor|those in favor|please say aye|say aye|"
    r"call(?:ing)? the roll|roll call(?: vote)?)\b", re.I
)

# Two things a chair says that an earlier version of this pattern missed, both
# of which are the normal way to say it out loud:
#
#   "The motion to approve the minutes carries, five to zero."
#       The subject and its verb are separated by the whole motion. So the
#       gap is allowed, bounded, and not permitted to cross a sentence.
#   "The committee voted unanimously to adopt the budget."
#       An adverb sits between the verb and what was voted on.
#
# Both were classified as discussion, which is the failure this module exists
# to prevent, pointing the other way: a real decision reported as mere talk.
# The gap between a subject and its verb, bounded, not crossing a sentence, and
# refusing to swallow a negation. Without the last part, "the motion to approve
# the contract was not passed" reads as passed, which is the worst mistake this
# file could make.
#
# It refuses the conditional and the future as well. Those were not in the
# minutes-style sentences this was first written against, and they are most of
# how a board talks about a vote: "if the article passes", "the article would
# be passed", "when the motion carries we will". Every one of those is
# discussion, and every one of them read as a vote.
_NOT_AN_OUTCOME = (r"not|never|fail(?:s|ed)?|defeat|reject|deny|withdraw|"
                   r"would|will|should|could|may|might|if|whether|when|once|until|unless|which")
_GAP = r"(?:(?!\b(?:" + _NOT_AN_OUTCOME + r")\b)[^.;?!]){0,60}?"

# An article is talked about far more than it is voted on, and usually from a
# distance: "warrant article 23 of 1946 of the laws passed by town meeting" is
# history. So an article only carries when its verb is within a few words.
_NEAR = r"(?:\s+(?!(?:" + _NOT_AN_OUTCOME + r")\b)[\w'-]+){0,3}?\s+"

_CARRIED_RE = re.compile(
    r"\b(?:motion\b" + _GAP + r"\b(?:carrie[sd]|passe[sd]|prevail(?:s|ed)|adopted|approved)|"
    r"(?:article|amendment|measure)" + _NEAR +
    r"(?:is |was )?(?:carrie[sd]|passe[sd]|prevail(?:s|ed)|adopted|approved)|"
    r"so (?:voted|ordered)|it (?:is |was )?(?:so )?voted|"
    # Past tense only. "We ask that the board vote to accept the grant" and "a
    # motion to approve the budget" are requests, and were being read as results.
    # with room for the count: "voted 4 to 1 to approve"
    r"voted(?:\s+\w+ly)?(?:\s+[\w]+\s*(?:-|to)\s*[\w]+)? to (?:approve|adopt|accept|authorize)|"
    r"(?:approved|adopted) (?:the |this )?(?:motion|article|plan|budget|bylaw))\b",
    re.I,
)

_FAILED_RE = re.compile(
    r"\b(?:motion\b[^.;?!]{0,60}?\b(?:fail(?:s|ed)|(?:is |was )?defeated|"
    r"does not carry|was not (?:adopted|approved|passed)|dies)|"
    r"(?:the )?(?:motion|article|amendment) (?:is |was )?(?:rejected|denied|defeated)|"
    r"vote(?:d)? (?:to )?(?:reject|deny|disapprove)|"
    r"fail(?:s|ed) for (?:the )?lack of a second)\b",
    re.I,
)

_TABLED_RE = re.compile(
    r"\b(?:tabled|laid on the table|postponed indefinitely|continued to|"
    r"referred (?:back )?to|held over|no action (?:was )?taken|"
    r"withdraw(?:n|s|ing)?)\b", re.I
)

# "A second" needs someone asking for it or announcing it. On its own it is
# also "a second reading", "a second time" and "just a second", and the first
# of those is on every School Committee agenda.
_MOTION_RE = re.compile(
    r"\b(?:i move (?:that|to)|so moved|moved (?:and seconded|by)|"
    r"(?:is there|do i hear|we have|i have|there is|there's|need) a second"
    r"(?!\s+(?:reading|time|look|night|meeting|session|round|one|thing|question|point|"
    r"opinion|thought|year|term|part|chance|vote|item|issue|piece|phase|\w+ing)\b)|"
    r"seconded by|entertain a motion|make a motion|"
    r"the motion (?:before us|on the floor))\b",
    re.I,
)

_SECOND_RE = re.compile(r"\b(?:seconded|second(?:s|ed)? (?:the|that|it)|i second)\b", re.I)

# Language that explicitly says a decision has NOT happened. This is the most
# useful signal in the whole module: it distinguishes a passage that is silent
# about a vote from one that says outright there was none.
_NO_DECISION_RE = re.compile(
    r"\b(?:no (?:motion|vote|action) was (?:made|taken)|"
    r"took no (?:vote|action)|no vote (?:was )?(?:taken|held)|"
    r"did not vote|without (?:taking )?a vote|"
    r"(?:for )?discussion (?:only|purposes)|no decision (?:was )?(?:made|reached)|"
    r"will (?:return|come back|be taken up) (?:at|on|next)|"
    r"asked staff to (?:return|report back|come back))\b",
    re.I,
)

_PROPOSAL_RE = re.compile(
    r"\b(?:warrant article|proposed|proposal|draft|recommend(?:s|ed|ation)?|"
    r"under consideration|would (?:allow|require|establish|create)|"
    r"seeks? to|petition(?:er|ed)?|request(?:s|ed|ing)? (?:that|approval))\b",
    re.I,
)

_DISCUSSION_RE = re.compile(
    r"\b(?:discuss(?:ed|ion|ing)|expressed (?:support|concern|opposition)|"
    r"public comment|raised (?:concerns?|questions?)|"
    r"asked (?:whether|about|if)|commented that|testimony|spoke (?:in favor|against))\b",
    re.I,
)

# Document types whose text IS the adopted thing, not a report about one.
_ADOPTED_DOCUMENT_TYPES = {"bylaw", "ordinance", "regulation", "charter", "code"}
_PROPOSED_DOCUMENT_TYPES = {"warrant", "warrant_article", "draft", "proposal", "petition"}


# A tally is two small numbers, and so is a contract number, a date range and
# the hours on a liquor licence. "Somewhere in the same passage as a motion"
# was the test, and in a 220 word passage that let "contract number PW 13-16"
# become a 13-16 vote of a five member board, and "12 to 9 Friday and Saturday"
# a 12-9 one. A tally is said beside the result, so that is where it has to be:
# "carries 4-1", "failed, two to three", "a 3-2 vote".
#
# A result may be a few words from its tally ("carries, as amended, four to
# one"). The word "vote" may not: "on the vote Sunday would be 11 to 9" is a
# board settling a restaurant's hours, and it was read as an 11-9 vote. So
# "vote" only introduces a tally it is directly attached to.
_BEFORE_A_TALLY = re.compile(
    r"\b(?:(?:carrie[sd]|passe[sd]|fail(?:s|ed)|prevail(?:s|ed)|adopted|approved|defeated)\b"
    r"(?:(?!\b(?:would|will|should|could|if)\b)[^.;?!\d]){0,25}"
    r"|(?:vote[sd]?|voting|tally|count)\b(?:\s+(?:of|was|is|were|at|stands at))?[\s,:]{0,3})$",
    re.I)
_AFTER_A_TALLY = re.compile(
    r"^[^.;?!\d]{0,12}\b(?:vote|in favor|decision|margin|majority)\b", re.I)


def _tally_beside_a_vote(text: str):
    """The first tally that sits next to vote language. ``(match, was_spoken)``."""
    for pattern, spoken in ((_TALLY_RE, False), (_WORD_TALLY_RE, True)):
        for match in pattern.finditer(text):
            before = text[max(0, match.start() - 40):match.start()]
            after = text[match.end():match.end() + 24]
            if _BEFORE_A_TALLY.search(before) or _AFTER_A_TALLY.search(after):
                return match, spoken
    return None, False


def _first(pattern: re.Pattern, text: str) -> str:
    match = pattern.search(text)
    return match.group(0).strip() if match else ""


# "The board never voted to approve the plan" contains "voted to approve".
# Reading that as an approval is the same error as reading discussion as a
# decision, so the words immediately before a match get a look.
_NEGATION_RE = re.compile(
    r"\b(?:not|never|no|n't|declined to|refused to|failed to|voted against)\s*$", re.I)


def _first_unnegated(pattern: re.Pattern, text: str, window: int = 24) -> str:
    """The first match whose lead-in does not negate it."""
    for match in pattern.finditer(text):
        before = text[max(0, match.start() - window):match.start()]
        if not _NEGATION_RE.search(before):
            return match.group(0).strip()
    return ""


def detect_vote(text: str) -> VoteEvidence:
    """Read the parliamentary state out of a passage."""
    evidence = VoteEvidence()
    if not text:
        return evidence

    # An explicit statement that nothing was decided outranks everything else.
    # A passage can contain both "I move that" and "no vote was taken"; the
    # second one is the outcome.
    no_decision = _first(_NO_DECISION_RE, text)

    motion = _first(_MOTION_RE, text)
    if motion:
        evidence.motion_made = True
        evidence.phrases.append(motion)

    second = _first(_SECOND_RE, text)
    if second:
        evidence.seconded = True

    carried = _first_unnegated(_CARRIED_RE, text)
    failed = _first(_FAILED_RE, text)
    tabled = _first(_TABLED_RE, text)
    unanimous = _first(_UNANIMOUS_RE, text)
    called = _first(_VOTE_CALLED_RE, text)

    # Digits first, then the spoken form. A bare "4-1" or "four to one" is only
    # a tally when something nearby says it is a vote: dates, scores, dollar
    # ranges and ordinary sentences look identical.
    tally_match, spoken = _tally_beside_a_vote(text)

    if tally_match and (carried or failed or unanimous or motion):
        def value(name: str):
            raw = tally_match.group(name)
            if raw is None:
                return None
            return _NUMBER_WORDS[raw.lower()] if spoken else int(raw)

        evidence.yes = value("yes")
        evidence.no = value("no")
        evidence.abstain = value("abstain")
        parts = [str(evidence.yes), str(evidence.no)]
        if evidence.abstain is not None:
            parts.append(str(evidence.abstain))
        evidence.tally = "-".join(parts)
        evidence.phrases.append(tally_match.group(0).strip())

    if no_decision and not (carried or failed):
        evidence.vote_taken = False
        evidence.outcome = "none"
        evidence.phrases.insert(0, no_decision)
        return evidence

    if failed:
        evidence.vote_taken = True
        evidence.outcome = "failed"
        evidence.phrases.append(failed)
    elif carried:
        evidence.vote_taken = True
        evidence.outcome = "passed"
        evidence.phrases.append(carried)
        if unanimous and not evidence.tally:
            evidence.tally = "unanimous"
            evidence.phrases.append(unanimous)
    elif tabled:
        evidence.vote_taken = False
        evidence.outcome = "tabled"
        evidence.phrases.append(tabled)
    elif (unanimous or called) and evidence.motion_made:
        # A motion, and then the vote on it. Nothing here says it failed, and
        # a failed motion says so. But the tally is only what somebody said it
        # was: a vote that was called is not thereby unanimous.
        evidence.vote_taken = True
        evidence.outcome = "passed"
        if unanimous:
            evidence.tally = evidence.tally or "unanimous"
        evidence.phrases.append(unanimous or called)

    return evidence


def classify_status(text: str, metadata: Optional[Dict[str, Any]] = None
                    ) -> StatusAssessment:
    """Decide what a passage represents: adopted action, a proposal, or talk."""
    metadata = metadata or {}
    assessment = StatusAssessment()
    text = text or ""

    source_type = metadata.get("source_type", "")
    document_type = str(metadata.get("document_type", "")).lower().strip()

    # A source that already knows its own status is authoritative. An operator
    # who tags a bylaw PDF as adopted has better information than any regex.
    declared = str(metadata.get("status", "")).strip().lower()
    if declared and declared not in ("", RecordStatus.UNKNOWN):
        assessment.status = declared
        assessment.confidence = 0.95
        assessment.reason = "declared on the source"
        assessment.vote = detect_vote(text)
        return assessment

    if document_type in _ADOPTED_DOCUMENT_TYPES:
        assessment.status = RecordStatus.ADOPTED
        assessment.confidence = 0.9
        assessment.reason = f"the document is a {document_type}, which is adopted text"
        return assessment

    if document_type in _PROPOSED_DOCUMENT_TYPES:
        assessment.status = RecordStatus.PROPOSED
        assessment.confidence = 0.85
        assessment.reason = f"the document is a {document_type}"
        return assessment

    vote = detect_vote(text)
    assessment.vote = vote

    if vote.vote_taken and vote.outcome == "passed":
        assessment.status = RecordStatus.ADOPTED
        assessment.confidence = 0.9 if vote.tally else 0.75
        assessment.reason = "the passage records a motion carrying"
        assessment.evidence = vote.phrases
        return assessment

    if vote.vote_taken and vote.outcome == "failed":
        # A failed motion is not adopted and is not merely discussion either.
        # It is a decision, and the answer "the board voted it down" needs it.
        assessment.status = RecordStatus.DISCUSSION
        assessment.confidence = 0.85
        assessment.reason = "the passage records a motion failing"
        assessment.evidence = vote.phrases
        return assessment

    if vote.outcome in ("none", "tabled"):
        assessment.status = RecordStatus.DISCUSSION
        assessment.confidence = 0.9
        assessment.reason = (
            "the passage states outright that no decision was reached"
            if vote.outcome == "none" else
            "the matter was tabled, continued or referred"
        )
        assessment.evidence = vote.phrases
        return assessment

    proposal = _first(_PROPOSAL_RE, text)
    discussion = _first(_DISCUSSION_RE, text)

    if source_type == SourceType.MEETING_TRANSCRIPT:
        # Default for meeting text. A meeting is talk until it says otherwise,
        # and treating silence as a decision is the failure this module exists
        # to prevent.
        assessment.status = RecordStatus.DISCUSSION
        assessment.confidence = 0.6 if discussion else 0.4
        assessment.reason = (
            "meeting discussion with no vote language"
            if not discussion else "the passage describes discussion"
        )
        if discussion:
            assessment.evidence = [discussion]
        if vote.motion_made:
            assessment.reason += "; a motion was made but no outcome is recorded here"
            assessment.evidence.extend(vote.phrases[:2])
        return assessment

    if proposal:
        assessment.status = RecordStatus.PROPOSED
        assessment.confidence = 0.55
        assessment.reason = "the passage reads as a proposal"
        assessment.evidence = [proposal]
        return assessment

    assessment.status = RecordStatus.INFORMATIONAL
    assessment.confidence = 0.4
    assessment.reason = "no decision, proposal or discussion language found"
    return assessment


def describe_for_context(assessment: StatusAssessment) -> str:
    """One line for the retrieved-records block, so the model is told, not left to infer."""
    if assessment.status == RecordStatus.ADOPTED and assessment.vote.vote_taken:
        tally = f" ({assessment.vote.tally})" if assessment.vote.tally else ""
        return f"RECORD STATUS: a vote was taken and it passed{tally}"
    if assessment.vote.outcome == "failed":
        return "RECORD STATUS: a vote was taken and the motion failed"
    if assessment.vote.outcome == "tabled":
        return "RECORD STATUS: the matter was tabled, continued or referred, not decided"
    if assessment.vote.outcome == "none":
        return "RECORD STATUS: the record states explicitly that no vote was taken"
    if assessment.status == RecordStatus.DISCUSSION:
        return ("RECORD STATUS: discussion. This passage does not record a vote. "
                "Do not describe it as a decision.")
    if assessment.status == RecordStatus.PROPOSED:
        return "RECORD STATUS: a proposal, not adopted policy"
    if assessment.status == RecordStatus.ADOPTED:
        return "RECORD STATUS: adopted text"
    return ""


if __name__ == "__main__":
    samples = [
        ("Several members expressed support for the redesign, and the board asked "
         "staff to return with cost figures. No motion was made.",
         {"source_type": "meeting_transcript"}),
        ("I move that we approve the site plan. Seconded. All those in favor? "
         "The motion carries 4-1.",
         {"source_type": "meeting_transcript"}),
        ("The motion failed for lack of a second.",
         {"source_type": "meeting_transcript"}),
        ("On a motion duly made and seconded, it was voted unanimously to adopt "
         "the amended budget.", {"source_type": "meeting_transcript"}),
        ("The article was tabled and continued to the May meeting.",
         {"source_type": "meeting_transcript"}),
        ("Article 8.4 permits accessory dwelling units by right in all "
         "residential districts.",
         {"source_type": "municipal_document", "document_type": "bylaw"}),
        ("Warrant Article 24-105 seeks to appropriate $5,000,000 for roof repair.",
         {"source_type": "municipal_document", "document_type": "warrant_article"}),
        ("The board discussed parking for about forty minutes.",
         {"source_type": "meeting_transcript"}),
    ]
    print(f"{'status':<16}{'conf':<7}{'vote':<9}{'tally':<12}passage")
    print("-" * 104)
    for text, meta in samples:
        a = classify_status(text, meta)
        vote = a.vote.outcome or ("-" if not a.vote.vote_taken else "passed")
        print(f"{a.status:<16}{a.confidence:<7.2f}{vote:<9}{a.vote.tally or '-':<12}"
              f"{text[:52]}")
    print()
    a = classify_status(samples[1][0], samples[1][1])
    print("context line:", describe_for_context(a))
    a = classify_status(samples[0][0], samples[0][1])
    print("context line:", describe_for_context(a))
