"""
Cross-encoder reranking.

Fusion produces a candidate pool cheaply; reranking decides what actually
reaches the model. A bi-encoder scores the question and the passage separately
and compares vectors, so it cannot notice that a passage is about the right
topic but the wrong year. A cross-encoder reads the pair together and can.

The guide's flow (section 5) is: ~20 candidates in, 8-15 passages out.

The model is optional. On a community server with no GPU, no internet, or no
model cache, the reranker degrades to the fusion order rather than failing the
request. That is a deliberate choice: a slightly worse ranking is recoverable,
a 500 on a resident's question is not.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Dict, List, Optional, Sequence

DEFAULT_RERANK_MODEL = os.getenv(
    "COMMUNITY_RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
)

_model_cache: Dict[str, Any] = {}
_model_lock = threading.Lock()
_load_failed: Dict[str, str] = {}


def _load_model(model_name: str):
    """Load and cache a CrossEncoder, remembering failure so we try once."""
    with _model_lock:
        if model_name in _model_cache:
            return _model_cache[model_name]
        if model_name in _load_failed:
            return None

        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            _load_failed[model_name] = f"sentence-transformers not installed: {exc}"
            return None

        try:
            model = CrossEncoder(model_name, max_length=512)
        except Exception as exc:  # network, disk, or unsupported hardware
            _load_failed[model_name] = f"{type(exc).__name__}: {exc}"
            return None

        _model_cache[model_name] = model
        return model


def rerank_available(model_name: str = DEFAULT_RERANK_MODEL) -> bool:
    return _load_model(model_name) is not None


def rerank_status(model_name: str = DEFAULT_RERANK_MODEL) -> Dict[str, Any]:
    """Report whether reranking is active, for the transparency panel."""
    available = rerank_available(model_name)
    return {
        "enabled": available,
        "model": model_name if available else None,
        "reason": None if available else _load_failed.get(model_name, "not attempted"),
    }


def rerank(
    query: str,
    candidates: Sequence[Dict[str, Any]],
    top_k: int = 8,
    model_name: str = DEFAULT_RERANK_MODEL,
    text_key: str = "text",
    score_key: str = "rerank_score",
) -> List[Dict[str, Any]]:
    """Reorder candidates by cross-encoder relevance.

    Returns the top ``top_k`` candidates. Each returned dict is annotated with
    ``rerank_score`` when a model ran, and ``reranked=False`` when it did not,
    so the caller can report honestly what produced the ordering.
    """
    if not candidates:
        return []

    keep = min(top_k, len(candidates))
    model = _load_model(model_name)
    if model is None:
        fallback = [dict(c) for c in candidates[:keep]]
        for item in fallback:
            item["reranked"] = False
        return fallback

    pairs = [(query, str(c.get(text_key, ""))) for c in candidates]
    try:
        scores = model.predict(pairs)
    except Exception:
        # A runtime failure mid-request gets the same treatment as a missing
        # model: return the fusion order rather than dropping the answer.
        fallback = [dict(c) for c in candidates[:keep]]
        for item in fallback:
            item["reranked"] = False
        return fallback

    scored = []
    for candidate, score in zip(candidates, scores):
        item = dict(candidate)
        item[score_key] = float(score)
        item["reranked"] = True
        scored.append(item)

    scored.sort(key=lambda c: c[score_key], reverse=True)
    return scored[:keep]


def select_context_window(
    ranked: Sequence[Dict[str, Any]],
    min_passages: int = 5,
    max_passages: int = 15,
    max_words: int = 4000,
    score_key: str = "rerank_score",
    relative_floor: float = 0.35,
) -> List[Dict[str, Any]]:
    """Choose how many of the ranked passages to actually send.

    A fixed top-k sends eight passages whether eight are relevant or one is.
    This keeps every passage above ``min_passages``, then continues only while
    passages stay within ``relative_floor`` of the best score, and stops at a
    word budget. Fewer, better passages reduce the chance the model answers from
    a passage that merely mentions the right street name.
    """
    if not ranked:
        return []

    selected: List[Dict[str, Any]] = []
    words = 0
    top_score = ranked[0].get(score_key)

    for i, item in enumerate(ranked):
        if i >= max_passages:
            break

        if i >= min_passages and top_score is not None:
            score = item.get(score_key)
            if score is not None and top_score > 0 and score < top_score * relative_floor:
                break

        item_words = len(str(item.get("text", "")).split())
        if words + item_words > max_words and selected:
            break

        selected.append(item)
        words += item_words

    return selected


if __name__ == "__main__":
    print("rerank status:", rerank_status())
    fake = [
        {"text": "The Select Board voted 4-1 to approve the redesign.", "id": "a"},
        {"text": "Trash collection moves to Tuesday during holiday weeks.", "id": "b"},
        {"text": "The redesign was discussed but no vote was taken.", "id": "c"},
    ]
    out = rerank("Did the Select Board approve the redesign?", fake, top_k=2)
    for item in out:
        print(f"  reranked={item.get('reranked')} {item['id']}: {item['text'][:50]}")
    print("window:", len(select_context_window(out)))
