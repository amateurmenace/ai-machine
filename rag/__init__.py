"""Retrieval-augmented generation for community records.

Hybrid dense + keyword retrieval, cross-encoder reranking, and citation
provenance, assembled by :mod:`rag.pipeline`.
"""

from rag.bm25 import BM25Index, reciprocal_rank_fusion, tokenize
from rag.citations import (
    Citation,
    CitationCheck,
    build_citations,
    build_context_block,
    citation_label,
    deep_link,
    embed_info,
    format_timestamp,
    strip_invalid_markers,
    verify_citations,
)
from rag.hybrid import (
    HybridRetriever,
    RetrievalFilters,
    RetrievalResult,
    RetrievedChunk,
    build_filters_from_dict,
)
from rag.reranker import rerank, rerank_status, select_context_window

__all__ = [
    "BM25Index",
    "reciprocal_rank_fusion",
    "tokenize",
    "Citation",
    "CitationCheck",
    "build_citations",
    "build_context_block",
    "citation_label",
    "deep_link",
    "embed_info",
    "format_timestamp",
    "strip_invalid_markers",
    "verify_citations",
    "HybridRetriever",
    "RetrievalFilters",
    "RetrievalResult",
    "RetrievedChunk",
    "build_filters_from_dict",
    "rerank",
    "rerank_status",
    "select_context_window",
]
