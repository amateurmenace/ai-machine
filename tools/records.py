"""
Searching the community archive as a tool.

Retrieval already runs once before the model sees the question. This tool lets
the model search again, with its own query and its own filters, when the first
pass missed. That matters for the question shapes the guide's evaluation set
names as hardest:

* **Historical** — "what was the policy in 2019" needs a date-filtered search
  the resident's phrasing would not produce.
* **Attribution** — "did Councilor Smith say that" needs a speaker filter.
* **Conflicting evidence** — noticing that two documents disagree usually takes
  a second, narrower search.

The tool returns the same citation shape as the main pipeline, so a passage the
model found itself is cited exactly like one that arrived with the question.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from knowledge.schemas import SourceType
from rag.citations import build_citations
from rag.hybrid import RetrievalFilters
from tools.base import Tool, ToolCitation, ToolResult


class SearchRecordsTool(Tool):
    name = "search_community_records"
    description = (
        "Search this community's archive of meeting transcripts, bylaws, "
        "budgets, plans and official pages. Use this for anything about this "
        "community, before searching the web. Supports filters, which is how "
        "you answer questions about a specific board, a specific year, or a "
        "specific person's statements."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string",
                      "description": "What to search for. Use the terms the "
                                     "records would use, not the resident's wording."},
            "body": {"type": "string",
                     "description": "Limit to one board or committee, e.g. "
                                    "'Select Board', 'School Committee'."},
            "speaker": {"type": "string",
                        "description": "Limit to passages spoken by this person."},
            "date_from": {"type": "string", "description": "Earliest date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Latest date, YYYY-MM-DD."},
            "source_type": {
                "type": "string",
                "enum": ["meeting_transcript", "municipal_document", "website"],
                "description": "Limit to meetings, documents, or web pages.",
            },
            "count": {"type": "integer", "description": "Passages to return, 1-10.",
                      "default": 5},
        },
        "required": ["query"],
    }
    external = False

    def __init__(self, retriever: Any, community: str = "this community",
                 use_reranker: bool = True) -> None:
        self.retriever = retriever
        self.community = community
        self.use_reranker = use_reranker

    def run(self, query: str = "", count: int = 5, **filters: Any) -> ToolResult:
        query = (query or "").strip()
        if not query:
            return ToolResult.failure("no search query was given")
        count = max(1, min(int(count or 5), 10))

        known = {"body", "speaker", "date_from", "date_to", "source_type"}
        applied = {k: v for k, v in filters.items() if k in known and v}

        try:
            result = self.retriever.retrieve(
                query,
                top_k=count,
                filters=RetrievalFilters(**applied) if applied else None,
                use_reranker=self.use_reranker,
            )
        except Exception as exc:
            return ToolResult.failure(
                f"searching the archive failed: {type(exc).__name__}: {exc}"
            )

        if not result.chunks:
            detail = f" with filters {applied}" if applied else ""
            hint = ""
            if applied:
                hint = (" The filters may be too narrow, or the archive may not "
                        "cover that board or period. Try again without them.")
            return ToolResult(
                content=(
                    f"No passages in {self.community}'s archive match {query!r}"
                    f"{detail}.{hint}"
                ),
                meta={"result_count": 0, "filters": applied,
                      "corpus_size": result.corpus_size},
            )

        citations = build_citations(result.chunks)
        lines = [
            f"{len(citations)} passage(s) from {self.community}'s archive "
            f"for {query!r}" + (f" (filters: {applied})" if applied else "") + ":",
            "",
        ]
        tool_citations: List[ToolCitation] = []
        for citation, chunk in zip(citations, result.chunks):
            lines.append(f"[{citation.label}]")
            if citation.attribution:
                lines.append(f"  {citation.attribution}")
            if citation.url:
                lines.append(f"  {citation.url}")
            lines.append(f"  {chunk.chunk.text}")
            lines.append("")
            tool_citations.append(ToolCitation(
                title=citation.label, url=citation.url,
                kind=citation.source_type or "record",
                snippet=chunk.chunk.text[:300],
            ))

        lines.append(
            "Cite these by their label, for example "
            f"[{citations[0].label}], so the resident can check the record."
        )

        return ToolResult(
            content="\n".join(lines),
            citations=tool_citations,
            meta={"result_count": len(citations), "filters": applied,
                  "corpus_size": result.corpus_size,
                  "retrieval": result.diagnostics()},
        )
