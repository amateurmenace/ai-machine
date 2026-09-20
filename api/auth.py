"""
Gateway authentication, application permissions, and rate limits.

Section 12 of the guide is blunt: do not expose LM Studio directly to the public
internet, put your own gateway in front of it. This module is the part of that
gateway that decides who is calling and whether they may.

Design choices worth stating:

* **Keys are stored hashed.** A leaked ``config.json`` should not hand an
  attacker a working key. The plaintext key is shown once at creation.
* **One key per application.** Section 13 lists app permissions as a gateway
  concern. With a single shared key, revoking a misbehaving application breaks
  every other one.
* **Comparison is constant-time.** Key checks use :func:`hmac.compare_digest`,
  because an ordinary string comparison leaks the key a character at a time.
* **Rate limits are per client.** A community server running a 26B model has
  roughly one generation in flight at a time; an unthrottled script can deny
  service to residents without meaning to.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

KEY_PREFIX = "cai"          # community AI
KEY_BYTES = 32

# Scopes an application key can hold.
SCOPE_ASK = "ask"           # generate answers (costs inference)
SCOPE_SEARCH = "search"     # retrieval only, no generation
SCOPE_READ = "read"         # read sources, meetings, documents, metadata
SCOPE_ADMIN = "admin"       # manage keys and configuration
ALL_SCOPES = (SCOPE_ASK, SCOPE_SEARCH, SCOPE_READ, SCOPE_ADMIN)
DEFAULT_SCOPES = (SCOPE_ASK, SCOPE_SEARCH, SCOPE_READ)


def generate_key() -> Tuple[str, str, str]:
    """Create a key. Returns ``(plaintext, sha256_hash, display_prefix)``."""
    secret = secrets.token_urlsafe(KEY_BYTES)
    plaintext = f"{KEY_PREFIX}_{secret}"
    return plaintext, hash_key(plaintext), plaintext[: len(KEY_PREFIX) + 9]


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def keys_match(presented: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_key(presented), stored_hash)


@dataclass
class Principal:
    """The authenticated caller of a gateway request."""

    project_id: str
    client_id: str
    name: str
    scopes: Tuple[str, ...] = DEFAULT_SCOPES
    rate_limit_per_minute: int = 60
    legacy: bool = False       # authenticated via the old single project key

    def may(self, scope: str) -> bool:
        return SCOPE_ADMIN in self.scopes or scope in self.scopes


class AuthError(Exception):
    """Authentication or authorization failure, with an HTTP status."""

    def __init__(self, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def extract_key(authorization: Optional[str], x_api_key: Optional[str]) -> Optional[str]:
    """Read the key from ``Authorization: Bearer`` or ``X-API-Key``.

    Bearer is what the OpenAI SDK sends, which is what makes an existing
    application able to switch to the community server by changing a base URL.
    """
    if authorization:
        parts = authorization.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            candidate = parts[1].strip()
            if candidate:
                return candidate
    if x_api_key:
        return x_api_key.strip()
    return None


def authenticate(project: Any, presented_key: Optional[str]) -> Principal:
    """Authenticate a key against a project's registered clients.

    Raises :class:`AuthError` rather than returning None, so a caller cannot
    forget to check the result.
    """
    if not getattr(project, "api_enabled", False):
        raise AuthError(
            "The community API is not enabled for this project. Enable it in "
            "Settings and issue an application key.",
            status_code=403,
        )

    if not presented_key:
        raise AuthError(
            "Missing API key. Send it as 'Authorization: Bearer <key>' or "
            "'X-API-Key: <key>'."
        )

    for client in getattr(project, "api_clients", None) or []:
        if not getattr(client, "enabled", True):
            continue
        if keys_match(presented_key, client.key_hash):
            return Principal(
                project_id=project.project_id,
                client_id=client.client_id,
                name=client.name,
                scopes=tuple(client.scopes or DEFAULT_SCOPES),
                rate_limit_per_minute=int(client.rate_limit_per_minute or 60),
            )

    # The single project-wide key predates per-application keys. It is stored in
    # plaintext by the original implementation, so it is compared in constant
    # time and given the default scopes.
    legacy_key = getattr(project, "project_api_key", None)
    if legacy_key and hmac.compare_digest(presented_key, legacy_key):
        return Principal(
            project_id=project.project_id,
            client_id="legacy-project-key",
            name="Project key",
            scopes=DEFAULT_SCOPES,
            rate_limit_per_minute=60,
            legacy=True,
        )

    raise AuthError("Invalid API key.")


def require(principal: Principal, scope: str) -> None:
    if not principal.may(scope):
        raise AuthError(
            f"This application key does not have the '{scope}' permission.",
            status_code=403,
        )


class RateLimiter:
    """A fixed-window rate limiter, keyed by client.

    A fixed window rather than a token bucket because the numbers involved are
    small and an operator reading the logs should be able to reason about it.
    In-memory, so limits reset on restart and are per-process; a deployment
    running several workers should move this to Redis, which is noted in the
    setup guide rather than pretended away.
    """

    def __init__(self, window_seconds: int = 60) -> None:
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._windows: Dict[str, Tuple[float, int]] = {}

    def check(self, key: str, limit: int) -> Tuple[bool, int, int]:
        """Record a request. Returns ``(allowed, remaining, retry_after)``."""
        if limit <= 0:
            return True, -1, 0

        now = time.time()
        with self._lock:
            window_start, count = self._windows.get(key, (now, 0))
            if now - window_start >= self.window_seconds:
                window_start, count = now, 0

            if count >= limit:
                retry_after = int(self.window_seconds - (now - window_start)) + 1
                self._windows[key] = (window_start, count)
                return False, 0, max(retry_after, 1)

            count += 1
            self._windows[key] = (window_start, count)
            return True, max(limit - count, 0), 0

    def reset(self, key: Optional[str] = None) -> None:
        with self._lock:
            if key is None:
                self._windows.clear()
            else:
                self._windows.pop(key, None)


# One limiter per process, shared by all gateway routes.
rate_limiter = RateLimiter()


def new_client_record(name: str, scopes: Optional[List[str]] = None,
                      rate_limit_per_minute: int = 60) -> Tuple[Dict[str, Any], str]:
    """Build an APIClient payload plus the plaintext key to show once."""
    plaintext, key_hash, prefix = generate_key()
    record = {
        "client_id": secrets.token_hex(8),
        "name": name,
        "key_hash": key_hash,
        "key_prefix": prefix,
        "scopes": list(scopes or DEFAULT_SCOPES),
        "rate_limit_per_minute": rate_limit_per_minute,
        "enabled": True,
    }
    return record, plaintext


if __name__ == "__main__":
    plaintext, key_hash, prefix = generate_key()
    print("key:", plaintext)
    print("prefix:", prefix)
    print("matches:", keys_match(plaintext, key_hash))
    print("wrong key matches:", keys_match("cai_wrong", key_hash))

    limiter = RateLimiter(window_seconds=60)
    results = [limiter.check("demo", 3)[0] for _ in range(5)]
    print("rate limit (limit 3, 5 requests):", results)
