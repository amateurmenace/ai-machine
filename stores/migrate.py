"""
Move a community's archive from Qdrant into PostgreSQL.

    python3 -m stores.migrate --project brookline-ma
    python3 -m stores.migrate --project brookline-ma --dry-run
    python3 -m stores.migrate --project brookline-ma --schema-only
    python3 -m stores.migrate --all

Two properties matter more than speed here, because what is being copied is a
town's public record and the copy may run for an hour over a decade of
meetings.

**Re-running is safe.** The schema is created with IF NOT EXISTS, chunk ids are
deterministic, and every row is written with ON CONFLICT DO UPDATE. An
interrupted run is resumed by running it again: ids already in Postgres are
skipped, so the second run costs one query plus whatever is left. ``--force``
re-copies everything, which is what to use after changing how chunks are built.

**Nothing is deleted.** The Qdrant index is left exactly as it was. A community
that finds something wrong after the cutover switches ``COMMUNITY_DB_URL`` back
off and is running on the old archive again, with no restore step.

Vectors are copied rather than recomputed. Re-embedding a decade of meetings
costs hours of GPU time to arrive at the same numbers, and a re-embed is only
needed when the embedding model itself changes, which is a re-ingestion rather
than a migration.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from stores import DSN_ENV_VAR, qdrant_path_for  # noqa: E402
from stores.pgvector_store import (  # noqa: E402
    EmbeddingDimensionMismatch, PgVectorStore, PgVectorUnavailable,
    default_embedding_model, embedding_dimension, payload_to_row,
    vector_literal,
)

DEFAULT_BATCH_SIZE = 500


class MigrationError(RuntimeError):
    """Something an operator has to fix before this project can be copied.

    Raised rather than exited on, because --all runs several projects and one
    community's missing index should not abandon the others.
    """


def redact(dsn: str) -> str:
    """Hide the password before printing a DSN.

    Migrations get pasted into tickets and chat logs, and a connection string
    with a live credential in it is the kind of thing that ends up in a
    screenshot.
    """
    return re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", dsn or "")


def project_ids_on_disk() -> List[str]:
    data = REPO_ROOT / "data"
    if not data.is_dir():
        return []
    return sorted(
        folder.name for folder in data.iterdir()
        if (folder / "config.json").is_file()
    )


def open_qdrant(path: str):
    """Open the embedded index read-only, without loading an embedding model.

    VectorStore would work, but it constructs a SentenceTransformer, and a copy
    that moves vectors already on disk has no text to embed.
    """
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise MigrationError(
            f"qdrant-client is not installed, so there is no source archive to "
            f"read ({exc}). Install it with:  pip install qdrant-client"
        )
    if not Path(path).exists():
        raise MigrationError(
            f"No Qdrant index at {path}. Pass --qdrant-path if this project's "
            f"archive lives elsewhere, or --schema-only to create the tables "
            f"and ingest fresh."
        )
    return QdrantClient(path=path)


def qdrant_count(client, collection: str) -> int:
    try:
        return int(client.get_collection(collection).points_count or 0)
    except Exception:
        return 0


def _point_vector(point) -> Optional[List[float]]:
    """Qdrant returns a list for an unnamed vector and a dict for named ones."""
    vector = getattr(point, "vector", None)
    if isinstance(vector, dict):
        vector = next(iter(vector.values()), None)
    if vector is None:
        return None
    return list(vector)


def iter_points(client, collection: str, batch_size: int) -> Iterable[Tuple[str, Dict, List[float]]]:
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=collection,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )
        if not points:
            return
        for point in points:
            payload = point.payload or {}
            vector = _point_vector(point)
            yield str(point.id), payload, vector or []
        if offset is None:
            return


def copy_collection(store: PgVectorStore, client, collection: str,
                    batch_size: int = DEFAULT_BATCH_SIZE,
                    force: bool = False) -> Dict[str, int]:
    """Copy every point, reporting progress as it goes."""
    total = qdrant_count(client, collection)
    already = set() if force else store.existing_ids()
    if already:
        print(f"  {len(already):,} chunk(s) already in Postgres; "
              f"they will be skipped. Use --force to re-copy.")

    counts = {"copied": 0, "skipped": 0, "no_vector": 0, "no_text": 0, "wrong_size": 0}
    batch: List[Dict[str, Any]] = []
    seen = 0

    for chunk_id, payload, vector in iter_points(client, collection, batch_size):
        seen += 1

        if chunk_id in already:
            counts["skipped"] += 1
        elif not payload.get("text"):
            # A point with no text cannot be retrieved or cited, so it is
            # counted and reported rather than copied into the new archive.
            counts["no_text"] += 1
        elif not vector:
            counts["no_vector"] += 1
        elif len(vector) != store.vector_size:
            counts["wrong_size"] += 1
        else:
            row = payload_to_row(payload, store.project_id, chunk_id)
            row["embedding"] = vector_literal(vector)
            batch.append(row)

        if len(batch) >= batch_size:
            counts["copied"] += store.write_rows(batch)
            batch = []
            print(f"  {counts['copied']:,} copied, {seen:,} of {total:,} read",
                  flush=True)

    counts["copied"] += store.write_rows(batch)

    counts["read"] = seen
    counts["source_total"] = total
    return counts


def migrate_project(project_id: str, dsn: str, args) -> int:
    print(f"\n{project_id}")
    print(f"  database:   {redact(dsn) or f'not set (${DSN_ENV_VAR})'}")

    embedding_model = args.embedding_model or default_embedding_model()
    dimension = args.dimension or embedding_dimension(embedding_model)
    print(f"  embeddings: {embedding_model} ({dimension}d)")

    collection = args.collection or project_id
    qdrant_path = args.qdrant_path or qdrant_path_for(project_id)

    if args.dry_run:
        print(f"  source:     {qdrant_path}, collection {collection}")
        client = open_qdrant(qdrant_path)
        print(f"  would create the schema and copy "
              f"{qdrant_count(client, collection):,} chunk(s).")
        print("  Dry run: nothing written.")
        return 0

    try:
        store = PgVectorStore(dsn, collection_name=project_id,
                              embedding_model=embedding_model,
                              vector_dimension=dimension)
    except PgVectorUnavailable as exc:
        print(f"  error: {exc}")
        return 1

    try:
        store.ensure_schema()
        print("  schema:     created or already present")
        store.check_dimension()
    except EmbeddingDimensionMismatch as exc:
        print(f"  error: {exc}")
        return 1
    except Exception as exc:
        print(f"  error: the schema could not be created: "
              f"{type(exc).__name__}: {exc}")
        print(f"  The role in {DSN_ENV_VAR} needs CREATE on the schema, and the "
              f"vector extension must be available on the instance.")
        return 1

    if args.schema_only:
        print("  Schema only: no chunks copied.")
        return 0

    print(f"  source:     {qdrant_path}, collection {collection}")
    client = open_qdrant(qdrant_path)

    try:
        counts = copy_collection(store, client, collection,
                                 batch_size=args.batch_size, force=args.force)
    except Exception as exc:
        print(f"  error: the copy stopped: {type(exc).__name__}: {exc}")
        print("  Nothing is lost. Run the same command again to resume.")
        return 1

    print(f"  copied {counts['copied']:,} of {counts['source_total']:,} chunk(s)")
    for key, label in (("skipped", "already present"),
                       ("no_text", "no text, not citable"),
                       ("no_vector", "no vector stored"),
                       ("wrong_size", f"wrong vector width for a {dimension}d column")):
        if counts.get(key):
            print(f"    {counts[key]:,} {label}")

    final = store.get_stats().get("total_documents", 0)
    print(f"  postgres now holds {final:,} chunk(s) for {project_id}")
    if counts["wrong_size"]:
        print("  Chunks of the wrong width were left behind. They were embedded "
              "with a different model and need re-ingesting, not copying.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create the PostgreSQL schema and copy a Qdrant archive into it.",
    )
    parser.add_argument("--project", help="project id to migrate")
    parser.add_argument("--all", action="store_true",
                        help="every project with a config.json under ./data")
    parser.add_argument("--dsn", help=f"overrides ${DSN_ENV_VAR}")
    parser.add_argument("--qdrant-path", help="source index (default: ./data/<project>/qdrant)")
    parser.add_argument("--collection", help="source collection (default: the project id)")
    parser.add_argument("--embedding-model", help="the model the corpus was embedded with")
    parser.add_argument("--dimension", type=int,
                        help="vector width, if the model is not in the known table")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--schema-only", action="store_true",
                        help="create the tables and indexes, copy nothing")
    parser.add_argument("--force", action="store_true",
                        help="re-copy chunks that are already in Postgres")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would happen and write nothing")
    args = parser.parse_args(argv)

    dsn = args.dsn or os.getenv(DSN_ENV_VAR, "")
    if not dsn and not args.dry_run:
        print(f"No database configured. Set ${DSN_ENV_VAR} or pass --dsn.")
        print("For Cloud SQL over the Cloud Run connector:")
        print("  postgresql://civic:PASSWORD@/civic"
              "?host=/cloudsql/PROJECT:REGION:INSTANCE")
        return 1

    if args.all:
        project_ids = project_ids_on_disk()
        if not project_ids:
            print("No projects found under ./data.")
            return 1
    elif args.project:
        project_ids = [args.project]
    else:
        parser.error("pass --project <id> or --all")
        return 2

    if len(project_ids) > 1 and (args.qdrant_path or args.collection):
        print("--qdrant-path and --collection describe one project; "
              "run them one at a time.")
        return 1

    print("=" * 62)
    print("Qdrant to PostgreSQL")
    print("=" * 62)

    failed = 0
    for project_id in project_ids:
        try:
            failed += migrate_project(project_id, dsn, args)
        except MigrationError as exc:
            print(f"  error: {exc}")
            failed += 1

    print()
    if failed:
        print(f"{failed} project(s) did not finish.")
        return 1

    if args.dry_run:
        return 0

    print(f"Done. Set {DSN_ENV_VAR} to point the app at the new archive, and")
    print("check it against the evaluation set before retiring the old one:")
    print(f"  python3 -m evals.run_evals --project {project_ids[0]} --retrieval-only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
