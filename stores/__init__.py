"""
Which database holds a community's archive.

There are now two: the embedded Qdrant index a community runs on its own
machine, and the PostgreSQL archive that ROADMAP.md section 2.3 argues for on
Google Cloud. They are not a progression. A town serving itself from a computer
in the town hall should not need a managed database, and a platform hosting
twelve communities should not be running twelve embedded indexes.

So the choice is configuration, not a code path: set ``COMMUNITY_DB_URL`` and
the archive is in Postgres, leave it unset and nothing changes. Both stores
implement the same interface, so :class:`rag.hybrid.HybridRetriever`, the
agent, the gateway and the evals never learn which one they got.

:func:`select_backend` is separated from :func:`build_store` because the
decision is worth being able to inspect and test without opening a database or
loading an embedding model, and because an operator asking "which archive is
this deployment actually using" deserves an answer that does not require
starting the app.

A configured Postgres that cannot be opened is an error rather than a quiet
fallback to Qdrant. Falling back would answer residents from a different
archive, or an empty one, without saying so, and a service whose whole claim is
that its answers come from the public record cannot do that quietly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

QDRANT = "qdrant"
PGVECTOR = "pgvector"

# The DSN. Cloud SQL over the Cloud Run connector looks like:
#   postgresql://civic:...@/civic?host=/cloudsql/PROJECT:REGION:INSTANCE
DSN_ENV_VAR = "COMMUNITY_DB_URL"


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


def project_id_of(project: Any) -> str:
    """Accept a ProjectConfig, anything carrying a project_id, or a bare id."""
    if isinstance(project, str):
        return project
    return str(getattr(project, "project_id", "") or "")


def qdrant_path_for(project_id: str) -> str:
    """Where the embedded index lives. Matches what app.py has always used."""
    return f"./data/{project_id}/qdrant"


def select_backend(project: Any, dsn: Optional[str] = None) -> BackendChoice:
    """Decide which store this project should use, without building it.

    A project setting beats the environment so one community can be moved to
    Postgres ahead of the others on a shared deployment, which is how a
    migration actually gets done: one town, verified, then the rest.
    """
    project_id = project_id_of(project)
    collection_name = project_id or "civic_knowledge"
    embedding_model = getattr(project, "embedding_model", None)

    setting = getattr(project, "community_db_url", None)
    if dsn:
        resolved, reason = dsn, "explicit dsn"
    elif setting:
        resolved, reason = str(setting), "project setting community_db_url"
    elif os.getenv(DSN_ENV_VAR):
        resolved, reason = os.environ[DSN_ENV_VAR], f"{DSN_ENV_VAR} environment variable"
    else:
        return BackendChoice(
            backend=QDRANT,
            collection_name=collection_name,
            embedding_model=embedding_model,
            path=qdrant_path_for(project_id),
            reason=f"no {DSN_ENV_VAR} configured",
        )

    return BackendChoice(
        backend=PGVECTOR,
        collection_name=collection_name,
        embedding_model=embedding_model,
        dsn=resolved,
        reason=reason,
    )


def build_store(project: Any, dsn: Optional[str] = None):
    """Open this project's archive.

    The imports are inside the branches so a Postgres deployment does not load
    qdrant-client and an embedded deployment does not need psycopg.
    """
    choice = select_backend(project, dsn=dsn)

    if choice.is_postgres:
        from stores.pgvector_store import PgVectorStore

        return PgVectorStore(
            dsn=choice.dsn,
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
    "PGVECTOR",
    "QDRANT",
    "build_store",
    "project_id_of",
    "qdrant_path_for",
    "select_backend",
]
