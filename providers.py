"""
Inference providers.

Section 12 of the community-owned AI guide puts a local LM Studio server at the
center of the architecture: it already speaks the OpenAI-compatible protocol, so
applications can point at a town's own hardware with the same code they used for
a commercial API.

This module adds LM Studio alongside the existing Ollama / OpenAI / Anthropic
providers and gives all four one calling convention, so the answer pipeline does
not branch on provider.

The guide is also emphatic that LM Studio must not face the internet directly.
Nothing here exposes it; the gateway in ``api/`` is the only public surface, and
it holds authentication, rate limits, and logging.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# LM Studio's default local server address. Override for a headless server on
# another host inside the community's own network.
LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")

# LM Studio does not check the key, but the OpenAI SDK requires one to be set.
LM_STUDIO_API_KEY = os.getenv("LM_STUDIO_API_KEY", "lm-studio")

DEFAULT_LOCAL_MODEL = os.getenv("COMMUNITY_MODEL", "gemma-4-26b-a4b")


class ProviderError(RuntimeError):
    """Raised with a message meant to be shown to an operator, not a stack trace."""


@dataclass
class GenerationSettings:
    model: str
    temperature: float = 0.7
    max_tokens: int = 2000
    context_window: int = 8192


class BaseProvider:
    """One method: turn a PromptBundle into text."""

    name = "base"

    def __init__(self, settings: GenerationSettings) -> None:
        self.settings = settings

    def complete(self, prompt: Any) -> str:
        raise NotImplementedError

    def raw_chat(self, messages: List[Dict[str, str]],
                 max_tokens: Optional[int] = None) -> str:
        """Plain chat with no constitution or retrieval, for query rewriting."""
        raise NotImplementedError

    def health(self) -> Dict[str, Any]:
        return {"provider": self.name, "reachable": None, "detail": "no health check"}


class OpenAICompatibleProvider(BaseProvider):
    """Any server speaking the OpenAI chat-completions protocol.

    Covers LM Studio, OpenAI itself, and other local servers such as llama.cpp's
    or vLLM's OpenAI-compatible modes. The only difference between them is the
    base URL and the key.
    """

    name = "openai-compatible"

    def __init__(self, settings: GenerationSettings, base_url: Optional[str] = None,
                 api_key: Optional[str] = None, timeout: float = 180.0) -> None:
        super().__init__(settings)
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self._client = None

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
            self._client = OpenAI(**kwargs)
        return self._client

    def complete(self, prompt: Any) -> str:
        messages = prompt.as_openai_messages() if hasattr(prompt, "as_openai_messages") else prompt
        return self.raw_chat(messages)

    def raw_chat(self, messages: List[Dict[str, str]],
                 max_tokens: Optional[int] = None) -> str:
        response = self.client.chat.completions.create(
            model=self.settings.model,
            messages=messages,
            temperature=self.settings.temperature,
            max_tokens=max_tokens or self.settings.max_tokens,
        )
        return response.choices[0].message.content or ""

    def health(self) -> Dict[str, Any]:
        try:
            models = self.client.models.list()
            names = [m.id for m in getattr(models, "data", [])]
            return {
                "provider": self.name,
                "reachable": True,
                "base_url": self.base_url,
                "models_loaded": names,
                "configured_model": self.settings.model,
                "configured_model_loaded": self.settings.model in names if names else None,
            }
        except Exception as exc:
            return {
                "provider": self.name,
                "reachable": False,
                "base_url": self.base_url,
                "detail": f"{type(exc).__name__}: {exc}",
            }


class LMStudioProvider(OpenAICompatibleProvider):
    """A local LM Studio server, desktop or headless."""

    name = "lmstudio"

    def __init__(self, settings: GenerationSettings, base_url: Optional[str] = None,
                 api_key: Optional[str] = None) -> None:
        super().__init__(
            settings,
            base_url=base_url or LM_STUDIO_BASE_URL,
            api_key=api_key or LM_STUDIO_API_KEY,
        )

    def health(self) -> Dict[str, Any]:
        status = super().health()
        if not status.get("reachable"):
            status["remedy"] = (
                f"LM Studio is not answering at {self.base_url}. Start the local "
                f"server (Developer tab -> Start Server, or `lms server start` "
                f"for a headless install) and load a model."
            )
        elif status.get("configured_model_loaded") is False:
            loaded = ", ".join(status.get("models_loaded") or []) or "none"
            status["remedy"] = (
                f"LM Studio is running but '{self.settings.model}' is not loaded. "
                f"Loaded: {loaded}. Load it in LM Studio, or set the project's "
                f"model to one of the loaded identifiers."
            )
        return status


class OllamaProvider(BaseProvider):
    name = "ollama"

    def complete(self, prompt: Any) -> str:
        messages = prompt.as_openai_messages() if hasattr(prompt, "as_openai_messages") else prompt
        return self.raw_chat(messages)

    def raw_chat(self, messages: List[Dict[str, str]],
                 max_tokens: Optional[int] = None) -> str:
        try:
            import ollama
        except ImportError as exc:
            raise ProviderError("The 'ollama' package is not installed.") from exc

        # Ollama accepts a single leading system message reliably; several are
        # merged so constitution and context both survive.
        merged = _merge_system_messages(messages)
        try:
            response = ollama.chat(
                model=self.settings.model,
                messages=merged,
                options={
                    "temperature": self.settings.temperature,
                    "num_ctx": self.settings.context_window,
                },
            )
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
        return response["message"]["content"]

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
            }
        except Exception as exc:
            return {
                "provider": self.name,
                "reachable": False,
                "detail": f"{type(exc).__name__}: {exc}",
                "remedy": "Start Ollama with `ollama serve`.",
            }


class AnthropicProvider(BaseProvider):
    name = "anthropic"

    def __init__(self, settings: GenerationSettings, api_key: Optional[str] = None) -> None:
        super().__init__(settings)
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._client = None

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

    def complete(self, prompt: Any) -> str:
        if hasattr(prompt, "as_anthropic_messages"):
            system, messages = prompt.as_anthropic_messages()
        else:
            system, messages = _split_system(prompt)
        response = self.client.messages.create(
            model=self.settings.model,
            max_tokens=self.settings.max_tokens,
            temperature=self.settings.temperature,
            system=system,
            messages=messages,
        )
        return response.content[0].text

    def raw_chat(self, messages: List[Dict[str, str]],
                 max_tokens: Optional[int] = None) -> str:
        system, turns = _split_system(messages)
        response = self.client.messages.create(
            model=self.settings.model,
            max_tokens=max_tokens or self.settings.max_tokens,
            temperature=self.settings.temperature,
            system=system or "You are a helpful assistant.",
            messages=turns,
        )
        return response.content[0].text

    def health(self) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "reachable": bool(self.api_key),
            "detail": "API key present" if self.api_key else "no API key configured",
        }


# --- helpers --------------------------------------------------------------


def _merge_system_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    system_parts = [m["content"] for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]
    if not system_parts:
        return rest
    return [{"role": "system", "content": "\n\n".join(system_parts)}] + rest


def _split_system(messages: List[Dict[str, str]]) -> Tuple[str, List[Dict[str, str]]]:
    system_parts = [m["content"] for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]
    return "\n\n".join(system_parts), rest


PROVIDER_LABELS = {
    "lmstudio": "LM Studio (local)",
    "ollama": "Ollama (local)",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
}


def build_provider(
    provider: str,
    model: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    context_window: int = 8192,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> BaseProvider:
    """Construct the provider for a project's configuration."""
    settings = GenerationSettings(
        model=model or DEFAULT_LOCAL_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        context_window=context_window,
    )
    provider = (provider or "ollama").lower()

    if provider == "lmstudio":
        return LMStudioProvider(settings, base_url=base_url, api_key=api_key)
    if provider == "ollama":
        return OllamaProvider(settings)
    if provider == "openai":
        return OpenAICompatibleProvider(
            settings,
            base_url=base_url,
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
        )
    if provider == "anthropic":
        return AnthropicProvider(settings, api_key=api_key)

    raise ProviderError(f"Unknown provider: {provider}")


def list_lmstudio_models(base_url: Optional[str] = None) -> Dict[str, Any]:
    """Ask a local LM Studio server which models it has loaded."""
    url = (base_url or LM_STUDIO_BASE_URL).rstrip("/") + "/models"
    try:
        import httpx
        response = httpx.get(url, timeout=5.0)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return {
            "available": False,
            "base_url": base_url or LM_STUDIO_BASE_URL,
            "models": [],
            "error": f"{type(exc).__name__}: {exc}",
            "remedy": (
                "Start the LM Studio local server and load a model. On a "
                "headless server run `lms server start`."
            ),
        }

    models = []
    for entry in data.get("data", []):
        model_id = entry.get("id")
        if not model_id:
            continue
        models.append({
            "name": model_id,
            "display": model_id,
            "description": entry.get("owned_by", "loaded in LM Studio"),
        })

    return {
        "available": True,
        "base_url": base_url or LM_STUDIO_BASE_URL,
        "models": models,
    }


if __name__ == "__main__":
    print("LM Studio base URL:", LM_STUDIO_BASE_URL)
    result = list_lmstudio_models()
    print("available:", result["available"])
    if not result["available"]:
        print("error:", result.get("error"))
        print("remedy:", result.get("remedy"))
    else:
        for m in result["models"]:
            print("  -", m["name"])
