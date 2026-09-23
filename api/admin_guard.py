"""
Administration stays on the machine that runs the API.

Everything under /api is the console's own interface: create a project, change
its model, add a source, ingest, delete. The resident-facing surface, the
gateway under /community and /v1, has keys, scopes and rate limits. This one
had nothing, and it listens on the same port. The API is meant to be reached
through a tunnel by a console served from Netlify, and the tunnel's hostname is
in that console's JavaScript, so anyone who opens the page can read where the
API is. As it stood, one anonymous DELETE removed a town's archive.

The rule is small enough to hold in one hand:

* A request from this machine is the operator. It is allowed.
* A request from anywhere else may do what a resident does: ask a question,
  read the record, read the rules. Anything else needs the admin token, set
  once in the server's environment and once in the operator's browser.
* If no token is configured there is no way to administer from outside. That
  is the safe default, and the recommended one.

"From this machine" has to mean the operator, and three things other than the
operator can make a request arrive from 127.0.0.1:

* A tunnel, which is a local process. cloudflared connects from loopback, and
  the only sign a request began elsewhere is the header it adds on the way
  through. A caller cannot strip it, because it is added after the request has
  left them.
* Another website, open in the operator's own browser. A form on any page can
  post to http://127.0.0.1:8400, and a POST with no body needs no CORS
  preflight, so the browser delivers it and only hides the answer from the page.
  The harm is done by then. The browser names the page it came from in Origin.
* The same website after DNS rebinding: its own name, re-pointed at 127.0.0.1,
  which makes the page and the API one origin as far as the browser can tell.
  The browser still sends the name it thinks it is talking to, as Host.

So a request is local only if its peer is loopback, it carries no forwarding
header, and its Host and Origin, when present, name this machine. Anything else
is treated as coming from anywhere else. A local caller could fake any of these
and would only be restricting themselves.

The public routes are listed; everything else under /api is administrative.
Deny by default means a route added next year is protected the day it is
written rather than the day somebody remembers.
"""

from __future__ import annotations

import hmac
import ipaddress
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import JSONResponse

ADMIN_TOKEN_ENV = "COMMUNITY_ADMIN_TOKEN"
TOKEN_HEADER = "x-admin-token"

# What a resident's browser needs, and nothing else. Method, then a pattern the
# whole path has to match.
PUBLIC_ROUTES: List[Tuple[str, re.Pattern]] = [
    (method, re.compile(pattern)) for method, pattern in [
        ("GET", r"/api/?"),
        ("GET", r"/api/health"),
        ("GET", r"/api/projects"),
        ("GET", r"/api/projects/[^/]+"),
        ("GET", r"/api/projects/[^/]+/(?:health|stats|constitution|documents|precompute)"),
        ("GET", r"/api/projects/[^/]+/second-opinion/options"),
        ("POST", r"/api/projects/[^/]+/second-opinion"),
        ("GET", r"/api/constitution/ledger"),
        ("POST", r"/api/chat"),
    ]
]

# Headers a proxy or a tunnel adds to a request it forwards. cloudflared sets
# the first three on everything it passes through.
FORWARDING_HEADERS = (
    "cf-connecting-ip", "cf-ray", "cf-visitor",
    "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto",
    "x-real-ip", "forwarded",
)


# What a secret looks like when it is sent to a browser that is not on this
# machine. Sending it back is a no-op; see strip_redaction.
REDACTED = "********"
SECRET_FIELDS = ("api_key", "project_api_key", "local_auth_header", "web_search_api_key")


def is_public(method: str, path: str) -> bool:
    method = "GET" if method == "HEAD" else method
    return any(m == method and pattern.fullmatch(path) for m, pattern in PUBLIC_ROUTES)


def _is_loopback(name: str) -> bool:
    name = (name or "").strip().lower()
    if name == "localhost":
        return True
    try:
        address = ipaddress.ip_address(name)
    except ValueError:
        return False
    mapped = getattr(address, "ipv4_mapped", None)     # ::ffff:127.0.0.1
    return (mapped or address).is_loopback


def _host_of(value: str) -> str:
    """The host in a Host header or an Origin: no scheme, no port, no brackets."""
    value = (value or "").strip().lower()
    if "://" in value:
        value = value.split("://", 1)[1]
    value = value.split("/", 1)[0]
    if value.startswith("["):                         # [::1]:8400
        return value[1:].split("]", 1)[0]
    if value.count(":") == 1:                         # 127.0.0.1:8400
        return value.split(":", 1)[0]
    return value                                      # a bare name, or bare IPv6


def is_remote_scope(scope: Dict[str, Any]) -> bool:
    """Whether this request began somewhere other than this machine."""
    headers = Headers(scope=scope)
    if any(name in headers for name in FORWARDING_HEADERS):
        return True
    client = scope.get("client")
    if not _is_loopback(client[0] if client else ""):
        return True
    host = headers.get("host")
    if host is not None and not _is_loopback(_host_of(host)):
        return True       # DNS rebinding: somebody else's name, pointed here
    origin = headers.get("origin")
    if origin is not None and not _is_loopback(_host_of(origin)):
        return True       # a page elsewhere, using the operator's browser
    return False


def is_remote(request: Request) -> bool:
    return is_remote_scope(request.scope)


def configured_token() -> str:
    return (os.getenv(ADMIN_TOKEN_ENV) or "").strip()


def presented_token(headers: Headers) -> str:
    token = (headers.get(TOKEN_HEADER) or "").strip()
    if token:
        return token
    auth = headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def redact_secrets(data: Dict[str, Any]) -> Dict[str, Any]:
    """A project, as a browser off this machine may see it."""
    out = dict(data)
    for field in SECRET_FIELDS:
        if out.get(field):
            out[field] = REDACTED
    clients = out.get("api_clients")
    if isinstance(clients, list):
        out["api_clients"] = [
            {**client, "key_hash": REDACTED}
            if isinstance(client, dict) and client.get("key_hash") else client
            for client in clients
        ]
    return out


def strip_redaction(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Drop the fields that came back as the mask.

    The console loads a project, edits one field and sends the whole thing
    back. If what it loaded had the secrets masked, saving must not write the
    mask over the real ones.
    """
    return {key: value for key, value in updates.items() if value != REDACTED}


class AdminGuard:
    """ASGI middleware. Installed inside the CORS middleware, so a refusal
    reaches the browser as a 401 it can show rather than as a CORS error it
    cannot read."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        method = str(scope.get("method", "GET")).upper()
        administrative = (path == "/api" or path.startswith("/api/")) and method != "OPTIONS" \
            and not is_public(method, path)
        if not administrative or not is_remote_scope(scope):
            await self.app(scope, receive, send)
            return

        refusal = self.refuse(Headers(scope=scope))
        if refusal is None:
            await self.app(scope, receive, send)
            return
        status, detail = refusal
        response = JSONResponse({"detail": detail, "admin_required": True}, status_code=status)
        await response(scope, receive, send)

    @staticmethod
    def refuse(headers: Headers) -> Optional[Tuple[int, str]]:
        """Why a remote administrative request is refused, or None to let it through."""
        expected = configured_token()
        given = presented_token(headers)
        if not expected:
            return 401, (
                "This is an administrative action, and it arrived from outside the "
                "machine that runs the API. No admin token is configured there "
                f"({ADMIN_TOKEN_ENV}), so administration is local-only. Residents' "
                "questions are unaffected."
            )
        if not given:
            return 401, (
                "This is an administrative action, and it arrived from outside the "
                "machine that runs the API. It needs the admin token: send it as "
                "X-Admin-Token, or enter it on the console's admin page."
            )
        if not hmac.compare_digest(given.encode("utf-8"), expected.encode("utf-8")):
            return 403, "The admin token is wrong."
        return None
