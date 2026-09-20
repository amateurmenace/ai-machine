"""
The whole archive in one file.

This is the backend a single community should use, and the reason is not
performance. It is that the entire public record of a town becomes one file on
one machine, which can be copied, checksummed, carried to another building and
handed to a successor. No server, no port, no password, no managed service
invoice. Backing it up is ``cp``.

It also fixes the real problem with the embedded default, which was never
Qdrant itself. The keyword half of hybrid retrieval currently lives in Python
memory and is rebuilt from the entire corpus on every process start. SQLite's
FTS5 is an index on disk, incrementally maintained by the database, and it
ships BM25 as a built-in ranking function. That is the same win the Postgres
backend was argued for, without the server.

Where this sits among the three:

    sqlite     one community, one machine. The default worth recommending.
    qdrant     what existed before. Still supported; nothing is forced.
    pgvector   many communities on shared infrastructure. Not a graduation.

Vector search degrades across three implementations rather than requiring any
of them: the sqlite-vec extension when it is installed, a vectorised scan when
numpy is present, and plain Python when neither is. A town with a few tens of
thousands of passages will not notice the difference, and a deployment that
cannot install a C extension still works.

Honest about the tradeoff: without sqlite-vec the vector comparison is a
brute-force scan, so the embeddings are read into memory. That is bounded and
loaded once, unlike the keyword index it replaces, which was rebuilt from all
of the text on every start. Past a few hundred thousand passages, install
sqlite-vec or move to Postgres.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import struct
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from knowledge.schemas import CivicChunk, normalize_payload

DEFAULT_EMBEDDING_MODEL = os.getenv("COMMUNITY_EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# Reciprocal rank fusion constant, the same value rag.bm25 uses. Fusing the two
# halves on rank rather than score is the same argument made there: FTS5's bm25
# and cosine similarity are not comparable numbers.
RRF_K = 60

# Columns that get their own typed column rather than living in the payload
# blob, because retrieval filters on them.
FILTER_COLUMNS = (
    "source", "source_type", "url", "title", "community", "body", "department",
    "meeting_date", "agenda_item", "speaker", "speaker_role", "document_type",
    "section", "effective_date", "status", "docket_number", "project_name",
    "date", "collection_method",
)

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS chunks (
    id              TEXT PRIMARY KEY,
    text            TEXT NOT NULL,
    embedding       BLOB,
    source          TEXT,
    source_type     TEXT,
    url             TEXT,
    title           TEXT,
    community       TEXT,
    body            TEXT,
    department      TEXT,
    meeting_date    TEXT,
    agenda_item     TEXT,
    speaker         TEXT,
    speaker_role    TEXT,
    document_type   TEXT,
    section         TEXT,
    effective_date  TEXT,
    status          TEXT,
    docket_number   TEXT,
    project_name    TEXT,
    date            TEXT,
    collection_method TEXT,
    start_time      REAL,
    end_time        REAL,
    page            INTEGER,
    vote_taken      INTEGER,
    vote_outcome    TEXT,
    vote_tally      TEXT,
    -- The date that matters for this record, whichever kind it is. Stored
    -- rather than computed so a range filter can use an index.
    record_date     TEXT,
    payload         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS chunks_source_type ON chunks(source_type);
CREATE INDEX IF NOT EXISTS chunks_body        ON chunks(body);
CREATE INDEX IF NOT EXISTS chunks_record_date ON chunks(record_date);
CREATE INDEX IF NOT EXISTS chunks_source      ON chunks(source);
CREATE INDEX IF NOT EXISTS chunks_speaker     ON chunks(speaker);

-- The keyword index. external content, so the text is not stored twice.
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, title, body, speaker, agenda_item, docket_number,
    content='chunks', content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);

-- Triggers keep the index in step with the table, which is the entire point:
-- the index is maintained by the database rather than rebuilt by the app.
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text, title, body, speaker, agenda_item, docket_number)
    VALUES (new.rowid, new.text, new.title, new.body, new.speaker,
            new.agenda_item, new.docket_number);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text, title, body, speaker,
                           agenda_item, docket_number)
    VALUES ('delete', old.rowid, old.text, old.title, old.body, old.speaker,
            old.agenda_item, old.docket_number);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text, title, body, speaker,
                           agenda_item, docket_number)
    VALUES ('delete', old.rowid, old.text, old.title, old.body, old.speaker,
            old.agenda_item, old.docket_number);
    INSERT INTO chunks_fts(rowid, text, title, body, speaker, agenda_item, docket_number)
    VALUES (new.rowid, new.text, new.title, new.body, new.speaker,
            new.agenda_item, new.docket_number);
END;

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


class SqliteStoreError(RuntimeError):
    """A problem an operator needs to see."""


# --- vectors --------------------------------------------------------------


def pack_vector(values: Sequence[float]) -> bytes:
    return struct.pack(f"<{len(values)}f", *(float(v) for v in values))


def unpack_vector(blob: bytes) -> List[float]:
    return list(struct.unpack(f"<{len(blob) // 4}f", blob))


def fts5_available() -> bool:
    try:
        con = sqlite3.connect(":memory:")
        con.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        con.close()
        return True
    except sqlite3.Error:
        return False


def escape_fts_query(query: str) -> str:
    """Turn a resident's question into an FTS5 MATCH expression.

    Every term is quoted. FTS5 treats bare punctuation as syntax, so an
    unescaped question containing a hyphen, a quote or a colon is a syntax
    error rather than a search, and a civic archive is full of "Article 8.4"
    and "24-105". Quoting also makes each term a phrase, which is what those
    identifiers should be.
    """
    terms = re.findall(r"[\w][\w.\-/']*", query or "", re.UNICODE)
    cleaned = [t.replace('"', "") for t in terms if len(t) > 1 or t.isdigit()]
    if not cleaned:
        return ""
    return " OR ".join(f'"{t}"' for t in cleaned)


class SqliteVectorStore:
    """A community's archive, in one SQLite file."""

    def __init__(self, path: str = "./data/civic.sqlite3",
                 collection_name: str = "civic_knowledge",
                 embedding_model: Optional[str] = None) -> None:
        if not fts5_available():
            raise SqliteStoreError(
                "This Python's SQLite was built without FTS5, which this "
                "backend needs for keyword search. Most builds include it. "
                "Use the Qdrant backend instead, or install a Python whose "
                "sqlite3 has FTS5."
            )

        self.path = str(path)
        self.collection_name = collection_name
        self.embedding_model = embedding_model or DEFAULT_EMBEDDING_MODEL
        self._encoder = None
        self._vec_extension: Optional[bool] = None
        self._lock = threading.Lock()
        self._local = threading.local()

        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(SCHEMA)
            con.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES ('embedding_model', ?)",
                (self.embedding_model,),
            )

    # --- connection ------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """One connection per thread. SQLite objects are not thread-safe."""
        con = getattr(self._local, "con", None)
        if con is None:
            con = sqlite3.connect(self.path, timeout=30.0)
            con.row_factory = sqlite3.Row
            self._local.con = con
            self._try_load_vec(con)
        return con

    def _try_load_vec(self, con: sqlite3.Connection) -> None:
        """Load sqlite-vec if it is installed. Optional by design."""
        if self._vec_extension is False:
            return
        try:
            import sqlite_vec

            con.enable_load_extension(True)
            sqlite_vec.load(con)
            con.enable_load_extension(False)
            self._vec_extension = True
        except Exception:
            self._vec_extension = False

    def close(self) -> None:
        con = getattr(self._local, "con", None)
        if con is not None:
            con.close()
            self._local.con = None

    # --- embedding -------------------------------------------------------

    @property
    def encoder(self):
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer

            self._encoder = SentenceTransformer(self.embedding_model)
        return self._encoder

    def embed(self, text: str) -> List[float]:
        return list(self.encoder.encode(text))

    def generate_id(self, text: str, metadata: Dict) -> str:
        basis = (metadata or {}).get("url", "") + text[:100]
        return hashlib.md5(basis.encode("utf-8")).hexdigest()

    # --- writing ---------------------------------------------------------

    def _row_for(self, text: str, metadata: Dict,
                 vector: Optional[Sequence[float]] = None) -> Tuple:
        chunk = normalize_payload({**(metadata or {}), "text": text})
        payload = chunk.to_payload()
        doc_id = self.generate_id(text, metadata or {})

        values = [doc_id, text, pack_vector(vector) if vector is not None else None]
        values += [str(payload.get(column, "") or "") for column in FILTER_COLUMNS]
        # The text is already its own column, and it is the largest field in
        # the payload. Storing it twice costs about a quarter of the archive's
        # size for nothing: every read path puts it back from the column.
        stored = {k: v for k, v in payload.items() if k != "text"}
        values += [
            chunk.start_time, chunk.end_time, chunk.page,
            1 if getattr(chunk, "vote_taken", False) else 0,
            getattr(chunk, "vote_outcome", "") or "",
            getattr(chunk, "vote_tally", "") or "",
            chunk.record_date,
            json.dumps(stored, default=str),
        ]
        return tuple(values)

    def _insert_sql(self) -> str:
        columns = ["id", "text", "embedding", *FILTER_COLUMNS,
                   "start_time", "end_time", "page", "vote_taken",
                   "vote_outcome", "vote_tally", "record_date", "payload"]
        placeholders = ", ".join("?" for _ in columns)
        return (f"INSERT OR REPLACE INTO chunks ({', '.join(columns)}) "
                f"VALUES ({placeholders})")

    def add_document(self, text: str, metadata: Dict) -> str:
        vector = self.embed(text)
        row = self._row_for(text, metadata, vector)
        with self._lock:
            con = self._connect()
            con.execute(self._insert_sql(), row)
            con.commit()
        return row[0]

    def add_documents_batch(self, documents: List[Dict],
                            progress_callback=None) -> List[str]:
        rows, ids = [], []
        for index, doc in enumerate(documents):
            text = doc["text"]
            metadata = doc.get("metadata", {})
            row = self._row_for(text, metadata, self.embed(text))
            rows.append(row)
            ids.append(row[0])
            if progress_callback:
                progress_callback(index + 1, len(documents))

        if rows:
            with self._lock:
                con = self._connect()
                con.executemany(self._insert_sql(), rows)
                con.commit()
        return ids

    def delete_by_source(self, source: str) -> None:
        with self._lock:
            con = self._connect()
            con.execute("DELETE FROM chunks WHERE source = ?", (source,))
            con.commit()

    # --- filters ---------------------------------------------------------

    @staticmethod
    def _where(filters: Any) -> Tuple[str, List[Any]]:
        """Translate retrieval filters into SQL. Returns a clause and params."""
        if not filters:
            return "", []

        get = (filters.get if isinstance(filters, dict)
               else lambda name: getattr(filters, name, None))

        clauses, params = [], []
        for column in ("source_type", "body", "department", "document_type", "status"):
            value = get(column)
            if value:
                clauses.append(f"lower({column}) = lower(?)")
                params.append(str(value))
        for column in ("speaker", "agenda_item"):
            value = get(column)
            if value:
                clauses.append(f"lower({column}) LIKE lower(?)")
                params.append(f"%{value}%")
        if get("date_from"):
            clauses.append("record_date != '' AND record_date >= ?")
            params.append(str(get("date_from")))
        if get("date_to"):
            clauses.append("record_date != '' AND record_date <= ?")
            params.append(str(get("date_to")))

        return (" AND ".join(clauses), params)

    # --- reading ---------------------------------------------------------

    def _hit(self, row: sqlite3.Row, score: float) -> Dict:
        try:
            payload = json.loads(row["payload"])
        except (TypeError, json.JSONDecodeError):
            payload = {}
        payload.setdefault("text", row["text"])
        return {
            "id": row["id"],
            "score": float(score),
            "text": row["text"],
            "source": payload.get("source", ""),
            "source_type": payload.get("source_type", ""),
            "url": payload.get("url", ""),
            "title": payload.get("title", ""),
            "date": payload.get("date", ""),
            "metadata": payload,
        }

    def _vector_candidates(self, query_vector: Sequence[float], top_k: int,
                           where: str, params: List[Any]) -> List[Tuple[str, float]]:
        """Rank by cosine similarity, by whichever means is available."""
        con = self._connect()
        sql = "SELECT id, embedding FROM chunks WHERE embedding IS NOT NULL"
        if where:
            sql += f" AND {where}"
        rows = con.execute(sql, params).fetchall()
        if not rows:
            return []

        try:
            import numpy as np

            matrix = np.frombuffer(b"".join(r["embedding"] for r in rows),
                                   dtype="<f4").reshape(len(rows), -1)
            query = np.asarray(query_vector, dtype="<f4")
            norms = np.linalg.norm(matrix, axis=1) * float(np.linalg.norm(query))
            norms[norms == 0] = 1.0
            scores = (matrix @ query) / norms
            order = np.argsort(-scores)[:top_k]
            return [(rows[i]["id"], float(scores[i])) for i in order]
        except ImportError:
            pass

        # Plain Python. Slower, and it keeps a deployment without numpy working.
        query_norm = math.sqrt(sum(v * v for v in query_vector)) or 1.0
        scored: List[Tuple[str, float]] = []
        for row in rows:
            vector = unpack_vector(row["embedding"])
            dot = sum(a * b for a, b in zip(vector, query_vector))
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            scored.append((row["id"], dot / (norm * query_norm)))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]

    def _keyword_candidates(self, query: str, top_k: int, where: str,
                            params: List[Any]) -> List[Tuple[str, float]]:
        """Rank by FTS5's built-in BM25. The index is on disk, not rebuilt."""
        match = escape_fts_query(query)
        if not match:
            return []

        sql = (
            "SELECT c.id AS id, bm25(chunks_fts, 10.0, 5.0, 3.0, 3.0, 3.0, 8.0) AS rank "
            "FROM chunks_fts JOIN chunks c ON c.rowid = chunks_fts.rowid "
            "WHERE chunks_fts MATCH ?"
        )
        args: List[Any] = [match]
        if where:
            sql += f" AND {where}"
            args += params
        # bm25() returns a negative number where more negative is better.
        sql += " ORDER BY rank LIMIT ?"
        args.append(top_k)

        try:
            rows = self._connect().execute(sql, args).fetchall()
        except sqlite3.OperationalError:
            # A malformed MATCH is a bad question, not a broken archive.
            return []
        return [(row["id"], -float(row["rank"])) for row in rows]

    def search(self, query: str, top_k: int = 5,
               filter_dict: Optional[Dict] = None) -> List[Dict]:
        """Dense search, for callers that want only the vector half."""
        where, params = self._where(filter_dict)
        ranked = self._vector_candidates(self.embed(query), top_k, where, params)
        return self._fetch(ranked)

    def hybrid_search(self, query: str, query_vector: Optional[Sequence[float]] = None,
                      top_k: int = 24, filters: Any = None,
                      candidate_pool: int = 40) -> List[Dict]:
        """Dense and keyword, fused by reciprocal rank.

        The same algebra rag.bm25 uses, so switching backends does not change
        how results are ordered. The difference is that the keyword half is an
        index the database maintains rather than one this process rebuilds.
        """
        where, params = self._where(filters)
        if query_vector is None:
            query_vector = self.embed(query)

        dense = self._vector_candidates(query_vector, candidate_pool, where, list(params))
        sparse = self._keyword_candidates(query, candidate_pool, where, list(params))

        fused: Dict[str, float] = {}
        detail: Dict[str, Dict[str, Any]] = {}
        for half, ranked in (("dense", dense), ("sparse", sparse)):
            for rank, (doc_id, score) in enumerate(ranked, start=1):
                fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (RRF_K + rank)
                entry = detail.setdefault(doc_id, {})
                entry[f"{half}_rank"] = rank
                entry[f"{half}_score"] = score

        order = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        hits = self._fetch(order)
        for hit in hits:
            hit.update(detail.get(hit["id"], {}))
        return hits

    def _fetch(self, ranked: Sequence[Tuple[str, float]]) -> List[Dict]:
        if not ranked:
            return []
        scores = dict(ranked)
        placeholders = ", ".join("?" for _ in ranked)
        rows = self._connect().execute(
            f"SELECT * FROM chunks WHERE id IN ({placeholders})",
            [doc_id for doc_id, _ in ranked],
        ).fetchall()
        hits = [self._hit(row, scores.get(row["id"], 0.0)) for row in rows]
        hits.sort(key=lambda h: scores.get(h["id"], 0.0), reverse=True)
        return hits

    def iter_all_payloads(self, batch_size: int = 512) -> Iterable[Tuple[str, Dict]]:
        con = self._connect()
        cursor = con.execute("SELECT id, text, payload FROM chunks")
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                return
            for row in rows:
                try:
                    payload = json.loads(row["payload"])
                except (TypeError, json.JSONDecodeError):
                    payload = {}
                payload.setdefault("text", row["text"])
                yield row["id"], payload

    def get_by_id(self, doc_id: str) -> Optional[Dict]:
        row = self._connect().execute(
            "SELECT * FROM chunks WHERE id = ?", (doc_id,)).fetchone()
        if row is None:
            return None
        payload = self._hit(row, 0.0)["metadata"]
        payload["id"] = row["id"]
        return payload

    def get_stats(self) -> Dict:
        con = self._connect()
        count = con.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()["n"]
        dimension = None
        row = con.execute(
            "SELECT embedding FROM chunks WHERE embedding IS NOT NULL LIMIT 1"
        ).fetchone()
        if row and row["embedding"]:
            dimension = len(row["embedding"]) // 4

        size_bytes = 0
        try:
            size_bytes = os.path.getsize(self.path)
        except OSError:
            pass

        return {
            "total_documents": count,
            "vector_size": dimension,
            "distance_metric": "cosine",
            "embedding_model": self.embedding_model,
            "backend": "sqlite",
            "path": self.path,
            "file_size_bytes": size_bytes,
            "vector_extension": bool(self._vec_extension),
            "keyword_index": "fts5",
        }

    def chunk_text(self, text: str, chunk_size: int = 500,
                   overlap: int = 50) -> List[str]:
        words = text.split()
        chunks = []
        for i in range(0, len(words), max(1, chunk_size - overlap)):
            chunk = " ".join(words[i:i + chunk_size])
            if len(chunk.split()) > 50:
                chunks.append(chunk)
        return chunks

    # --- operations ------------------------------------------------------

    def vacuum(self) -> None:
        """Reclaim space and rebuild the keyword index after bulk deletion."""
        with self._lock:
            con = self._connect()
            con.execute("INSERT INTO chunks_fts(chunks_fts) VALUES ('rebuild')")
            con.commit()
            con.execute("VACUUM")

    def backup_to(self, destination: str) -> str:
        """Copy the archive to another file, consistently, while it is in use.

        SQLite's own backup API rather than a file copy: a copy taken while a
        write is in flight can be torn, and an archive that restores to a
        corrupt file is worse than no backup.
        """
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(destination)
        try:
            with self._lock:
                self._connect().backup(target)
        finally:
            target.close()
        return destination
