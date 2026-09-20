"""
The community answer pipeline.

This is the end-to-end flow from section 18 of the guide, in one place:

    question -> constitution -> query rewrite -> hybrid retrieval
             -> rerank -> generation -> citation check -> answer

The pipeline does not know how to talk to a model. Generation is injected as a
callable, so the same pipeline serves the existing chat endpoint, the
OpenAI-compatible gateway, and the offline evaluation runner without any of
them importing each other.

The output carries a full provenance record. Section 14 asks for a "Why did you
answer this way?" control that shows sources retrieved, sources used, corpus
freshness, model version, and constitution version, without exposing hidden
reasoning. :class:`AnswerProvenance` is exactly that payload.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from community.constitution import Constitution
from rag.citations import (
    Citation,
    CitationCheck,
    build_citations,
    build_context_block,
    strip_invalid_markers,
    verify_citations,
)
from rag.hybrid import HybridRetriever, RetrievalFilters, RetrievalResult
from rag.query import PreparedQuery, prepare_query

# A generator takes the assembled prompt and returns the answer text.
Generator = Callable[["PromptBundle"], str]


@dataclass
class PromptBundle:
    """The assembled request, in a provider-neutral shape.

    Section 8 of the guide injects the constitution as its own system message so
    that amending the constitution changes behavior on the next request. That
    layering is preserved here and flattened only at the provider boundary,
    because some APIs accept many system messages and some accept one.
    """

    identity: str
    constitution_text: str
    context_block: str
    question: str
    history: List[Dict[str, str]] = field(default_factory=list)
    tool_instructions: str = ""

    def system_blocks(self) -> List[str]:
        return [
            b for b in (self.identity, self.constitution_text, self.context_block,
                        self.tool_instructions)
            if b
        ]

    def as_openai_messages(self) -> List[Dict[str, str]]:
        """Multiple system messages, which OpenAI-compatible APIs accept."""
        messages = [{"role": "system", "content": block} for block in self.system_blocks()]
        messages.extend(self.history)
        messages.append({"role": "user", "content": self.question})
        return messages

    def as_anthropic_messages(self) -> Tuple[str, List[Dict[str, str]]]:
        """One system string plus the turn list, which the Messages API wants."""
        system = "\n\n".join(self.system_blocks())
        messages = list(self.history)
        messages.append({"role": "user", "content": self.question})
        return system, messages

    def approx_tokens(self) -> int:
        """Rough size estimate for budgeting, at ~4 characters per token."""
        total = sum(len(b) for b in self.system_blocks())
        total += sum(len(m.get("content", "")) for m in self.history)
        total += len(self.question)
        return total // 4


@dataclass
class AnswerProvenance:
    """Operational facts about how an answer was produced.

    Deliberately excludes any hidden chain-of-thought. Section 14 is explicit
    that the transparency control shows what the system did, not what the model
    was thinking.
    """

    sources_retrieved: int = 0
    sources_used: int = 0
    corpus_size: int = 0
    knowledge_updated: Optional[str] = None
    constitution_version: str = "none"
    constitution_status: str = "unknown"
    # The hash is the binding claim. A version string can stay "1.0" while the
    # text changes; a hash cannot. This is what makes "these rules produced this
    # answer" checkable a year later.
    constitution_hash: str = ""
    constitution_ratified: bool = False
    constitution_ledger_ok: Optional[bool] = None
    model: str = ""
    provider: str = ""
    system_version: str = "0.1"
    retrieval: Dict[str, Any] = field(default_factory=dict)
    query: Dict[str, Any] = field(default_factory=dict)
    citation_check: Dict[str, Any] = field(default_factory=dict)
    # What the assistant did beyond the first retrieval: searched the web, read
    # a page, searched the archive again. Section 14 asks the transparency panel
    # to name "relevant tools invoked", and a resident deserves to know when an
    # answer left the community's own records.
    tools: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CommunityAnswer:
    """The full result of one question."""

    answer: str
    citations: List[Citation] = field(default_factory=list)
    provenance: AnswerProvenance = field(default_factory=AnswerProvenance)
    prompt: Optional[PromptBundle] = None
    retrieval: Optional[RetrievalResult] = None
    error: Optional[str] = None

    def sources_payload(self, used_only: bool = False) -> List[Dict[str, Any]]:
        """Citations in the shape the chat UI and API return."""
        items = [c for c in self.citations if c.used] if used_only else list(self.citations)
        return [c.to_dict() for c in items]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "sources": self.sources_payload(),
            "provenance": self.provenance.to_dict(),
            "error": self.error,
        }


DEFAULT_IDENTITY_TEMPLATE = """You are {project_name}, the community AI assistant for {community}.

You serve residents, community organizations, journalists, students, educators, and municipal staff. You answer questions about the community's public record, and you are also a capable general-purpose assistant for ordinary writing, analysis, and research.

Tone: {tone}.

How to answer questions about this community:
- Ground factual claims about the community in the retrieved passages, and cite them by number.
- Say plainly when the retrieved records do not answer the question. Missing evidence is an answer; a plausible guess is not.
- Distinguish what was discussed from what was proposed, voted on, adopted, and implemented.
- Name who said something when it matters, and whether they were a resident, an official, or a document.
- Give dates when they change the meaning of the answer.

For general questions with no community dimension, answer normally and helpfully. You do not need to cite community records for a question about Python, algebra, or a cover letter."""


def _anthropic_messages(prompt: "PromptBundle") -> List[Dict[str, Any]]:
    """Flatten a prompt for a provider that wants one system string."""
    system, turns = prompt.as_anthropic_messages()
    return [{"role": "system", "content": system}] + list(turns)


def _tool_citations(tool_citations: Sequence[Any], offset: int) -> List[Citation]:
    """Turn sources a tool produced into numbered citations."""
    out: List[Citation] = []
    for i, tc in enumerate(tool_citations, start=offset + 1):
        out.append(Citation(
            number=i,
            chunk_id=f"tool:{i}",
            label=tc.title or tc.url,
            url=tc.url,
            source_type=tc.kind,
            title=tc.title or tc.url,
            date=tc.retrieved_at,
            attribution=("retrieved from the web during this answer"
                         if tc.kind in ("web", "page") else ""),
            excerpt=tc.snippet,
        ))
    return out


class CommunityPipeline:
    """Runs one question end to end."""

    def __init__(
        self,
        retriever: HybridRetriever,
        constitution: Constitution,
        project_name: str = "Community AI",
        community: str = "this community",
        tone: str = "clear, plain, and civic-minded",
        identity: Optional[str] = None,
        top_k: int = 8,
        candidate_pool: int = 24,
        model: str = "",
        provider: str = "",
        knowledge_updated: Optional[str] = None,
        system_version: str = "0.1",
        diversity: float = 0.0,
    ) -> None:
        self.retriever = retriever
        self.constitution = constitution
        self.project_name = project_name
        self.community = community
        self.tone = tone
        self.identity = identity or DEFAULT_IDENTITY_TEMPLATE.format(
            project_name=project_name, community=community, tone=tone
        )
        self.top_k = top_k
        self.candidate_pool = candidate_pool
        self.model = model
        self.provider = provider
        self.knowledge_updated = knowledge_updated
        self.system_version = system_version
        self.diversity = diversity

    # --- stages ----------------------------------------------------------

    def retrieve(
        self,
        question: str,
        filters: Optional[RetrievalFilters] = None,
        rewriter: Optional[Callable[[str], str]] = None,
        top_k: Optional[int] = None,
        use_reranker: bool = True,
        expand: bool = True,
    ) -> Tuple[PreparedQuery, RetrievalResult]:
        if expand:
            prepared = prepare_query(question, rewriter=rewriter)
        else:
            prepared = PreparedQuery(original=question, search_text=question)
        result = self.retriever.retrieve(
            prepared.search_text,
            top_k=top_k or self.top_k,
            filters=filters,
            candidate_pool=self.candidate_pool,
            use_reranker=use_reranker,
            diversity=self.diversity,
        )
        # Report the question the user asked, not the expanded form.
        result.query = question
        return prepared, result

    def build_prompt(
        self,
        question: str,
        retrieval: RetrievalResult,
        citations: Sequence[Citation],
        history: Optional[Sequence[Dict[str, str]]] = None,
        tool_instructions: str = "",
    ) -> PromptBundle:
        context = build_context_block(retrieval.chunks, citations)

        # Principle 18 (Data Freshness): if the question looks time-sensitive
        # and the corpus is small or empty, say so in the context rather than
        # hoping the model infers it.
        if retrieval.corpus_size == 0:
            context += (
                "\n\nNOTE: the community knowledge base is empty or unavailable "
                "for this request. Do not state local facts as if they came from "
                "the record."
            )

        return PromptBundle(
            identity=self.identity,
            constitution_text=self.constitution.render_for_prompt(self.community),
            context_block=context,
            question=question,
            history=[dict(h) for h in (history or [])],
            tool_instructions=tool_instructions,
        )

    def answer(
        self,
        question: str,
        generate: Generator,
        filters: Optional[RetrievalFilters] = None,
        history: Optional[Sequence[Dict[str, str]]] = None,
        rewriter: Optional[Callable[[str], str]] = None,
        top_k: Optional[int] = None,
        use_reranker: bool = True,
        enforce_citations: bool = True,
        expand: bool = True,
        tool_registry: Any = None,
        provider: Any = None,
        max_tool_iterations: int = 4,
    ) -> CommunityAnswer:
        """Retrieve, generate, and verify one answer.

        When ``tool_registry`` holds tools and ``provider`` can drive them, the
        model may call tools mid-answer instead of answering from the first
        retrieval alone. Everything after generation is unchanged: the citation
        check, the provenance record, and the constitution all apply the same
        way whether the evidence arrived up front or was fetched on the way.
        """
        prepared, retrieval = self.retrieve(
            question, filters=filters, rewriter=rewriter,
            top_k=top_k, use_reranker=use_reranker, expand=expand,
        )
        citations = build_citations(retrieval.chunks)

        use_tools = bool(tool_registry) and provider is not None \
            and getattr(provider, "supports_tools", False)
        tool_instructions = ""
        if use_tools:
            from tools.base import TOOL_SYSTEM_PROMPT
            tool_instructions = TOOL_SYSTEM_PROMPT

        prompt = self.build_prompt(question, retrieval, citations, history=history,
                                   tool_instructions=tool_instructions)

        provenance = AnswerProvenance(
            sources_retrieved=len(citations),
            corpus_size=retrieval.corpus_size,
            knowledge_updated=self.knowledge_updated,
            constitution_version=self.constitution.version,
            constitution_status=self.constitution.status,
            constitution_hash=self.constitution.content_hash,
            constitution_ratified=self.constitution.ratified,
            constitution_ledger_ok=self.constitution.ledger_verified,
            model=self.model,
            provider=self.provider,
            system_version=self.system_version,
            retrieval=retrieval.diagnostics(),
            query=prepared.diagnostics(),
        )

        if use_tools:
            from tools.runner import run_tool_loop

            loop = run_tool_loop(
                provider,
                prompt.as_openai_messages()
                if provider.protocol != "anthropic"
                else _anthropic_messages(prompt),
                tool_registry,
                max_iterations=max_tool_iterations,
                max_tokens=None,
            )
            provenance.tools = loop.diagnostics()

            if loop.error:
                provenance.warnings.append(f"generation failed: {loop.error}")
                return CommunityAnswer(
                    answer="", citations=citations, provenance=provenance,
                    prompt=prompt, retrieval=retrieval, error=loop.error,
                )

            raw_answer = loop.text
            if loop.hit_limit:
                provenance.warnings.append(
                    f"reached the limit of {max_tool_iterations} tool rounds; the "
                    f"answer uses what was found by then"
                )
            # Sources a tool produced are citable too, numbered after the
            # passages that arrived with the question.
            citations = citations + _tool_citations(loop.citations, len(citations))
            provenance.sources_retrieved = len(citations)
        else:
            try:
                raw_answer = generate(prompt)
            except Exception as exc:
                provenance.warnings.append(f"generation failed: {type(exc).__name__}")
                return CommunityAnswer(
                    answer="",
                    citations=citations,
                    provenance=provenance,
                    prompt=prompt,
                    retrieval=retrieval,
                    error=str(exc),
                )

        raw_answer = (raw_answer or "").strip()
        check: CitationCheck = verify_citations(raw_answer, citations)

        final_answer = raw_answer
        if enforce_citations and check.invalid_numbers:
            # The model cited a passage that was never supplied. Drop the marker
            # rather than leave the reader a reference that goes nowhere.
            final_answer = strip_invalid_markers(
                raw_answer, [c.number for c in citations]
            )
            provenance.warnings.append(
                "removed citation markers with no matching source: "
                + ", ".join(str(n) for n in check.invalid_numbers)
            )
            check = verify_citations(final_answer, citations)

        if self.constitution.ledger_verified is False:
            provenance.warnings.append(
                "the constitution ledger does not verify; the rules governing "
                "this answer may not be the rules that were adopted"
            )

        if citations and not check.has_citations:
            provenance.warnings.append(
                "answer cites no community source although passages were retrieved"
            )

        provenance.sources_used = check.sources_used
        provenance.citation_check = check.to_dict()

        return CommunityAnswer(
            answer=final_answer,
            citations=citations,
            provenance=provenance,
            prompt=prompt,
            retrieval=retrieval,
        )
