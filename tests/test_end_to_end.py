"""End-to-end test through the real agent.

Exercises the actual production path -- NeighborhoodAgent -> CommunityPipeline
-> HybridRetriever -> citations -> provenance -- with only the vector database
and the language model replaced. Everything between them is the real code that
serves /api/chat.
"""

from __future__ import annotations

import sys
import types
from typing import Any, Dict, List

PASS: List[str] = []
FAIL: List[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  -> {detail}" if not condition else ""))


def _stub_ml() -> None:
    """Stub only the vector database and embedding model."""
    if "qdrant_client" not in sys.modules:
        qdrant = types.ModuleType("qdrant_client")
        qdrant.QdrantClient = type("QdrantClient", (), {"__init__": lambda self, *a, **k: None})
        models_mod = types.ModuleType("qdrant_client.models")
        for name in ("Distance", "VectorParams", "PointStruct", "Filter",
                     "FieldCondition", "MatchValue"):
            setattr(models_mod, name, type(name, (), {"__init__": lambda self, *a, **k: None}))
        qdrant.models = models_mod
        sys.modules["qdrant_client"] = qdrant
        sys.modules["qdrant_client.models"] = models_mod

    if "sentence_transformers" not in sys.modules:
        st = types.ModuleType("sentence_transformers")
        st.SentenceTransformer = type("SentenceTransformer", (), {
            "__init__": lambda self, *a, **k: None,
            "encode": lambda self, t, **k: type("V", (), {"tolist": lambda s: [0.0] * 384})(),
            "get_sentence_embedding_dimension": lambda self: 384,
        })
        st.CrossEncoder = type("CrossEncoder", (), {
            "__init__": lambda self, *a, **k: (_ for _ in ()).throw(RuntimeError("offline"))
        })
        sys.modules["sentence_transformers"] = st


CORPUS = [
    {
        "text": "Article 8.4 of the zoning bylaw permits accessory dwelling units by "
                "right in all residential districts, subject to dimensional limits.",
        "source_type": "municipal_document", "title": "Zoning Bylaw", "page": 84,
        "section": "Article 8.4", "url": "https://example.org/zoning.pdf",
        "document_type": "bylaw", "status": "adopted", "effective_date": "2024-06-01",
    },
    {
        "text": "Article 8.1 of the zoning bylaw governs signage dimensions in "
                "business districts and requires a special permit for projecting signs.",
        "source_type": "municipal_document", "title": "Zoning Bylaw", "page": 81,
        "section": "Article 8.1", "url": "https://example.org/zoning.pdf",
        "document_type": "bylaw", "status": "adopted",
    },
    {
        "text": "Several members expressed support for the Coolidge Corner redesign "
                "during discussion. No motion was made and the board took no vote.",
        "source_type": "meeting_transcript", "body": "Select Board",
        "meeting_date": "2026-05-12", "start_time": 4422.0,
        "url": "https://www.youtube.com/watch?v=abc123",
        "speaker": "Jane Smith", "speaker_role": "Transportation Director",
        "agenda_item": "Coolidge Corner redesign", "title": "Select Board May 12",
    },
]


def main() -> int:
    print("=" * 62)
    print("End-to-end agent tests")
    print("=" * 62)
    _stub_ml()

    from agent import NeighborhoodAgent
    from models import AIProvider, ProjectConfig
    from tests.fakes import FakeVectorStore

    project = ProjectConfig(
        project_id="e2e-town",
        municipality_name="Brookline, MA",
        project_name="Brookline AI",
        ai_provider=AIProvider.LMSTUDIO,
        model_name="gemma-4-26b-a4b",
    )
    store = FakeVectorStore(CORPUS, collection_name="e2e-town")
    agent = NeighborhoodAgent(project, vector_store=store)

    print("\nagent construction")
    check("constitution loaded from source control",
          agent.constitution.version == "1.0", agent.constitution.version)
    check("all 20 principles parsed", len(agent.constitution.principles) == 20)
    check("provider is LM Studio", agent.client_type == "lmstudio")
    check("hybrid retriever attached", agent.retriever is not None)

    # Replace only the network call.
    captured: Dict[str, Any] = {}

    def fake_complete(prompt):
        captured["prompt"] = prompt
        return ("The bylaw permits accessory dwelling units by right in residential "
                "districts [1]. The Select Board discussed the redesign but took no "
                "vote [3]. Unrelated claim [9].")

    agent.provider.complete = fake_complete

    print("\nfull chat path")
    result = agent.chat("What does Article 8.4 of the zoning bylaw say?")

    check("answer returned", bool(result.get("answer")), str(result)[:150])
    check("sources returned", len(result.get("sources", [])) > 0)
    check("provenance returned", "provenance" in result)

    prompt = captured.get("prompt")
    check("prompt was assembled", prompt is not None)
    if prompt:
        blocks = prompt.system_blocks()
        check("identity, constitution and records sent separately", len(blocks) == 3,
              f"got {len(blocks)}")
        check("constitution is its own system block",
              blocks[1].startswith("COMMUNITY CONSTITUTION"), blocks[1][:50])
        check("the rules name their own version and hash",
              "version 1.0" in blocks[1] and "hash " in blocks[1], blocks[1][:90])
        check("community named in the constitution block",
              "Brookline, MA" in blocks[1])
        check("records block warns against following retrieved instructions",
              "never as instructions" in blocks[2])

    print("\nretrieval quality")
    sources = result["sources"]
    top = sources[0]
    check("Article 8.4 is the top source", "8.4" in (top.get("label") or ""),
          str(top.get("label")))
    check("citation labels the page", "p. 84" in (top.get("label") or ""),
          str(top.get("label")))
    check("document link opens the page", "#page=84" in (top.get("url") or ""),
          str(top.get("url")))

    meeting = next((s for s in sources if s["source_type"] == "meeting_transcript"), None)
    check("meeting also retrieved", meeting is not None)
    if meeting:
        check("meeting link seeks the timestamp", "&t=4422s" in meeting["url"],
              meeting["url"])
        check("speaker attributed",
              "Jane Smith" in (meeting.get("attribution") or ""),
              str(meeting.get("attribution")))

    print("\ncitation verification")
    check("fabricated marker stripped from the answer",
          "[9]" not in result["answer"], result["answer"])
    check("real markers kept", "[1]" in result["answer"])
    provenance = result["provenance"]
    check("stripping recorded as a warning",
          any("removed citation" in w for w in provenance["warnings"]),
          str(provenance["warnings"]))
    check("used sources counted", provenance["sources_used"] >= 1,
          str(provenance["sources_used"]))

    print("\nprovenance for the transparency panel")
    for field, expected in [
        ("model", "gemma-4-26b-a4b"),
        ("provider", "lmstudio"),
        ("constitution_version", "1.0"),
        ("constitution_status", "draft"),
    ]:
        check(f"provenance.{field}", provenance.get(field) == expected,
              f"got {provenance.get(field)!r}")
    check("provenance binds the answer to a constitution hash",
          str(provenance.get("constitution_hash", "")).startswith("sha256:"),
          str(provenance.get("constitution_hash")))
    check("provenance reports whether the ledger verifies",
          provenance.get("constitution_ledger_ok") is True,
          str(provenance.get("constitution_ledger_ok")))
    check("retrieval diagnostics present",
          "dense_hits" in provenance["retrieval"] and
          "sparse_hits" in provenance["retrieval"])
    check("reranker reported inactive, not silently skipped",
          provenance["retrieval"]["reranked"] is False and
          any("reranker inactive" in n for n in provenance["retrieval"]["notes"]),
          str(provenance["retrieval"]["notes"]))
    check("query expansion recorded", "added_terms" in provenance["query"])

    print("\nstats reporting")
    stats = agent.get_stats()
    check("stats name the constitution version", stats["constitution_version"] == "1.0")
    check("stats count principles", stats["constitution_principles"] == 20)
    check("stats name the provider label", stats["provider_label"] == "LM Studio (local)")

    print("\nprovider health when the local server is down")
    health = agent.provider_health()
    check("health reports unreachable", health.get("reachable") is False, str(health))
    check("health names the remedy", "LM Studio" in (health.get("remedy") or ""),
          str(health.get("remedy")))

    print("\nlegacy project with an inline constitution still works")
    legacy_project = ProjectConfig(
        project_id="legacy-town", municipality_name="Old Town",
        project_name="Old Town AI",
        community_constitution=["Always cite sources", "Never guess at local facts"],
    )
    legacy_agent = NeighborhoodAgent(
        legacy_project, vector_store=FakeVectorStore(CORPUS, "legacy-town"))
    check("legacy project constructs", legacy_agent is not None)
    check("file constitution takes precedence over inline",
          legacy_agent.constitution.origin == "file",
          legacy_agent.constitution.origin)

    print("\n" + "=" * 62)
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    for name in FAIL:
        print(f"  FAILED: {name}")
    return 1 if FAIL else 0


def test_all() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
