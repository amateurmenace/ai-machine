"""
Rate limits that survive more than one instance.

``api.auth.RateLimiter`` counts requests inside one process, which is exactly
right for the deployment this project is built around and exactly wrong the
moment Cloud Run runs four instances: each one enforces the full limit, so a
community that configured sixty requests a minute is serving two hundred and
forty. ROADMAP.md 2.4 names this, and this module is the fix.

Four decisions worth stating:

* **The same fixed window, not a better algorithm.** A token bucket would be
  smoother. It would also mean an operator reading a 429 in the logs has to
  reason about drip rates to know what happened. The numbers here are small and
  the local limiter is a fixed window, so this is a fixed window, and the two
  backends answer identically.
* **The window is aligned to the clock and the counter key carries it.** Every
  instance derives the same key from the same wall clock, so they count into
  the same number without coordinating. The key expires with its window, so
  nothing accumulates.
* **Counting is one atomic operation.** ``INCR`` then ``EXPIRE`` as two
  commands can leave a key with no expiry if the process dies between them, and
  that key throttles a client forever. A Lua script makes it one step. Managed
  Redis instances that refuse ``EVAL`` fall back to the two commands, which
  also repair a key found without a TTL.
* **A Redis outage degrades to per-process limits.** Failing closed would turn
  a blip in a cache into a town's assistant refusing to answer, which is the
  one outcome this project will not accept. Failing open would leave a 26B
  model on someone's desk unprotected. Falling back to the in-memory limiter
  keeps the protection and loses only the part that needed Redis, and
  ``/api/admin/cloud-status`` reports that it happened.

redis-py is an optional import and is not in ``requirements.txt``. A community
running on one machine should never have to install it.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

from cloud import CloudUnavailable

REDIS_URL_ENV = "COMMUNITY_REDIS_URL"
DEFAULT_KEY_PREFIX = "community-ai:ratelimit"

INSTALL_REMEDY = (
    "Install it with: pip install redis  (or unset "
    f"{REDIS_URL_ENV} to keep per-process rate limits)."
)

# INCR, set the expiry only on the request that created the window, and report
# the time left. One round trip, and no window can outlive its TTL.
_WINDOW_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return {count, redis.call('TTL', KEYS[1])}
"""


def redis_url() -> str:
    """The configured Redis URL, or an empty string for per-process limits."""
    return (os.getenv(REDIS_URL_ENV) or "").strip()


def safe_url(url: str) -> str:
    """A URL with any password removed, for logs and the status endpoint."""
    if "@" not in url:
        return url
    scheme, _, rest = url.partition("://")
    credentials, _, host = rest.rpartition("@")
    user = credentials.split(":")[0]
    return f"{scheme}://{user + ':***@' if user else ''}{host}"


def connect(url: str, timeout: float = 2.0) -> Any:
    """Open and check a Redis connection, or explain why not.

    The check happens here, at startup, because an operator reading a boot log
    can fix a wrong URL and a resident hitting a 500 cannot.
    """
    try:
        import redis
    except ImportError as exc:
        raise CloudUnavailable(
            f"{REDIS_URL_ENV} is set but the 'redis' package is not installed.",
            remedy=INSTALL_REMEDY,
        ) from exc

    try:
        client = redis.Redis.from_url(
            url, decode_responses=True,
            socket_timeout=timeout, socket_connect_timeout=timeout,
        )
        client.ping()
    except Exception as exc:
        raise CloudUnavailable(
            f"Could not reach Redis at {safe_url(url)}: {type(exc).__name__}: {exc}",
            remedy=(
                "Check the Memorystore instance is running and that Cloud Run "
                "has a VPC connector to reach it, or unset "
                f"{REDIS_URL_ENV} to keep per-process rate limits."
            ),
        ) from exc
    return client


class RedisRateLimiter:
    """A fixed-window rate limiter shared by every instance.

    Same interface as :class:`api.auth.RateLimiter`: ``check(key, limit)``
    returns ``(allowed, remaining, retry_after)``, and the two are
    interchangeable on purpose, so the gateway never learns which one it has.

    ``clock`` exists so the window can be advanced in a test without sleeping
    through one.
    """

    backend = "redis"

    def __init__(self, url: Optional[str] = None, *, window_seconds: int = 60,
                 client: Any = None, key_prefix: str = DEFAULT_KEY_PREFIX,
                 fallback: Any = None, clock: Callable[[], float] = time.time) -> None:
        if client is None and not url:
            raise CloudUnavailable(
                "A Redis rate limiter needs a URL.",
                remedy=f"Set {REDIS_URL_ENV}, for example redis://10.0.0.3:6379/0.",
            )
        self.url = url or ""
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix
        self.client = client if client is not None else connect(url)
        self.clock = clock

        self._lock = threading.Lock()
        self._fallback = fallback
        self._scripting = True
        self.healthy = True
        self.last_error: Optional[str] = None
        self.last_error_at: Optional[str] = None
        self.degraded_checks = 0

    # --- the limiter interface -------------------------------------------

    def check(self, key: str, limit: int) -> Tuple[bool, int, int]:
        """Record a request. Returns ``(allowed, remaining, retry_after)``."""
        if limit <= 0:
            return True, -1, 0

        now = self.clock()
        try:
            count, ttl = self._count(self._window_key(key, now), self._ttl(now))
        except Exception as exc:
            # Redis is unreachable or misbehaving. The community loses shared
            # limits, not its assistant.
            self._note_failure(exc)
            return self._local().check(key, limit)

        self.healthy = True
        if count > limit:
            return False, 0, max(int(ttl), 1)
        return True, max(limit - count, 0), 0

    def reset(self, key: Optional[str] = None) -> None:
        """Clear counters. Used by tests and by an operator unblocking a client."""
        try:
            if key is None:
                for stored in self.client.scan_iter(match=f"{self.key_prefix}:*"):
                    self.client.delete(stored)
            else:
                now = self.clock()
                self.client.delete(self._window_key(key, now))
        except Exception as exc:
            self._note_failure(exc)
        if self._fallback is not None:
            self._fallback.reset(key)

    def status(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "configured": True,
            "active": bool(self.healthy),
            "url": safe_url(self.url) if self.url else "(injected client)",
            "window_seconds": self.window_seconds,
            "atomic": "lua" if self._scripting else "incr+expire",
            "detail": (
                "Rate limits are counted in Redis, so every instance shares one window."
                if self.healthy else
                "Redis is not answering; limits are being counted per process, so "
                "each instance currently enforces the full limit on its own."
            ),
            "degraded_checks": self.degraded_checks,
            "last_error": self.last_error,
            "last_error_at": self.last_error_at,
            "remedy": None if self.healthy else (
                "Check the Redis instance and the VPC connector. The gateway "
                "recovers on its own as soon as Redis answers again."
            ),
        }

    # --- internals --------------------------------------------------------

    def _window_key(self, key: str, now: float) -> str:
        window = int(now // self.window_seconds)
        return f"{self.key_prefix}:{window}:{key}"

    def _ttl(self, now: float) -> int:
        """Seconds left in the current window, never less than one."""
        window_end = (int(now // self.window_seconds) + 1) * self.window_seconds
        return max(int(window_end - now) + 1, 1)

    def _count(self, key: str, ttl: int) -> Tuple[int, int]:
        script_error: Optional[Exception] = None
        if self._scripting:
            try:
                result = self.client.eval(_WINDOW_SCRIPT, 1, key, ttl)
                return int(result[0]), int(result[1])
            except Exception as exc:
                script_error = exc

        count = int(self.client.incr(key))
        remaining = int(self.client.ttl(key) or -1)
        if count == 1 or remaining < 0:
            # Either a fresh window, or one left without an expiry by a process
            # that died mid-write. Both want the same repair.
            self.client.expire(key, ttl)
            remaining = ttl

        if script_error is not None and self._scripting:
            self._scripting = False
            print(
                "[cloud.ratelimit] This Redis does not run EVAL "
                f"({type(script_error).__name__}: {script_error}). Counting with "
                "INCR and EXPIRE instead, which is correct but not atomic."
            )
        return count, remaining

    def _note_failure(self, exc: Exception) -> None:
        with self._lock:
            self.healthy = False
            self.degraded_checks += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.last_error_at = time.strftime("%Y-%m-%dT%H:%M:%S")
            first = self.degraded_checks == 1
        if first:
            print(
                f"[cloud.ratelimit] Redis at {safe_url(self.url) or 'the configured client'} "
                f"is not answering "
                f"({self.last_error}). Falling back to per-process rate limits, "
                f"so each instance now enforces the full limit on its own. "
                f"Answers are unaffected."
            )

    def _local(self) -> Any:
        """The in-memory limiter this falls back to.

        Imported here rather than at module scope: ``api.auth`` is what chooses
        this backend, and a module-level import back into it would be a cycle.
        """
        if self._fallback is None:
            from api.auth import RateLimiter
            self._fallback = RateLimiter(window_seconds=self.window_seconds)
        return self._fallback


def ratelimit_status() -> Dict[str, Any]:
    """What the environment asks for, for callers with no limiter in hand.

    :func:`cloud.cloud_status` prefers the live limiter, which knows whether it
    has fallen back. This is the answer when there is no live limiter to ask.
    """
    url = redis_url()
    if not url:
        return {
            "backend": "memory",
            "configured": False,
            "active": True,
            "detail": ("Rate limits are counted per process. Correct for one "
                       "server, and four instances would each enforce the full limit."),
            "remedy": None,
        }

    try:
        import redis  # noqa: F401
    except ImportError:
        return {
            "backend": "memory",
            "configured": True,
            "active": False,
            "url": safe_url(url),
            "detail": f"{REDIS_URL_ENV} is set but the 'redis' package is not installed.",
            "remedy": INSTALL_REMEDY,
        }

    return {
        "backend": "redis",
        "configured": True,
        "active": True,
        "url": safe_url(url),
        "detail": "Rate limits are counted in Redis, shared by every instance.",
        "remedy": None,
    }


if __name__ == "__main__":
    from api.auth import RateLimiter

    class _Demo:
        """The smallest Redis that can answer this module's questions."""

        def __init__(self) -> None:
            self.values: Dict[str, int] = {}

        def eval(self, *args):
            raise NotImplementedError("no scripting in the demo")

        def incr(self, key):
            self.values[key] = self.values.get(key, 0) + 1
            return self.values[key]

        def expire(self, key, ttl):
            return True

        def ttl(self, key):
            return 42

        def delete(self, key):
            self.values.pop(key, None)

        def scan_iter(self, match=None):
            return list(self.values)

    shared = RedisRateLimiter(client=_Demo(), window_seconds=60)
    local = RateLimiter(window_seconds=60)
    print("redis  (limit 3, 5 requests):", [shared.check("demo", 3) for _ in range(5)])
    print("memory (limit 3, 5 requests):", [local.check("demo", 3) for _ in range(5)])

    class _Broken(_Demo):
        def incr(self, key):
            raise ConnectionError("connection refused")

    degraded = RedisRateLimiter(client=_Broken(), window_seconds=60)
    print("with Redis down:", [degraded.check("demo", 3)[0] for _ in range(5)])
    print("status:", degraded.status()["detail"])
