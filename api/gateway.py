"""
The Community AI gateway.

Section 13 of the guide describes two interfaces in front of the local model:

* An **OpenAI-compatible** surface, so an application already written against a
  commercial provider can switch to the community's own server by changing a
  base URL.
* A **civic knowledge API**, so community-built applications get structured
  access to the public record with real filters and machine-readable citations,
  instead of every application reinventing retrieval.

Everything here sits in front of the inference server. The model server itself
should never be reachable from the internet; this gateway holds authentication,
application permissions, rate limits, constitution injection, retrieval,
citation checking, and privacy-aware logging.

The gateway is wired into the existing app by :func:`configure_gateway`, which
injects project lookup and agent construction. That indirection keeps this
module free of imports from ``app.py`` and therefore free of a circular import.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.audit import log_request, prune_logs, usage_summary
from api.auth import (
    SCOPE_ADMIN,
    SCOPE_ASK,
    SCOPE_READ,
    SCOPE_SEARCH,
    AuthError,
    Principal,
    authenticate,
    extract_key,
    rate_limiter,
    require,
)
from knowledge.schemas import SourceType
from rag.citations import build_citations, citation_label, deep_link
from rag.hybrid import build_filters_from_dict

router = APIRouter(tags=["community"])

# The model identifier applications use. Section 13's example calls the local
# service "community-ai"; the underlying model is an implementation detail the
# community can change without breaking every application.
COMMUNITY_MODEL_ALIAS = "community-ai"


@dataclass
class GatewayContext:
    """Dependencies injected by the host application."""

    load_project: Callable[[str], Any]
    list_project_ids: Callable[[], List[str]]
    get_agent: Callable[[str], Any]
    save_project: Callable[[Any], None]
    data_root: str = "./data"


_context: Optional[GatewayContext] = None


def configure_gateway(context: GatewayContext) -> None:
    global _context
    _context = context


def ctx() -> GatewayContext:
    if _context is None:
        raise HTTPException(
            status_code=503,
            detail="The community gateway is not configured on this server.",
        )
    return _context


# --- request models -------------------------------------------------------


class ChatCompletionMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = COMMUNITY_MODEL_ALIAS
    messages: List[ChatCompletionMessage]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False
    # Extensions, ignored by standard OpenAI clients.
    community_filters: Optional[Dict[str, Any]] = None
    include_sources: bool = True


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    filters: Optional[Dict[str, Any]] = None
    top_k: Optional[int] = Field(default=None, ge=1, le=15)
    history: List[ChatCompletionMessage] = []


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    filters: Optional[Dict[str, Any]] = None
    top_k: int = Field(default=10, ge=1, le=50)
    rerank: bool = True


# --- authentication -------------------------------------------------------


def _resolve(
    authorization: Optional[str],
    x_api_key: Optional[str],
    project_hint: Optional[str],
) -> tuple[Any, Principal]:
    """Find the project this key belongs to and authenticate it."""
    context = ctx()
    key = extract_key(authorization, x_api_key)
    if not key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Send 'Authorization: Bearer <key>' or "
                   "'X-API-Key: <key>'.",
        )

    candidates: Iterable[str]
    if project_hint:
        candidates = [project_hint]
    else:
        candidates = context.list_project_ids()

    last_error: Optional[AuthError] = None
    for project_id in candidates:
        project = context.load_project(project_id)
        if project is None:
            continue
        try:
            principal = authenticate(project, key)
        except AuthError as exc:
            last_error = exc
            continue
        return project, principal

    if project_hint and last_error is not None:
        raise HTTPException(status_code=last_error.status_code, detail=last_error.message)
    raise HTTPException(status_code=401, detail="Invalid API key.")


def _require(principal: Principal, scope: str) -> None:
    """Scope check that surfaces as an HTTP status.

    ``api.auth`` is deliberately framework-agnostic and raises ``AuthError``;
    without this translation the error escapes the handler as a 500, which tells
    the caller nothing about the missing permission.
    """
    try:
        require(principal, scope)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


def _enforce_rate_limit(principal: Principal) -> None:
    allowed, remaining, retry_after = rate_limiter.check(
        f"{principal.project_id}:{principal.client_id}", principal.rate_limit_per_minute
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit of {principal.rate_limit_per_minute} requests per "
                   f"minute exceeded for this application key.",
            headers={"Retry-After": str(retry_after)},
        )


def _log(project: Any, principal: Principal, endpoint: str, question: str,
         provenance: Dict[str, Any], started: float, status: str = "ok",
         error: Optional[str] = None) -> None:
    log_request(
        project.project_id,
        endpoint=endpoint,
        client_id=principal.client_id,
        client_name=principal.name,
        question=question,
        log_question_text=getattr(project, "log_question_text", False),
        provenance=provenance,
        status=status,
        error=error,
        latency_ms=(time.perf_counter() - started) * 1000,
        data_root=ctx().data_root,
        enabled=getattr(project, "log_requests", True),
    )


# --- OpenAI-compatible surface -------------------------------------------


@router.get("/v1/models")
async def list_models(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_community_project: Optional[str] = Header(None, alias="X-Community-Project"),
):
    """List the models this gateway serves, in OpenAI's response shape."""
    project, principal = _resolve(authorization, x_api_key, x_community_project)
    created = int(datetime.now().timestamp())
    return {
        "object": "list",
        "data": [
            {
                "id": COMMUNITY_MODEL_ALIAS,
                "object": "model",
                "created": created,
                "owned_by": project.municipality_name,
            },
            {
                "id": project.model_name,
                "object": "model",
                "created": created,
                "owned_by": str(getattr(project.ai_provider, "value", project.ai_provider)),
            },
        ],
    }


def _split_messages(messages: List[ChatCompletionMessage]) -> tuple[str, List[Dict[str, str]]]:
    """Take the final user turn as the question and the rest as history.

    System messages from the caller are dropped on purpose. The constitution is
    the system policy for this service and an application must not be able to
    replace it by sending its own system prompt.
    """
    history: List[Dict[str, str]] = []
    question = ""
    for message in messages:
        if message.role == "system":
            continue
        if message.role == "user":
            question = message.content
        history.append({"role": message.role, "content": message.content})

    if history and history[-1]["role"] == "user":
        history = history[:-1]
    return question, history[-10:]


@router.post("/v1/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_community_project: Optional[str] = Header(None, alias="X-Community-Project"),
):
    """OpenAI-compatible chat completions, answered from the community record."""
    started = time.perf_counter()
    project, principal = _resolve(authorization, x_api_key, x_community_project)
    _require(principal, SCOPE_ASK)
    _enforce_rate_limit(principal)

    question, history = _split_messages(body.messages)
    if not question:
        raise HTTPException(status_code=400, detail="No user message in 'messages'.")

    agent = ctx().get_agent(project.project_id)
    filters = build_filters_from_dict(body.community_filters)

    try:
        result = agent.chat(question, conversation_history=history, filters=filters)
    except Exception as exc:
        _log(project, principal, "/v1/chat/completions", question, {}, started,
             status="error", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Generation failed: {exc}")

    provenance = result.get("provenance", {}) or {}
    _log(project, principal, "/v1/chat/completions", question, provenance, started,
         status="error" if result.get("error") else "ok", error=result.get("error"))

    answer = result.get("answer", "")
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(datetime.now().timestamp())

    community_extension: Dict[str, Any] = {
        "constitution_version": provenance.get("constitution_version"),
        "sources_retrieved": provenance.get("sources_retrieved"),
        "sources_used": provenance.get("sources_used"),
        "knowledge_updated": provenance.get("knowledge_updated"),
        "warnings": provenance.get("warnings", []),
    }
    if body.include_sources:
        community_extension["sources"] = result.get("sources", [])

    if body.stream:
        return StreamingResponse(
            _stream_completion(completion_id, created, body.model, answer,
                               community_extension),
            media_type="text/event-stream",
        )

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": body.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }
        ],
        # Token accounting is not available uniformly across local backends, so
        # it is reported as zero rather than estimated and presented as fact.
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "community": community_extension,
    }


def _stream_completion(completion_id: str, created: int, model: str,
                       answer: str, community: Dict[str, Any]) -> Iterable[str]:
    """Emit a completed answer as server-sent events.

    This is a compatibility shim, not true token streaming: the answer is
    generated in full and then chunked, because the answer pipeline verifies
    citations against the finished text before any of it is shown. A streamed
    token cannot be unsent once a citation check fails.
    """
    def event(payload: Dict[str, Any]) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    yield event({
        "id": completion_id, "object": "chat.completion.chunk", "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
    })

    step = 40
    for i in range(0, len(answer), step):
        yield event({
            "id": completion_id, "object": "chat.completion.chunk", "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {"content": answer[i:i + step]},
                         "finish_reason": None}],
        })

    yield event({
        "id": completion_id, "object": "chat.completion.chunk", "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        "community": community,
    })
    yield "data: [DONE]\n\n"


# --- civic knowledge API --------------------------------------------------


@router.post("/community/ask")
async def community_ask(
    body: AskRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_community_project: Optional[str] = Header(None, alias="X-Community-Project"),
):
    """Answer a question with citations and full provenance."""
    started = time.perf_counter()
    project, principal = _resolve(authorization, x_api_key, x_community_project)
    _require(principal, SCOPE_ASK)
    _enforce_rate_limit(principal)

    agent = ctx().get_agent(project.project_id)
    filters = build_filters_from_dict(body.filters)
    history = [{"role": m.role, "content": m.content} for m in body.history[-10:]]

    try:
        result = agent.chat(body.question, conversation_history=history, filters=filters)
    except Exception as exc:
        _log(project, principal, "/community/ask", body.question, {}, started,
             status="error", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Generation failed: {exc}")

    provenance = result.get("provenance", {}) or {}
    _log(project, principal, "/community/ask", body.question, provenance, started,
         status="error" if result.get("error") else "ok", error=result.get("error"))

    return {
        "question": body.question,
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "provenance": provenance,
        "error": result.get("error"),
    }


@router.post("/community/search")
async def community_search(
    body: SearchRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_community_project: Optional[str] = Header(None, alias="X-Community-Project"),
):
    """Retrieval without generation.

    An application that wants to show the public record, rather than an answer
    about it, should not have to pay for inference or accept a model's summary.
    """
    started = time.perf_counter()
    project, principal = _resolve(authorization, x_api_key, x_community_project)
    _require(principal, SCOPE_SEARCH)
    _enforce_rate_limit(principal)

    agent = ctx().get_agent(project.project_id)
    filters = build_filters_from_dict(body.filters)
    result = agent.retriever.retrieve(
        body.query, top_k=body.top_k, filters=filters, use_reranker=body.rerank
    )
    citations = build_citations(result.chunks)

    _log(project, principal, "/community/search", body.query,
         {"sources_retrieved": len(citations), "retrieval": result.diagnostics()}, started)

    return {
        "query": body.query,
        "results": [
            {
                **citation.to_dict(),
                "text": chunk.chunk.text,
                "retrieval_path": chunk.retrieval_path,
            }
            for citation, chunk in zip(citations, result.chunks)
        ],
        "diagnostics": result.diagnostics(),
    }


@router.get("/community/sources/{source_id}")
async def community_source(
    source_id: str,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_community_project: Optional[str] = Header(None, alias="X-Community-Project"),
):
    """Fetch one indexed passage and its provenance, for source inspection."""
    project, principal = _resolve(authorization, x_api_key, x_community_project)
    _require(principal, SCOPE_READ)

    agent = ctx().get_agent(project.project_id)
    payload = agent.vector_store.get_by_id(source_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Source not found.")

    from knowledge.schemas import normalize_payload

    chunk = normalize_payload(payload)
    return {
        "id": source_id,
        "label": citation_label(chunk),
        "url": deep_link(chunk),
        "text": chunk.text,
        "metadata": chunk.to_payload(),
    }


def _corpus_chunks(agent: Any) -> List[Any]:
    corpus = agent.retriever._get_corpus()  # noqa: SLF001 - internal by design
    return list(corpus.chunks) if corpus else []


@router.get("/community/meetings")
async def community_meetings(
    body: Optional[str] = Query(None, description="Board or committee name"),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=500),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_community_project: Optional[str] = Header(None, alias="X-Community-Project"),
):
    """List the meetings in the archive, newest first."""
    project, principal = _resolve(authorization, x_api_key, x_community_project)
    _require(principal, SCOPE_READ)

    agent = ctx().get_agent(project.project_id)
    meetings: Dict[str, Dict[str, Any]] = {}

    for chunk in _corpus_chunks(agent):
        if chunk.source_type != SourceType.MEETING_TRANSCRIPT:
            continue
        if body and chunk.body.strip().lower() != body.strip().lower():
            continue
        record_date = chunk.meeting_date or chunk.date
        if date_from and (not record_date or record_date < date_from):
            continue
        if date_to and (not record_date or record_date > date_to):
            continue

        key = f"{chunk.body}|{record_date}|{chunk.video_url or chunk.url}"
        entry = meetings.setdefault(key, {
            "body": chunk.body,
            "date": record_date,
            "title": chunk.title,
            "url": chunk.video_url or chunk.url,
            "passages": 0,
            "speakers": set(),
            "agenda_items": set(),
        })
        entry["passages"] += 1
        if chunk.speaker:
            entry["speakers"].add(chunk.speaker)
        if chunk.agenda_item:
            entry["agenda_items"].add(chunk.agenda_item)

    listing = []
    for entry in meetings.values():
        listing.append({
            **{k: v for k, v in entry.items() if k not in ("speakers", "agenda_items")},
            "speakers": sorted(entry["speakers"]),
            "agenda_items": sorted(entry["agenda_items"]),
        })
    listing.sort(key=lambda m: m.get("date") or "", reverse=True)

    return {"count": len(listing), "meetings": listing[:limit]}


@router.get("/community/documents")
async def community_documents(
    department: Optional[str] = Query(None),
    document_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_community_project: Optional[str] = Header(None, alias="X-Community-Project"),
):
    """List the documents in the archive."""
    project, principal = _resolve(authorization, x_api_key, x_community_project)
    _require(principal, SCOPE_READ)

    agent = ctx().get_agent(project.project_id)
    documents: Dict[str, Dict[str, Any]] = {}

    for chunk in _corpus_chunks(agent):
        if chunk.source_type not in (SourceType.MUNICIPAL_DOCUMENT, SourceType.WEBSITE):
            continue
        if department and chunk.department.strip().lower() != department.strip().lower():
            continue
        if document_type and chunk.document_type.strip().lower() != document_type.strip().lower():
            continue

        key = f"{chunk.title}|{chunk.url}"
        entry = documents.setdefault(key, {
            "title": chunk.title,
            "url": chunk.url,
            "department": chunk.department,
            "document_type": chunk.document_type,
            "source_type": chunk.source_type,
            "status": chunk.status,
            "date": chunk.effective_date or chunk.date,
            "passages": 0,
            "pages": set(),
        })
        entry["passages"] += 1
        if chunk.page:
            entry["pages"].add(chunk.page)

    listing = []
    for entry in documents.values():
        pages = sorted(entry.pop("pages"))
        listing.append({**entry, "page_count": len(pages),
                        "page_range": [pages[0], pages[-1]] if pages else None})
    listing.sort(key=lambda d: d.get("title") or "")

    return {"count": len(listing), "documents": listing[:limit]}


# --- public transparency endpoints ---------------------------------------


@router.get("/community/{project_id}/constitution")
async def community_constitution(project_id: str):
    """The constitution governing a project. Public: it is a public artifact."""
    project = ctx().load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    agent = ctx().get_agent(project_id)
    constitution = agent.constitution
    return {
        "project_id": project_id,
        "community": project.municipality_name,
        **constitution.summary(),
        "text": constitution.text,
    }


@router.get("/community/{project_id}/stats")
async def community_stats(project_id: str):
    """Public system facts: versions, corpus size, freshness.

    Principle 10 (Transparency) and Principle 18 (Data Freshness) both need this
    to be inspectable without an API key.
    """
    project = ctx().load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    agent = ctx().get_agent(project_id)
    stats = agent.get_stats()
    return {
        "project_id": project_id,
        "community": project.municipality_name,
        "system_version": stats.get("system_version"),
        "model": stats.get("model"),
        "provider": stats.get("provider_label"),
        "embedding_model": stats.get("embedding_model"),
        "constitution_version": stats.get("constitution_version"),
        "constitution_status": stats.get("constitution_status"),
        "constitution_principles": stats.get("constitution_principles"),
        "total_passages": stats.get("total_documents"),
        "knowledge_updated": stats.get("knowledge_updated"),
        "data_sources": stats.get("data_sources"),
        "hybrid_search": getattr(project, "enable_hybrid_search", True),
        "reranking": getattr(project, "enable_reranking", True),
    }


@router.get("/community/usage")
async def community_usage(
    days: int = Query(30, ge=1, le=365),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_community_project: Optional[str] = Header(None, alias="X-Community-Project"),
):
    """Aggregate usage statistics. No question text, per governance.md."""
    project, principal = _resolve(authorization, x_api_key, x_community_project)
    _require(principal, SCOPE_ADMIN)

    retention = getattr(project, "log_retention_days", 30)
    prune_logs(project.project_id, retention, data_root=ctx().data_root)
    return usage_summary(project.project_id, days=days, data_root=ctx().data_root)
