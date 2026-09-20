"""
Hybrid retrieval: dense + keyword, fused, filtered, reranked.

This implements the retrieval path in sections 5 and 18 of the guide:

    question
      ├── semantic / dense vector search
      └── keyword / sparse search
            combine candidates
                reranker
             best 8-15 chunks
                 model

Two things here are worth more than the ranking algebra:

1. **Metadata filters.** "What did the Planning Board decide in 2019" is a
   filter query wearing a search query's clothes. Filtering by board and date
   before ranking beats hoping the embedding noticed the year.

2. **Diagnostics.** Every retrieval returns what it searched, what it found, and
   what it dropped. Section 16 requires telling a retrieval failure apart from a
   generation failure, and that is only possible if retrieval says what it did.

The BM25 half indexes the corpus in memory. For a single community's archive
that is cheap; ``max_corpus_chunks`` caps it so a runaway ingestion cannot
exhaust the server's memory on a request path.

It is also the piece that pins the whole app to one instance, which is why a
store may offer to do the work itself. When ``vector_store`` provides
``hybrid_search``, both halves and their fusion run where the data lives, and
no corpus is walked or held in memory at all. :class:`stores.pgvector_store.PgVectorStore`
does; the embedded Qdrant store does not. Nothing above this module learns
which one answered, and a store that offers the method but fails on the day
falls back to the in-process path rather than failing the question.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from knowledge.schemas import CivicChunk, SourceType, normalize_payload
from rag.bm25 import BM25Index, reciprocal_rank_fusion
from rag.diversity import select_diverse
from rag.reranker import DEFAULT_RERANK_MODEL, rerank, rerank_status, select_context_window

# Rebuild the keyword index if the corpus changed or the index is older than
# this. Ingestion runs in a background task in the same process, so a request
# can otherwise sit on a stale index until restart.
CORPUS_CACHE_TTL_SECONDS = 600
MAX_CORPUS_CHUNKS = 200_000


@dataclass
class RetrievalFilters:
    """Structured filters over civic metadata.

    These map onto the filters the civic API exposes (section 13): date ranges,
    boards, document types, agenda items, speakers.
    """

    source_type: Optional[str] = None
    body: Optional[str] = None
    department: Optional[str] = None
    speaker: Optional[str] = None
    document_type: Optional[str] = None
    status: Optional[str] = None
    agenda_item: Optional[str] = None
    date_from: Optional[str] = None   # YYYY-MM-DD, inclusive
    date_to: Optional[str] = None     # YYYY-MM-DD, inclusive

    def is_empty(self) -> bool:
        return not any(
            getattr(self, f) for f in self.__dataclass_fields__  # type: ignore[attr-defined]
        )

    def matches(self, chunk: CivicChunk) -> bool:
        def same(actual: str, wanted: Optional[str]) -> bool:
            if not wanted:
                return True
            return actual.strip().lower() == wanted.strip().lower()

        def contains(actual: str, wanted: Optional[str]) -> bool:
            if not wanted:
                return True
            return wanted.strip().lower() in actual.strip().lower()

        if not same(chunk.source_type, self.source_type):
            return False
        if not same(chunk.body, self.body):
            return False
        if not same(chunk.department, self.department):
            return False
        if not same(chunk.document_type, self.document_type):
            return False
        if not same(chunk.status, self.status):
            return False
        if not contains(chunk.speaker, self.speaker):
            return False
        if not contains(chunk.agenda_item, self.agenda_item):
            return False

        record_date = chunk.record_date
        if self.date_from:
            # A record with no usable date cannot be shown to fall in the range,
            # so it is excluded rather than assumed to qualify.
            if not record_date or record_date < self.date_from:
                return False
        if self.date_to:
            if not record_date or record_date > self.date_to:
                return False
        return True

    def describe(self) -> Dict[str, str]:
        return {
            f: getattr(self, f)
            for f in self.__dataclass_fields__  # type: ignore[attr-defined]
            if getattr(self, f)
        }


@dataclass
class RetrievedChunk:
    """A chunk plus how it was found."""

    chunk: CivicChunk
    chunk_id: str
    dense_rank: Optional[int] = None
    dense_score: Optional[float] = None
    sparse_rank: Optional[int] = None
    sparse_score: Optional[float] = None
    fused_score: float = 0.0
    rerank_score: Optional[float] = None
    reranked: bool = False

    @property
    def retrieval_path(self) -> str:
        if self.dense_rank is not None and self.sparse_rank is not None:
            return "both"
        if self.dense_rank is not None:
            return "dense"
        if self.sparse_rank is not None:
            return "keyword"
        return "unknown"

    def to_dict(self) -> Dict[str, Any]:
        data = self.chunk.to_payload()
        data.update(
            {
                "id": self.chunk_id,
                "retrieval_path": self.retrieval_path,
                "dense_rank": self.dense_rank,
                "dense_score": self.dense_score,
                "sparse_rank": self.sparse_rank,
                "fused_score": round(self.fused_score, 6),
                "rerank_score": self.rerank_score,
            }
        )
        return data


@dataclass
class RetrievalResult:
    """Everything the pipeline and the transparency panel need."""

    query: str
    chunks: List[RetrievedChunk] = field(default_factory=list)
    candidates_considered: int = 0
    dense_hits: int = 0
    sparse_hits: int = 0
    filters: Dict[str, str] = field(default_factory=dict)
    reranked: bool = False
    rerank_model: Optional[str] = None
    diversity: float = 0.0
    corpus_size: int = 0
    elapsed_ms: float = 0.0
    notes: List[str] = field(default_factory=list)

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "corpus_size": self.corpus_size,
            "candidates_considered": self.candidates_considered,
            "dense_hits": self.dense_hits,
            "sparse_hits": self.sparse_hits,
            "passages_returned": len(self.chunks),
            "filters": self.filters,
            "reranked": self.reranked,
            "rerank_model": self.rerank_model,
            "diversity": self.diversity,
            "elapsed_ms": round(self.elapsed_ms, 1),
            "notes": self.notes,
        }


class _CorpusIndex:
    """A cached BM25 index over one project's corpus."""

    def __init__(self, chunks: List[CivicChunk], ids: List[str], fingerprint: str) -> None:
        self.chunks = chunks
        self.ids = ids
        self.fingerprint = fingerprint
        self.built_at = time.time()
        self.index = BM25Index.build([c.text for c in chunks])
        self.id_to_pos = {chunk_id: i for i, chunk_id in enumerate(ids)}

    def is_stale(self, fingerprint: str) -> bool:
        if fingerprint != self.fingerprint:
            return True
        return (time.time() - self.built_at) > CORPUS_CACHE_TTL_SECONDS


class HybridRetriever:
    """Combines dense vector search with keyword search over one corpus.

    ``vector_store`` must provide:
      * ``search(query, top_k, filter_dict=None) -> list[dict]``
      * ``iter_all_payloads() -> Iterable[tuple[str, dict]]``
      * ``get_stats() -> dict`` containing ``total_documents``

    ``VectorStore`` satisfies this. Tests pass a stand-in.

    It may also provide, and this one is preferred when present:
      * ``hybrid_search(query, query_vector, top_k, filters) -> list[dict]``

    ``PgVectorStore`` does. Each hit it returns carries ``dense_rank`` and
    ``sparse_rank`` so the transparency panel can still report how a passage
    was found.
    """

    _caches: Dict[str, _CorpusIndex] = {}
    _lock = threading.Lock()

    def __init__(
        self,
        vector_store: Any,
        cache_key: Optional[str] = None,
        dense_weight: float = 1.0,
        keyword_weight: float = 1.0,
        rerank_model: str = DEFAULT_RERANK_MODEL,
    ) -> None:
        self.vector_store = vector_store
        self.cache_key = cache_key or getattr(
            vector_store, "collection_name", "default"
        )
        self.dense_weight = dense_weight
        self.keyword_weight = keyword_weight
        self.rerank_model = rerank_model

    # --- corpus ----------------------------------------------------------

    def _fingerprint(self) -> str:
        try:
            stats = self.vector_store.get_stats()
            return f"{self.cache_key}:{stats.get('total_documents', 0)}"
        except Exception:
            return f"{self.cache_key}:unknown"

    def _get_corpus(self) -> Optional[_CorpusIndex]:
        fingerprint = self._fingerprint()
        with self._lock:
            cached = self._caches.get(self.cache_key)
            if cached is not None and not cached.is_stale(fingerprint):
                return cached

        chunks: List[CivicChunk] = []
        ids: List[str] = []
        try:
            for chunk_id, payload in self.vector_store.iter_all_payloads():
                chunk = normalize_payload(payload)
                if not chunk.text:
                    continue
                chunks.append(chunk)
                ids.append(str(chunk_id))
                if len(chunks) >= MAX_CORPUS_CHUNKS:
                    break
        except Exception:
            return None

        if not chunks:
            return None

        built = _CorpusIndex(chunks, ids, fingerprint)
        with self._lock:
            self._caches[self.cache_key] = built
        return built

    def invalidate(self) -> None:
        """Drop the cached keyword index. Call after ingestion."""
        with self._lock:
            self._caches.pop(self.cache_key, None)

    @classmethod
    def invalidate_all(cls) -> None:
        with cls._lock:
            cls._caches.clear()

    # --- candidates ------------------------------------------------------

    def _database_candidates(
        self,
        query: str,
        result: RetrievalResult,
        filters: RetrievalFilters,
        candidate_pool: int,
    ) -> Optional[List[RetrievedChunk]]:
        """Let the store run both halves and the fusion itself.

        Returns ``None`` when the store could not answer, which sends the
        caller back to the in-process path. A database that is briefly
        unreachable should cost a slower answer, not a failed one.
        """
        try:
            hits = self.vector_store.hybrid_search(
                query, None, candidate_pool, filters
            )
        except Exception as exc:
            result.notes.append(
                f"database hybrid search unavailable: {type(exc).__name__}"
            )
            return None

        candidates: List[RetrievedChunk] = []
        for hit in hits:
            payload = hit.get("metadata") or hit
            chunk = normalize_payload(payload)
            if not chunk.text:
                continue
            entry = RetrievedChunk(
                chunk=chunk,
                chunk_id=str(hit.get("id", chunk.chunk_id())),
                dense_rank=hit.get("dense_rank"),
                sparse_rank=hit.get("sparse_rank"),
                fused_score=float(hit.get("score") or 0.0),
            )
            candidates.append(entry)

        result.dense_hits = sum(1 for c in candidates if c.dense_rank is not None)
        result.sparse_hits = sum(1 for c in candidates if c.sparse_rank is not None)
        # No corpus was walked, so the size has to be asked for rather than
        # counted. The transparency panel reports it either way.
        try:
            result.corpus_size = int(
                self.vector_store.get_stats().get("total_documents", 0)
            )
        except Exception:
            result.corpus_size = 0
        result.notes.append("hybrid search ran in the database")
        return candidates

    def _fused_candidates(
        self,
        query: str,
        result: RetrievalResult,
        filters: RetrievalFilters,
        candidate_pool: int,
    ) -> Tuple[Dict[str, RetrievedChunk], List[RetrievedChunk]]:
        """Dense search from the store, keyword search from the in-memory index."""
        corpus = self._get_corpus()
        result.corpus_size = len(corpus.chunks) if corpus else 0

        by_id: Dict[str, RetrievedChunk] = {}
        dense_order: List[str] = []
        sparse_order: List[str] = []

        # --- dense half ---
        # Over-fetch when filtering, since filters are applied after the vector
        # search and would otherwise leave too few survivors.
        dense_k = candidate_pool * (3 if not filters.is_empty() else 1)
        try:
            dense_hits = self.vector_store.search(query, top_k=dense_k)
        except Exception as exc:
            dense_hits = []
            result.notes.append(f"dense search unavailable: {type(exc).__name__}")

        for rank, hit in enumerate(dense_hits, start=1):
            payload = hit.get("metadata") or hit
            chunk = normalize_payload(payload)
            if not chunk.text or not filters.matches(chunk):
                continue
            chunk_id = str(hit.get("id", chunk.chunk_id()))
            entry = by_id.get(chunk_id)
            if entry is None:
                entry = RetrievedChunk(chunk=chunk, chunk_id=chunk_id)
                by_id[chunk_id] = entry
            entry.dense_rank = rank
            score = hit.get("score")
            entry.dense_score = float(score) if score is not None else None
            dense_order.append(chunk_id)
            if len(dense_order) >= candidate_pool:
                break

        result.dense_hits = len(dense_order)

        # --- keyword half ---
        if corpus is not None:
            allowed: Optional[Iterable[int]] = None
            if not filters.is_empty():
                allowed = [
                    i for i, chunk in enumerate(corpus.chunks) if filters.matches(chunk)
                ]
                if not allowed:
                    result.notes.append("no chunks matched the metadata filters")

            sparse_hits = corpus.index.search(query, top_k=candidate_pool, allowed=allowed)
            for rank, (doc_idx, score) in enumerate(sparse_hits, start=1):
                chunk = corpus.chunks[doc_idx]
                chunk_id = corpus.ids[doc_idx]
                entry = by_id.get(chunk_id)
                if entry is None:
                    entry = RetrievedChunk(chunk=chunk, chunk_id=chunk_id)
                    by_id[chunk_id] = entry
                entry.sparse_rank = rank
                entry.sparse_score = float(score)
                sparse_order.append(chunk_id)
        else:
            result.notes.append("keyword index unavailable; dense search only")

        result.sparse_hits = len(sparse_order)

        if not by_id:
            return {}, []

        # --- fuse ---
        fused = reciprocal_rank_fusion(
            [dense_order, sparse_order],
            weights=[self.dense_weight, self.keyword_weight],
        )
        for chunk_id, score in fused:
            if chunk_id in by_id:
                by_id[chunk_id].fused_score = score

        return by_id, [by_id[cid] for cid, _ in fused if cid in by_id]

    # --- retrieval -------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: int = 8,
        filters: Optional[RetrievalFilters] = None,
        candidate_pool: int = 24,
        use_reranker: bool = True,
        adaptive_window: bool = True,
        diversity: float = 0.0,
    ) -> RetrievalResult:
        started = time.perf_counter()
        filters = filters or RetrievalFilters()
        result = RetrievalResult(query=query, filters=filters.describe())

        # A store that can fuse both halves itself is preferred: it needs no
        # in-memory keyword index, which is what keeps this app on one instance.
        candidates: Optional[List[RetrievedChunk]] = None
        by_id: Dict[str, RetrievedChunk] = {}
        if hasattr(self.vector_store, "hybrid_search"):
            candidates = self._database_candidates(
                query, result, filters, candidate_pool
            )
            if candidates is not None:
                by_id = {c.chunk_id: c for c in candidates}

        if candidates is None:
            by_id, candidates = self._fused_candidates(
                query, result, filters, candidate_pool
            )

        if not by_id:
            result.elapsed_ms = (time.perf_counter() - started) * 1000
            return result

        result.candidates_considered = len(candidates)

        # --- rerank ---
        if use_reranker and candidates:
            payloads = [
                {"text": c.chunk.text, "_id": c.chunk_id} for c in candidates[:candidate_pool]
            ]
            ranked = rerank(
                query, payloads, top_k=len(payloads), model_name=self.rerank_model
            )
            order: List[RetrievedChunk] = []
            for item in ranked:
                entry = by_id.get(item["_id"])
                if entry is None:
                    continue
                if item.get("reranked"):
                    entry.rerank_score = item.get("rerank_score")
                    entry.reranked = True
                order.append(entry)
            candidates = order
            status = rerank_status(self.rerank_model)
            result.reranked = bool(status["enabled"])
            result.rerank_model = status["model"]
            if not status["enabled"]:
                result.notes.append(f"reranker inactive ({status['reason']})")

        # --- select the context window ---
        if diversity > 0 and candidates:
            # Opt-in, and it replaces the adaptive window rather than following
            # it: that window keeps only passages scoring near the best one,
            # which is precisely how the dissenting passage gets dropped. See
            # rag/diversity.py for why this matters on conflicting evidence.
            result.chunks = select_diverse(candidates, top_k=top_k, diversity=diversity)
            result.diversity = float(diversity)
            result.notes.append(
                f"diversity pass at {diversity:.2f}; passages chosen for "
                f"difference as well as relevance"
            )
        elif adaptive_window and result.reranked:
            chosen_dicts = select_context_window(
                [
                    {"text": c.chunk.text, "rerank_score": c.rerank_score, "_id": c.chunk_id}
                    for c in candidates
                ],
                min_passages=min(5, top_k),
                max_passages=top_k,
            )
            chosen_ids = [d["_id"] for d in chosen_dicts]
            result.chunks = [by_id[cid] for cid in chosen_ids if cid in by_id]
        else:
            result.chunks = candidates[:top_k]

        result.elapsed_ms = (time.perf_counter() - started) * 1000
        return result


def build_filters_from_dict(raw: Optional[Dict[str, Any]]) -> RetrievalFilters:
    """Build filters from an API request body, ignoring unknown keys."""
    if not raw:
        return RetrievalFilters()
    known = RetrievalFilters.__dataclass_fields__  # type: ignore[attr-defined]
    return RetrievalFilters(
        **{k: v for k, v in raw.items() if k in known and v not in (None, "")}
    )
