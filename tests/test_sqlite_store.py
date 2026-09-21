"""Tests for the one-file archive.

Unlike tests/test_pgvector.py, this suite opens the real database, because the
whole argument for this backend is that doing so costs nothing: no server, no
port, no credentials, a temporary directory and a file. What is faked is the
embedding model, replaced with a deterministic bag-of-words vector, so that
ranking is reproducible and the suite does not download 90MB of weights to
prove that cosine similarity sorts descending.

The checks that matter most are the ones about the FTS5 triggers. The reason
to prefer this backend over the in-memory keyword index is that the database
maintains the index instead of the application rebuilding it on every start.
That claim is only true if a delete and an overwrite both reach the index, so
those are tested by searching for text that should have stopped existing.

Run with:  python3 -m tests.test_sqlite_store     (no pytest required)
       or:  python3 -m pytest tests/
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
import tempfile
from typing import Any, Dict, List

from stores import (
    PGVECTOR, QDRANT, SQLITE, has_qdrant_index, parse_dsn, select_backend,
    sqlite_path_for,
)
from stores.sqlite_store import (
    FILTER_COLUMNS, RRF_K, SqliteStoreError, SqliteVectorStore,
    escape_fts_query, fts5_available, pack_vector, unpack_vector,
)

PASS: List[str] = []
FAIL: List[str] = []

DIMENSION = 64


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  -> {detail}" if not condition else ""))


class FakeProject:
    def __init__(self, project_id: str, community_db_url: str = "") -> None:
        self.project_id = project_id
        self.community_db_url = community_db_url
        self.embedding_model = "all-MiniLM-L6-v2"


class TestStore(SqliteVectorStore):
    """The real store with a deterministic stand-in for the encoder.

    Bag of words over a fixed number of slots: two passages about the same
    subject land near each other, and the same text always produces the same
    vector, which is what makes an ordering check meaningful.
    """

    def embed(self, text: str) -> List[float]:
        vector = [0.0] * DIMENSION
        for word in (text or "").lower().split():
            word = word.strip(".,;:()\"'")
            if not word:
                continue
            slot = int(hashlib.md5(word.encode()).hexdigest(), 16) % DIMENSION
            vector[slot] += 1.0
        if not any(vector):
            vector[0] = 1.0
        return vector


CORPUS = [
    {
        "text": "Article 8.4 of the zoning bylaw permits accessory dwelling units "
                "on any lot that already contains a single family home.",
        "metadata": {"source": "zoning-bylaw.pdf", "source_type": "municipal_document",
                     "title": "Zoning Bylaw", "document_type": "bylaw",
                     "section": "Article 8.4", "page": 84,
                     "url": "https://example.org/zoning.pdf"},
    },
    {
        "text": "Article 8.1 of the zoning bylaw governs the dimensions of signage "
                "in the commercial district.",
        "metadata": {"source": "zoning-bylaw.pdf", "source_type": "municipal_document",
                     "title": "Zoning Bylaw", "document_type": "bylaw",
                     "section": "Article 8.1", "page": 81,
                     "url": "https://example.org/zoning.pdf"},
    },
    {
        "text": "Chair Wilson: the motion to approve the accessory dwelling unit "
                "amendment carries, four to one.",
        "metadata": {"source": "selectboard-2024-03-12", "source_type": "meeting_transcript",
                     "title": "Select Board Meeting", "body": "Select Board",
                     "meeting_date": "2024-03-12", "speaker": "Chair Wilson",
                     "agenda_item": "Zoning amendment", "vote_taken": True,
                     "vote_outcome": "passed", "vote_tally": "4-1",
                     "start_time": 1820.0,
                     "url": "https://youtube.com/watch?v=abc123"},
    },
    {
        "text": "Member Ortiz: I move we table the sidewalk repair contract until "
                "the engineering report is complete.",
        "metadata": {"source": "selectboard-2023-11-02", "source_type": "meeting_transcript",
                     "title": "Select Board Meeting", "body": "Select Board",
                     "meeting_date": "2023-11-02", "speaker": "Member Ortiz",
                     "agenda_item": "Sidewalk repair", "start_time": 640.0,
                     "url": "https://youtube.com/watch?v=def456"},
    },
    {
        "text": "The School Committee voted unanimously to adopt the fiscal year "
                "2025 budget as presented by the superintendent.",
        "metadata": {"source": "schoolcommittee-2024-06-04", "source_type": "meeting_transcript",
                     "title": "School Committee Meeting", "body": "School Committee",
                     "meeting_date": "2024-06-04", "speaker": "Chair Nguyen",
                     "vote_taken": True, "vote_outcome": "passed",
                     "vote_tally": "unanimous",
                     "url": "https://youtube.com/watch?v=ghi789"},
    },
]


def loaded_store(directory: str) -> TestStore:
    store = TestStore(path=os.path.join(directory, "archive.sqlite3"),
                      collection_name="brookline-ma")
    store.add_documents_batch(CORPUS)
    return store


# --- the precondition -----------------------------------------------------


def test_fts5_is_there() -> None:
    print("\nthe one thing this backend actually requires")
    check("this Python's sqlite3 has FTS5 compiled in", fts5_available(),
          "without it the store refuses to open rather than searching badly")
    check("SqliteStoreError exists to say so", issubclass(SqliteStoreError, RuntimeError))


# --- query escaping -------------------------------------------------------


def test_a_question_survives_becoming_a_match_expression() -> None:
    print("\nturning a resident's question into FTS5 syntax")
    check("a plain question is quoted term by term",
          escape_fts_query("accessory dwelling units")
          == '"accessory" OR "dwelling" OR "units"',
          escape_fts_query("accessory dwelling units"))
    check("a section number stays one term",
          '"article"' in escape_fts_query("Article 8.4").lower()
          and '"8.4"' in escape_fts_query("Article 8.4"),
          escape_fts_query("Article 8.4"))
    check("a docket number keeps its hyphen",
          '"24-105"' in escape_fts_query("docket 24-105"),
          escape_fts_query("docket 24-105"))
    check("an empty question produces no expression", escape_fts_query("") == "")
    check("punctuation alone produces no expression", escape_fts_query("?? -- ,") == "")
    check("an embedded quote cannot close the quoting",
          '"' not in escape_fts_query('say "hello"').replace('"say"', "")
          .replace(" OR ", "").replace('"hello"', ""),
          escape_fts_query('say "hello"'))

    with tempfile.TemporaryDirectory() as d:
        store = loaded_store(d)
        for hostile in ['zoning: "article" (8.4) -- NEAR/2', "AND OR NOT", "*", '"'"'"'']:
            try:
                store.hybrid_search(hostile, top_k=3)
                ok = True
            except sqlite3.OperationalError as exc:  # pragma: no cover
                ok = False
                detail = str(exc)
            check(f"a question containing {hostile!r} searches rather than erroring", ok,
                  detail if not ok else "")


# --- storage --------------------------------------------------------------


def test_a_payload_survives_the_round_trip() -> None:
    print("\nwhat goes in comes back out")
    with tempfile.TemporaryDirectory() as d:
        store = loaded_store(d)

        ids = [doc_id for doc_id, _ in store.iter_all_payloads()]
        check("every document was stored", len(ids) == len(CORPUS), str(len(ids)))
        check("ids are stable", len(set(ids)) == len(ids))

        vote = None
        for _, payload in store.iter_all_payloads():
            if payload.get("speaker") == "Chair Wilson":
                vote = payload
        check("a transcript chunk keeps its speaker", vote is not None)
        if vote:
            check("and its body", vote.get("body") == "Select Board", str(vote.get("body")))
            check("and its meeting date", vote.get("meeting_date") == "2024-03-12")
            check("and its timestamp into the recording",
                  float(vote.get("start_time") or 0) == 1820.0, str(vote.get("start_time")))
            check("and the fact that a vote was taken", bool(vote.get("vote_taken")))
            check("and the tally", vote.get("vote_tally") == "4-1", str(vote.get("vote_tally")))
            check("and the video url, which is how the citation embeds",
                  "youtube.com" in str(vote.get("url")))

        doc_id = ids[0]
        fetched = store.get_by_id(doc_id)
        check("get_by_id returns the payload", isinstance(fetched, dict))
        check("carrying its id", (fetched or {}).get("id") == doc_id)
        check("a missing id is None, not an error", store.get_by_id("nope") is None)

        row = store._connect().execute(
            "SELECT * FROM chunks WHERE id = ?", (doc_id,)).fetchone()
        missing = [c for c in FILTER_COLUMNS if c not in row.keys()]
        check("every filterable field has its own column", not missing, str(missing))


def test_vectors_pack_and_unpack() -> None:
    print("\nembeddings on disk")
    values = [0.5, -0.25, 0.125, 0.0]
    blob = pack_vector(values)
    check("a vector is four bytes per dimension", len(blob) == len(values) * 4, str(len(blob)))
    check("and survives the round trip", unpack_vector(blob) == values, str(unpack_vector(blob)))
    check("width is recoverable from the blob alone", len(blob) // 4 == len(values))


# --- retrieval ------------------------------------------------------------


def test_the_keyword_half_is_the_database_not_the_app() -> None:
    print("\nBM25 from FTS5, no Python index")
    with tempfile.TemporaryDirectory() as d:
        store = loaded_store(d)

        hits = store._keyword_candidates("Article 8.4", 5, "", [])
        check("an exact section number matches", bool(hits))
        if hits:
            top = store.get_by_id(hits[0][0]) or {}
            check("and 8.4 outranks 8.1, which is the bug this backend exists to fix",
                  top.get("section") == "Article 8.4", str(top.get("section")))

        tally = store._keyword_candidates("four to one", 5, "", [])
        check("a spoken tally is findable", bool(tally))

        empty = store._keyword_candidates("", 5, "", [])
        check("an empty query returns nothing rather than everything", empty == [])

        rows = store._connect().execute("SELECT COUNT(*) AS n FROM chunks_fts").fetchone()
        check("the index has a row per document, maintained by sqlite",
              rows["n"] == len(CORPUS), str(rows["n"]))


def test_the_dense_half_ranks_by_similarity() -> None:
    print("\ncosine similarity over the stored embeddings")
    with tempfile.TemporaryDirectory() as d:
        store = loaded_store(d)

        ranked = store._vector_candidates(
            store.embed("accessory dwelling units zoning"), 5, "", [])
        check("every document is a candidate", len(ranked) == len(CORPUS), str(len(ranked)))
        check("scores descend", all(a[1] >= b[1] for a, b in zip(ranked, ranked[1:])),
              str([round(s, 3) for _, s in ranked]))
        top = store.get_by_id(ranked[0][0]) or {}
        check("the nearest passage is the one about the subject asked about",
              "accessory dwelling" in str(top.get("text", "")).lower(),
              str(top.get("text", ""))[:60])

        hits = store.search("school budget", top_k=2)
        check("search() returns hit dictionaries", all("score" in h for h in hits))
        check("with the text", all(h.get("text") for h in hits))


def test_hybrid_search_fuses_both_halves() -> None:
    print("\nreciprocal rank fusion, the same algebra as the in-memory path")
    with tempfile.TemporaryDirectory() as d:
        store = loaded_store(d)

        hits = store.hybrid_search("accessory dwelling unit amendment", top_k=4)
        check("it returns results", bool(hits))
        check("no more than asked for", len(hits) <= 4, str(len(hits)))
        check("ordered by fused score", all(a["score"] >= b["score"]
                                            for a, b in zip(hits, hits[1:])),
              str([round(h["score"], 4) for h in hits]))
        check("and it records which half found each hit",
              any("dense_rank" in h or "sparse_rank" in h for h in hits))
        check("the fusion constant is the one rag.bm25 uses", RRF_K == 60, str(RRF_K))

        top_texts = " ".join(h["text"].lower() for h in hits[:2])
        check("the vote and the bylaw both surface for a question spanning them",
              "carries" in top_texts and "8.4" in top_texts, top_texts[:120])

        # Worth being exact about: dense retrieval always returns its nearest
        # neighbours, so a nonsense question still produces rows. What it does
        # not produce is keyword evidence, and refusing to answer on weak
        # evidence is the reranker's job and the constitution's, not the
        # store's. A test asserting the store returns nothing here would be
        # asserting something false about how vector search works.
        check("a nonsense query finds no keyword evidence",
              store._keyword_candidates("qqzzxx", 5, "", []) == [])
        check("though dense neighbours still come back, as they must",
              bool(store.hybrid_search("qqzzxx", top_k=5)))


def test_filters_narrow_the_archive() -> None:
    print("\ncivic filters as SQL")
    with tempfile.TemporaryDirectory() as d:
        store = loaded_store(d)

        only_docs = store.hybrid_search("zoning", top_k=10,
                                        filters={"source_type": "municipal_document"})
        check("source_type excludes transcripts",
              all(h["metadata"].get("source_type") == "municipal_document" for h in only_docs),
              str([h["metadata"].get("source_type") for h in only_docs]))

        board = store.hybrid_search("motion", top_k=10, filters={"body": "select board"})
        check("body matches case insensitively",
              bool(board) and all(h["metadata"].get("body") == "Select Board" for h in board),
              str([h["metadata"].get("body") for h in board]))

        recent = store.hybrid_search("motion vote budget", top_k=10,
                                     filters={"date_from": "2024-01-01"})
        check("a date floor drops older meetings",
              all(h["metadata"].get("meeting_date", "") >= "2024-01-01"
                  for h in recent if h["metadata"].get("meeting_date")),
              str([h["metadata"].get("meeting_date") for h in recent]))
        check("and does not drop undated documents silently by including them",
              all(h["metadata"].get("source_type") == "meeting_transcript" for h in recent),
              "a date filter on an undated record should exclude it")

        ortiz = store.hybrid_search("sidewalk", top_k=10, filters={"speaker": "Ortiz"})
        check("a speaker matches on part of the name",
              bool(ortiz) and all("Ortiz" in h["metadata"].get("speaker", "") for h in ortiz))

        none = store.hybrid_search("zoning", top_k=10, filters={"body": "Planning Board"})
        check("a filter matching nothing returns nothing, not everything", none == [])


# --- the triggers, which are the actual claim -----------------------------


def test_deleting_a_source_reaches_the_keyword_index() -> None:
    print("\nDELETE keeps the index in step")
    with tempfile.TemporaryDirectory() as d:
        store = loaded_store(d)
        before = store._keyword_candidates("sidewalk", 5, "", [])
        check("the passage is findable first", bool(before))

        store.delete_by_source("selectboard-2023-11-02")

        after = store._keyword_candidates("sidewalk", 5, "", [])
        check("and gone from the keyword index afterwards", after == [], str(after))
        check("gone from the table too",
              len(list(store.iter_all_payloads())) == len(CORPUS) - 1)
        check("and gone from hybrid search",
              all("sidewalk" not in h["text"].lower()
                  for h in store.hybrid_search("sidewalk repair contract", top_k=5)))


def test_overwriting_a_document_reaches_the_keyword_index() -> None:
    print("\nre-ingesting the same chunk replaces it rather than duplicating it")
    with tempfile.TemporaryDirectory() as d:
        store = TestStore(path=os.path.join(d, "archive.sqlite3"))
        metadata = {"source": "corrections.txt", "source_type": "municipal_document",
                    "url": "https://example.org/correction"}
        text = "The culvert replacement is scheduled for Thursday."
        first = store.add_document(text, metadata)
        again = store.add_document(text, metadata)
        check("the same text and url produce the same id", first == again, f"{first} {again}")
        check("and one row, not two", len(list(store.iter_all_payloads())) == 1)

        rows = store._connect().execute("SELECT COUNT(*) AS n FROM chunks_fts").fetchone()
        check("and one index entry, not two", rows["n"] == 1, str(rows["n"]))
        check("still findable", bool(store._keyword_candidates("culvert", 5, "", [])))


def test_two_passages_of_one_meeting_that_open_alike_are_both_kept() -> None:
    print("\npassage ids within a recording")
    import hashlib

    from stores.ids import passage_id
    from stores.pgvector_store import PgVectorStore

    video = "https://www.youtube.com/watch?v=-qBhj-2C4Pw"
    music = "[music] " * 40      # what a stream sounds like before the gavel, and at the recess
    with tempfile.TemporaryDirectory() as d:
        store = TestStore(path=os.path.join(d, "archive.sqlite3"))
        store.add_documents_batch([
            {"text": music, "metadata": {"url": video, "start_time": 7.0, "source": "bigtv"}},
            {"text": music, "metadata": {"url": video, "start_time": 5306.0, "source": "bigtv"}},
        ])
        check("the second did not overwrite the first",
              len(list(store.iter_all_payloads())) == 2,
              str(len(list(store.iter_all_payloads()))))

        store.add_documents_batch([
            {"text": music, "metadata": {"url": video, "start_time": 7.0, "source": "bigtv"}}])
        check("and ingesting a passage again still replaces it",
              len(list(store.iter_all_payloads())) == 2)

    page = {"url": "https://example.org/zoning.pdf", "page": 84}
    text = "Article 8.4 permits accessory dwelling units by right."
    check("a passage with no start time keeps the id it always had",
          passage_id(text, page) == hashlib.md5((page["url"] + text[:100]).encode()).hexdigest())

    timed = {"url": video, "start_time": 754.2}
    check("the backends agree, so a migrated archive does not double",
          TestStore.generate_id(None, text, timed) == PgVectorStore.generate_id(None, text, timed)
          == passage_id(text, timed))
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "vector_store.py"), encoding="utf-8") as handle:
        check("including the one that predates them",
              "passage_id(text, metadata)" in handle.read())


def test_vacuum_rebuilds_rather_than_corrupting() -> None:
    print("\nmaintenance after bulk deletion")
    with tempfile.TemporaryDirectory() as d:
        store = loaded_store(d)
        store.delete_by_source("zoning-bylaw.pdf")
        store.vacuum()
        check("the archive still answers after a vacuum",
              bool(store.hybrid_search("budget", top_k=3)))
        check("and the deleted source stays deleted",
              store._keyword_candidates("signage", 5, "", []) == [])
        integrity = store._connect().execute("PRAGMA integrity_check").fetchone()[0]
        check("integrity check passes", integrity == "ok", integrity)


# --- operations -----------------------------------------------------------


def test_stats_tell_an_operator_where_the_archive_is() -> None:
    print("\nget_stats")
    with tempfile.TemporaryDirectory() as d:
        store = loaded_store(d)
        stats = store.get_stats()
        check("the count is right", stats["total_documents"] == len(CORPUS),
              str(stats["total_documents"]))
        check("the vector width is reported", stats["vector_size"] == DIMENSION,
              str(stats["vector_size"]))
        check("the backend names itself", stats["backend"] == "sqlite", stats["backend"])
        check("the path is absolute enough to find", stats["path"].endswith("archive.sqlite3"))
        check("the file size is real", stats["file_size_bytes"] > 0,
              str(stats["file_size_bytes"]))
        check("and it says the keyword index is fts5", stats["keyword_index"] == "fts5")
        check("and whether the vector extension is loaded",
              isinstance(stats["vector_extension"], bool))


def test_a_backup_is_a_working_archive() -> None:
    print("\nbackup_to")
    with tempfile.TemporaryDirectory() as d:
        store = loaded_store(d)
        destination = os.path.join(d, "backups", "archive-2026-09-20.sqlite3")
        store.backup_to(destination)
        check("the backup exists", os.path.exists(destination))

        restored = TestStore(path=destination)
        check("it opens as an archive",
              len(list(restored.iter_all_payloads())) == len(CORPUS))
        check("with a working keyword index, not just the rows",
              bool(restored._keyword_candidates("accessory dwelling", 5, "", [])))
        check("and it answers questions",
              bool(restored.hybrid_search("what did the board decide about zoning", top_k=3)))
        restored.close()

        store.add_document("A later addition after the backup was taken.",
                           {"source": "later.txt", "url": "https://example.org/later"})
        second = TestStore(path=destination)
        check("the backup is a snapshot, not a live mirror",
              len(list(second.iter_all_payloads())) == len(CORPUS), "a copy should not grow")
        second.close()


def test_the_store_offers_what_the_application_calls() -> None:
    print("\ninterface parity with the other two backends")
    required = ["add_document", "add_documents_batch", "search", "hybrid_search",
                "iter_all_payloads", "get_by_id", "get_stats", "delete_by_source",
                "chunk_text", "embed", "generate_id"]
    missing = [name for name in required if not callable(getattr(SqliteVectorStore, name, None))]
    check("every method the app calls on a store is present", not missing, str(missing))

    with tempfile.TemporaryDirectory() as d:
        store = TestStore(path=os.path.join(d, "a.sqlite3"))
        chunks = store.chunk_text(" ".join(f"word{i}" for i in range(1200)))
        check("chunk_text splits long text", len(chunks) > 1, str(len(chunks)))
        check("and drops fragments too short to cite",
              all(len(c.split()) > 50 for c in chunks))


# --- the factory ----------------------------------------------------------


def test_connection_strings_name_their_backend() -> None:
    print("\nparse_dsn")
    cases = [
        ("postgresql://civic@db/civic", PGVECTOR, ""),
        ("postgres://civic@db/civic", PGVECTOR, ""),
        ("sqlite:///srv/civic/archive.sqlite3", SQLITE, "/srv/civic/archive.sqlite3"),
        ("sqlite://data/archive.sqlite3", SQLITE, "data/archive.sqlite3"),
        ("./data/brookline/archive.sqlite3", SQLITE, "./data/brookline/archive.sqlite3"),
        ("/srv/civic.db", SQLITE, "/srv/civic.db"),
    ]
    for value, backend, path in cases:
        got_backend, _, got_path = parse_dsn(value)
        check(f"{value} is {backend}", got_backend == backend, got_backend)
        if path:
            check(f"  with path {path}", got_path == path, got_path)


def test_the_default_is_a_local_file() -> None:
    print("\nwhat a community gets when it configures nothing")
    saved_url = os.environ.pop("COMMUNITY_DB_URL", None)
    saved_path = os.environ.pop("COMMUNITY_DB_PATH", None)
    cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)

            choice = select_backend(FakeProject("brookline-ma"))
            check("the default backend is sqlite", choice.backend == SQLITE, choice.backend)
            check("at ./data/<project>/archive.sqlite3",
                  choice.path == sqlite_path_for("brookline-ma"), choice.path)
            check("and it says why in words an operator can act on",
                  "one file" in choice.reason, choice.reason)
            check("location reports the file for sqlite",
                  choice.location == choice.path, choice.location)

            # The rule that keeps a default change from being a data loss.
            os.makedirs("./data/cambridge-ma/qdrant/collection", exist_ok=True)
            open("./data/cambridge-ma/qdrant/meta.json", "w").write("{}")
            check("an existing qdrant index is detected", has_qdrant_index("cambridge-ma"))
            existing = select_backend(FakeProject("cambridge-ma"))
            check("and left alone rather than silently replaced with an empty file",
                  existing.backend == QDRANT, existing.backend)
            check("saying so", "existing qdrant" in existing.reason, existing.reason)

            os.makedirs("./data/empty-ma/qdrant", exist_ok=True)
            check("an empty directory is not an archive",
                  not has_qdrant_index("empty-ma"))
            check("so a fresh install still gets the new default",
                  select_backend(FakeProject("empty-ma")).backend == SQLITE)

            os.environ["COMMUNITY_DB_URL"] = "postgresql://civic@db/civic"
            check("an explicit Postgres dsn still wins over a local index",
                  select_backend(FakeProject("cambridge-ma")).backend == PGVECTOR)
            os.environ.pop("COMMUNITY_DB_URL")

            os.environ["COMMUNITY_DB_URL"] = "sqlite:///srv/shared/brookline.sqlite3"
            choice = select_backend(FakeProject("brookline-ma"))
            check("one setting can name either backend",
                  choice.backend == SQLITE
                  and choice.path == "/srv/shared/brookline.sqlite3", choice.path)
    finally:
        os.chdir(cwd)
        os.environ.pop("COMMUNITY_DB_URL", None)
        os.environ.pop("COMMUNITY_DB_PATH", None)
        if saved_url is not None:
            os.environ["COMMUNITY_DB_URL"] = saved_url
        if saved_path is not None:
            os.environ["COMMUNITY_DB_PATH"] = saved_path


def test_build_store_opens_the_file_it_named() -> None:
    print("\nbuild_store, for real, because it costs a temporary directory")
    from stores import build_store

    saved_url = os.environ.pop("COMMUNITY_DB_URL", None)
    saved_path = os.environ.pop("COMMUNITY_DB_PATH", None)
    cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            os.environ["COMMUNITY_DB_PATH"] = os.path.join(d, "built.sqlite3")
            store = build_store(FakeProject("brookline-ma"))
            check("it returns a SqliteVectorStore",
                  type(store).__name__ == "SqliteVectorStore", type(store).__name__)
            check("the file exists on disk", os.path.exists(os.path.join(d, "built.sqlite3")))
            check("the collection is the project id",
                  store.collection_name == "brookline-ma", store.collection_name)
            check("and nothing was ingested by opening it",
                  store.get_stats()["total_documents"] == 0)
            store.close()
    finally:
        os.chdir(cwd)
        os.environ.pop("COMMUNITY_DB_PATH", None)
        if saved_url is not None:
            os.environ["COMMUNITY_DB_URL"] = saved_url
        if saved_path is not None:
            os.environ["COMMUNITY_DB_PATH"] = saved_path


# --- backups --------------------------------------------------------------


def test_a_snapshot_is_taken_verified_and_described() -> None:
    print("\nstores.backup create")
    from stores import backup as backup_module

    with tempfile.TemporaryDirectory() as d:
        store = loaded_store(d)
        root = os.path.join(d, "backups")

        snapshot = backup_module.create(store.path, project_id="brookline-ma", root=root)
        check("the snapshot file exists", os.path.exists(snapshot.path))
        check("it verified", snapshot.verified, snapshot.verify_error)
        check("it counted the passages",
              snapshot.document_count == len(CORPUS), str(snapshot.document_count))
        check("so it counts as a good copy", snapshot.trustworthy)
        check("it carries a sha256", snapshot.sha256.startswith("sha256:"), snapshot.sha256)
        check("which matches the file",
              snapshot.sha256 == backup_module.sha256_file(snapshot.path))
        check("it recorded the embedding model, which a restore must match",
              snapshot.embedding_model == store.embedding_model, snapshot.embedding_model)
        check("it recorded the backend", snapshot.backend == "sqlite")
        check("and where it came from", store.path in snapshot.source_path
              or snapshot.source_path.endswith("archive.sqlite3"), snapshot.source_path)

        check("a manifest was written next to it", os.path.exists(snapshot.manifest_path))
        reread = backup_module.Snapshot.read_manifest(snapshot.manifest_path)
        check("and it round trips", reread.sha256 == snapshot.sha256)

        listed = backup_module.list_snapshots("brookline-ma", root)
        check("it shows up in the listing", len(listed) == 1, str(len(listed)))
        check("with its verification intact", listed[0].trustworthy)

        check("uploading with no bucket configured is a silent no-op",
              backup_module.upload(snapshot, bucket="").remote_uri == "")


def test_an_empty_archive_is_not_a_good_copy() -> None:
    print("\nverified but empty")
    from stores import backup as backup_module

    with tempfile.TemporaryDirectory() as d:
        store = TestStore(path=os.path.join(d, "archive.sqlite3"))
        snapshot = backup_module.create(store.path, project_id="new-ma",
                                        root=os.path.join(d, "backups"))
        check("an empty archive still verifies", snapshot.verified)
        check("but is not trustworthy", not snapshot.trustworthy)
        check("and says why in the manifest",
              any("empty" in note for note in snapshot.notes), str(snapshot.notes))


def test_a_changed_snapshot_is_caught() -> None:
    print("\nintegrity, which is the only security property a public archive needs")
    from stores import backup as backup_module

    with tempfile.TemporaryDirectory() as d:
        store = loaded_store(d)
        root = os.path.join(d, "backups")
        snapshot = backup_module.create(store.path, project_id="brookline-ma", root=root)

        # Writing zeros would not be a tamper: the middle of a SQLite page is
        # already unallocated zeros, so the file would be byte-identical and
        # the test would pass without testing anything.
        with open(snapshot.path, "r+b") as handle:
            handle.seek(200)
            handle.write(b"\xde\xad\xbe\xef" * 16)

        check("the hash no longer matches the manifest",
              backup_module.sha256_file(snapshot.path) != snapshot.sha256)

        target = os.path.join(d, "restored.sqlite3")
        try:
            backup_module.restore(snapshot.path, target)
            refused = False
            detail = "restore accepted a modified snapshot"
        except backup_module.BackupError as exc:
            refused = True
            detail = str(exc)
        check("and a restore refuses rather than installing it", refused, detail)
        check("saying what changed and what to do",
              "does not match its manifest" in detail or "does not open cleanly" in detail,
              detail[:80])
        check("and nothing was written to the destination", not os.path.exists(target))


def test_a_broken_snapshot_is_never_restored_quietly() -> None:
    print("\na snapshot that does not open")
    from stores import backup as backup_module

    with tempfile.TemporaryDirectory() as d:
        root = os.path.join(d, "backups")
        os.makedirs(root, exist_ok=True)
        broken = os.path.join(root, "archive-broken.sqlite3")
        open(broken, "wb").write(b"this is not a database")

        result = backup_module.verify(broken)
        check("verify says so", not result["verified"])
        check("with the database's own words", bool(result["verify_error"]),
              result["verify_error"])

        try:
            backup_module.restore(broken, os.path.join(d, "live.sqlite3"))
            refused = False
        except backup_module.BackupError:
            refused = True
        check("and restore refuses without --force", refused)


def test_restoring_moves_the_current_archive_aside() -> None:
    print("\nrestore does not overwrite what is there")
    from stores import backup as backup_module

    with tempfile.TemporaryDirectory() as d:
        store = loaded_store(d)
        root = os.path.join(d, "backups")
        snapshot = backup_module.create(store.path, project_id="brookline-ma", root=root)

        store.add_document("A regrettable later ingestion nobody wanted.",
                           {"source": "oops.txt", "url": "https://example.org/oops"})
        check("the live archive has grown",
              len(list(store.iter_all_payloads())) == len(CORPUS) + 1)
        store.close()

        result = backup_module.restore(snapshot.path, store.path)
        check("the restore reports what it put back",
              result["documents"] == len(CORPUS), str(result["documents"]))
        check("the displaced archive was kept, not deleted",
              bool(result["displaced"]) and os.path.exists(result["displaced"]))

        back = TestStore(path=store.path)
        check("the archive is the snapshot again",
              len(list(back.iter_all_payloads())) == len(CORPUS))
        check("and the regrettable ingestion is gone",
              not back._keyword_candidates("regrettable", 5, "", []))
        check("and it still answers", bool(back.hybrid_search("zoning bylaw", top_k=3)))
        back.close()


def test_retention_never_deletes_the_last_good_copy() -> None:
    print("\nprune")
    from stores import backup as backup_module

    with tempfile.TemporaryDirectory() as d:
        store = loaded_store(d)
        root = os.path.join(d, "backups")
        for n in range(5):
            backup_module.create(store.path, project_id="brookline-ma", root=root,
                                 label=f"2026-09-{10 + n}T00-00-00Z")

        check("five snapshots exist",
              len(backup_module.list_snapshots("brookline-ma", root)) == 5)

        planned = backup_module.prune("brookline-ma", root, keep=2, dry_run=True)
        check("a dry run reports what would go", len(planned) == 3, str(len(planned)))
        check("and deletes nothing",
              len(backup_module.list_snapshots("brookline-ma", root)) == 5)

        gone = backup_module.prune("brookline-ma", root, keep=2)
        remaining = backup_module.list_snapshots("brookline-ma", root)
        check("pruning to two leaves two", len(remaining) == 2, str(len(remaining)))
        check("the newest survives",
              remaining[0].taken_at >= remaining[-1].taken_at)
        check("the manifests went with them",
              not any(os.path.exists(s.manifest_path) for s in gone))

        backup_module.prune("brookline-ma", root, keep=0)
        left = backup_module.list_snapshots("brookline-ma", root)
        check("keep=0 still leaves the newest good copy, because the policy is "
              "not more important than the data", len(left) == 1, str(len(left)))
        check("and it is a good one", left[0].trustworthy)


def test_retention_does_nothing_when_no_copy_is_good() -> None:
    print("\nprune with nothing worth keeping")
    from stores import backup as backup_module

    with tempfile.TemporaryDirectory() as d:
        root = os.path.join(d, "backups", "brookline-ma")
        os.makedirs(root, exist_ok=True)
        for n in range(3):
            open(os.path.join(root, f"archive-2026-09-0{n}T00-00-00Z.sqlite3"),
                 "wb").write(b"not a database")

        gone = backup_module.prune("brookline-ma", os.path.join(d, "backups"), keep=1)
        check("nothing is deleted", gone == [], str(len(gone)))
        check("because pruning to a pile of broken files is data loss on a schedule",
              len(backup_module.list_snapshots(
                  "brookline-ma", os.path.join(d, "backups"))) == 3)
        listed = backup_module.list_snapshots("brookline-ma", os.path.join(d, "backups"))
        check("and a file with no manifest is reported as unverified",
              all(not s.verified for s in listed))
        check("saying so", all(s.notes for s in listed))


def test_postgres_is_sent_to_pg_dump_rather_than_half_handled() -> None:
    print("\nwhat backup says about the backend it should not touch")
    from stores import backup as backup_module

    saved = os.environ.get("COMMUNITY_DB_URL")
    os.environ["COMMUNITY_DB_URL"] = "postgresql://civic@db/civic"
    try:
        backup_module.archive_path_for("brookline-ma")
        refused, detail = False, "it tried"
    except backup_module.BackupError as exc:
        refused, detail = True, str(exc)
    finally:
        os.environ.pop("COMMUNITY_DB_URL", None)
        if saved is not None:
            os.environ["COMMUNITY_DB_URL"] = saved

    check("it refuses", refused)
    check("and hands over the command that does the job properly",
          "pg_dump" in detail, detail[:80])


def main() -> int:
    print("=" * 62)
    print("SQLite archive tests")
    print("=" * 62)
    for fn in [
        test_fts5_is_there,
        test_a_question_survives_becoming_a_match_expression,
        test_a_payload_survives_the_round_trip,
        test_vectors_pack_and_unpack,
        test_the_keyword_half_is_the_database_not_the_app,
        test_the_dense_half_ranks_by_similarity,
        test_hybrid_search_fuses_both_halves,
        test_filters_narrow_the_archive,
        test_deleting_a_source_reaches_the_keyword_index,
        test_overwriting_a_document_reaches_the_keyword_index,
        test_two_passages_of_one_meeting_that_open_alike_are_both_kept,
        test_vacuum_rebuilds_rather_than_corrupting,
        test_stats_tell_an_operator_where_the_archive_is,
        test_a_backup_is_a_working_archive,
        test_the_store_offers_what_the_application_calls,
        test_connection_strings_name_their_backend,
        test_the_default_is_a_local_file,
        test_build_store_opens_the_file_it_named,
        test_a_snapshot_is_taken_verified_and_described,
        test_an_empty_archive_is_not_a_good_copy,
        test_a_changed_snapshot_is_caught,
        test_a_broken_snapshot_is_never_restored_quietly,
        test_restoring_moves_the_current_archive_aside,
        test_retention_never_deletes_the_last_good_copy,
        test_retention_does_nothing_when_no_copy_is_good,
        test_postgres_is_sent_to_pg_dump_rather_than_half_handled,
    ]:
        fn()

    print("\n" + "=" * 62)
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    for name in FAIL:
        print(f"  FAILED: {name}")
    print("\nNot covered here: sqlite-vec, which is optional and not installed;")
    print("concurrent writers, which WAL handles and a single community does not")
    print("exercise; and the real embedding model, which is stubbed on purpose.")
    return 1 if FAIL else 0


def test_all() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
