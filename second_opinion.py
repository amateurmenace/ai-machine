"""
Asking a frontier model, on purpose and in the open.

Section 1.3 of the roadmap, and the part of it that says what NOT to build:
**not** automatic routing by difficulty. Automatic routing sends a resident's
question to a frontier provider without them knowing, which is precisely the
property this project exists to avoid. A system that quietly forwards the hard
questions to Anthropic is not a locally governed system; it is a proxy with
extra steps.

So the control is a button, and the button says where the question is going.

    Answered locally by Gemma 4 26B.
    [ Ask a frontier model too ]  — this sends your question to Anthropic

The disclosure is the feature. A resident asking about a zoning bylaw gets a
local answer. A resident asking for help drafting a grant proposal can decide
for themselves whether that is worth sending out. Neither decision is made for
them.

Two design choices worth stating:

* **Retrieval is reused, not repeated.** The second opinion sees exactly the
  passages the first answer saw. That makes the comparison about the model,
  which is the thing being compared, and it means the community's archive is
  searched once rather than twice.
* **The constitution still applies.** A frontier model answering a civic
  question is bound by the same rules, cited the same way, and its answer
  carries the same provenance. A second opinion is not an escape hatch from
  governance.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from providers import PROVIDER_LABELS, ProviderError, build_provider

# Which company receives the question, in words a resident can act on. Naming
# the operator rather than the model is deliberate: "Gemini" is a product,
# "Google" is who ends up holding the question.
PROVIDER_RECIPIENTS = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "gemini": "Google",
    "lmstudio": "nobody: this runs on hardware your community owns",
    "ollama": "nobody: this runs on hardware your community owns",
}

# Sensible default model per provider when the operator has not chosen one.
DEFAULT_MODELS = {
    "anthropic": "claude-opus-5",
    "openai": "gpt-5.5",
    "gemini": "gemini-3.1-pro",
}

_ENV_KEYS = {
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
}


@dataclass
class SecondOpinionOption:
    """A provider a resident could choose to ask."""

    provider: str
    label: str
    model: str
    recipient: str
    local: bool = False
    configured: bool = False
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _key_for(provider: str, project: Any) -> Optional[str]:
    """Find a usable key, preferring the project's own over the environment's."""
    configured_provider = str(
        getattr(project.ai_provider, "value", project.ai_provider)
    ).lower()
    if configured_provider == provider and getattr(project, "api_key", None):
        return project.api_key

    extra = getattr(project, "second_opinion_keys", None) or {}
    if isinstance(extra, dict) and extra.get(provider):
        return extra[provider]

    for name in _ENV_KEYS.get(provider, ()):
        value = os.getenv(name)
        if value:
            return value
    return None


def available_options(project: Any) -> List[SecondOpinionOption]:
    """Which second opinions this deployment can actually offer.

    A provider with no key is listed anyway, marked unconfigured, so an operator
    looking at the console can see what is missing rather than wondering why a
    button is absent.
    """
    primary = str(getattr(project.ai_provider, "value", project.ai_provider)).lower()
    options: List[SecondOpinionOption] = []

    for provider in ("anthropic", "openai", "gemini"):
        if provider == primary:
            # Offering the model that just answered as a second opinion on
            # itself would be theatre.
            continue
        key = _key_for(provider, project)
        options.append(SecondOpinionOption(
            provider=provider,
            label=PROVIDER_LABELS.get(provider, provider),
            model=DEFAULT_MODELS.get(provider, ""),
            recipient=PROVIDER_RECIPIENTS.get(provider, provider),
            local=False,
            configured=bool(key),
            reason="" if key else (
                f"no API key configured for {provider}. Add one in Settings or "
                f"set {_ENV_KEYS.get(provider, ('an API key',))[0]}."
            ),
        ))

    return options


@dataclass
class SecondOpinion:
    provider: str
    model: str
    recipient: str
    answer: str = ""
    sources: List[Dict[str, Any]] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    disclosure: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def ask(project: Any, agent: Any, question: str, provider: str,
        model: str = "", history: Optional[List[Dict[str, str]]] = None
        ) -> SecondOpinion:
    """Answer one question with a different provider, reusing the same evidence.

    ``agent`` supplies the pipeline, the constitution and the retriever, so the
    second opinion is governed identically and reads the same passages. Only the
    model changes.
    """
    provider = (provider or "").lower()
    model = model or DEFAULT_MODELS.get(provider, "")
    recipient = PROVIDER_RECIPIENTS.get(provider, provider)

    opinion = SecondOpinion(
        provider=provider,
        model=model,
        recipient=recipient,
        disclosure=(
            f"This question and the community records retrieved for it were sent "
            f"to {recipient}."
        ),
    )

    if provider not in DEFAULT_MODELS:
        opinion.error = (
            f"{provider!r} is not available as a second opinion. Choose one of: "
            f"{', '.join(sorted(DEFAULT_MODELS))}."
        )
        return opinion

    key = _key_for(provider, project)
    if not key:
        opinion.error = (
            f"No API key is configured for {provider}. A second opinion cannot "
            f"be requested until one is."
        )
        return opinion

    try:
        other = build_provider(
            provider=provider,
            model=model,
            temperature=getattr(project, "temperature", 0.3),
            max_tokens=getattr(project, "max_tokens", 2000),
            context_window=getattr(project, "context_window", 8192),
            api_key=key,
        )
    except ProviderError as exc:
        opinion.error = str(exc)
        return opinion

    try:
        result = agent.pipeline.answer(
            question,
            generate=other.complete,
            history=history or [],
            use_reranker=getattr(project, "enable_reranking", True),
            enforce_citations=getattr(project, "require_citations", True),
            expand=getattr(project, "enable_query_expansion", True),
        )
    except Exception as exc:
        opinion.error = f"{type(exc).__name__}: {exc}"
        return opinion

    if result.error:
        opinion.error = result.error
        return opinion

    provenance = result.provenance.to_dict()
    provenance["second_opinion"] = True
    provenance["recipient"] = recipient
    # Overwrite rather than trust the pipeline's defaults: the pipeline was
    # built around the project's primary provider and would otherwise report it.
    provenance["provider"] = provider
    provenance["model"] = model

    opinion.answer = result.answer
    opinion.sources = result.sources_payload()
    opinion.provenance = provenance
    return opinion


def compare(local_answer: Dict[str, Any], opinion: SecondOpinion) -> Dict[str, Any]:
    """Describe how the two answers differ, without judging which is right.

    Deliberately mechanical. An automated verdict on which answer is better
    would be a third model's opinion presented as fact, and Principle 15 asks
    the system to help people understand tradeoffs rather than decide for them.
    """
    local_provenance = local_answer.get("provenance", {}) or {}
    local_sources = {s.get("id") for s in local_answer.get("sources", []) if s.get("used")}
    other_sources = {s.get("id") for s in opinion.sources if s.get("used")}

    return {
        "local": {
            "model": local_provenance.get("model"),
            "provider": local_provenance.get("provider"),
            "sources_used": local_provenance.get("sources_used"),
            "length": len(local_answer.get("answer", "")),
        },
        "second_opinion": {
            "model": opinion.model,
            "provider": opinion.provider,
            "recipient": opinion.recipient,
            "sources_used": opinion.provenance.get("sources_used"),
            "length": len(opinion.answer),
        },
        "cited_the_same_sources": local_sources == other_sources and bool(local_sources),
        "sources_only_local_used": sorted(s for s in local_sources - other_sources if s),
        "sources_only_other_used": sorted(s for s in other_sources - local_sources if s),
        "note": (
            "Both answers were produced under the same constitution and from the "
            "same retrieved records. Where they differ, the difference is the "
            "model, not the evidence."
        ),
    }
