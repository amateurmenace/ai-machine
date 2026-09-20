"""
Keyword retrieval for municipal text.

Section 5 of the guide is blunt about this: do not rely on vector embeddings
alone. Municipal information is full of addresses, article numbers, legal
citations, acronyms, docket numbers, project names, and exact phrases. A dense
retriever asked for "Article 8.4" happily returns Article 8.1, because the two
are semantically almost identical and lexically distinct in exactly the way that
matters.

This is a self-contained Okapi BM25 implementation with a tokenizer built for
civic text. It has no third-party dependencies on purpose: keyword search is the
half of retrieval that has to keep working when the embedding model or the GPU
is unavailable.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Dict, Iterable, List, Sequence, Tuple

# Tokens worth preserving whole because splitting them destroys the match:
#   8.4        zoning article
#   fy2027     fiscal year
#   2026-04-14 dates
#   24-105     docket / case numbers
#   §8.4       section marks
#   401k, 40b  statute shorthand ("Chapter 40B" is a term of art in Massachusetts)
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.\-/][a-z0-9]+)*")

# Deliberately small. BM25's IDF already discounts common words, and an
# aggressive stoplist removes terms that carry real meaning in civic questions
# ("no" in "no vote", "not" in "not adopted").
_STOPWORDS = frozenset(
    """a an the of to in for on at by with from as is are was were be been being
    and or but if then than that this these those it its""".split()
)


def tokenize(text: str) -> List[str]:
    """Tokenize for civic keyword matching.

    Compound identifiers are emitted whole *and* split, so "article 8.4" matches
    a document that writes "Article 8.4" and one that writes "Article 8, Section
    4", without the compound form drowning out either.
    """
    tokens: List[str] = []
    for raw in _TOKEN_RE.findall(text.lower()):
        if raw in _STOPWORDS:
            continue
        tokens.append(raw)
        if any(sep in raw for sep in ".-/"):
            for part in re.split(r"[.\-/]", raw):
                if part and part not in _STOPWORDS:
                    tokens.append(part)
    return tokens


class BM25Index:
    """An in-memory BM25 index over a fixed list of documents.

    Built once per project corpus and reused. ``k1`` controls term-frequency
    saturation, ``b`` controls length normalization; the defaults are the usual
    Okapi values and are fine for passage-length civic text.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.doc_count = 0
        self.avg_len = 0.0
        self.doc_lengths: List[int] = []
        # term -> list of (doc index, term frequency)
        self.postings: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
        self._idf: Dict[str, float] = {}

    @classmethod
    def build(cls, documents: Sequence[str], k1: float = 1.5, b: float = 0.75) -> "BM25Index":
        index = cls(k1=k1, b=b)
        index._index_all(documents)
        return index

    def _index_all(self, documents: Sequence[str]) -> None:
        total_len = 0
        for doc_idx, text in enumerate(documents):
            tokens = tokenize(text)
            self.doc_lengths.append(len(tokens))
            total_len += len(tokens)

            freqs: Dict[str, int] = defaultdict(int)
            for token in tokens:
                freqs[token] += 1
            for token, freq in freqs.items():
                self.postings[token].append((doc_idx, freq))

        self.doc_count = len(documents)
        self.avg_len = (total_len / self.doc_count) if self.doc_count else 0.0
        self._compute_idf()

    def _compute_idf(self) -> None:
        # Robertson/Sparck-Jones IDF with the +0.5 smoothing, floored at a small
        # positive value so a term appearing in most documents contributes a
        # little rather than pushing scores negative.
        self._idf = {}
        for term, posting in self.postings.items():
            df = len(posting)
            value = math.log((self.doc_count - df + 0.5) / (df + 0.5) + 1.0)
            self._idf[term] = max(value, 1e-6)

    def search(self, query: str, top_k: int = 50,
               allowed: Iterable[int] | None = None) -> List[Tuple[int, float]]:
        """Score documents against a query.

        ``allowed`` restricts scoring to a set of document indices, which is how
        metadata filters (board, date range, source type) are applied without
        rebuilding the index.
        """
        if not self.doc_count:
            return []

        allowed_set = set(allowed) if allowed is not None else None
        scores: Dict[int, float] = defaultdict(float)

        query_terms = tokenize(query)
        if not query_terms:
            return []

        # A term repeated in the query should not be counted twice.
        for term in set(query_terms):
            posting = self.postings.get(term)
            if not posting:
                continue
            idf = self._idf.get(term, 0.0)
            for doc_idx, freq in posting:
                if allowed_set is not None and doc_idx not in allowed_set:
                    continue
                doc_len = self.doc_lengths[doc_idx]
                norm = 1.0 - self.b + self.b * (doc_len / self.avg_len if self.avg_len else 1.0)
                scores[doc_idx] += idf * (freq * (self.k1 + 1.0)) / (freq + self.k1 * norm)

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:top_k]


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]],
    weights: Sequence[float] | None = None,
    k: int = 60,
) -> List[Tuple[str, float]]:
    """Combine ranked id lists into one ranking.

    Reciprocal rank fusion is used rather than score normalization because the
    two retrievers produce incomparable numbers: cosine similarity sits in a
    narrow band near 1.0 while BM25 is unbounded and corpus-dependent. Fusing on
    rank sidesteps the calibration problem entirely, which matters here because
    every community's corpus has a different score distribution.

    ``k`` damps the contribution of top ranks; 60 is the value from the original
    RRF paper and is not sensitive enough to be worth tuning per community.
    """
    if weights is None:
        weights = [1.0] * len(rankings)

    fused: Dict[str, float] = defaultdict(float)
    for ranking, weight in zip(rankings, weights):
        for rank, doc_id in enumerate(ranking, start=1):
            fused[doc_id] += weight / (k + rank)

    return sorted(fused.items(), key=lambda kv: kv[1], reverse=True)


if __name__ == "__main__":
    docs = [
        "Article 8.4 of the zoning bylaw governs accessory dwelling units.",
        "Article 8.1 of the zoning bylaw governs signage in business districts.",
        "The Select Board discussed the Washington Street redesign at length.",
        "Warrant Article 24-105 appropriates $4.2M for school roof repair.",
    ]
    index = BM25Index.build(docs)
    for query in ["Article 8.4", "warrant article 24-105", "zoning bylaw"]:
        hits = index.search(query, top_k=2)
        print(f"{query!r}")
        for doc_idx, score in hits:
            print(f"   {score:6.3f}  {docs[doc_idx][:60]}")
    print()
    print("RRF:", reciprocal_rank_fusion([["a", "b", "c"], ["c", "a", "d"]])[:3])
