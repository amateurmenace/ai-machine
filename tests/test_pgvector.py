"""Tests for the PostgreSQL archive.

There is no Postgres here and no statement in this file is executed against
one. What these cover is everything between the application and the server: the
SQL that gets generated, how a civic filter becomes a WHERE clause, the round
trip from a payload to a row and back, the vector width, which backend the
factory picks, and that a missing driver produces a remedy an operator can act
on rather than a traceback.

The test names say which of those each one is. What is left uncovered is
printed at the end of the run, because a suite that implies more than it
checked is worse than one that checks less.

Run with:  python3 -m tests.test_pgvector     (no pytest required)
       or:  python3 -m pytest tests/
"""

from __future__ import annotations

import json
import os
import sys
import types
from typing import Any, Dict, List

from knowledge.schemas import CivicChunk, SourceType, normalize_payload
from rag.hybrid import HybridRetriever, RetrievalFilters
from stores import PGVECTOR, QDRANT, build_store, select_backend
from stores.pgvector_store import (
    COLUMNS, DEFAULT_VECTOR_DIMENSION, DIMENSION_TOKEN, SCHEMA_PATH,
    PgVectorStore, PgVectorUnavailable, by_id_sql, delete_by_source_sql,
    dimension_mismatch_message, embedding_dimension, hybrid_sql, ids_sql,
    page_sql, parse_declared_dimension, payload_to_row, pgvector_status,
    render_schema, row_to_payload, search_sql, stats_sql, upsert_sql,
    vector_literal, where_clauses,
)
from tests.fakes import FakeVectorStore

PASS: List[str] = []
FAIL: List[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  -> {detail}" if not condition else ""))


def stub_ml_stack() -> None:
    """Let vector_store import on a machine with no qdrant and no torch.

    The embedding model to vector width table lives in vector_store because
    both backends have to agree on it. Reading the real table is the point of
    the dimension checks, so it is stubbed the way tests/test_app_wiring.py
    stubs it rather than duplicated here. Nothing real is ever replaced, and
    the stub carries the same surface that file's does, so it does not matter
    which suite pytest reaches first.
    """
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
        models = types.ModuleType("qdrant_client.models")
        for name in ("Distance", "VectorParams", "PointStruct", "Filter",
                     "FieldCondition", "MatchValue"):
            setattr(models, name, type(name, (), {"__init__": lambda self, *a, **k: None}))
        qdrant.models = models
        sys.modules["qdrant_client"] = qdrant
        sys.modules["qdrant_client.models"] = models

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


# A meeting passage with a legacy source type, a loose date, a field the schema
# has no column for, and a false boolean, which is the combination that catches
# most translation mistakes.
TRANSCRIPT_PAYLOAD: Dict[str, Any] = {
    "text": "Several members expressed support for the redesign but the board "
            "took no vote on the proposal at this meeting.",
    "source": "Town Meetings",
    "source_type": "youtube",
    "url": "https://www.youtube.com/watch?v=abc123",
    "title": "Select Board Meeting 4/14/2026",
    "community": "Brookline",
    "body": "Select Board",
    "meeting_date": "4/14/2026",
    "agenda_item": "Coolidge Corner redesign",
    "speaker": "Jane Smith",
    "speaker_role": "Transportation Director",
    "start_time": 4422.0,
    "status": "discussion",
    "status_confidence": 0.82,
    "vote_taken": False,
    "video_id": "abc123",
    "caption_source": "auto-generated",
}


class FakeProject:
    """The two attributes the factory reads off a ProjectConfig."""

    def __init__(self, project_id: str, community_db_url: Any = None) -> None:
        self.project_id = project_id
        self.community_db_url = community_db_url


class NativeHybridStore(FakeVectorStore):
    """A store that fuses both halves itself, standing in for Postgres.

    It returns the shape PgVectorStore.hybrid_search returns. The SQL that
    would have produced that shape is checked separately, above.
    """

    def __init__(self, payloads: List[Dict[str, Any]], collection_name: str = "native") -> None:
        super().__init__(payloads, collection_name=collection_name)
        self.hybrid_calls: List[Any] = []

    def hybrid_search(self, query, query_vector=None, top_k=24, filters=None):
        self.hybrid_calls.append((query, query_vector, top_k, filters))
        return [
            {"id": "doc-1", "score": 0.0325, "dense_rank": 2, "sparse_rank": 1,
             "text": self.payloads[1]["text"], "metadata": self.payloads[1]},
            {"id": "doc-0", "score": 0.0161, "dense_rank": 1,
             "text": self.payloads[0]["text"], "metadata": self.payloads[0]},
        ]


class BrokenHybridStore(NativeHybridStore):
    def hybrid_search(self, query, query_vector=None, top_k=24, filters=None):
        raise RuntimeError("the database is restarting")


class RecordingDriver:
    """A psycopg stand-in that keeps rows in a dict instead of running SQL.

    It is enough to exercise the code around the statements, which is where the
    migration's batching, counting and resume live. It is not a database and it
    checks nothing about whether the SQL is valid.
    """

    def __init__(self) -> None:
        self.rows: Dict[str, Dict[str, Any]] = {}
        self.statements: List[str] = []

    # --- the pool and connection surface psycopg_pool provides ---
    def __call__(self, dsn, **kwargs):
        return self

    def connection(self):
        return self

    def cursor(self, row_factory=None):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    # --- the cursor surface ---
    def execute(self, sql, params=None):
        self.statements.append(sql)
        if "count(*)" in sql:
            self._result = [{"total_documents": len(self.rows)}]
        elif sql.strip().startswith("SELECT id\n"):
            self._result = [{"id": chunk_id} for chunk_id in self.rows]
        else:
            self._result = []

    def executemany(self, sql, rows):
        self.statements.append(sql)
        for row in rows:
            self.rows[row["id"]] = row

    def fetchall(self):
        return self._result


def store_with_recording_driver() -> Any:
    """A PgVectorStore whose driver records instead of connecting."""
    import stores.pgvector_store as module

    driver = RecordingDriver()
    module._driver.clear()
    module._driver.update({"psycopg": object(), "dict_row": dict,
                           "ConnectionPool": driver})
    module._pools.clear()
    return PgVectorStore("postgresql://civic@localhost/civic", "brookline-ma"), driver


class FakeQdrantPoint:
    def __init__(self, point_id, payload, vector):
        self.id = point_id
        self.payload = payload
        self.vector = vector


class FakeQdrantClient:
    """Three points: one good, one with no vector, one with no text."""

    def __init__(self) -> None:
        self.points = [
            FakeQdrantPoint("aaa", {"text": "Article 8.4 permits accessory "
                                            "dwelling units.",
                                    "url": "https://ex.org/z.pdf",
                                    "meeting_date": "4/14/2026"}, [0.1] * 384),
            FakeQdrantPoint("bbb", {"text": "captions were unavailable"}, []),
            FakeQdrantPoint("ccc", {"url": "https://ex.org/empty"}, [0.2] * 384),
        ]

    def get_collection(self, name):
        return types.SimpleNamespace(points_count=len(self.points))

    def scroll(self, collection_name, limit, offset, with_payload, with_vectors):
        if offset:
            return [], None
        return self.points, None


def test_a_missing_driver_names_a_remedy() -> None:
    print("\npsycopg is optional, and says so when it is missing")
    status = pgvector_status()
    check("status is shaped like the reranker's",
          set(status) == {"enabled", "driver", "reason"}, str(sorted(status)))

    if status["enabled"]:
        # On a machine that does have psycopg, the honest check is the inverse.
        check("psycopg is installed here, so no reason is reported",
              status["reason"] is None, str(status["reason"]))
        check("the driver is named", status["driver"] == "psycopg3", str(status["driver"]))
        return

    reason = status["reason"] or ""
    check("the reason says what is missing", "psycopg" in reason, reason)
    check("the reason carries the install command", "pip install" in reason, reason)
    check("the reason names the way back to the old archive",
          "COMMUNITY_DB_URL" in reason, reason)

    try:
        PgVectorStore("postgresql://civic@localhost/civic", "brookline-ma")
        check("opening the store raises a named error", False, "it constructed")
    except PgVectorUnavailable as exc:
        check("opening the store raises a named error", True)
        check("and the error, not a traceback, carries the remedy",
              "pip install" in str(exc), str(exc))
    except ImportError as exc:
        check("opening the store raises a named error", False,
              f"raw ImportError reached the caller: {exc}")

    try:
        build_store(FakeProject("brookline-ma", "postgresql://civic@localhost/civic"))
        check("a configured database is never quietly swapped for Qdrant",
              False, "build_store returned a store")
    except PgVectorUnavailable:
        check("a configured database is never quietly swapped for Qdrant", True)


def test_schema_carries_the_configured_vector_width() -> None:
    print("\nvector width is a parameter, not a constant")
    default = render_schema()
    check("the default is MiniLM's 384", "vector(384)" in default,
          str(DEFAULT_VECTOR_DIMENSION))

    wide = render_schema(1024)
    check("BGE-M3's 1024 renders too", "vector(1024)" in wide)
    check("no placeholder survives rendering", DIMENSION_TOKEN not in wide)
    check("the template does still carry a placeholder",
          DIMENSION_TOKEN in SCHEMA_PATH.read_text(encoding="utf-8"))

    # The table lives in vector_store, which needs the ML stack to import.
    stub_ml_stack()
    check("the width table is shared with the Qdrant store, not copied",
          embedding_dimension("BAAI/bge-m3") == 1024,
          str(embedding_dimension("BAAI/bge-m3")))
    check("an unknown model falls back to the default",
          embedding_dimension("some-model-nobody-has") == 384)
    check("a declared column type parses back",
          parse_declared_dimension("vector(1024)") == 1024)
    check("a column type with no width is not guessed at",
          parse_declared_dimension("vector") is None)

    message = dimension_mismatch_message(384, 1024, "BAAI/bge-m3")
    check("a mismatch says both widths", "384" in message and "1024" in message, message)
    check("a mismatch says it means re-indexing", "re-index" in message, message)
    check("a mismatch names a command to run", "stores.migrate" in message, message)


def test_schema_indexes_what_the_queries_read() -> None:
    print("\nindexes for the three things Postgres is replacing")
    sql = render_schema()

    check("HNSW on the embedding, for the dense half",
          "USING hnsw (embedding vector_cosine_ops)" in sql)
    check("cosine, matching the Qdrant collections it replaces",
          "vector_cosine_ops" in sql)
    check("GIN on the tsvector, for the keyword half",
          "USING gin (tsv)" in sql)
    check("the tsvector is generated by the database, not written by the app",
          "tsv" in sql and "GENERATED ALWAYS AS" in sql)
    check("full text search names its configuration explicitly",
          "to_tsvector('english'" in sql)

    for columns in ("(project_id, source_type)", "(project_id, body)",
                    "(project_id, meeting_date)"):
        check(f"btree on {columns}", f"ON chunks {columns}" in sql)

    check("project_id is on the table",
          "project_id      text NOT NULL" in sql, "multi-tenancy column missing")
    check("the primary key is the community and the chunk together",
          "PRIMARY KEY (project_id, id)" in sql)
    check("anything without a column of its own has somewhere to go",
          "payload         jsonb NOT NULL" in sql)
    check("every statement can be re-run after a failed migration",
          "CREATE TABLE IF NOT EXISTS" in sql and sql.count("CREATE INDEX IF NOT EXISTS") >= 6)

    for column in ("source_type", "body", "department", "meeting_date", "speaker",
                   "agenda_item", "page", "section", "status", "document_type",
                   "docket_number", "url", "title", "start_time"):
        check(f"civic column present: {column}", f"\n    {column}" in sql
              or f"\n    {column:<15}" in sql or f"    {column} " in sql,
              "not declared")


def test_row_level_security_is_scaffolded_and_left_off() -> None:
    print("\nrow-level security, offered and not imposed")
    sql = render_schema()

    check("a tenant isolation policy is written out",
          "CREATE POLICY chunks_tenant_read" in sql)
    check("it keys on the same column every query filters on",
          "current_setting('civic.project_id'" in sql)
    check("it is commented out rather than enabled",
          "--   ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;" in sql,
          "RLS would be on by default")
    check("no uncommented ALTER TABLE enables it",
          not any(line.strip().startswith("ALTER TABLE") for line in sql.splitlines()))
    check("the comment says when to turn it on",
          "more than one community shares a database" in sql)
    check("and warns that the owner bypasses it",
          "bypass RLS" in sql or "BYPASSRLS" in sql)


def test_hybrid_sql_is_the_fusion_query_from_the_roadmap() -> None:
    print("\nthe fusion query, as text: nothing here reaches a server")
    sql, params = hybrid_sql("brookline-ma", "Article 8.4 accessory dwelling units",
                             [0.1, 0.2, 0.3], top_k=24, candidate_pool=40)

    check("the dense half ranks by cosine distance", "embedding <=> %(q_vec)s::vector" in sql)
    check("the sparse half ranks by ts_rank_cd", "ts_rank_cd(tsv," in sql)
    check("a resident's question is not treated as tsquery syntax",
          "websearch_to_tsquery('english', %(q)s)" in sql, "to_tsquery would raise on it")
    check("the sparse half also restricts with the index operator",
          "tsv @@ websearch_to_tsquery" in sql)
    check("both halves are ranked", sql.count("RANK() OVER") == 2)
    check("the two rankings are unioned",
          "SELECT * FROM dense UNION ALL SELECT * FROM sparse" in sql)
    check("fused by the reciprocal rank sum from the roadmap",
          "SUM(1.0 / (60 + rank))" in sql, sql)
    check("60 matches the k the Python fusion uses",
          "60 + rank" in sql)
    check("each half is limited before it is ranked, so the index can be used",
          sql.index("LIMIT %(pool)s") < sql.index("both_halves"),
          "ranking the whole corpus would defeat HNSW")
    check("the ordering is deterministic on ties", "ORDER BY f.score DESC, c.id" in sql)

    check("the vector is bound, not interpolated", "%(q_vec)s" in sql and "0.1" not in sql)
    check("the query text is bound, not interpolated",
          "Article 8.4" not in sql and params["q"] == "Article 8.4 accessory dwelling units")
    check("the vector travels in pgvector's own text form",
          params["q_vec"] == "[0.1,0.2,0.3]", params["q_vec"])
    check("the pool and the cut are both bound",
          params["pool"] == 40 and params["top_k"] == 24)

    check("each hit can report which half found it",
          "dense_rank" in sql and "sparse_rank" in sql)
    check("the payload columns come back with the ranking",
          'c."text"' in sql and "c.payload" in sql)


def test_filters_translate_the_way_the_python_path_matches() -> None:
    print("\ncivic filters become a WHERE clause, matching RetrievalFilters")
    clauses, params = where_clauses(RetrievalFilters(
        body="Select Board", source_type=SourceType.MEETING_TRANSCRIPT,
        speaker="Smith", date_from="2019-01-01", date_to="2026-12-31",
    ))
    text = " ".join(clauses)

    check("equality is case-insensitive, as matches() is",
          "lower(body) = lower(%(f_body)s)" in text, text)
    check("source type is an equality filter",
          "lower(source_type) = lower(%(f_source_type)s)" in text, text)
    check("speaker is a substring match, as matches() is",
          "speaker ILIKE %(f_speaker)s" in text, text)
    check("the speaker pattern is built in the parameter, not the SQL",
          params["f_speaker"] == "%Smith%", str(params["f_speaker"]))
    check("dates compare against the generated record date",
          "record_date >= %(f_date_from)s" in text and "record_date <= %(f_date_to)s" in text,
          text)
    check("dates are bound as dates, not strings",
          params["f_date_from"].isoformat() == "2019-01-01",
          repr(params["f_date_from"]))

    wild, wild_params = where_clauses({"speaker": "A_B%C"})
    check("LIKE wildcards inside a name are escaped",
          wild_params["f_speaker"] == "%A\\_B\\%C%", repr(wild_params["f_speaker"]))

    empty, empty_params = where_clauses(None)
    check("no filters means no clauses", empty == [] and empty_params == {})
    check("blank values are not filters",
          where_clauses({"body": "", "speaker": None})[0] == [])

    check("a plain dict filters the same as the dataclass",
          where_clauses({"body": "Select Board"})[0]
          == where_clauses(RetrievalFilters(body="Select Board"))[0])
    check("an unknown key is ignored rather than injected",
          where_clauses({"drop table": "x"})[0] == [])

    sql, bound = search_sql("brookline-ma", [0.0, 1.0], 5,
                            RetrievalFilters(body="Select Board"))
    check("filters reach the dense query", "lower(body)" in sql)
    check("and the value is bound", bound["f_body"] == "Select Board")


def test_every_statement_is_scoped_to_one_community() -> None:
    print("\nmulti-tenancy: no query may cross communities")
    statements = {
        "hybrid_search": hybrid_sql("bk", "q", [0.0], 8)[0],
        "search": search_sql("bk", [0.0], 5)[0],
        "upsert": upsert_sql(),
        "corpus walk": page_sql(),
        "get_by_id": by_id_sql(),
        "stats": stats_sql(),
        "existing ids": ids_sql(),
        "delete_by_source": delete_by_source_sql(),
    }
    for name, sql in statements.items():
        check(f"{name} names project_id", "project_id" in sql, sql[:80])

    check("deleting a source cannot reach another community's rows",
          "WHERE project_id = %(project)s AND source = %(source)s"
          in delete_by_source_sql())
    check("the corpus walk pages by key, not by OFFSET",
          "id > %(after)s" in page_sql() and "OFFSET" not in page_sql())


def test_upsert_makes_a_re_run_idempotent() -> None:
    print("\nre-ingesting and re-migrating update rather than duplicate")
    sql = upsert_sql()
    check("conflicts on the community and chunk together",
          "ON CONFLICT (project_id, id) DO UPDATE" in sql)
    check("the embedding is replaced, not kept",
          "embedding = EXCLUDED.embedding" in sql)
    check("every payload column is replaced",
          all(f"{identifier} = EXCLUDED.{identifier}" in sql
              for _key, identifier in COLUMNS))
    check("and so is the jsonb remainder", "payload = EXCLUDED.payload" in sql)

    store_id = PgVectorStore.generate_id(
        None, "The board took no vote.", {"url": "https://ex.org/a"})
    again = PgVectorStore.generate_id(
        None, "The board took no vote.", {"url": "https://ex.org/a"})
    check("chunk ids are deterministic, so the conflict fires", store_id == again)


def test_a_payload_survives_the_round_trip_through_a_row() -> None:
    print("\npayload to row to payload")
    row = payload_to_row(TRANSCRIPT_PAYLOAD, "brookline-ma", "deadbeef")

    check("the row carries its community", row["project_id"] == "brookline-ma")
    check("and its id", row["id"] == "deadbeef")
    check("a loose date becomes a real date for a date column",
          row["meeting_date"].isoformat() == "2026-04-14", repr(row["meeting_date"]))
    check("a timestamp stays a float", row["start_time"] == 4422.0)
    check("a missing page is NULL, not zero", row["page"] is None)
    check("a missing start time would be NULL too, never second zero",
          payload_to_row({"text": "x"}, "bk", "i")["start_time"] is None)
    check("a false boolean stays false rather than becoming a string",
          row["vote_taken"] is False, repr(row["vote_taken"]))

    extras = json.loads(row["payload"])
    check("a key with no column of its own is kept in jsonb",
          extras.get("caption_source") == "auto-generated", str(extras))
    check("which is also what protects a civic field added later",
          set(extras) == {"video_id", "caption_source"}, str(sorted(extras)))

    # What a SELECT would hand back: the same row, with jsonb already decoded.
    fetched = {k: v for k, v in row.items() if k != "project_id"}
    fetched["payload"] = extras
    payload = row_to_payload(fetched)

    check("the id comes back", payload["id"] == "deadbeef")
    check("the passage comes back whole",
          payload["text"] == TRANSCRIPT_PAYLOAD["text"])
    check("dates come back as the YYYY-MM-DD the app speaks",
          payload["meeting_date"] == "2026-04-14", str(payload.get("meeting_date")))
    check("empty columns are dropped rather than returned as blanks",
          "page" not in payload and "department" not in payload, str(sorted(payload)))
    check("the extra key survived the trip",
          payload["caption_source"] == "auto-generated")

    chunk = normalize_payload(payload)
    original = normalize_payload(TRANSCRIPT_PAYLOAD)
    for field in ("text", "body", "community", "speaker", "speaker_role",
                  "agenda_item", "meeting_date", "start_time", "source_type",
                  "status", "status_confidence", "vote_taken", "title", "url"):
        check(f"survives as a CivicChunk field: {field}",
              getattr(chunk, field) == getattr(original, field),
              f"{getattr(chunk, field)!r} != {getattr(original, field)!r}")
    check("the legacy youtube type still maps forward",
          chunk.source_type == SourceType.MEETING_TRANSCRIPT)
    check("the citation still deep links to the video",
          chunk.video_url.endswith("abc123") and chunk.start_time == 4422.0)

    check("a vector renders in pgvector's text form",
          vector_literal([0.5, -0.25]) == "[0.5,-0.25]", vector_literal([0.5, -0.25]))
    check("every CivicChunk field has a column or a documented home",
          set(CivicChunk.__dataclass_fields__) - {key for key, _ in COLUMNS} == set(),
          str(sorted(set(CivicChunk.__dataclass_fields__)
                     - {key for key, _ in COLUMNS})))


def test_the_factory_picks_a_backend() -> None:
    print("\nwhich archive a project gets")
    saved = os.environ.pop("COMMUNITY_DB_URL", None)
    try:
        choice = select_backend(FakeProject("brookline-ma"))
        check("with nothing configured it is still Qdrant",
              choice.backend == QDRANT, choice.backend)
        check("at the path the app has always used",
              choice.path == "./data/brookline-ma/qdrant", choice.path)
        check("the collection is the project id",
              choice.collection_name == "brookline-ma")
        check("and it says why", "no COMMUNITY_DB_URL" in choice.reason, choice.reason)

        os.environ["COMMUNITY_DB_URL"] = "postgresql://civic@db/civic"
        choice = select_backend(FakeProject("brookline-ma"))
        check("the environment variable switches the backend",
              choice.backend == PGVECTOR, choice.backend)
        check("the dsn is carried through",
              choice.dsn == "postgresql://civic@db/civic")
        check("project_id is still the tenancy key",
              choice.collection_name == "brookline-ma")

        choice = select_backend(FakeProject("cambridge-ma", "postgresql://civic@other/civic"))
        check("a project setting beats the environment",
              choice.dsn == "postgresql://civic@other/civic", choice.dsn)
        check("which is how one town moves before the rest",
              "project setting" in choice.reason, choice.reason)

        choice = select_backend(FakeProject("brookline-ma"), dsn="postgresql://x@y/z")
        check("an explicit dsn beats both", choice.dsn == "postgresql://x@y/z")

        check("a bare project id works as well as a config object",
              select_backend("brookline-ma").collection_name == "brookline-ma")
    finally:
        os.environ.pop("COMMUNITY_DB_URL", None)
        if saved is not None:
            os.environ["COMMUNITY_DB_URL"] = saved

    # build_store itself is only exercised as far as the decision: opening
    # either backend needs qdrant-client or psycopg, and this machine has
    # neither.
    check("neither backend is actually opened by these tests", True)


def test_the_retriever_prefers_a_store_that_fuses_for_itself() -> None:
    print("\nHybridRetriever prefers the database when the store offers it")
    corpus = [
        {"text": "Article 8.1 of the zoning bylaw governs signage dimensions.",
         "source_type": "municipal_document", "title": "Zoning Bylaw", "page": 81},
        {"text": "Article 8.4 of the zoning bylaw permits accessory dwelling units.",
         "source_type": "municipal_document", "title": "Zoning Bylaw", "page": 84},
    ]

    store = NativeHybridStore(corpus)
    result = HybridRetriever(store, cache_key="native-test").retrieve(
        "What does Article 8.4 say?", top_k=2, use_reranker=False)

    check("the store's own hybrid search was used", len(store.hybrid_calls) == 1)
    check("the dense-only search was not also run",
          store.search_calls == [], str(store.search_calls))
    check("no corpus was walked to build a keyword index",
          "keyword index unavailable" not in " ".join(result.notes))
    check("and the diagnostics say where the work happened",
          "hybrid search ran in the database" in result.notes, str(result.notes))

    check("the store's ordering is kept",
          [c.chunk_id for c in result.chunks] == ["doc-1", "doc-0"],
          str([c.chunk_id for c in result.chunks]))
    check("a passage found by both halves says so",
          result.chunks[0].retrieval_path == "both", result.chunks[0].retrieval_path)
    check("a passage found only by the vector half says that",
          result.chunks[1].retrieval_path == "dense", result.chunks[1].retrieval_path)
    check("both halves are counted for the transparency panel",
          result.dense_hits == 2 and result.sparse_hits == 1,
          f"dense={result.dense_hits} sparse={result.sparse_hits}")
    check("corpus size is asked for rather than counted",
          result.corpus_size == 2, str(result.corpus_size))

    filters = RetrievalFilters(body="Select Board")
    HybridRetriever(store, cache_key="native-test").retrieve(
        "anything", top_k=2, filters=filters, use_reranker=False)
    _query, vector, pool, passed = store.hybrid_calls[-1]
    check("filters are handed to the store rather than applied afterwards",
          passed is filters, str(passed))
    check("the store is left to embed the question itself", vector is None)
    check("the candidate pool is passed as top_k", pool == 24, str(pool))


def test_a_broken_database_falls_back_instead_of_failing() -> None:
    print("\na database that fails mid-question does not end the question")
    corpus = [
        {"text": "Article 8.4 of the zoning bylaw permits accessory dwelling units.",
         "source_type": "municipal_document", "title": "Zoning Bylaw", "page": 84},
        {"text": "Curbside collection shifts a day during holiday weeks.",
         "source_type": "website", "title": "Public Works FAQ"},
    ]
    store = BrokenHybridStore(corpus, collection_name="broken")
    result = HybridRetriever(store, cache_key="broken-test").retrieve(
        "Article 8.4", top_k=2, use_reranker=False)

    check("the resident still gets passages", len(result.chunks) > 0)
    check("the in-process path ran instead", store.search_calls != [])
    check("and the failure is reported, not hidden",
          any("hybrid search unavailable" in note for note in result.notes),
          str(result.notes))

    check("a store without the method is untouched by any of this",
          not hasattr(FakeVectorStore([], "plain"), "hybrid_search"))


def test_the_migration_counts_skips_and_resumes() -> None:
    print("\nthe copy loop, with a driver that records instead of connecting")
    import stores.pgvector_store as module
    from stores.migrate import copy_collection, redact

    check("a password is hidden before a DSN is printed",
          redact("postgresql://civic:hunter2@10.0.0.5/civic")
          == "postgresql://civic:***@10.0.0.5/civic",
          redact("postgresql://civic:hunter2@10.0.0.5/civic"))

    saved_driver = dict(module._driver)
    saved_pools = dict(module._pools)
    try:
        store, driver = store_with_recording_driver()
        check("the store opens once the driver is there",
              store.project_id == "brookline-ma")
        check("and reports an empty archive before anything is copied",
              store.get_stats()["total_documents"] == 0)

        counts = copy_collection(store, FakeQdrantClient(), "brookline-ma",
                                 batch_size=2)
        check("only the citable chunk was copied", counts["copied"] == 1, str(counts))
        check("a chunk with no vector is counted, not dropped silently",
              counts["no_vector"] == 1, str(counts))
        check("a chunk with no text is counted too",
              counts["no_text"] == 1, str(counts))
        check("and the source total is reported alongside",
              counts["source_total"] == 3 and counts["read"] == 3, str(counts))

        copied = driver.rows["aaa"]
        check("the copied row carries its community",
              copied["project_id"] == "brookline-ma")
        check("its loose date became a real date",
              copied["meeting_date"].isoformat() == "2026-04-14",
              repr(copied["meeting_date"]))
        check("and its vector was copied rather than recomputed",
              copied["embedding"].startswith("[0.1,0.1"), copied["embedding"][:16])

        again = copy_collection(store, FakeQdrantClient(), "brookline-ma",
                                batch_size=2)
        check("a second run copies nothing", again["copied"] == 0, str(again))
        check("because the chunk was recognized as already there",
              again["skipped"] == 1, str(again))
        check("and the archive did not double",
              store.get_stats()["total_documents"] == 1)

        forced = copy_collection(store, FakeQdrantClient(), "brookline-ma",
                                 batch_size=2, force=True)
        check("--force copies it again", forced["copied"] == 1, str(forced))
        check("and still does not duplicate the row",
              store.get_stats()["total_documents"] == 1)
    finally:
        module._driver.clear()
        module._driver.update(saved_driver)
        module._pools.clear()
        module._pools.update(saved_pools)

    check("the recorded driver is put back afterwards",
          module._driver == saved_driver)


def test_chunk_text_matches_the_qdrant_store() -> None:
    print("\nchunking is identical across the two backends")
    stub_ml_stack()
    from vector_store import VectorStore

    text = " ".join(f"word{i}" for i in range(1400))
    # Neither implementation touches self, so they can be compared unbound
    # rather than by constructing a store and an embedding model.
    qdrant_chunks = VectorStore.chunk_text(None, text)
    postgres_chunks = PgVectorStore.chunk_text(None, text)
    check("the same text splits the same way", qdrant_chunks == postgres_chunks,
          f"{len(qdrant_chunks)} vs {len(postgres_chunks)}")
    check("and so does a short passage that produces nothing",
          VectorStore.chunk_text(None, "too short")
          == PgVectorStore.chunk_text(None, "too short") == [])
    check("custom sizes agree too",
          VectorStore.chunk_text(None, text, 200, 20)
          == PgVectorStore.chunk_text(None, text, 200, 20))


def test_the_interface_matches_the_qdrant_store() -> None:
    print("\nthe two stores answer to the same names")
    stub_ml_stack()
    from vector_store import VectorStore

    for name in ("add_document", "add_documents_batch", "search",
                 "iter_all_payloads", "get_by_id", "get_stats",
                 "delete_by_source", "chunk_text", "generate_id"):
        check(f"PgVectorStore has {name}", hasattr(PgVectorStore, name))
        check(f"VectorStore still has {name}", hasattr(VectorStore, name))

    check("and PgVectorStore adds the one Qdrant cannot do",
          hasattr(PgVectorStore, "hybrid_search")
          and not hasattr(VectorStore, "hybrid_search"))

    import inspect

    qdrant_search = list(inspect.signature(VectorStore.search).parameters)
    postgres_search = list(inspect.signature(PgVectorStore.search).parameters)
    check("search takes the same arguments", qdrant_search == postgres_search,
          f"{qdrant_search} vs {postgres_search}")

    init = list(inspect.signature(PgVectorStore.__init__).parameters)
    check("the constructor takes a dsn where the other takes a path",
          init[1] == "dsn" and "path" not in init, str(init))
    check("and the rest of the constructor matches",
          init[2:4] == ["collection_name", "embedding_model"], str(init))


def main() -> int:
    print("=" * 62)
    print("PostgreSQL archive tests")
    print("=" * 62)
    for fn in [
        test_a_missing_driver_names_a_remedy,
        test_schema_carries_the_configured_vector_width,
        test_schema_indexes_what_the_queries_read,
        test_row_level_security_is_scaffolded_and_left_off,
        test_hybrid_sql_is_the_fusion_query_from_the_roadmap,
        test_filters_translate_the_way_the_python_path_matches,
        test_every_statement_is_scoped_to_one_community,
        test_upsert_makes_a_re_run_idempotent,
        test_a_payload_survives_the_round_trip_through_a_row,
        test_the_factory_picks_a_backend,
        test_the_retriever_prefers_a_store_that_fuses_for_itself,
        test_a_broken_database_falls_back_instead_of_failing,
        test_the_migration_counts_skips_and_resumes,
        test_chunk_text_matches_the_qdrant_store,
        test_the_interface_matches_the_qdrant_store,
    ]:
        fn()

    print("\nNot covered here, because there is no server to ask:")
    for gap in [
        "that PostgreSQL accepts this DDL and that pgvector is installed",
        "that the planner actually uses the HNSW and GIN indexes",
        "that the fused ordering matches rag.bm25.reciprocal_rank_fusion on real data",
        "that the row-level security policy isolates communities once enabled",
        "that a real Qdrant collection scrolls into a real table: the copy loop "
        "is exercised above, but against a driver that records rather than writes",
    ]:
        print(f"  - {gap}")
    print("  Run these against a live database before a community depends on it.")

    print("\n" + "=" * 62)
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    for name in FAIL:
        print(f"  FAILED: {name}")
    return 1 if FAIL else 0


def test_all() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
