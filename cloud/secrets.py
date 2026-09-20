"""
Secrets that are referenced rather than stored.

``config.json`` holds a project's whole configuration and gets copied, backed
up, and occasionally pasted into a support thread. An Anthropic key or a
Cloudflare tunnel credential sitting in it is a key that has effectively
already leaked. ROADMAP.md 2.4 says those belong in Secret Manager, and this is
how they get there without every deployment needing Google Cloud.

The shape is a URI in the place the value used to be:

    "api_key": "sm://projects/brookline/secrets/anthropic-key/versions/latest"

Anything without the ``sm://`` prefix is returned unchanged, which is what
makes this safe to put in the path of every configuration read: a community
that keeps its key in an environment variable on its own machine never notices
this module exists.

Decisions worth stating:

* **A reference can appear inside a larger string.** ``local_auth_header`` is a
  whole header line, so ``Authorization: Bearer sm://.../versions/latest``
  resolves the token and leaves the header alone.
* **Resolved values are cached, and so are failures.** A secret read per
  question would add a network round trip to every answer. A failure that is
  retried per question adds the same round trip and the same delay, every time,
  for a problem only an operator can fix, so it is remembered and reported once.
* **A secret that cannot be resolved returns nothing, not the URI.** Handing
  ``sm://...`` to a provider as an API key produces a confusing 401 somewhere
  else. Returning nothing produces the message the provider already has for a
  missing key, and the operator sees the real cause in the logs and in
  ``/api/admin/cloud-status``.

google-cloud-secret-manager is an optional import and is not in
``requirements.txt``.
"""

from __future__ import annotations

import os
import re
import threading
from typing import Any, Dict, Optional

from cloud import CloudUnavailable

SECRET_SCHEME = "sm://"
PROJECT_ENV = ("COMMUNITY_GCP_PROJECT", "GOOGLE_CLOUD_PROJECT", "GCP_PROJECT")

INSTALL_REMEDY = (
    "Install it with: pip install google-cloud-secret-manager  (or put the "
    "value itself in the configuration field instead of an sm:// reference)."
)

# The characters a Secret Manager resource name can contain. Stopping at a
# space is what lets a reference sit inside a header line.
_REFERENCE = re.compile(r"sm://[A-Za-z0-9/_.\-]+")

_cache: Dict[str, str] = {}
_failures: Dict[str, str] = {}
_lock = threading.Lock()
_resolved_count = 0


def is_secret_uri(value: Any) -> bool:
    return isinstance(value, str) and value.strip().startswith(SECRET_SCHEME)


def gcp_project() -> str:
    for name in PROJECT_ENV:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return ""


def parse_secret_uri(uri: str) -> str:
    """Turn a reference into a Secret Manager resource name.

    Accepts the full form, the form without a version, and the short form that
    names only the secret and takes the project from the environment. The
    project is not guessed from anything else: a key read out of the wrong
    project is a security incident, not a convenience.
    """
    text = (uri or "").strip()
    if not text.startswith(SECRET_SCHEME):
        raise ValueError(f"not a secret reference: {uri!r}")

    body = text[len(SECRET_SCHEME):].strip("/")
    if not body:
        raise ValueError(
            "empty secret reference. Use "
            "sm://projects/PROJECT/secrets/NAME/versions/latest"
        )

    if body.startswith("projects/"):
        parts = body.split("/")
        if len(parts) == 4 and parts[2] == "secrets":
            return f"{body}/versions/latest"
        if len(parts) == 6 and parts[2] == "secrets" and parts[4] == "versions":
            return body
        raise ValueError(
            f"malformed secret reference {uri!r}. Use "
            f"sm://projects/PROJECT/secrets/NAME/versions/latest"
        )

    project = gcp_project()
    if not project:
        raise ValueError(
            f"{uri!r} names a secret but not a project, and none of "
            f"{', '.join(PROJECT_ENV)} is set. Either set one or write the "
            f"full form: sm://projects/PROJECT/secrets/NAME/versions/latest"
        )

    parts = body.split("/")
    name = parts[0]
    version = parts[2] if len(parts) >= 3 and parts[1] == "versions" else "latest"
    return f"projects/{project}/secrets/{name}/versions/{version}"


def _client() -> Any:
    try:
        from google.cloud import secretmanager
    except ImportError as exc:
        raise CloudUnavailable(
            "A configuration value is an sm:// reference but the "
            "'google-cloud-secret-manager' package is not installed.",
            remedy=INSTALL_REMEDY,
        ) from exc
    try:
        return secretmanager.SecretManagerServiceClient()
    except Exception as exc:
        raise CloudUnavailable(
            f"Could not open a Secret Manager client: {type(exc).__name__}: {exc}",
            remedy=("Give the service account the Secret Manager Secret "
                    "Accessor role, or run `gcloud auth application-default "
                    "login` locally."),
        ) from exc


def _fetch(resource: str) -> str:
    response = _client().access_secret_version(request={"name": resource})
    return response.payload.data.decode("utf-8").strip()


def resolve_secret(value: Any, default: Optional[str] = None) -> Any:
    """Resolve any ``sm://`` reference in ``value``. Anything else passes through.

    Never raises. A value that cannot be resolved becomes ``default`` and the
    reason is printed once and reported by ``/api/admin/cloud-status``, because
    a resident's question must not fail over a configuration problem.
    """
    global _resolved_count
    if not isinstance(value, str) or SECRET_SCHEME not in value:
        return value

    stripped = value.strip()
    if stripped.startswith(SECRET_SCHEME) and " " not in stripped:
        resolved = _resolve_one(stripped)
        if resolved is None:
            return default
        with _lock:
            _resolved_count += 1
        return resolved

    # A reference embedded in a larger string, such as a whole header line.
    failed = False

    def substitute(match: "re.Match[str]") -> str:
        nonlocal failed
        resolved = _resolve_one(match.group(0))
        if resolved is None:
            failed = True
            return match.group(0)
        return resolved

    rendered = _REFERENCE.sub(substitute, value)
    if failed:
        return default
    with _lock:
        _resolved_count += 1
    return rendered


def _resolve_one(reference: str) -> Optional[str]:
    try:
        resource = parse_secret_uri(reference)
    except ValueError as exc:
        _remember_failure(reference, str(exc), remedy="")
        return None

    with _lock:
        if resource in _cache:
            return _cache[resource]
        if resource in _failures:
            return None

    try:
        value = _fetch(resource)
    except CloudUnavailable as exc:
        _remember_failure(resource, exc.message, exc.remedy)
        return None
    except Exception as exc:
        _remember_failure(
            resource, f"{type(exc).__name__}: {exc}",
            remedy=("Check the secret exists and that the service account has "
                    "the Secret Manager Secret Accessor role on it."),
        )
        return None

    with _lock:
        _cache[resource] = value
    return value


def _remember_failure(resource: str, detail: str, remedy: str) -> None:
    with _lock:
        first = resource not in _failures
        _failures[resource] = f"{detail} {remedy}".strip()
    if first:
        print(f"[cloud.secrets] Could not resolve {resource}: {detail} {remedy}".rstrip())


def resolve_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read an environment variable, resolving an ``sm://`` value in it."""
    raw = os.getenv(name)
    if raw is None:
        return default
    resolved = resolve_secret(raw, default)
    return resolved if resolved is not None else default


def clear_cache() -> None:
    """Forget resolved values and remembered failures. For tests and reloads."""
    global _resolved_count
    with _lock:
        _cache.clear()
        _failures.clear()
        _resolved_count = 0


def secrets_status() -> Dict[str, Any]:
    """Whether anything is being read from Secret Manager, and what failed.

    Unlike the other backends there is no variable to read: a reference lives
    in a configuration field, so this reports what this process has actually
    been asked to resolve rather than what was configured somewhere.
    """
    with _lock:
        resolved, failures = _resolved_count, dict(_failures)

    try:
        from google.cloud import secretmanager  # noqa: F401
        available = True
    except ImportError:
        available = False

    if not (resolved or failures):
        return {
            "backend": "plain",
            "configured": False,
            "active": True,
            "available": available,
            "gcp_project": gcp_project(),
            "resolved_values": 0,
            "failures": {},
            "detail": ("Configuration values are used as written. No sm:// "
                       "references have been seen."),
            "remedy": None,
        }

    healthy = available and not failures
    return {
        "backend": "secret-manager" if healthy else "plain",
        "configured": True,
        "active": healthy,
        "available": available,
        "gcp_project": gcp_project(),
        "resolved_values": resolved,
        "failures": failures,
        "detail": (
            "Secrets are read from Secret Manager and cached for this process."
            if healthy else
            "An sm:// reference could not be resolved, so that value is missing."
        ),
        "remedy": None if healthy else (
            INSTALL_REMEDY if not available else
            "See the failures above. Resolved values and failures are both "
            "cached until the service restarts."
        ),
    }


if __name__ == "__main__":
    print("plain value passes through:", resolve_secret("sk-ant-example"))
    print("None passes through:", resolve_secret(None))
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "brookline")
    print("short form:", parse_secret_uri("sm://anthropic-key"))
    print("full form:", parse_secret_uri(
        "sm://projects/brookline/secrets/anthropic-key/versions/3"))
    print("no version:", parse_secret_uri("sm://projects/brookline/secrets/tunnel"))
    print("unresolvable reference becomes:", repr(
        resolve_secret("sm://projects/brookline/secrets/absent/versions/latest")))
    print("status:", secrets_status()["detail"])
