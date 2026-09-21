"""
The community archive in PostgreSQL, with pgvector.

ROADMAP.md section 2.3 makes the case: Postgres does not replace one component
here, it replaces three. Qdrant's vectors become a `vector` column with an HNSW
index. The Python metadata filtering becomes a WHERE clause over typed columns.
And the in-memory BM25 index becomes a `tsvector` the database maintains.

That third one is the reason this module exists. The keyword index is rebuilt
per process today, which pins the app to a single instance, costs a cold-start
rebuild, and caps a community's corpus at 200,000 chunks. A GIN index on disk
has none of those properties, which is what makes Cloud Run and multi-community
hosting possible at all.

:class:`PgVectorStore` implements the same interface as
:class:`vector_store.VectorStore`, so :class:`rag.hybrid.HybridRetriever`, the
agent, the gateway and the evals are unchanged. It adds one method they do not
have, ``hybrid_search``, which runs both halves of retrieval and the reciprocal
rank fusion in one query where the data already is.

Three decisions worth knowing about:

**The store never creates its own schema.** Qdrant's client creates a collection
on first use because it is a file in a folder. Creating a table is a migration,
and the role a Cloud Run instance connects as should not hold DDL rights on a
town's public record. `python3 -m stores.migrate` does it, once, deliberately.

**Vectors travel as text.** pgvector accepts `'[0.1,0.2]'::vector`, so this
needs no binary adapter and therefore no `pgvector` Python package. One fewer
optional dependency between a community and its own archive.

**A missing driver is loud, not quiet.** psycopg is optional the way
sentence-transformers is optional in rag/reranker.py, but the remedy is
different. A missing reranker costs a slightly worse ordering, so that degrades
silently and reports itself. A missing database driver means there is no
archive at all, and answering "I have no record of that" to every resident
would be a worse failure than an error an operator can see and fix. So the
failure is an exception carrying the install command, and ``pgvector_status()``
lets a health check surface it before a resident ever asks.
"""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from knowledge.schemas import normalize_payload
from stores.ids import passage_id

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# The token stores/schema.sql carries in place of the vector width, because a
# pgvector column has a fixed size and 384 (all-MiniLM-L6-v2) and 1024
# (BAAI/bge-m3) are both real deployments.
DIMENSION_TOKEN = "{{VECTOR_DIMENSION}}"
DEFAULT_VECTOR_DIMENSION = 384

# Must match the configuration named in the generated tsv column in schema.sql.
# A query using a different one silently matches nothing, so this is a constant
# rather than a setting: changing it means rebuilding the column.
TEXT_SEARCH_CONFIG = "english"

# The damping constant from the reciprocal rank fusion paper, and the same
# value rag/bm25.py uses, so the two retrieval paths rank alike.
RRF_K = 60

DEFAULT_CANDIDATE_POOL = 40

# How many connections one process may hold. Cloud SQL counts connections
# against a per-instance limit that several Cloud Run instances share, so the
# default is deliberately small: a town's traffic is answered by concurrency in
# the model, not in the database.
POOL_MAX_SIZE = int(os.getenv("COMMUNITY_DB_POOL_MAX", "4"))

# Every CivicChunk field, paired with the identifier it takes in the table.
# "text" and "date" are quoted because both are also type names; the column
# names match the payload keys so the round trip has no renaming step.
COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("text", '"text"'),
    ("source", "source"),
    ("source_type", "source_type"),
    ("url", "url"),
    ("title", "title"),
    ("community", "community"),
    ("body", "body"),
    ("department", "department"),
    ("meeting_date", "meeting_date"),
    ("agenda_item", "agenda_item"),
    ("speaker", "speaker"),
    ("speaker_role", "speaker_role"),
    ("start_time", "start_time"),
    ("end_time", "end_time"),
    ("video_url", "video_url"),
    ("document_type", "document_type"),
    ("page", "page"),
    ("section", "section"),
    ("effective_date", "effective_date"),
    ("status", "status"),
    ("status_confidence", "status_confidence"),
    ("vote_taken", "vote_taken"),
    ("vote_outcome", "vote_outcome"),
    ("vote_tally", "vote_tally"),
    ("status_evidence", "status_evidence"),
    ("docket_number", "docket_number"),
    ("project_name", "project_name"),
    ("address", "address"),
    ("geography", "geography"),
    ("collection_method", "collection_method"),
    ("ingested_at", "ingested_at"),
    ("date", '"date"'),
)

COLUMN_KEYS = frozenset(key for key, _identifier in COLUMNS)

DATE_COLUMNS = frozenset({"meeting_date", "effective_date", "ingested_at", "date"})
INTEGER_COLUMNS = frozenset({"page"})
FLOAT_COLUMNS = frozenset({"start_time", "end_time", "status_confidence"})
BOOLEAN_COLUMNS = frozenset({"vote_taken"})

# The filters rag.hybrid.RetrievalFilters carries, in the order they are applied.
FILTER_FIELDS = (
    "source_type", "body", "department", "speaker", "document_type",
    "status", "agenda_item", "date_from", "date_to",
)

# Filters compared for equality, case-insensitively, matching
# RetrievalFilters.matches(). Speaker and agenda item are substring matches
# there, so they become ILIKE here.
EXACT_FILTERS = ("source_type", "body", "department", "document_type", "status")
CONTAINS_FILTERS = ("speaker", "agenda_item")


class PgVectorUnavailable(RuntimeError):
    """The Postgres archive cannot be reached, with the remedy in the message."""


class EmbeddingDimensionMismatch(RuntimeError):
    """The configured embedding model does not fit the column it would write to."""


# --- the driver, which is optional ----------------------------------------


_driver: Dict[str, Any] = {}
_driver_error: Optional[str] = None
_driver_lock = threading.Lock()

_INSTALL_HINT = (
    "Install it with:  pip install 'psycopg[binary,pool]'\n"
    "Or unset COMMUNITY_DB_URL to keep using the embedded Qdrant archive."
)


def _load_driver() -> Optional[Dict[str, Any]]:
    """Import psycopg once, remembering failure so the attempt is not repeated."""
    global _driver_error
    with _driver_lock:
        if _driver:
            return _driver
        if _driver_error is not None:
            return None

        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            _driver_error = (
                f"psycopg (v3) is not installed, so the PostgreSQL archive "
                f"cannot be opened ({exc}).\n{_INSTALL_HINT}"
            )
            return None

        try:
            from psycopg_pool import ConnectionPool
        except ImportError as exc:
            _driver_error = (
                f"psycopg is installed but its connection pool is not "
                f"({exc}).\n{_INSTALL_HINT}"
            )
            return None

        _driver.update({
            "psycopg": psycopg,
            "dict_row": dict_row,
            "ConnectionPool": ConnectionPool,
        })
        return _driver


def pgvector_status() -> Dict[str, Any]:
    """Report whether the Postgres backend can run, for a health endpoint.

    Shaped like ``rag.reranker.rerank_status()`` so an operator reads the two
    the same way.
    """
    driver = _load_driver()
    return {
        "enabled": driver is not None,
        "driver": "psycopg3" if driver is not None else None,
        "reason": None if driver is not None else _driver_error,
    }


def require_driver() -> Dict[str, Any]:
    driver = _load_driver()
    if driver is None:
        raise PgVectorUnavailable(_driver_error or "psycopg is unavailable")
    return driver


_pools: Dict[str, Any] = {}
_pool_lock = threading.Lock()


def connection_pool(dsn: str):
    """One pool per DSN, shared by every project on that database.

    Several communities on one Cloud SQL instance is the point of section 3.1,
    and giving each of them its own pool would multiply the connection count by
    the number of towns.
    """
    driver = require_driver()
    with _pool_lock:
        pool = _pools.get(dsn)
        if pool is None:
            # The pool is not waited on: a database that is briefly unreachable
            # should not stop the process from starting and reporting why.
            pool = driver["ConnectionPool"](
                dsn, min_size=1, max_size=POOL_MAX_SIZE, open=True
            )
            _pools[dsn] = pool
        return pool


# --- embedding width ------------------------------------------------------


def _embedding_defaults() -> Tuple[str, Dict[str, int]]:
    """The model name and the model-to-dimension table, from vector_store.

    Imported here rather than at module scope because that module pulls in
    qdrant-client, and a community that has finished the migration should be
    able to drop it from requirements.txt. The table itself is not duplicated:
    two copies of it is how a 384-wide column ends up holding 1024-wide vectors.
    """
    try:
        from vector_store import DEFAULT_EMBEDDING_MODEL, EMBEDDING_MODELS
        return DEFAULT_EMBEDDING_MODEL, dict(EMBEDDING_MODELS)
    except Exception:
        return os.getenv("COMMUNITY_EMBEDDING_MODEL", "all-MiniLM-L6-v2"), {}


def default_embedding_model() -> str:
    return _embedding_defaults()[0]


def embedding_dimension(model_name: str,
                        default: int = DEFAULT_VECTOR_DIMENSION) -> int:
    """How wide a vector this embedding model produces."""
    return _embedding_defaults()[1].get(model_name, default)


def parse_declared_dimension(declared: str) -> Optional[int]:
    """Pull the width out of a column type such as ``vector(1024)``."""
    match = re.search(r"\((\d+)\)", declared or "")
    return int(match.group(1)) if match else None


def dimension_mismatch_message(declared: int, configured: int, model: str) -> str:
    """What an operator needs to read when the model and the column disagree."""
    return (
        f"The chunks.embedding column holds {declared}-dimensional vectors, but "
        f"the configured embedding model '{model}' produces {configured}. "
        f"Changing embedding models requires re-indexing the corpus. Either set "
        f"COMMUNITY_EMBEDDING_MODEL back to the previous model, or create a "
        f"fresh database with "
        f"`python3 -m stores.migrate --dimension {configured}` and re-ingest. "
        f"See COMMUNITY_AI_SETUP.md, 'Switching embedding models'."
    )


# --- schema ---------------------------------------------------------------


def render_schema(dimension: int = DEFAULT_VECTOR_DIMENSION) -> str:
    """Read stores/schema.sql with the vector width filled in."""
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    return sql.replace(DIMENSION_TOKEN, str(int(dimension)))


# --- rows and payloads ----------------------------------------------------


def vector_literal(values: Sequence[float]) -> str:
    """pgvector's own text form, so no binary adapter is needed."""
    return "[" + ",".join(f"{float(v):.7g}" for v in values) + "]"


def _as_date(value: Any) -> Optional[date]:
    """Coerce a stored date string to a real date, or None.

    Parameters bound to a date column have to be date objects; a string is sent
    as text and Postgres refuses the assignment. CivicChunk has already
    normalized these to YYYY-MM-DD, so anything that still fails to parse is
    data this schema cannot represent and is dropped rather than guessed at.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def payload_to_row(payload: Dict[str, Any], project_id: str,
                   chunk_id: str) -> Dict[str, Any]:
    """Turn a stored payload into the columns of one row.

    Normalization happens here rather than at read time because a typed column
    cannot hold "4/14/2026". :func:`knowledge.schemas.normalize_payload` is the
    same mapping the retriever applies to Qdrant payloads, so an already
    ingested corpus and a freshly ingested one land in the same shape.

    Anything the collectors recorded that has no column of its own goes to the
    jsonb payload instead of being thrown away.
    """
    chunk = normalize_payload(payload)

    row: Dict[str, Any] = {"project_id": project_id, "id": chunk_id}
    for key, _identifier in COLUMNS:
        value = getattr(chunk, key, None)
        if key in DATE_COLUMNS:
            row[key] = _as_date(value)
        elif key in INTEGER_COLUMNS:
            row[key] = _as_int(value)
        elif key in FLOAT_COLUMNS:
            # None, not 0.0: a document has no start time, and a passage
            # claiming to begin at second zero of a video is a wrong citation.
            row[key] = _as_float(value)
        elif key in BOOLEAN_COLUMNS:
            row[key] = bool(value)
        else:
            row[key] = "" if value is None else str(value)

    # Everything without a column of its own, which includes any CivicChunk
    # field added after this schema was written. Keying on the columns rather
    # than on the dataclass means a new field lands in jsonb and is still
    # readable, instead of being dropped until someone notices.
    extras = {
        key: value
        for key, value in payload.items()
        if key not in COLUMN_KEYS and key not in ("id", "word_count")
    }
    row["payload"] = json.dumps(extras, default=str)
    return row


def row_to_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    """Turn one row back into the payload shape the rest of the app expects.

    Empty columns are dropped rather than returned as "", matching
    :meth:`CivicChunk.to_payload`, so a chunk that was never given a speaker
    does not arrive claiming to have an empty one.
    """
    raw_extras = row.get("payload") or {}
    if isinstance(raw_extras, str):
        try:
            raw_extras = json.loads(raw_extras)
        except ValueError:
            raw_extras = {}
    payload: Dict[str, Any] = dict(raw_extras)

    for key, _identifier in COLUMNS:
        value = row.get(key)
        if value is None or value == "":
            continue
        if key in DATE_COLUMNS:
            payload[key] = value.isoformat() if isinstance(value, (date, datetime)) else str(value)
        elif key in INTEGER_COLUMNS:
            payload[key] = int(value)
        elif key in FLOAT_COLUMNS:
            payload[key] = float(value)
        elif key in BOOLEAN_COLUMNS:
            payload[key] = bool(value)
        else:
            payload[key] = value

    payload["text"] = row.get("text") or ""
    payload["word_count"] = len(payload["text"].split())
    if row.get("id") is not None:
        payload["id"] = str(row["id"])
    return payload


# --- filters --------------------------------------------------------------


def filter_values(filters: Any) -> Dict[str, str]:
    """Read a RetrievalFilters, a plain dict, or nothing into a flat mapping."""
    if not filters:
        return {}
    if isinstance(filters, dict):
        raw = filters
    else:
        raw = {name: getattr(filters, name, None) for name in FILTER_FIELDS}
    return {
        name: str(value).strip()
        for name, value in raw.items()
        if name in FILTER_FIELDS and value not in (None, "")
    }


def _ilike_pattern(value: str) -> str:
    """Escape a value used as a substring match.

    A speaker recorded as "A_B" must not match "AxB": in LIKE, `_` is a
    wildcard. The backslash is LIKE's default escape character.
    """
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def where_clauses(filters: Any) -> Tuple[List[str], Dict[str, Any]]:
    """Translate civic filters into SQL fragments and their bound parameters.

    The translation mirrors :meth:`rag.hybrid.RetrievalFilters.matches` on
    purpose, so moving a community to Postgres does not quietly change which
    passages a filtered question returns. Equality is case-insensitive, speaker
    and agenda item are substring matches, and a date range compares against
    the generated ``record_date`` column. A record with no usable date compares
    NULL and is excluded, which is the same judgment the Python path makes.
    """
    values = filter_values(filters)
    clauses: List[str] = []
    params: Dict[str, Any] = {}

    for name in EXACT_FILTERS:
        if name in values:
            clauses.append(f"lower({name}) = lower(%(f_{name})s)")
            params[f"f_{name}"] = values[name]

    for name in CONTAINS_FILTERS:
        if name in values:
            clauses.append(f"{name} ILIKE %(f_{name})s")
            params[f"f_{name}"] = _ilike_pattern(values[name])

    if "date_from" in values:
        clauses.append("record_date >= %(f_date_from)s")
        params["f_date_from"] = _as_date(values["date_from"])
    if "date_to" in values:
        clauses.append("record_date <= %(f_date_to)s")
        params["f_date_to"] = _as_date(values["date_to"])

    return clauses, params


def _and(clauses: Sequence[str], indent: int) -> str:
    """Render filter clauses as a suffix to an existing WHERE.

    Indented to line up under it, because these statements end up in slow query
    logs and an operator reading one should be able to see the shape.
    """
    pad = " " * indent
    return "".join(f"\n{pad}AND {clause}" for clause in clauses)


# --- statements -----------------------------------------------------------


def _wrap(parts: Sequence[str], indent: int, width: int = 62) -> str:
    """Join a long list of column names so the statement stays readable.

    These statements end up in slow query logs and in operator tickets, and a
    thirty-column SELECT on one line is not something anybody reads.
    """
    lines: List[str] = []
    current = ""
    for part in parts:
        candidate = f"{current}{part}, "
        if len(candidate) > width and current:
            lines.append(current.rstrip())
            current = f"{part}, "
        else:
            current = candidate
    lines.append(current.rstrip().rstrip(","))
    return f"\n{' ' * indent}".join(lines)


def _selected_columns(prefix: str = "", indent: int = 15) -> str:
    dot = f"{prefix}." if prefix else ""
    return _wrap([f"{dot}{identifier}" for _key, identifier in COLUMNS], indent)


def hybrid_sql(project_id: str, query: str, query_vector: Sequence[float],
               top_k: int = 24, filters: Any = None,
               candidate_pool: int = DEFAULT_CANDIDATE_POOL
               ) -> Tuple[str, Dict[str, Any]]:
    """The whole of hybrid retrieval, as one statement.

    This is the query from ROADMAP.md section 2.3: a dense ranking by cosine
    distance, a sparse ranking by ts_rank_cd, fused by summing 1/(60 + rank).
    It is the same reciprocal rank fusion :func:`rag.bm25.reciprocal_rank_fusion`
    performs, executed where the data lives, which is what lets the keyword
    index stop being a per-process object.

    One deliberate difference from the sketch in the roadmap. There the window
    function is computed in the same SELECT that carries the LIMIT, which makes
    Postgres rank every matching row in the community's corpus before taking
    forty of them, and an HNSW index cannot help with that. Ranking inside a
    subquery that is already limited produces the identical ordering and lets
    the index do its job.

    ``websearch_to_tsquery`` rather than ``to_tsquery`` because a resident's
    question is not tsquery syntax. It accepts quoted phrases, OR and a leading
    minus, and it never raises on input it cannot parse, which matters on a
    path that must not turn a question into an error.
    """
    clauses, params = where_clauses(filters)
    filter_sql = _and(clauses, indent=18)

    params.update({
        "project": project_id,
        "q": query,
        "q_vec": vector_literal(query_vector),
        "pool": int(candidate_pool),
        "top_k": int(top_k),
    })

    sql = f"""
        WITH dense AS (
            SELECT id, RANK() OVER (ORDER BY distance) AS rank,
                   'dense' AS half, 1 - distance AS half_score
            FROM (
                SELECT id, embedding <=> %(q_vec)s::vector AS distance
                FROM chunks
                WHERE project_id = %(project)s{filter_sql}
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> %(q_vec)s::vector
                LIMIT %(pool)s
            ) dense_pool
        ),
        sparse AS (
            SELECT id, RANK() OVER (ORDER BY relevance DESC) AS rank,
                   'sparse' AS half, relevance AS half_score
            FROM (
                SELECT id,
                       ts_rank_cd(tsv, websearch_to_tsquery('{TEXT_SEARCH_CONFIG}', %(q)s)) AS relevance
                FROM chunks
                WHERE project_id = %(project)s{filter_sql}
                  AND tsv @@ websearch_to_tsquery('{TEXT_SEARCH_CONFIG}', %(q)s)
                ORDER BY relevance DESC
                LIMIT %(pool)s
            ) sparse_pool
        ),
        fused AS (
            SELECT id,
                   SUM(1.0 / ({RRF_K} + rank)) AS score,
                   MIN(rank) FILTER (WHERE half = 'dense') AS dense_rank,
                   MIN(rank) FILTER (WHERE half = 'sparse') AS sparse_rank,
                   MAX(half_score) FILTER (WHERE half = 'dense') AS dense_score,
                   MAX(half_score) FILTER (WHERE half = 'sparse') AS sparse_score
            FROM (SELECT * FROM dense UNION ALL SELECT * FROM sparse) both_halves
            GROUP BY id
        )
        SELECT c.id, f.score, f.dense_rank, f.sparse_rank,
               f.dense_score, f.sparse_score,
               {_selected_columns('c')}, c.payload
        FROM fused f
        JOIN chunks c ON c.project_id = %(project)s AND c.id = f.id
        ORDER BY f.score DESC, c.id
        LIMIT %(top_k)s
    """
    return sql, params


def search_sql(project_id: str, query_vector: Sequence[float], top_k: int = 5,
               filters: Any = None) -> Tuple[str, Dict[str, Any]]:
    """Dense search alone, for the VectorStore-compatible ``search``.

    ``<=>`` is cosine distance and Qdrant reports cosine similarity, so the
    score is subtracted from one. The transparency panel prints this number,
    and two backends disagreeing about what 0.9 means would be worse than
    either convention.
    """
    clauses, params = where_clauses(filters)
    params.update({
        "project": project_id,
        "q_vec": vector_literal(query_vector),
        "top_k": int(top_k),
    })

    sql = f"""
        SELECT id, 1 - (embedding <=> %(q_vec)s::vector) AS score,
               {_selected_columns()}, payload
        FROM chunks
        WHERE project_id = %(project)s{_and(clauses, indent=14)}
              AND embedding IS NOT NULL
        ORDER BY embedding <=> %(q_vec)s::vector
        LIMIT %(top_k)s
    """
    return sql, params


def upsert_sql() -> str:
    """Write one chunk, replacing any earlier version of it.

    Chunk ids are deterministic, so re-ingesting a source has to update rather
    than duplicate. It is also what makes `stores.migrate` safe to re-run after
    an interrupted copy.
    """
    identifiers = _wrap([identifier for _key, identifier in COLUMNS], indent=16)
    placeholders = _wrap([f"%({key})s" for key, _identifier in COLUMNS], indent=16)
    updates = ",\n                ".join(
        f"{identifier} = EXCLUDED.{identifier}" for _key, identifier in COLUMNS
    )
    return f"""
        INSERT INTO chunks (
                project_id, id, embedding,
                {identifiers},
                payload)
        VALUES (
                %(project_id)s, %(id)s, %(embedding)s::vector,
                {placeholders},
                %(payload)s::jsonb)
        ON CONFLICT (project_id, id) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                {updates},
                payload = EXCLUDED.payload
    """


def page_sql() -> str:
    """One page of the corpus, by keyset rather than OFFSET.

    OFFSET re-scans everything it skips, so walking a decade of meetings would
    get slower with every page.
    """
    return f"""
        SELECT id, {_selected_columns(indent=19)}, payload
        FROM chunks
        WHERE project_id = %(project)s AND id > %(after)s
        ORDER BY id
        LIMIT %(batch)s
    """


def by_id_sql() -> str:
    return f"""
        SELECT id, {_selected_columns(indent=19)}, payload
        FROM chunks
        WHERE project_id = %(project)s AND id = %(id)s
    """


def stats_sql() -> str:
    return """
        SELECT count(*) AS total_documents
        FROM chunks
        WHERE project_id = %(project)s
    """


def ids_sql() -> str:
    return """
        SELECT id
        FROM chunks
        WHERE project_id = %(project)s
    """


def delete_by_source_sql() -> str:
    return """
        DELETE FROM chunks
        WHERE project_id = %(project)s AND source = %(source)s
    """


def declared_dimension_sql() -> str:
    return """
        SELECT format_type(atttypid, atttypmod) AS declared
        FROM pg_attribute
        WHERE attrelid = to_regclass('chunks') AND attname = 'embedding'
    """


# --- the store ------------------------------------------------------------


class PgVectorStore:
    """One community's archive, in one Postgres table shared by all of them.

    ``collection_name`` is the project id, and it is the ``project_id`` column
    on every row. Nothing here ever queries without it.
    """

    def __init__(self, dsn: str, collection_name: str = "civic_knowledge",
                 embedding_model: Optional[str] = None,
                 vector_dimension: Optional[int] = None):
        self.dsn = dsn
        self.collection_name = collection_name
        self.project_id = collection_name
        self.embedding_model = embedding_model or default_embedding_model()
        self.vector_size = vector_dimension or embedding_dimension(self.embedding_model)

        # Raises PgVectorUnavailable with the install command if psycopg is
        # missing, which is the point at which an operator finds out.
        self.pool = connection_pool(dsn)

        # Loaded on first use rather than here: /stats, source inspection, the
        # corpus walk and a hybrid search whose caller supplied the vector all
        # run without it, and loading a sentence-transformer is the slowest
        # part of a Cloud Run cold start.
        self._encoder: Any = None
        self._encoder_lock = threading.Lock()

    # --- plumbing ---------------------------------------------------------

    def _rows(self, sql: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        driver = require_driver()
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=driver["dict_row"]) as cur:
                cur.execute(sql, params)
                return list(cur.fetchall())

    def _execute(self, sql: str, params: Any, many: bool = False) -> None:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                if many:
                    cur.executemany(sql, params)
                else:
                    cur.execute(sql, params)

    @property
    def encoder(self):
        with self._encoder_lock:
            if self._encoder is None:
                try:
                    from sentence_transformers import SentenceTransformer
                except ImportError as exc:
                    raise PgVectorUnavailable(
                        f"sentence-transformers is not installed, so questions "
                        f"cannot be embedded ({exc}). Install it with: "
                        f"pip install sentence-transformers"
                    ) from exc
                self._encoder = SentenceTransformer(self.embedding_model)
            return self._encoder

    def embed(self, text: str) -> List[float]:
        return self.encoder.encode(text).tolist()

    def generate_id(self, text: str, metadata: Dict) -> str:
        """The same id VectorStore would give this chunk.

        Kept identical on purpose: a corpus copied from Qdrant and one
        re-ingested through this store have to agree on ids, or a re-ingestion
        after a migration silently doubles the archive.
        """
        return passage_id(text, metadata)

    # --- schema -----------------------------------------------------------

    def ensure_schema(self) -> None:
        """Create the table and indexes. Called by the migration, not by a request.

        The whole file goes in one call, which psycopg allows only because no
        parameters are bound: with parameters it would use the extended
        protocol, which takes one statement at a time.
        """
        self._execute(render_schema(self.vector_size), None)

    def check_dimension(self) -> None:
        """Refuse to write vectors the column cannot hold.

        The equivalent of VectorStore's collection size check: a mismatch is a
        re-index, and it should say so rather than fail one row at a time
        halfway through a backfill.
        """
        rows = self._rows(declared_dimension_sql(), {})
        if not rows:
            raise PgVectorUnavailable(
                "The chunks table does not exist yet. Create it with: "
                "python3 -m stores.migrate --schema-only"
            )
        declared = parse_declared_dimension(rows[0].get("declared", ""))
        if declared is not None and declared != self.vector_size:
            raise EmbeddingDimensionMismatch(
                dimension_mismatch_message(declared, self.vector_size,
                                           self.embedding_model)
            )

    # --- writing ----------------------------------------------------------

    def _row_for(self, text: str, metadata: Dict) -> Tuple[str, Dict[str, Any]]:
        doc_id = self.generate_id(text, metadata)
        row = payload_to_row({**metadata, "text": text}, self.project_id, doc_id)
        row["embedding"] = vector_literal(self.embed(text))
        return doc_id, row

    def add_document(self, text: str, metadata: Dict) -> str:
        """Add a single document to the archive."""
        doc_id, row = self._row_for(text, metadata)
        self._execute(upsert_sql(), row)
        return doc_id

    def write_rows(self, rows: Sequence[Dict[str, Any]]) -> int:
        """Upsert rows that already carry their embedding.

        The migration copies vectors that were computed once already, so it
        writes through here rather than through ``add_documents_batch`` and its
        embedding step.
        """
        prepared = list(rows)
        if prepared:
            self._execute(upsert_sql(), prepared, many=True)
        return len(prepared)

    def existing_ids(self) -> set:
        """Every chunk id already stored for this project.

        A migration resumed after an interruption skips what it copied, which
        turns a second run over a decade of meetings into one query.
        """
        rows = self._rows(ids_sql(), {"project": self.project_id})
        return {str(row["id"]) for row in rows}

    def add_documents_batch(self, documents: List[Dict],
                            progress_callback=None) -> List[str]:
        """Add many documents in one transaction.

        Embedding happens one document at a time so ``progress_callback``
        reports the same units the Qdrant path reports and a long backfill
        still shows movement.
        """
        rows: List[Dict[str, Any]] = []
        doc_ids: List[str] = []

        for i, doc in enumerate(documents):
            doc_id, row = self._row_for(doc['text'], doc.get('metadata', {}))
            doc_ids.append(doc_id)
            rows.append(row)
            if progress_callback:
                progress_callback(i + 1, len(documents))

        self.write_rows(rows)
        return doc_ids

    def delete_by_source(self, source: str):
        """Delete every passage from one source, within this project only."""
        self._execute(delete_by_source_sql(),
                      {"project": self.project_id, "source": source})

    # --- reading ----------------------------------------------------------

    def _hit(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """One result in the shape VectorStore.search returns."""
        payload = row_to_payload(row)
        hit = {
            'id': str(row.get('id', '')),
            'score': float(row['score']) if row.get('score') is not None else None,
            'text': payload.get('text', ''),
            'source': payload.get('source', ''),
            'source_type': payload.get('source_type', ''),
            'url': payload.get('url', ''),
            'title': payload.get('title', ''),
            'date': payload.get('date', ''),
            'metadata': payload,
        }
        # Only hybrid_search returns these. The panel reports how a passage was
        # found, so the ranks and the raw half scores come back with it.
        for key in ('dense_rank', 'sparse_rank'):
            if row.get(key) is not None:
                hit[key] = int(row[key])
        for key in ('dense_score', 'sparse_score'):
            if row.get(key) is not None:
                hit[key] = float(row[key])
        return hit

    def search(self, query: str, top_k: int = 5,
               filter_dict: Optional[Dict] = None) -> List[Dict]:
        """Dense search.

        ``filter_dict`` is a plain mapping of the civic filters here, where the
        Qdrant store expects a qdrant_client Filter object. Nothing in the app
        passes one today, and the shape the API already speaks is the dict, so
        this is the direction to converge on rather than reproducing Qdrant's.
        """
        sql, params = search_sql(self.project_id, self.embed(query), top_k, filter_dict)
        return [self._hit(row) for row in self._rows(sql, params)]

    def hybrid_search(self, query: str, query_vector: Optional[Sequence[float]] = None,
                      top_k: int = 24, filters: Any = None,
                      candidate_pool: int = DEFAULT_CANDIDATE_POOL) -> List[Dict]:
        """Both halves of retrieval and their fusion, in one round trip.

        This is what HybridRetriever prefers when the store offers it. The
        keyword half comes from an index on disk that every instance shares,
        which is the property the in-memory BM25 index cannot have.

        Each hit carries ``dense_rank`` and ``sparse_rank`` so the transparency
        panel can still say whether a passage was found by meaning, by wording,
        or by both.
        """
        vector = query_vector if query_vector is not None else self.embed(query)
        sql, params = hybrid_sql(self.project_id, query, vector, top_k=top_k,
                                 filters=filters, candidate_pool=candidate_pool)
        return [self._hit(row) for row in self._rows(sql, params)]

    def iter_all_payloads(self, batch_size: int = 512) -> Iterable[Tuple[str, Dict]]:
        """Stream every stored payload as (id, payload).

        With ``hybrid_search`` available the retriever no longer walks the
        corpus to build a keyword index, so this exists for the evals, the
        exports, and any caller that still wants the whole archive. A failure
        ends the stream rather than raising, matching VectorStore, because the
        callers treat an empty corpus as a condition to report.
        """
        after = ""
        while True:
            try:
                rows = self._rows(page_sql(), {
                    "project": self.project_id, "after": after, "batch": batch_size,
                })
            except Exception:
                return

            if not rows:
                return

            for row in rows:
                after = str(row["id"])
                payload = row_to_payload(row)
                if payload.get('text'):
                    yield after, payload

    def get_by_id(self, doc_id: str) -> Optional[Dict]:
        """Fetch one stored payload by id, for the source-inspection endpoint."""
        try:
            rows = self._rows(by_id_sql(), {"project": self.project_id, "id": doc_id})
        except Exception:
            return None
        if not rows:
            return None
        return row_to_payload(rows[0])

    def get_stats(self) -> Dict:
        """Corpus size and what it was embedded with."""
        stats = {
            'total_documents': 0,
            'vector_size': self.vector_size,
            'distance_metric': 'cosine',
            'embedding_model': self.embedding_model,
        }
        try:
            rows = self._rows(stats_sql(), {"project": self.project_id})
        except Exception as exc:
            # A health endpoint asking how big the archive is must not be the
            # thing that takes the site down when the database is restarting.
            stats['error'] = f"{type(exc).__name__}: {exc}"
            return stats
        if rows:
            stats['total_documents'] = int(rows[0].get('total_documents', 0) or 0)
        return stats

    def chunk_text(self, text: str, chunk_size: int = 500,
                   overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks, as VectorStore does."""
        words = text.split()
        chunks = []

        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            if len(chunk.split()) > 50:
                chunks.append(chunk)

        return chunks


if __name__ == "__main__":
    status = pgvector_status()
    print("pgvector backend:", "ready" if status["enabled"] else "unavailable")
    if not status["enabled"]:
        print(status["reason"])
    print()
    print(f"schema at {DEFAULT_VECTOR_DIMENSION}d:",
          render_schema(DEFAULT_VECTOR_DIMENSION).count("CREATE INDEX"), "indexes")
    sql, params = hybrid_sql("brookline-ma", "Article 8.4 accessory dwelling units",
                             [0.0] * 4, top_k=8,
                             filters={"body": "Select Board", "date_from": "2019-01-01"})
    print(sql)
    print({k: (v[:40] + "..." if isinstance(v, str) and len(v) > 40 else v)
           for k, v in sorted(params.items())})
