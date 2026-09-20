"""
Inference providers.

The point of this project is that a community runs its own model. LM Studio on
hardware the community owns is the primary path, either on the local network or
reached through a tunnel so a machine in a closet can serve a whole town without
a static IP or an open inbound port. Frontier providers are here so a community
can compare, can fall back, and can decide for itself what it gives up by
sending a resident's question to someone else's data center.

Five providers, one calling convention:

    lmstudio   local or tunneled, OpenAI protocol      <- the default
    ollama     local, Ollama protocol
    anthropic  Claude
    openai     GPT
    gemini     Google, via its OpenAI-compatible endpoint

Every provider exposes :meth:`chat`, which returns text *and* any tool calls the
model wants to make. That one method is what lets a local model search the web
or the community archive mid-answer; see ``tools/``.

Two things are deliberate:

* **The model server never faces the internet directly.** The gateway in
  ``api/`` holds authentication, rate limits and logging. A tunnel terminates at
  the gateway, not at LM Studio.
* **The hardcoded model lists are a fallback.** Lineups move faster than this
  file. :func:`discover_models` asks a provider what it actually serves.
* **A key can be a reference instead of a value.** An API key or a tunnel
  credential written as ``sm://projects/.../versions/latest`` is resolved
  through Secret Manager on the way in, so it never sits in ``config.json``.
  Anything else is used exactly as written, which is what a community keeping
  its key in an environment variable on its own machine wants.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from cloud.secrets import resolve_env, resolve_secret

# --- endpoints ------------------------------------------------------------

LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
LM_STUDIO_API_KEY = os.getenv("LM_STUDIO_API_KEY", "lm-studio")

# Google exposes an OpenAI-compatible surface. Using it means one code path for
# three of the five providers, at the cost of not reaching Gemini-only features.
GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

DEFAULT_LOCAL_MODEL = os.getenv("COMMUNITY_MODEL", "gemma-4-26b-a4b")

PROVIDER_LABELS = {
    "lmstudio": "LM Studio (local)",
    "ollama": "Ollama (local)",
    "anthropic": "Anthropic Claude",
    "openai": "OpenAI",
    "gemini": "Google Gemini",
}

# Models whose tool calling this app cannot drive. OpenAI moved tool calling to
# the Responses API for its newest models; this app speaks Chat Completions, so
# those models work for plain answers but cannot use web search here. Saying so
# is better than letting a resident wonder why the assistant never searches.
NO_CHAT_COMPLETIONS_TOOLS = {"gpt-6-astra"}


class ProviderError(RuntimeError):
    """Raised with a message meant for an operator, not a stack trace."""


@dataclass
class GenerationSettings:
    model: str
    temperature: float = 0.7
    max_tokens: int = 2000
    context_window: int = 8192


@dataclass
class ToolCall:
    """A model's request to run one tool."""

    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatTurn:
    """One assistant turn: text, tool calls, or both."""

    text: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: str = ""
    # The assistant message in the provider's own shape, to append to history
    # before sending tool results back.
    assistant_message: Optional[Any] = None

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


def _parse_arguments(raw: Any) -> Dict[str, Any]:
    """Parse tool-call arguments defensively.

    Models emit tool arguments as a JSON string, and a small local model will
    occasionally emit one that does not parse. A malformed call should surface
    as a tool error the model can recover from, never as a crashed request.
    """
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"__unparsed__": str(raw)[:500]}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


# --- base -----------------------------------------------------------------


class BaseProvider:
    name = "base"
    protocol = "unknown"

    def __init__(self, settings: GenerationSettings) -> None:
        self.settings = settings

    # --- capability ---

    @property
    def supports_tools(self) -> bool:
        return False

    # --- generation ---

    def chat(self, messages: List[Dict[str, Any]],
             tools: Optional[List[Dict[str, Any]]] = None,
             max_tokens: Optional[int] = None) -> ChatTurn:
        raise NotImplementedError

    def complete(self, prompt: Any) -> str:
        """Answer a PromptBundle with no tools. The simple path."""
        messages = prompt.as_openai_messages() if hasattr(prompt, "as_openai_messages") else prompt
        return self.chat(messages).text

    def raw_chat(self, messages: List[Dict[str, str]],
                 max_tokens: Optional[int] = None) -> str:
        return self.chat(messages, max_tokens=max_tokens).text

    # --- tool plumbing ---

    def tool_result_messages(self, results: List[Tuple[ToolCall, str]]) -> List[Dict[str, Any]]:
        """Turn executed tool results into messages to send back."""
        raise NotImplementedError

    def health(self) -> Dict[str, Any]:
        return {"provider": self.name, "reachable": None, "detail": "no health check"}


# --- OpenAI-compatible ----------------------------------------------------


class OpenAICompatibleProvider(BaseProvider):
    """Any server speaking the OpenAI Chat Completions protocol.

    Covers LM Studio, Ollama's compatibility endpoint, OpenAI, Gemini's
    compatible surface, vLLM, and llama.cpp. The only differences are the base
    URL, the key, and any headers a tunnel in front of it requires.
    """

    name = "openai-compatible"
    protocol = "openai"

    def __init__(self, settings: GenerationSettings, base_url: Optional[str] = None,
                 api_key: Optional[str] = None, timeout: float = 300.0,
                 extra_headers: Optional[Dict[str, str]] = None,
                 verify_tls: bool = True) -> None:
        super().__init__(settings)
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.extra_headers = extra_headers or {}
        self.verify_tls = verify_tls
        self._client = None

    @property
    def supports_tools(self) -> bool:
        return self.settings.model not in NO_CHAT_COMPLETIONS_TOOLS

    @property
    def client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ProviderError(
                    "The 'openai' package is required for this provider. "
                    "Install it with: pip install openai"
                ) from exc

            kwargs: Dict[str, Any] = {"timeout": self.timeout}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            kwargs["api_key"] = self.api_key or "not-needed"
            if self.extra_headers:
                kwargs["default_headers"] = dict(self.extra_headers)
            if not self.verify_tls:
                # Only reachable when an operator sets local_verify_tls=false,
                # which the setup guide restricts to a self-signed certificate
                # on a network the community controls.
                try:
                    import httpx
                    kwargs["http_client"] = httpx.Client(verify=False, timeout=self.timeout)
                except ImportError:
                    pass

            self._client = OpenAI(**kwargs)
        return self._client

    def chat(self, messages: List[Dict[str, Any]],
             tools: Optional[List[Dict[str, Any]]] = None,
             max_tokens: Optional[int] = None) -> ChatTurn:
        request: Dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": self.settings.temperature,
            "max_tokens": max_tokens or self.settings.max_tokens,
        }
        if tools and self.supports_tools:
            request["tools"] = tools
            request["tool_choice"] = "auto"

        try:
            response = self.client.chat.completions.create(**request)
        except Exception as exc:
            raise self._translate(exc) from exc

        choice = response.choices[0]
        message = choice.message

        calls: List[ToolCall] = []
        for call in (getattr(message, "tool_calls", None) or []):
            function = getattr(call, "function", None)
            if function is None:
                continue
            calls.append(ToolCall(
                id=getattr(call, "id", "") or f"call_{len(calls)}",
                name=getattr(function, "name", "") or "",
                arguments=_parse_arguments(getattr(function, "arguments", None)),
            ))

        return ChatTurn(
            text=message.content or "",
            tool_calls=calls,
            finish_reason=getattr(choice, "finish_reason", "") or "",
            assistant_message=message,
        )

    def tool_result_messages(self, results: List[Tuple[ToolCall, str]]) -> List[Dict[str, Any]]:
        return [
            {"role": "tool", "tool_call_id": call.id, "name": call.name, "content": output}
            for call, output in results
        ]

    def _translate(self, exc: Exception) -> Exception:
        text = str(exc).lower()
        if "connection" in text or "refused" in text or "timed out" in text:
            return ProviderError(
                f"Could not reach the model server at {self.base_url or 'the default endpoint'}. "
                f"{exc}"
            )
        if "api key" in text or "unauthorized" in text or "401" in text:
            return ProviderError("The API key was rejected by this provider.")
        return exc

    def health(self) -> Dict[str, Any]:
        try:
            models = self.client.models.list()
            names = [m.id for m in getattr(models, "data", [])]
            return {
                "provider": self.name,
                "reachable": True,
                "base_url": self.base_url,
                "models_loaded": names[:50],
                "configured_model": self.settings.model,
                "configured_model_loaded": (
                    self.settings.model in names if names else None
                ),
                "supports_tools": self.supports_tools,
            }
        except Exception as exc:
            return {
                "provider": self.name,
                "reachable": False,
                "base_url": self.base_url,
                "detail": f"{type(exc).__name__}: {exc}",
            }


class LMStudioProvider(OpenAICompatibleProvider):
    """LM Studio, local or reached over a tunnel."""

    name = "lmstudio"

    def __init__(self, settings: GenerationSettings, base_url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 extra_headers: Optional[Dict[str, str]] = None,
                 verify_tls: bool = True) -> None:
        super().__init__(
            settings,
            base_url=base_url or LM_STUDIO_BASE_URL,
            api_key=api_key or LM_STUDIO_API_KEY,
            extra_headers=extra_headers,
            verify_tls=verify_tls,
        )

    @property
    def is_remote(self) -> bool:
        url = (self.base_url or "").lower()
        return not any(host in url for host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"))

    def health(self) -> Dict[str, Any]:
        status = super().health()
        status["remote"] = self.is_remote
        if not status.get("reachable"):
            if self.is_remote:
                status["remedy"] = (
                    f"LM Studio is not answering at {self.base_url}. Check that the "
                    f"tunnel is up on the server (cloudflared/ngrok), that LM Studio "
                    f"is running with its server started, and that any tunnel "
                    f"credential is set in the project's local auth header."
                )
            else:
                status["remedy"] = (
                    f"LM Studio is not answering at {self.base_url}. Start the local "
                    f"server (Developer tab -> Start Server, or `lms server start` "
                    f"on a headless install) and load a model."
                )
        elif status.get("configured_model_loaded") is False:
            loaded = ", ".join(status.get("models_loaded") or []) or "none"
            status["remedy"] = (
                f"LM Studio is running but '{self.settings.model}' is not loaded. "
                f"Loaded: {loaded}. Load it, or set the project's model to one of those."
            )
        return status


class OpenAIProvider(OpenAICompatibleProvider):
    name = "openai"

    def __init__(self, settings: GenerationSettings, api_key: Optional[str] = None,
                 base_url: Optional[str] = None) -> None:
        super().__init__(settings, base_url=base_url,
                         api_key=api_key or resolve_env("OPENAI_API_KEY"))

    def health(self) -> Dict[str, Any]:
        if not self.api_key:
            return {"provider": self.name, "reachable": False,
                    "detail": "no API key configured",
                    "remedy": "Add an OpenAI API key in Settings."}
        status = super().health()
        if not self.supports_tools:
            status["tools_note"] = (
                f"{self.settings.model} handles tool calling through OpenAI's "
                f"Responses API, which this app does not speak. The model answers "
                f"normally; web search is unavailable on it. Use gpt-5.5 for tools."
            )
        return status


class GeminiProvider(OpenAICompatibleProvider):
    """Google Gemini through its OpenAI-compatible endpoint."""

    name = "gemini"

    def __init__(self, settings: GenerationSettings, api_key: Optional[str] = None,
                 base_url: Optional[str] = None) -> None:
        super().__init__(
            settings,
            base_url=base_url or GEMINI_BASE_URL,
            api_key=api_key or resolve_env("GEMINI_API_KEY") or resolve_env("GOOGLE_API_KEY"),
        )

    def health(self) -> Dict[str, Any]:
        if not self.api_key:
            return {"provider": self.name, "reachable": False,
                    "detail": "no API key configured",
                    "remedy": "Add a Gemini API key in Settings, or set "
                              "GEMINI_API_KEY in the environment."}
        return super().health()


# --- Ollama ---------------------------------------------------------------


class OllamaProvider(BaseProvider):
    """Ollama's native protocol, which also carries tool calls."""

    name = "ollama"
    protocol = "ollama"

    @property
    def supports_tools(self) -> bool:
        return True

    def chat(self, messages: List[Dict[str, Any]],
             tools: Optional[List[Dict[str, Any]]] = None,
             max_tokens: Optional[int] = None) -> ChatTurn:
        try:
            import ollama
        except ImportError as exc:
            raise ProviderError("The 'ollama' package is not installed.") from exc

        merged = _merge_system_messages(_strip_tool_fields(messages))
        request: Dict[str, Any] = {
            "model": self.settings.model,
            "messages": merged,
            "options": {
                "temperature": self.settings.temperature,
                "num_ctx": self.settings.context_window,
            },
        }
        if tools:
            request["tools"] = tools

        try:
            response = ollama.chat(**request)
        except Exception as exc:
            text = str(exc).lower()
            if "connection" in text or "refused" in text:
                raise ProviderError(
                    "Ollama is not running. Start it with `ollama serve`."
                ) from exc
            if "not found" in text or "pull" in text:
                raise ProviderError(
                    f"Model '{self.settings.model}' is not installed. "
                    f"Run `ollama pull {self.settings.model}`."
                ) from exc
            raise

        message = response.get("message", {}) or {}
        calls = []
        for i, call in enumerate(message.get("tool_calls") or []):
            function = call.get("function", {}) or {}
            calls.append(ToolCall(
                id=call.get("id") or f"call_{i}",
                name=function.get("name", ""),
                arguments=_parse_arguments(function.get("arguments")),
            ))

        return ChatTurn(
            text=message.get("content", "") or "",
            tool_calls=calls,
            assistant_message=message,
        )

    def tool_result_messages(self, results: List[Tuple[ToolCall, str]]) -> List[Dict[str, Any]]:
        return [{"role": "tool", "content": output} for _, output in results]

    def health(self) -> Dict[str, Any]:
        try:
            import ollama
            listed = ollama.list()
            names = [m.get("name", m.get("model", "")) for m in listed.get("models", [])]
            return {
                "provider": self.name,
                "reachable": True,
                "models_loaded": names,
                "configured_model": self.settings.model,
                "configured_model_loaded": any(
                    n.startswith(self.settings.model.split(":")[0]) for n in names
                ),
                "supports_tools": True,
            }
        except Exception as exc:
            return {
                "provider": self.name,
                "reachable": False,
                "detail": f"{type(exc).__name__}: {exc}",
                "remedy": "Start Ollama with `ollama serve`.",
            }


# --- Anthropic ------------------------------------------------------------


class AnthropicProvider(BaseProvider):
    name = "anthropic"
    protocol = "anthropic"

    def __init__(self, settings: GenerationSettings, api_key: Optional[str] = None) -> None:
        super().__init__(settings)
        self.api_key = api_key or resolve_env("ANTHROPIC_API_KEY")
        self._client = None

    @property
    def supports_tools(self) -> bool:
        return True

    @property
    def client(self):
        if self._client is None:
            try:
                from anthropic import Anthropic
            except ImportError as exc:
                raise ProviderError("The 'anthropic' package is not installed.") from exc
            if not self.api_key:
                raise ProviderError(
                    "Anthropic API key is not configured. Add it in Settings."
                )
            self._client = Anthropic(api_key=self.api_key)
        return self._client

    def chat(self, messages: List[Dict[str, Any]],
             tools: Optional[List[Dict[str, Any]]] = None,
             max_tokens: Optional[int] = None) -> ChatTurn:
        system, turns = _split_system(messages)
        request: Dict[str, Any] = {
            "model": self.settings.model,
            "max_tokens": max_tokens or self.settings.max_tokens,
            "system": system or "You are a helpful assistant.",
            "messages": _to_anthropic_turns(turns),
        }
        # Sampling parameters were removed on current Claude models, so they are
        # only sent to models old enough to accept them.
        if not _is_current_claude(self.settings.model):
            request["temperature"] = self.settings.temperature
        if tools:
            request["tools"] = [_to_anthropic_tool(t) for t in tools]

        response = self.client.messages.create(**request)

        text_parts, calls = [], []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name,
                                      arguments=_parse_arguments(block.input)))

        return ChatTurn(
            text="".join(text_parts),
            tool_calls=calls,
            finish_reason=getattr(response, "stop_reason", "") or "",
            assistant_message={"role": "assistant", "content": response.content},
        )

    def tool_result_messages(self, results: List[Tuple[ToolCall, str]]) -> List[Dict[str, Any]]:
        # Anthropic expects every tool result for a turn in one user message.
        return [{
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": call.id, "content": output}
                for call, output in results
            ],
        }]

    def complete(self, prompt: Any) -> str:
        if hasattr(prompt, "as_anthropic_messages"):
            system, turns = prompt.as_anthropic_messages()
            messages = [{"role": "system", "content": system}] + list(turns)
        else:
            messages = prompt
        return self.chat(messages).text

    def health(self) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "reachable": bool(self.api_key),
            "supports_tools": True,
            "detail": "API key present" if self.api_key else "no API key configured",
            "remedy": None if self.api_key else "Add an Anthropic API key in Settings.",
        }


# --- helpers --------------------------------------------------------------


def _is_current_claude(model: str) -> bool:
    """Current Claude models reject temperature and top_p."""
    model = (model or "").lower()
    return any(model.startswith(prefix) for prefix in (
        "claude-opus-5", "claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8",
        "claude-sonnet-5", "claude-sonnet-4-6", "claude-fable-5", "claude-mythos-5",
    ))


def _merge_system_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    system_parts = [m["content"] for m in messages
                    if m.get("role") == "system" and isinstance(m.get("content"), str)]
    rest = [m for m in messages if m.get("role") != "system"]
    if not system_parts:
        return rest
    return [{"role": "system", "content": "\n\n".join(system_parts)}] + rest


def _strip_tool_fields(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop OpenAI-only keys Ollama does not accept."""
    cleaned = []
    for message in messages:
        if not isinstance(message, dict):
            cleaned.append(message)
            continue
        cleaned.append({k: v for k, v in message.items()
                        if k not in ("tool_call_id", "tool_calls", "name")})
    return cleaned


def _split_system(messages: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    system_parts = [m["content"] for m in messages
                    if m.get("role") == "system" and isinstance(m.get("content"), str)]
    rest = [m for m in messages if m.get("role") != "system"]
    return "\n\n".join(system_parts), rest


def _to_anthropic_turns(turns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert OpenAI-shaped turns, including tool results, to Anthropic's shape."""
    converted: List[Dict[str, Any]] = []
    for turn in turns:
        role = turn.get("role")
        if role == "tool":
            block = {"type": "tool_result",
                     "tool_use_id": turn.get("tool_call_id", ""),
                     "content": turn.get("content", "")}
            if converted and converted[-1]["role"] == "user" \
                    and isinstance(converted[-1].get("content"), list):
                converted[-1]["content"].append(block)
            else:
                converted.append({"role": "user", "content": [block]})
        else:
            converted.append(turn)
    return converted


def _to_anthropic_tool(tool: Dict[str, Any]) -> Dict[str, Any]:
    """OpenAI tool schema to Anthropic tool schema."""
    function = tool.get("function", tool)
    return {
        "name": function.get("name", ""),
        "description": function.get("description", ""),
        "input_schema": function.get("parameters", {"type": "object", "properties": {}}),
    }


def parse_auth_header(raw: Optional[str]) -> Dict[str, str]:
    """Parse a stored ``Name: value`` header string.

    A tunnel in front of a community's server usually wants a header: a
    Cloudflare Access service token, a bearer token, a shared secret. Storing it
    as one line keeps the setup wizard to a single field.
    """
    if not raw or ":" not in raw:
        return {}
    headers: Dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        name, _, value = line.partition(":")
        name, value = name.strip(), value.strip()
        if name and value:
            headers[name] = value
    return headers


# --- construction ---------------------------------------------------------


def build_provider(
    provider: str,
    model: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    context_window: int = 8192,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    auth_header: Optional[str] = None,
    verify_tls: bool = True,
) -> BaseProvider:
    """Construct the provider for a project's configuration."""
    # Resolved here, once, for every provider: this is the single place a
    # configured credential turns into a credential in use.
    api_key = resolve_secret(api_key)
    auth_header = resolve_secret(auth_header)

    settings = GenerationSettings(
        model=model or DEFAULT_LOCAL_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        context_window=context_window,
    )
    provider = (provider or "lmstudio").lower()

    if provider == "lmstudio":
        return LMStudioProvider(
            settings, base_url=base_url, api_key=api_key,
            extra_headers=parse_auth_header(auth_header), verify_tls=verify_tls,
        )
    if provider == "ollama":
        return OllamaProvider(settings)
    if provider == "openai":
        return OpenAIProvider(settings, api_key=api_key, base_url=base_url)
    if provider == "gemini":
        return GeminiProvider(settings, api_key=api_key, base_url=base_url)
    if provider == "anthropic":
        return AnthropicProvider(settings, api_key=api_key)

    raise ProviderError(f"Unknown provider: {provider}")


def build_provider_for(project: Any) -> BaseProvider:
    """Build the provider a ProjectConfig describes."""
    provider = getattr(project.ai_provider, "value", project.ai_provider)
    return build_provider(
        provider=str(provider),
        model=project.model_name,
        temperature=project.temperature,
        max_tokens=project.max_tokens,
        context_window=project.context_window,
        api_key=project.api_key,
        base_url=getattr(project, "lmstudio_base_url", None),
        auth_header=getattr(project, "local_auth_header", None),
        verify_tls=getattr(project, "local_verify_tls", True),
    )


# --- discovery ------------------------------------------------------------


def discover_models(provider: str, base_url: Optional[str] = None,
                    api_key: Optional[str] = None,
                    auth_header: Optional[str] = None,
                    timeout: float = 8.0) -> Dict[str, Any]:
    """Ask a provider what it actually serves.

    The hardcoded registry in ``models.py`` goes stale; this does not. For a
    local server it reports what is loaded right now, which is what an operator
    needs when a model name does not match.
    """
    provider = (provider or "").lower()
    api_key = resolve_secret(api_key)
    auth_header = resolve_secret(auth_header)

    endpoints = {
        "lmstudio": (base_url or LM_STUDIO_BASE_URL, api_key or LM_STUDIO_API_KEY),
        "openai": ("https://api.openai.com/v1", api_key or resolve_env("OPENAI_API_KEY")),
        "gemini": (base_url or GEMINI_BASE_URL,
                   api_key or resolve_env("GEMINI_API_KEY") or resolve_env("GOOGLE_API_KEY")),
    }

    if provider == "ollama":
        try:
            import ollama
            listed = ollama.list()
            models = [
                {"name": m.get("name", m.get("model", "")),
                 "display": m.get("name", m.get("model", "")),
                 "description": f"{round((m.get('size', 0) or 0) / 1e9, 1)} GB"}
                for m in listed.get("models", [])
            ]
            return {"available": True, "provider": provider, "models": models}
        except Exception as exc:
            return {"available": False, "provider": provider, "models": [],
                    "error": f"{type(exc).__name__}: {exc}",
                    "remedy": "Start Ollama with `ollama serve`."}

    if provider == "anthropic":
        # The Anthropic SDK has a models endpoint, but it needs a valid key; the
        # registry is a fine answer when there is no key to spend.
        try:
            from anthropic import Anthropic
            key = api_key or resolve_env("ANTHROPIC_API_KEY")
            if not key:
                raise ProviderError("no API key")
            listed = Anthropic(api_key=key).models.list()
            models = [{"name": m.id, "display": getattr(m, "display_name", m.id),
                       "description": ""} for m in listed.data]
            return {"available": True, "provider": provider, "models": models}
        except Exception as exc:
            return {"available": False, "provider": provider, "models": [],
                    "error": f"{type(exc).__name__}: {exc}"}

    if provider not in endpoints:
        return {"available": False, "provider": provider, "models": [],
                "error": f"unknown provider {provider!r}"}

    url, key = endpoints[provider]
    listing_url = url.rstrip("/") + "/models"

    try:
        import httpx
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        headers.update(parse_auth_header(auth_header))
        response = httpx.get(listing_url, headers=headers, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        remedy = None
        if provider == "lmstudio":
            remedy = ("Start the LM Studio local server and load a model. On a "
                      "headless server run `lms server start`. If this is a "
                      "tunneled server, check the tunnel and the auth header.")
        return {"available": False, "provider": provider, "base_url": url,
                "models": [], "error": f"{type(exc).__name__}: {exc}",
                "remedy": remedy}

    models = []
    for entry in data.get("data", []):
        model_id = entry.get("id")
        if not model_id:
            continue
        models.append({
            "name": model_id,
            "display": model_id,
            "description": entry.get("owned_by", ""),
            "tools": model_id not in NO_CHAT_COMPLETIONS_TOOLS,
        })

    return {"available": True, "provider": provider, "base_url": url, "models": models}


def list_lmstudio_models(base_url: Optional[str] = None,
                         auth_header: Optional[str] = None) -> Dict[str, Any]:
    """Backwards-compatible wrapper used by the existing API route."""
    result = discover_models("lmstudio", base_url=base_url, auth_header=auth_header)
    result.setdefault("base_url", base_url or LM_STUDIO_BASE_URL)
    return result


if __name__ == "__main__":
    for provider in ("lmstudio", "ollama"):
        result = discover_models(provider)
        print(f"{provider}: available={result['available']}")
        if not result["available"]:
            print(f"  {result.get('error')}")
            if result.get("remedy"):
                print(f"  remedy: {result['remedy']}")
        for model in result["models"][:5]:
            print(f"  - {model['name']}")
    print()
    print("auth header parse:", parse_auth_header("CF-Access-Client-Id: abc123"))
