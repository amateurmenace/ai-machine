"""Administration is local unless it carries the token.

No network, no model. A small application with routes shaped like app.py's,
behind the same two middlewares in the same order, driven by a test client
whose requests arrive as if from another machine, and a wrapper that makes
them arrive as if from this one.

Run with:  python3 -m tests.test_admin_guard
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from api.admin_guard import (
    ADMIN_TOKEN_ENV, REDACTED, AdminGuard, is_public, is_remote_scope,
    redact_secrets, strip_redaction,
)

PASS: List[str] = []
FAIL: List[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  -> {detail}" if not condition else ""))


ORIGIN = "https://create.neighborhoodai.org"
TOKEN = "a-token-long-enough-to-be-worth-having-1234"


def build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    @app.get("/api/projects/{project_id}")
    async def project(project_id: str):
        return {"project_id": project_id}

    @app.put("/api/projects/{project_id}")
    async def update(project_id: str, updates: Dict[str, Any]):
        return {"updated": sorted(updates)}

    @app.delete("/api/projects/{project_id}")
    async def delete(project_id: str):
        return {"deleted": project_id}

    @app.get("/api/projects/{project_id}/config")
    async def config(project_id: str):
        return {"config": "{}"}

    @app.post("/api/chat")
    async def chat(payload: Dict[str, Any]):
        return {"answer": "..."}

    @app.post("/api/projects/{project_id}/second-opinion")
    async def second(project_id: str, payload: Dict[str, Any]):
        return {"ok": True}

    @app.post("/api/constitution/seal")
    async def seal(payload: Dict[str, Any]):
        return {"sealed": True}

    @app.post("/api/projects/{project_id}/sync-all")
    async def sync_all(project_id: str):
        return {"syncing": project_id}

    @app.get("/api/admin/jobs")
    async def jobs():
        return {"jobs": []}

    @app.post("/community/{project_id}/ask")
    async def ask(project_id: str, payload: Dict[str, Any]):
        return {"gateway": True}

    # The same order as app.py: the guard first, so CORS wraps it.
    app.add_middleware(AdminGuard)
    app.add_middleware(CORSMiddleware, allow_origins=[ORIGIN], allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])
    return app


class AsIfLocal:
    """Make every request look like it came from this machine."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            scope = dict(scope, client=("127.0.0.1", 40000))
        await self.app(scope, receive, send)


def with_token(value) -> None:
    if value is None:
        os.environ.pop(ADMIN_TOKEN_ENV, None)
    else:
        os.environ[ADMIN_TOKEN_ENV] = value


def test_a_resident_can_ask_and_read_and_nothing_else() -> None:
    print("\nfrom another machine, without the token")
    with_token(TOKEN)
    client = TestClient(build_app())
    check("a question is answered", client.post("/api/chat", json={"message": "?"}).status_code == 200)
    check("health is public", client.get("/api/health").status_code == 200)
    check("a project can be read", client.get("/api/projects/brookline-ma").status_code == 200)
    check("a second opinion is a resident's button",
          client.post("/api/projects/brookline-ma/second-opinion", json={}).status_code == 200)

    r = client.delete("/api/projects/brookline-ma")
    check("deleting the project is refused", r.status_code == 401, str(r.status_code))
    check("with a reason the console can show",
          "X-Admin-Token" in r.json()["detail"] and r.json()["admin_required"] is True, str(r.json()))
    check("so is reading the raw config, which holds the keys",
          client.get("/api/projects/brookline-ma/config").status_code == 401)
    check("and sealing the constitution",
          client.post("/api/constitution/seal", json={"version": "1.1"}).status_code == 401)
    check("and the job list", client.get("/api/admin/jobs").status_code == 401)
    check("the gateway is not this middleware's business",
          client.post("/community/brookline-ma/ask", json={}).status_code == 200)


def test_the_token_opens_administration_from_anywhere() -> None:
    print("\nwith the token")
    with_token(TOKEN)
    client = TestClient(build_app())
    check("as X-Admin-Token",
          client.delete("/api/projects/x", headers={"X-Admin-Token": TOKEN}).status_code == 200)
    check("as a bearer token",
          client.delete("/api/projects/x",
                        headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 200)
    r = client.delete("/api/projects/x", headers={"X-Admin-Token": "wrong"})
    check("a wrong token is refused, and told so",
          r.status_code == 403 and "wrong" in r.json()["detail"], str(r.status_code))
    check("a token with the right prefix is still wrong",
          client.delete("/api/projects/x", headers={"X-Admin-Token": TOKEN[:-1]}).status_code == 403)


def test_no_token_configured_means_local_only() -> None:
    print("\nno token on the server")
    with_token(None)
    client = TestClient(build_app())
    r = client.delete("/api/projects/x", headers={"X-Admin-Token": "anything"})
    check("nothing presented from outside can open it", r.status_code == 401, str(r.status_code))
    check("and the reason says how to change that", ADMIN_TOKEN_ENV in r.json()["detail"],
          r.json()["detail"])
    check("residents are unaffected", client.post("/api/chat", json={}).status_code == 200)


def test_this_machine_is_the_operator() -> None:
    print("\nfrom this machine")
    with_token(None)
    client = TestClient(AsIfLocal(build_app()), base_url="http://127.0.0.1:8400")
    check("administration needs no token", client.delete("/api/projects/x").status_code == 200)
    check("even with none configured", client.get("/api/projects/x/config").status_code == 200)

    print("\nthrough a tunnel, which is a local process")
    for header in ("cf-connecting-ip", "cf-ray", "x-forwarded-for", "x-real-ip", "forwarded"):
        r = client.delete("/api/projects/x", headers={header: "203.0.113.7"})
        check(f"loopback plus {header} is another machine", r.status_code == 401,
              str(r.status_code))
    check("the question still goes through",
          client.post("/api/chat", json={},
                      headers={"cf-connecting-ip": "203.0.113.7"}).status_code == 200)


def test_a_page_elsewhere_cannot_borrow_the_operators_browser() -> None:
    print("\nfrom this machine's browser, on somebody else's page")
    with_token(None)
    client = TestClient(AsIfLocal(build_app()), base_url="http://127.0.0.1:8400")

    r = client.post("/api/projects/x/sync-all", headers={"Origin": "https://evil.example"})
    check("a form on another site cannot start a sync: a bodiless POST gets no preflight",
          r.status_code == 401, str(r.status_code))
    check("nor delete a project",
          client.delete("/api/projects/x",
                        headers={"Origin": "https://evil.example"}).status_code == 401)
    check("an opaque origin is not this machine either",
          client.post("/api/projects/x/sync-all", headers={"Origin": "null"}).status_code == 401)
    r = client.delete("/api/projects/x", headers={"Host": "rebound.evil.example"})
    check("a page whose own name now resolves here (DNS rebinding) is refused",
          r.status_code == 401, str(r.status_code))

    for origin in ("http://localhost:3000", "http://127.0.0.1:8400", "http://[::1]:8400"):
        check(f"the console at {origin} is the operator",
              client.post("/api/projects/x/sync-all",
                          headers={"Origin": origin}).status_code == 200)
    for host in ("localhost:8400", "127.0.0.1", "[::1]:8400"):
        check(f"and so is the API addressed as {host}",
              client.delete("/api/projects/x", headers={"Host": host}).status_code == 200)
    check("a question from any page is still just a question",
          client.post("/api/chat", json={},
                      headers={"Origin": "https://evil.example"}).status_code == 200)


def test_a_refusal_reaches_the_browser_as_a_refusal() -> None:
    print("\nCORS")
    with_token(TOKEN)
    client = TestClient(build_app())
    r = client.options("/api/projects/x", headers={
        "Origin": ORIGIN, "Access-Control-Request-Method": "DELETE",
        "Access-Control-Request-Headers": "x-admin-token"})
    check("the preflight is answered", r.status_code == 200, str(r.status_code))
    check("and allows the token header",
          "x-admin-token" in (r.headers.get("access-control-allow-headers") or "").lower(),
          str(dict(r.headers)))
    r = client.delete("/api/projects/x", headers={"Origin": ORIGIN})
    check("a refusal carries the CORS header, so the browser shows a 401 and not a CORS error",
          r.status_code == 401 and r.headers.get("access-control-allow-origin") == ORIGIN,
          str(dict(r.headers)))


def test_what_is_public_is_a_short_list() -> None:
    print("\nthe list")
    for method, path in [
        ("GET", "/api"), ("GET", "/api/health"), ("GET", "/api/projects"),
        ("GET", "/api/projects/brookline-ma"), ("GET", "/api/projects/brookline-ma/health"),
        ("GET", "/api/projects/brookline-ma/stats"),
        ("GET", "/api/projects/brookline-ma/documents"),
        ("GET", "/api/projects/brookline-ma/constitution"),
        ("GET", "/api/constitution/ledger"), ("POST", "/api/chat"),
        ("POST", "/api/projects/brookline-ma/second-opinion"), ("HEAD", "/api/health"),
    ]:
        check(f"public: {method} {path}", is_public(method, path))
    for method, path in [
        ("DELETE", "/api/projects/brookline-ma"), ("PUT", "/api/projects/brookline-ma"),
        ("POST", "/api/projects"), ("GET", "/api/projects/brookline-ma/config"),
        ("PUT", "/api/projects/brookline-ma/config"),
        ("POST", "/api/projects/brookline-ma/sync-all"),
        ("POST", "/api/projects/brookline-ma/sources/x/ingest"), ("GET", "/api/admin/jobs"),
        ("GET", "/api/lmstudio/models"), ("POST", "/api/constitution/seal"),
        ("GET", "/api/projects/brookline-ma/api-clients"),
        ("POST", "/api/projects/brookline-ma/generate-api-key"),
        ("GET", "/api/projects/brookline-ma/sources/x/sync-state"),
        ("POST", "/api/projects/brookline-ma/precompute"),
        ("GET", "/api/projects/brookline-ma/documents/extra"),
    ]:
        check(f"administrative: {method} {path}", not is_public(method, path))
    check("no client address at all is not this machine",
          is_remote_scope({"type": "http", "headers": [], "client": None}))


def test_secrets_do_not_leave_the_machine() -> None:
    print("\nwhat a browser elsewhere sees of a project")
    project = {
        "project_id": "brookline-ma", "model_name": "gemma", "api_key": "sk-ant-real",
        "local_auth_header": "Authorization: Bearer tunnel-secret",
        "web_search_api_key": "brave-key", "project_api_key": "cai_legacy", "temperature": 0.3,
        "api_clients": [{"name": "newsletter", "key_hash": "abc123", "scopes": ["ask"]}],
    }
    shown = redact_secrets(project)
    for field in ("api_key", "local_auth_header", "web_search_api_key", "project_api_key"):
        check(f"{field} is masked", shown[field] == REDACTED, str(shown[field]))
    check("the client key hash too", shown["api_clients"][0]["key_hash"] == REDACTED)
    check("and nothing else changes",
          shown["model_name"] == "gemma" and shown["temperature"] == 0.3
          and shown["api_clients"][0]["name"] == "newsletter")
    check("an unset secret stays unset, not masked",
          "api_key" not in redact_secrets({"project_id": "x"})
          and redact_secrets({"api_key": None})["api_key"] is None)

    print("\nand what happens when it is sent back")
    kept = strip_redaction({"model_name": "gemma-2", "api_key": REDACTED, "temperature": 0.2})
    check("the mask is not saved over the real key",
          "api_key" not in kept and kept["model_name"] == "gemma-2", str(kept))
    check("clearing a key on purpose still works",
          strip_redaction({"api_key": None}) == {"api_key": None})


def main() -> int:
    print("=" * 62)
    print("Admin guard tests")
    print("=" * 62)
    had = os.environ.get(ADMIN_TOKEN_ENV)
    try:
        for fn in [
            test_a_resident_can_ask_and_read_and_nothing_else,
            test_the_token_opens_administration_from_anywhere,
            test_no_token_configured_means_local_only,
            test_this_machine_is_the_operator,
            test_a_page_elsewhere_cannot_borrow_the_operators_browser,
            test_a_refusal_reaches_the_browser_as_a_refusal,
            test_what_is_public_is_a_short_list,
            test_secrets_do_not_leave_the_machine,
        ]:
            fn()
    finally:
        with_token(had)

    print("\n" + "=" * 62)
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    for name in FAIL:
        print(f"  FAILED: {name}")
    return 1 if FAIL else 0


def test_all() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
