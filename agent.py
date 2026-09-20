"""
AI Agent

The community answer path: constitution + hybrid retrieval + citations +
provenance, per the community-owned AI guide.

This keeps the original ``CivicAgent`` interface — ``chat()``,
``search_knowledge()``, ``get_stats()``, ``build_system_prompt()`` — so the
existing API and frontend keep working, while the work behind ``chat()`` now
runs through :mod:`rag.pipeline`:

    question -> constitution -> query expansion -> hybrid dense + keyword search
             -> rerank -> generation -> citation check -> answer + provenance

The pieces are each independently replaceable. Swapping the foundation model
does not touch the constitution, the archive, the citations, or the evaluation
set, which is the property section 1 of the guide asks the architecture to have.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from community.constitution import Constitution, corpus_freshness, resolve_for_project
from models import ChatMessage, ProjectConfig
from providers import PROVIDER_LABELS, ProviderError, build_provider_for
from tools import build_registry
from rag.hybrid import HybridRetriever, RetrievalFilters
from rag.pipeline import CommunityPipeline, PromptBundle
from stores import build_store

SYSTEM_VERSION = os.getenv("COMMUNITY_AI_VERSION", "0.3")


class CivicAgent:
    """AI agent that answers questions from the community's public record."""

    def __init__(self, config: ProjectConfig, vector_store: Optional[Any] = None):
        self.config = config

        # Which archive this is, Qdrant or Postgres, is a configuration
        # decision made in stores/. Nothing below this line depends on it.
        self.vector_store = vector_store or build_store(config)

        # The constitution that governs this project. A file in source control
        # wins over an inline one; see community/constitution.py.
        self.constitution: Constitution = resolve_for_project(
            config, version=getattr(config, "constitution_version", "latest") or "latest"
        )

        self.retriever = HybridRetriever(
            self.vector_store,
            cache_key=config.project_id,
            # An all-keyword or all-dense corpus is rare; equal weighting is the
            # reasonable default and reciprocal rank fusion is insensitive to
            # small changes here.
            dense_weight=1.0,
            keyword_weight=1.0,
        )

        self.provider = build_provider_for(config)
        self.client_type = self.provider.name

        # Tools are opt-in per project. With them off, the assistant answers
        # only from the community's own archive, which is a legitimate choice
        # for a public-facing civic service rather than a missing feature.
        self.tools = build_registry(config, retriever=self.retriever)

        self.pipeline = CommunityPipeline(
            retriever=self.retriever,
            constitution=self.constitution,
            project_name=config.project_name,
            community=config.municipality_name,
            tone=config.tone,
            identity=config.system_prompt or None,
            top_k=getattr(config, "retrieval_top_k", 8),
            candidate_pool=getattr(config, "retrieval_candidate_pool", 24),
            model=config.model_name,
            provider=self.client_type,
            knowledge_updated=corpus_freshness(config.project_id),
            system_version=SYSTEM_VERSION,
            # Zero unless the community turned it on, which leaves every
            # existing project's retrieval exactly as it was.
            diversity=(getattr(config, "retrieval_diversity", 0.0)
                       if getattr(config, "enable_retrieval_diversity", False) else 0.0),
        )

    # --- compatibility ---------------------------------------------------

    def build_system_prompt(self) -> str:
        """The assembled system text, for callers that want to inspect it."""
        return "\n\n".join(
            [self.pipeline.identity, self.constitution.render_for_prompt(
                self.config.municipality_name)]
        )

    def search_knowledge(self, query: str, top_k: int = 8) -> List[Dict]:
        """Search the community corpus. Returns dicts, as before."""
        result = self.retriever.retrieve(
            query,
            top_k=top_k,
            use_reranker=getattr(self.config, "enable_reranking", True),
        )
        return [chunk.to_dict() for chunk in result.chunks]

    def format_context(self, search_results: List[Dict]) -> str:
        """Kept for compatibility with callers that build context themselves."""
        from rag.citations import build_context_block
        from knowledge.schemas import normalize_payload

        chunks = [normalize_payload(r.get("metadata", r)) for r in search_results]
        return build_context_block(chunks)

    # --- main path -------------------------------------------------------

    def _rewriter(self):
        """A query rewriter backed by the project's own model, or None.

        Section 18 puts a rewriter in front of retrieval. It costs one extra
        generation per question, which on a local server is real latency, so it
        is opt-in. With it off, ``rag.query`` still expands the question using
        the civic vocabulary map, which is free.
        """
        if not getattr(self.config, "enable_model_query_rewrite", False):
            return None

        def rewrite(instruction: str) -> str:
            return self.provider.raw_chat(
                [{"role": "user", "content": instruction}], max_tokens=120
            )

        return rewrite

    def chat(
        self,
        message: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        filters: Optional[RetrievalFilters] = None,
    ) -> Dict:
        """Answer one question with retrieval, citations, and provenance."""
        history: List[Dict[str, str]] = []
        for msg in (conversation_history or [])[-5:]:
            role = getattr(msg, "role", None) or (
                msg.get("role") if isinstance(msg, dict) else None)
            content = getattr(msg, "content", None) or (
                msg.get("content") if isinstance(msg, dict) else None)
            if role in ("user", "assistant") and content:
                history.append({"role": role, "content": content})

        def generate(prompt: PromptBundle) -> str:
            return self.provider.complete(prompt)

        try:
            result = self.pipeline.answer(
                message,
                generate=generate,
                filters=filters,
                history=history,
                rewriter=self._rewriter(),
                use_reranker=getattr(self.config, "enable_reranking", True),
                enforce_citations=getattr(self.config, "require_citations", True),
                expand=getattr(self.config, "enable_query_expansion", True),
                tool_registry=self.tools,
                provider=self.provider,
                max_tool_iterations=getattr(self.config, "max_tool_iterations", 4),
            )
        except ProviderError as exc:
            # A misconfigured or stopped local server is the most common failure
            # in this deployment, and the operator needs the remedy, not a trace.
            return {
                "answer": str(exc),
                "sources": [],
                "error": "provider_unavailable",
                "error_detail": str(exc),
                "provenance": {
                    "provider": self.client_type,
                    "model": self.config.model_name,
                    "constitution_version": self.constitution.version,
                },
            }

        if result.error:
            return {
                "answer": self._friendly_error(result.error),
                "sources": [],
                "error": result.error,
                "provenance": result.provenance.to_dict(),
            }

        show_sources = getattr(self.config, "enable_citations", True)
        return {
            "answer": result.answer,
            "sources": result.sources_payload() if show_sources else [],
            "context_used": len(result.citations) > 0,
            "provenance": result.provenance.to_dict(),
        }

    @staticmethod
    def _friendly_error(error: str) -> str:
        text = (error or "").lower()
        if "api_key" in text or "authentication" in text:
            return "API key is invalid or missing. Please check your API key in Settings."
        if "rate" in text and "limit" in text:
            return "Rate limit exceeded. Please wait a moment and try again."
        if "connection" in text or "refused" in text:
            return (
                "The model server is not reachable. If this project uses LM Studio, "
                "start its local server and load the configured model."
            )
        if "model" in text and "not found" in text:
            return "The configured model is not available. Choose another in Settings."
        return f"I apologize, but I encountered an error: {error}"

    # --- reporting -------------------------------------------------------

    def get_stats(self) -> Dict:
        vector_stats = self.vector_store.get_stats()
        return {
            "project_name": self.config.project_name,
            "municipality": self.config.municipality_name,
            "ai_provider": self.client_type,
            "provider_label": PROVIDER_LABELS.get(self.client_type, self.client_type),
            "model": self.config.model_name,
            "total_documents": vector_stats.get("total_documents", 0),
            "embedding_model": vector_stats.get("embedding_model"),
            "data_sources": len(self.config.data_sources),
            "active_sources": len([s for s in self.config.data_sources if s.enabled]),
            "constitution_version": self.constitution.version,
            "constitution_status": self.constitution.status,
            "constitution_hash": self.constitution.content_hash,
            "constitution_hash_short": self.constitution.short_hash,
            "constitution_ratified": self.constitution.ratified,
            "constitution_ledger_ok": self.constitution.ledger_verified,
            "constitution_principles": len(self.constitution.principles),
            "system_version": SYSTEM_VERSION,
            "knowledge_updated": corpus_freshness(self.config.project_id),
            "tools_enabled": self.tools.names(),
            "provider_supports_tools": self.provider.supports_tools,
            "local_inference": self.client_type in ("lmstudio", "ollama"),
        }

    def provider_health(self) -> Dict:
        return self.provider.health()

    def invalidate_corpus_cache(self) -> None:
        """Drop the keyword index after ingestion so new records are searchable."""
        self.retriever.invalidate()


# The agent was called NeighborhoodAgent before the project was named the Civic
# AI Engine. Anything already deployed or scripted against the old name keeps
# working; a rename is not a reason to break someone's integration.
NeighborhoodAgent = CivicAgent
