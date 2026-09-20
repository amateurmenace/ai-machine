"""Tools the community assistant can call while answering.

A local model has a fixed knowledge cutoff and no network. These give it both,
under the community's control: its own archive, the open web, and one page at a
time. See ``tools/base.py`` for the rules every tool follows.
"""

from typing import Any, List, Optional

from tools.base import (
    TOOL_SYSTEM_PROMPT,
    Tool,
    ToolCitation,
    ToolRegistry,
    ToolResult,
)
from tools.records import SearchRecordsTool
from tools.runner import ToolInvocation, ToolLoopResult, run_tool_loop
from tools.web import BlockedURLError, FetchURLTool, WebSearchTool, assert_public_url

__all__ = [
    "TOOL_SYSTEM_PROMPT",
    "Tool",
    "ToolCitation",
    "ToolRegistry",
    "ToolResult",
    "SearchRecordsTool",
    "WebSearchTool",
    "FetchURLTool",
    "BlockedURLError",
    "assert_public_url",
    "ToolInvocation",
    "ToolLoopResult",
    "run_tool_loop",
    "build_registry",
]


def build_registry(project: Any, retriever: Any = None) -> ToolRegistry:
    """Build the tool set one project has enabled.

    Tools are opt-in per project. A community that wants a purely archive-bound
    assistant, one that can only answer from its own public record, gets that by
    leaving them off; that is a legitimate civic choice, not a missing feature.
    """
    if not getattr(project, "enable_tools", False):
        return ToolRegistry()

    enabled = set(getattr(project, "enabled_tools", None) or [])
    tools: List[Tool] = []

    if "search_community_records" in enabled and retriever is not None:
        tools.append(SearchRecordsTool(
            retriever=retriever,
            community=getattr(project, "municipality_name", "this community"),
            use_reranker=getattr(project, "enable_reranking", True),
        ))

    if "web_search" in enabled:
        tools.append(WebSearchTool(
            backend=getattr(project, "web_search_backend", "duckduckgo"),
            base_url=getattr(project, "web_search_base_url", None),
            api_key=getattr(project, "web_search_api_key", None),
        ))

    if "fetch_url" in enabled:
        tools.append(FetchURLTool())

    return ToolRegistry(tools)
