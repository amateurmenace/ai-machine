"""
Retrieval diversity, for the questions where the record disagrees with itself.

A reranker is trained to put the passage most similar to the question first.
Run it over a civic archive and the top three results are very often the same
claim three times: three speakers agreeing in one meeting, a draft and the
adopted text of one bylaw, a press release and the page that quotes it. For an
ordinary factual question that is fine and even desirable.

For the `conflicting_evidence` category it is exactly wrong. Principle 17 asks
the assistant to surface a disagreement rather than pick a winner, and it cannot
surface what retrieval never fetched. The dissenting passage loses the ranking
precisely because it is the odd one out, which is the property that makes it
worth reading.

This is Maximal Marginal Relevance: after the first passage, a candidate is
scored on how relevant it is *minus* how much it repeats what has already been
selected. The ``diversity`` dial sets the trade. It is off by default, because
on a question with one right answer, spending a slot on a different passage buys
difference at the cost of accuracy.

Two choices are deliberate.

**Similarity is lexical, not embedded.** It reuses the civic tokenizer from
``rag.bm25`` and compares token sets. A cosine over embeddings would be a better
similarity measure, but it would need the embedding model at selection time, and
``rag.reranker`` already degrades to the fusion order when no model can be
loaded. A diversity pass that needs a model is unavailable in exactly the
situation where ranking is already degraded and the diversity would help most.
This adds no dependency and cannot fail.

**Provenance counts, not just wording.** Lexical difference alone is a poor
proxy for disagreement in municipal text, because two passages that contradict
each other about the same project share most of their vocabulary. What actually
predicts a second side in a civic archive is where the passage came from: a
different board, a different date, a different document status, a different
document. The 2019 Planning Board approval and the 2026 Select Board discussion
of the same corner are the conflict; two speaker turns from one meeting are
usually one voice. So provenance difference is weighted explicitly rather than
left for the wording to imply.
"""

from __future__ import annotations

from typing import Any, List, Optional, Sequence

from rag.bm25 import tokenize

# How much of the similarity judgment comes from provenance rather than wording.
# High enough that two passages from one meeting are treated as near-duplicates
# even when they use different words, low enough that two unrelated documents
# are not called similar merely because both lack metadata.
DEFAULT_PROVENANCE_WEIGHT = 0.4

# Values that are present in the schema but say nothing. Comparing two records
# that both record status "unknown" and concluding they have the same status
# would manufacture agreement out of missing data.
_UNINFORMATIVE = frozenset({"", "unknown", "none", "n/a"})


def _informative(value: Any) -> str:
    text = str(value or "").strip().lower()
    return "" if text in _UNINFORMATIVE else text


def lexical_similarity(left: str, right: str) -> float:
    """Jaccard overlap of civic tokens, in 0.0 to 1.0.

    The same tokenizer the keyword index uses, so "Article 8.4" and "Article
    8.1" are correctly seen as different passages rather than the same one.
    """
    a, b = set(tokenize(left or "")), set(tokenize(right or ""))
    if not a or not b:
        return 0.0
    union = len(a | b)
    return (len(a & b) / union) if union else 0.0


def provenance_similarity(left: Any, right: Any) -> Optional[float]:
    """How much two chunks share an origin, or None when nothing is comparable.

    Returns the fraction of the populated provenance fields that match. None
    means neither chunk carries enough metadata to judge, which is common in a
    corpus ingested before the metadata schema existed; the caller then falls
    back to wording alone rather than inventing a number.
    """
    pairs = [
        # Which board or department produced it. Two boards disagreeing is the
        # commonest shape of civic conflicting evidence.
        (_informative(getattr(left, "body", "") or getattr(left, "department", "")),
         _informative(getattr(right, "body", "") or getattr(right, "department", ""))),
        # When. A 2019 decision and a 2026 discussion are different evidence
        # even when they use identical language.
        (_informative(getattr(left, "record_date", "")),
         _informative(getattr(right, "record_date", ""))),
        # Discussion, proposed, or adopted. Principle 4 lives here: the whole
        # point is to show the talk next to the vote, not one of them twice.
        (_informative(getattr(left, "status", "")),
         _informative(getattr(right, "status", ""))),
        # Which document or recording. Two chunks of one PDF rarely dissent.
        (_informative(getattr(left, "url", "") or getattr(left, "source", "")
                      or getattr(left, "title", "")),
         _informative(getattr(right, "url", "") or getattr(right, "source", "")
                      or getattr(right, "title", ""))),
    ]
    comparable = [(a, b) for a, b in pairs if a and b]
    if not comparable:
        return None
    return sum(1.0 for a, b in comparable if a == b) / len(comparable)


def passage_similarity(left: Any, right: Any,
                       provenance_weight: float = DEFAULT_PROVENANCE_WEIGHT) -> float:
    """Redundancy between two chunks: wording, weighted with shared origin."""
    lexical = lexical_similarity(getattr(left, "text", ""), getattr(right, "text", ""))
    shared_origin = provenance_similarity(left, right)
    if shared_origin is None:
        return lexical
    weight = max(0.0, min(1.0, float(provenance_weight)))
    return (1.0 - weight) * lexical + weight * shared_origin


def _relevance_by_rank(count: int) -> List[float]:
    """Relevance as position in the incoming ranking, on a 0.0 to 1.0 scale.

    The scores themselves are deliberately not used. ``rag.bm25`` fuses on rank
    rather than score because a cross-encoder logit and a fusion weight are
    incomparable numbers whose distribution differs per corpus, and the same
    argument applies with more force here: one side of the MMR subtraction is a
    similarity bounded in 0.0 to 1.0, so pitting a raw logit against it would
    make one setting of the dial behave differently in every community. Rank is
    the calibration-free quantity both retrievers already agree on.
    """
    if count <= 0:
        return []
    return [1.0 - (i / count) for i in range(count)]


def select_diverse(
    candidates: Sequence[Any],
    top_k: int = 8,
    diversity: float = 0.0,
    provenance_weight: float = DEFAULT_PROVENANCE_WEIGHT,
) -> List[Any]:
    """Pick ``top_k`` passages, trading relevance against repetition.

    ``candidates`` are anything carrying a ``chunk``, already in relevance
    order: ``RetrievedChunk`` from :mod:`rag.hybrid` is the caller that matters.
    ``diversity`` runs from 0.0 (pure relevance, the ranking is returned
    untouched) to 1.0 (pure difference).

    The most relevant passage is always selected first. Diversity decides what
    joins it, never what displaces it, so turning this on cannot cost a question
    its best answer.
    """
    ordered = list(candidates)
    if diversity <= 0 or len(ordered) <= 1 or top_k <= 0:
        return ordered[:top_k]

    weight = max(0.0, min(1.0, float(diversity)))
    relevance = _relevance_by_rank(len(ordered))
    chunks = [getattr(item, "chunk", item) for item in ordered]

    selected = [0]
    remaining = list(range(1, len(ordered)))

    while remaining and len(selected) < top_k:
        best_index: Optional[int] = None
        best_score = float("-inf")
        for index in remaining:
            redundancy = max(
                passage_similarity(chunks[index], chunks[chosen], provenance_weight)
                for chosen in selected
            )
            score = (1.0 - weight) * relevance[index] - weight * redundancy
            if score > best_score:
                best_index, best_score = index, score
        if best_index is None:          # unreachable in practice; never loop forever
            break
        selected.append(best_index)
        remaining.remove(best_index)

    return [ordered[i] for i in selected]


if __name__ == "__main__":
    from knowledge.schemas import CivicChunk

    passages = [
        CivicChunk(text="Members spoke in favor of the Coolidge Corner redesign.",
                   body="Select Board", meeting_date="2026-05-12", status="discussion",
                   url="https://example.org/sb-may"),
        CivicChunk(text="Members spoke in support of the Coolidge Corner redesign plan.",
                   body="Select Board", meeting_date="2026-05-12", status="discussion",
                   url="https://example.org/sb-may"),
        CivicChunk(text="The Transportation Board rejected the Coolidge Corner "
                        "redesign as unsafe for cyclists.",
                   body="Transportation Board", meeting_date="2026-06-03",
                   status="adopted", url="https://example.org/tb-june"),
    ]
    items = [type("Item", (), {"chunk": chunk})() for chunk in passages]
    for label, dial in (("relevance only", 0.0), ("diverse", 0.5)):
        picked = select_diverse(items, top_k=2, diversity=dial)
        print(f"{label}: " + " | ".join(p.chunk.text[:38] for p in picked))
