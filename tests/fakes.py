"""Test doubles that stand in for Qdrant and an LLM.

The retrieval pipeline is defined against two narrow interfaces so it can be
exercised without a vector database, an embedding model, or a GPU. These are
those interfaces, implemented over a list of dicts.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _overlap_score(query: str, text: str) -> float:
    """A crude stand-in for cosine similarity.

    Deliberately bag-of-words and case-insensitive, with punctuation stripped,
    so it behaves like a dense retriever in the way that matters for these
    tests: it finds topically similar passages and cannot tell "8.4" from "8.1".
    """
    def words(s: str) -> set:
        return set(re.findall(r"[a-z]+", s.lower()))

    q, t = words(query), words(text)
    if not q or not t:
        return 0.0
    return len(q & t) / (len(q) ** 0.5 * len(t) ** 0.5)


class FakeVectorStore:
    """Implements the surface HybridRetriever needs from VectorStore."""

    def __init__(self, payloads: List[Dict[str, Any]], collection_name: str = "test") -> None:
        self.payloads = payloads
        self.collection_name = collection_name
        self.search_calls: List[Tuple[str, int]] = []

    def iter_all_payloads(self) -> Iterable[Tuple[str, Dict[str, Any]]]:
        for i, payload in enumerate(self.payloads):
            yield f"doc-{i}", payload

    def search(self, query: str, top_k: int = 5,
               filter_dict: Optional[Dict] = None) -> List[Dict[str, Any]]:
        self.search_calls.append((query, top_k))
        scored = []
        for i, payload in enumerate(self.payloads):
            score = _overlap_score(query, payload.get("text", ""))
            if score > 0:
                scored.append((score, i, payload))
        scored.sort(key=lambda s: s[0], reverse=True)

        return [
            {
                "id": f"doc-{i}",
                "score": score,
                "text": payload.get("text", ""),
                "source": payload.get("source", ""),
                "source_type": payload.get("source_type", ""),
                "url": payload.get("url", ""),
                "title": payload.get("title", ""),
                "date": payload.get("date", ""),
                "metadata": payload,
            }
            for score, i, payload in scored[:top_k]
        ]

    def get_stats(self) -> Dict[str, Any]:
        return {"total_documents": len(self.payloads)}


class ScriptedModel:
    """A generator callable that returns canned answers.

    Records the prompt it was given so tests can assert on what the pipeline
    actually sent, which is the part that matters for constitution injection.
    """

    def __init__(self, reply: str = "No answer configured.") -> None:
        self.reply = reply
        self.prompts: List[Any] = []

    def __call__(self, prompt: Any) -> str:
        self.prompts.append(prompt)
        return self.reply
