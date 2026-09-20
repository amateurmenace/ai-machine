"""
The tool-calling loop.

Provider-neutral: it drives :meth:`BaseProvider.chat`, which every provider
implements, so the same loop serves a local Gemma, Claude, and Gemini.

The loop is bounded and everything it did is recorded. A resident asking why an
answer says what it says should be able to see that the assistant searched the
web twice and read one page, which tools ran, and what they returned.

One deliberate limit: the loop stops at ``max_iterations`` and tells the model
so, rather than cutting the turn off. A model that knows it is out of tool calls
writes "based on what I found so far"; a model that is simply truncated does not.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from providers import BaseProvider, ChatTurn, ToolCall
from tools.base import ToolCitation, ToolRegistry, ToolResult


@dataclass
class ToolInvocation:
    """One executed tool call, for the transparency panel."""

    name: str
    arguments: Dict[str, Any]
    ok: bool
    summary: str
    elapsed_ms: float
    external: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.name,
            "arguments": self.arguments,
            "ok": self.ok,
            "summary": self.summary,
            "elapsed_ms": round(self.elapsed_ms, 1),
            "external": self.external,
        }


@dataclass
class ToolLoopResult:
    text: str = ""
    invocations: List[ToolInvocation] = field(default_factory=list)
    citations: List[ToolCitation] = field(default_factory=list)
    iterations: int = 0
    hit_limit: bool = False
    error: Optional[str] = None

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "iterations": self.iterations,
            "tool_calls": len(self.invocations),
            "hit_limit": self.hit_limit,
            "tools_used": sorted({i.name for i in self.invocations}),
            "external_calls": sum(1 for i in self.invocations if i.external),
            "invocations": [i.to_dict() for i in self.invocations],
        }


def _as_message(assistant_message: Any) -> Any:
    """Normalize a provider's assistant message for appending to history."""
    if assistant_message is None:
        return {"role": "assistant", "content": ""}
    if isinstance(assistant_message, dict):
        return assistant_message
    for method in ("model_dump", "dict"):
        if hasattr(assistant_message, method):
            try:
                return getattr(assistant_message, method)()
            except Exception:
                pass
    return {"role": "assistant", "content": str(assistant_message)}


def run_tool_loop(
    provider: BaseProvider,
    messages: List[Dict[str, Any]],
    registry: ToolRegistry,
    max_iterations: int = 4,
    max_tokens: Optional[int] = None,
) -> ToolLoopResult:
    """Drive the model until it answers or runs out of tool calls."""
    result = ToolLoopResult()

    if not registry or not provider.supports_tools:
        try:
            turn = provider.chat(messages, max_tokens=max_tokens)
            result.text = turn.text
            result.iterations = 1
        except Exception as exc:
            result.error = str(exc)
        return result

    history = list(messages)
    schemas = registry.schemas()

    for iteration in range(1, max_iterations + 1):
        result.iterations = iteration
        try:
            turn: ChatTurn = provider.chat(history, tools=schemas, max_tokens=max_tokens)
        except Exception as exc:
            result.error = str(exc)
            return result

        if not turn.wants_tools:
            result.text = turn.text
            return result

        history.append(_as_message(turn.assistant_message))

        executed: List[Tuple[ToolCall, str]] = []
        for call in turn.tool_calls:
            started = time.perf_counter()
            tool = registry.get(call.name)

            if tool is None:
                output = ToolResult.failure(
                    f"no tool named {call.name!r}. Available: "
                    f"{', '.join(registry.names())}"
                )
            else:
                try:
                    output = tool.run(**call.arguments)
                except TypeError as exc:
                    # Wrong or missing arguments: recoverable, so tell the model.
                    output = ToolResult.failure(
                        f"{call.name} was called with arguments it does not "
                        f"accept ({exc}). Check the tool's parameters and retry."
                    )
                except Exception as exc:
                    output = ToolResult.failure(
                        f"{call.name} failed: {type(exc).__name__}: {exc}"
                    )

            elapsed = (time.perf_counter() - started) * 1000
            result.invocations.append(ToolInvocation(
                name=call.name,
                arguments=call.arguments,
                ok=output.error is None,
                summary=output.error or _summarize(output),
                elapsed_ms=elapsed,
                external=bool(tool.external) if tool else False,
            ))
            result.citations.extend(output.citations)
            executed.append((call, output.for_model()))

        history.extend(provider.tool_result_messages(executed))

        if iteration == max_iterations:
            result.hit_limit = True
            history.append({
                "role": "user",
                "content": (
                    "You have used all available tool calls for this question. "
                    "Answer now using what you found. Say plainly what you could "
                    "not confirm, rather than filling the gap with a guess."
                ),
            })
            try:
                final = provider.chat(history, max_tokens=max_tokens)
                result.text = final.text
            except Exception as exc:
                result.error = str(exc)
            return result

    return result


def _summarize(output: ToolResult) -> str:
    count = output.meta.get("result_count")
    if count is not None:
        return f"{count} result(s)"
    if output.meta.get("chars") is not None:
        return f"{output.meta['chars']} characters"
    return f"{len(output.content)} characters"
