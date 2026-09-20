"""
Optional Google Cloud backends.

Everything in this package is a second implementation of something the system
already does on one machine: rate limits, uploaded files, secrets, request
logs. The local implementation stays the default and stays supported, because
the deployment this project is built around is a computer in a community's own
building, and a town should never be made to open a Google Cloud account to run
its own assistant.

So each module here follows the same three rules:

* **One environment variable turns it on.** ``COMMUNITY_REDIS_URL``,
  ``COMMUNITY_STORAGE_BUCKET``, ``sm://`` in a config field,
  ``COMMUNITY_CLOUD_LOGGING``. Unset means local, which is why a machine that
  has never heard of Google Cloud runs the tests and the app unchanged.
* **The client libraries are optional imports and are not in
  ``requirements.txt``.** A missing library is an operator's configuration
  mistake, not a resident's problem: it degrades to the local backend and says
  what to install.
* **A cloud failure is never a failed answer.** Redis going away costs the
  community cross-instance rate limits, not its assistant.

The one thing an operator cannot see from the outside is which of those
fallbacks are in effect, because a misconfigured cloud deployment looks exactly
like a working local one. :func:`cloud_status` is the answer to that, and
``/api/admin/cloud-status`` publishes it.

The submodules are imported where they are used rather than re-exported here,
so one backend failing to import cannot take the others down with it.
"""

from __future__ import annotations

from typing import Any, Dict


class CloudUnavailable(RuntimeError):
    """A cloud backend was asked for and cannot be provided.

    Carries a ``remedy`` because the person who sees this message is an
    operator who can fix it, and "ImportError: no module named redis" is not an
    instruction.
    """

    def __init__(self, message: str, remedy: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.remedy = remedy

    def __str__(self) -> str:
        return f"{self.message} {self.remedy}".strip()


def cloud_status() -> Dict[str, Any]:
    """Which backend is actually serving each piece, and why.

    Reports the live objects where it can rather than re-reading the
    environment, because the question an operator is asking is not "what did I
    configure" but "what is running". A backend that was configured and then
    fell back reports ``configured: true, active: false`` with the reason.
    """
    from cloud.logging_sink import logging_status
    from cloud.secrets import secrets_status
    from cloud.storage import storage_status

    sections: Dict[str, Any] = {
        "rate_limits": _live_rate_limit_status(),
        "storage": storage_status(),
        "secrets": secrets_status(),
        "request_logs": logging_status(),
    }
    return {
        "cloud_configured": any(s.get("configured") for s in sections.values()),
        "cloud_active": any(s.get("configured") and s.get("active")
                            for s in sections.values()),
        "degraded": [name for name, s in sections.items()
                     if s.get("configured") and not s.get("active")],
        **sections,
    }


def _live_rate_limit_status() -> Dict[str, Any]:
    """Ask the gateway's limiter what it is, not the environment.

    The limiter is chosen once at import and can have fallen back since, so the
    object knows something the environment does not.
    """
    try:
        from api.auth import rate_limiter_status
        return rate_limiter_status()
    except Exception as exc:                       # pragma: no cover - defensive
        from cloud.ratelimit import ratelimit_status

        status = ratelimit_status()
        status["detail"] = f"{status.get('detail', '')} ({type(exc).__name__}: {exc})".strip()
        return status


__all__ = ["CloudUnavailable", "cloud_status"]
