"""Verify app.py imports and exposes the community gateway.

The heavy inference dependencies (qdrant-client, sentence-transformers, torch)
are stubbed, so this checks wiring rather than retrieval quality. It catches the
failures that actually happen when integrating: a bad import, a route that never
registered, a circular dependency, a name that does not exist.
"""

from __future__ import annotations

import sys
import types
from typing import Any, Dict, List


def _install_stubs() -> None:
    """Stub the ML stack so app.py can be imported on a machine without it."""
    if "qdrant_client" not in sys.modules:
        qdrant = types.ModuleType("qdrant_client")

        class _FakeClient:
            def __init__(self, *a, **k): ...
            def get_collection(self, *a, **k): raise RuntimeError("no collection")
            def create_collection(self, *a, **k): ...
            def upsert(self, *a, **k): ...
            def query_points(self, *a, **k): return types.SimpleNamespace(points=[])
            def scroll(self, *a, **k): return [], None
            def retrieve(self, *a, **k): return []
            def delete(self, *a, **k): ...

        qdrant.QdrantClient = _FakeClient
        models_mod = types.ModuleType("qdrant_client.models")
        for name in ("Distance", "VectorParams", "PointStruct", "Filter",
                     "FieldCondition", "MatchValue"):
            setattr(models_mod, name, type(name, (), {"__init__": lambda self, *a, **k: None}))
        qdrant.models = models_mod
        sys.modules["qdrant_client"] = qdrant
        sys.modules["qdrant_client.models"] = models_mod

    if "sentence_transformers" not in sys.modules:
        st = types.ModuleType("sentence_transformers")

        class _FakeEncoder:
            def __init__(self, *a, **k): ...
            def encode(self, text, **k):
                return type("V", (), {"tolist": lambda self: [0.0] * 384})()
            def get_sentence_embedding_dimension(self): return 384

        class _FakeCrossEncoder:
            def __init__(self, *a, **k): raise RuntimeError("no reranker in tests")

        st.SentenceTransformer = _FakeEncoder
        st.CrossEncoder = _FakeCrossEncoder
        sys.modules["sentence_transformers"] = st

    for name in ("ollama", "anthropic", "openai"):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    # Collector dependencies.
    for name, attrs in [
        ("youtube_transcript_api", ["YouTubeTranscriptApi"]),
        ("youtube_transcript_api._errors", ["TranscriptsDisabled", "NoTranscriptFound",
                                            "VideoUnavailable"]),
        ("bs4", ["BeautifulSoup"]),
        ("pypdf", ["PdfReader"]),
        ("validators", []),
        ("yt_dlp", ["YoutubeDL"]),
        ("googleapiclient", []),
        ("googleapiclient.discovery", ["build"]),
        ("googleapiclient.errors", ["HttpError"]),
        ("playwright", []),
        ("playwright.sync_api", ["sync_playwright"]),
        ("playwright.async_api", ["async_playwright"]),
        ("docx", ["Document"]),
    ]:
        if name not in sys.modules:
            mod = types.ModuleType(name)
            for attr in attrs:
                setattr(mod, attr, type(attr, (), {}))
            sys.modules[name] = mod


PASS: List[str] = []
FAIL: List[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  {detail}" if not condition else ""))


def main() -> int:
    print("=" * 62)
    print("App wiring tests")
    print("=" * 62)
    _install_stubs()

    print("\nimport")
    try:
        import app  # noqa: F401
        check("app.py imports", True)
    except Exception as exc:
        check("app.py imports", False, f"{type(exc).__name__}: {exc}")
        import traceback; traceback.print_exc()
        return 1

    routes = {getattr(r, "path", "") for r in app.app.routes}

    print("\nOpenAI-compatible surface (guide section 13)")
    for path in ["/v1/models", "/v1/chat/completions"]:
        check(f"{path} registered", path in routes, str(sorted(routes)[:5]))

    print("\ncivic knowledge API (guide section 13)")
    for path in [
        "/community/ask",
        "/community/search",
        "/community/sources/{source_id}",
        "/community/meetings",
        "/community/documents",
        "/community/usage",
        "/community/{project_id}/constitution",
        "/community/{project_id}/stats",
    ]:
        check(f"{path} registered", path in routes)

    print("\nplatform endpoints")
    for path in [
        "/api/tenants",
        "/api/tenants/{tenant_id}/governance",
        "/api/tenants/{tenant_id}/scaffold",
        "/api/projects/{project_id}/second-opinion",
        "/api/projects/{project_id}/second-opinion/options",
        "/api/projects/{project_id}/precompute",
        "/api/projects/{project_id}/common-questions",
        "/api/constitution/ledger",
        "/api/constitution/seal",
        "/api/admin/cloud-status",
        "/api/providers",
    ]:
        check(f"{path} registered", path in routes)

    print("\nmanagement endpoints")
    for path in [
        "/api/lmstudio/models",
        "/api/projects/{project_id}/constitution",
        "/api/projects/{project_id}/api-clients",
        "/api/projects/{project_id}/api-clients/{client_id}",
    ]:
        check(f"{path} registered", path in routes)

    print("\npre-existing endpoints still present")
    for path in ["/api/chat", "/api/projects", "/api/health",
                 "/api/projects/{project_id}/stats"]:
        check(f"{path} still registered", path in routes)

    print("\ngateway context")
    from api.gateway import ctx
    try:
        context = ctx()
        check("gateway configured", context is not None)
        check("project listing callable", callable(context.list_project_ids))
        check("listing returns a list", isinstance(context.list_project_ids(), list))
    except Exception as exc:
        check("gateway configured", False, str(exc))

    print("\nOpenAPI schema builds")
    try:
        schema = app.app.openapi()
        check("openapi() succeeds", bool(schema.get("paths")))
        check("chat completions documented",
              "/v1/chat/completions" in schema.get("paths", {}))
    except Exception as exc:
        check("openapi() succeeds", False, f"{type(exc).__name__}: {exc}")

    print("\n" + "=" * 62)
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    for name in FAIL:
        print(f"  FAILED: {name}")
    return 1 if FAIL else 0


def test_all() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
