"""
Which database holds a community's archive.

There are three, and they are not a progression:

    sqlite     one community, one machine. One file holding the whole public
               record, copyable and checksummable. The default.
    qdrant     the original embedded index. Still supported, never converted
               out from under anyone.
    pgvector   many communities on shared infrastructure, or an archive large
               enough that one machine is genuinely the constraint.

A town serving itself from a computer in the town hall should not need a
managed database, and a platform hosting twelve communities should not be
running twelve embedded indexes. So the choice is configuration, not a code
path: point ``COMMUNITY_DB_URL`` at Postgres and the archive is in Postgres,
leave it unset and the archive is a file next to the inference server. All
three stores implement the same interface, so :class:`rag.hybrid.HybridRetriever`,
the agent, the gateway and the evals never learn which one they got.

:func:`select_backend` is separated from :func:`build_store` because the
decision is worth being able to inspect and test without opening a database or
loading an embedding model, and because an operator asking "which archive is
this deployment actually using" deserves an answer that does not require
starting the app.

Two rules keep that honest:

A configured database that cannot be opened is an error rather than a quiet
fallback. Falling back would answer residents from a different archive, or an
empty one, without saying so, and a service whose whole claim is that its
answers come from the public record cannot do that quietly.

A deployment that already has a Qdrant index keeps using it. SQLite is the
better default for a new community, but "better default" is not a licence to
silently read from an empty archive on somebody's next restart. Moving is a
decision an operator makes, with :mod:`stores.migrate`, on purpose.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

SQLITE = "sqlite"
QDRANT = "qdrant"
PGVECTOR = "pgvector"

# The DSN. Cloud SQL over the Cloud Run connector looks like:
#   postgresql://civic:...@/civic?host=/cloudsql/PROJECT:REGION:INSTANCE
# A sqlite:// URL is accepted here too, so a single setting can name any
# backend and deployment tooling does not need a second variable.
DSN_ENV_VAR = "COMMUNITY_DB_URL"

# The plainer way to say the same thing for the common case: a file path.
PATH_ENV_VAR = "COMMUNITY_DB_PATH"

POSTGRES_SCHEMES = ("postgresql://", "postgres://", "postgresql+psycopg://")
SQLITE_SCHEME = "sqlite://"
SQLITE_SUFFIXES = (".sqlite3", ".sqlite", ".db")


@dataclass
class BackendChoice:
    """Which store a project gets, and why."""

    backend: str
    collection_name: str
    embedding_model: Optional[str] = None
    dsn: str = ""
    path: str = ""
    reason: str = ""

    @property
    def is_postgres(self) -> bool:
        return self.backend == PGVECTOR

    @property
    def is_sqlite(self) -> bool:
        return self.backend == SQLITE

    @property
    def location(self) -> str:
        """What to print when an operator asks where the archive is."""
        return self.path or self.dsn


def project_id_of(project: Any) -> str:
    """Accept a ProjectConfig, anything carrying a project_id, or a bare id."""
    if isinstance(project, str):
        return project
    return str(getattr(project, "project_id", "") or "")


def qdrant_path_for(project_id: str) -> str:
    """Where the embedded index lives. Matches what app.py has always used."""
    return f"./data/{project_id}/qdrant"


def sqlite_path_for(project_id: str) -> str:
    """Where the one-file archive lives. Same tree, so backups catch both."""
    return f"./data/{project_id}/archive.sqlite3"


def has_qdrant_index(project_id: str) -> bool:
    """Is there already an embedded index here with something in it?

    An empty directory does not count: the app creates the tree before it has
    ingested anything, and treating that as "already on Qdrant" would pin every
    fresh install to the old default forever.
    """
    path = qdrant_path_for(project_id)
    try:
        return os.path.isdir(path) and any(os.scandir(path))
    except OSError:
        return False


def parse_dsn(value: str) -> tuple:
    """Work out which backend a connection string names.

    Returns ``(backend, dsn, path)``. A ``sqlite://`` URL keeps whatever
    follows the scheme verbatim, so ``sqlite:///srv/civic.sqlite3`` is the
    absolute path and ``sqlite://data/civic.sqlite3`` is the relative one. A
    bare path ending in a SQLite suffix is accepted as well, because operators
    write those and there is no other thing it could mean.
    """
    text = (value or "").strip()
    lowered = text.lower()

    if lowered.startswith(POSTGRES_SCHEMES):
        return PGVECTOR, text, ""
    if lowered.startswith(SQLITE_SCHEME):
        return SQLITE, text, text[len(SQLITE_SCHEME):]
    if lowered.endswith(SQLITE_SUFFIXES):
        return SQLITE, text, text
    # Anything else is assumed to be a Postgres DSN, which is what it was
    # before sqlite:// existed. psycopg will say so if it is not.
    return PGVECTOR, text, ""


def select_backend(project: Any, dsn: Optional[str] = None) -> BackendChoice:
    """Decide which store this project should use, without building it.

    Precedence, most explicit first: an argument, then the project's own
    setting, then ``COMMUNITY_DB_URL``, then ``COMMUNITY_DB_PATH``, then the
    default. A project setting beats the environment so one community can be
    moved to Postgres ahead of the others on a shared deployment, which is how
    a migration actually gets done: one town, verified, then the rest.
    """
    project_id = project_id_of(project)
    collection_name = project_id or "civic_knowledge"
    embedding_model = getattr(project, "embedding_model", None)

    def chosen(value: str, reason: str) -> BackendChoice:
        backend, resolved, path = parse_dsn(value)
        return BackendChoice(
            backend=backend,
            collection_name=collection_name,
            embedding_model=embedding_model,
            dsn=resolved if backend == PGVECTOR else "",
            path=path,
            reason=reason,
        )

    setting = getattr(project, "community_db_url", None)
    if dsn:
        return chosen(dsn, "explicit dsn")
    if setting:
        return chosen(str(setting), "project setting community_db_url")
    if os.getenv(DSN_ENV_VAR):
        return chosen(os.environ[DSN_ENV_VAR], f"{DSN_ENV_VAR} environment variable")
    if os.getenv(PATH_ENV_VAR):
        return BackendChoice(
            backend=SQLITE,
            collection_name=collection_name,
            embedding_model=embedding_model,
            path=os.environ[PATH_ENV_VAR],
            reason=f"{PATH_ENV_VAR} environment variable",
        )

    if has_qdrant_index(project_id):
        return BackendChoice(
            backend=QDRANT,
            collection_name=collection_name,
            embedding_model=embedding_model,
            path=qdrant_path_for(project_id),
            reason="existing qdrant index, left alone",
        )

    return BackendChoice(
        backend=SQLITE,
        collection_name=collection_name,
        embedding_model=embedding_model,
        path=sqlite_path_for(project_id),
        reason="default: one file on this machine",
    )


def build_store(project: Any, dsn: Optional[str] = None):
    """Open this project's archive.

    The imports are inside the branches so a Postgres deployment does not load
    qdrant-client, an embedded deployment does not need psycopg, and the
    default needs neither.
    """
    choice = select_backend(project, dsn=dsn)

    if choice.is_postgres:
        from stores.pgvector_store import PgVectorStore

        return PgVectorStore(
            dsn=choice.dsn,
            collection_name=choice.collection_name,
            embedding_model=choice.embedding_model,
        )

    if choice.is_sqlite:
        from stores.sqlite_store import SqliteVectorStore

        return SqliteVectorStore(
            path=choice.path,
            collection_name=choice.collection_name,
            embedding_model=choice.embedding_model,
        )

    from vector_store import VectorStore

    return VectorStore(
        path=choice.path,
        collection_name=choice.collection_name,
        embedding_model=choice.embedding_model,
    )


__all__ = [
    "BackendChoice",
    "DSN_ENV_VAR",
    "PATH_ENV_VAR",
    "PGVECTOR",
    "QDRANT",
    "SQLITE",
    "build_store",
    "has_qdrant_index",
    "parse_dsn",
    "project_id_of",
    "qdrant_path_for",
    "select_backend",
    "sqlite_path_for",
]
