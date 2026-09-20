"""
Snapshots of a community's archive.

The point of keeping the database on the machine next to the inference server
is that the whole public record is one file somebody can hold. The cost of
that decision is that the file is on one machine, and machines die. This is
the answer to that, and it is deliberately dull: copy the file, hash it, write
down what was in it, and optionally put a copy somewhere else.

Three things here are not dull, and they are the reasons this is a module
rather than a line in a cron file.

A copy taken while the database is being written to can be torn. SQLite's own
backup API takes a consistent snapshot of a live database; ``cp`` does not.
So the snapshot goes through :meth:`SqliteVectorStore.backup_to`.

A backup nobody has opened is not a backup. Every snapshot is verified by
opening it, running an integrity check and counting the rows, and the count is
written into the manifest. A snapshot that fails verification is kept, marked
failed, and never counted as the good copy that lets an older one be pruned.

An archive of the public record has no confidentiality to protect, so these
snapshots are not encrypted. What they need is integrity: a resident who is
told "the board voted four to one" should be able to check that the archive
that answer came from is the archive that was ingested. So the manifest
carries a SHA-256 of the snapshot, and the constitution hash in force when it
was taken, which is the same chain of custody :mod:`community.ledger` makes
for the rules.

Upload to a bucket is optional, off by default, and never destroys the local
copy. A community with no cloud account gets working backups; a community with
a bucket gets the same backups and an offsite copy.

Postgres is not backed up here. ``pg_dump`` exists, is better than anything
this file would do, and pretending otherwise would be the sort of half-measure
that fails on the day it is needed.

    python3 -m stores.backup create   --project brookline-ma
    python3 -m stores.backup list     --project brookline-ma
    python3 -m stores.backup verify   data/backups/brookline-ma/archive-2026-09-20T12-00-00Z.sqlite3
    python3 -m stores.backup restore  data/backups/brookline-ma/archive-2026-09-20T12-00-00Z.sqlite3
    python3 -m stores.backup prune    --project brookline-ma --keep 14
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tarfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Where snapshots go when nobody says otherwise. Under ./data so one backup of
# the data directory catches archive and snapshots alike, and so a community
# that already excludes ./data from version control does not have to learn a
# second rule.
BACKUP_ROOT_ENV = "COMMUNITY_BACKUP_DIR"
DEFAULT_BACKUP_ROOT = "./data/backups"

# Offsite copy, if there is one. Same variable the uploads adapter uses, so a
# community configures a bucket once.
BUCKET_ENV = "COMMUNITY_STORAGE_BUCKET"

DEFAULT_KEEP = 14
MANIFEST_SUFFIX = ".manifest.json"
TIMESTAMP_FORMAT = "%Y-%m-%dT%H-%M-%SZ"

# Not snapshots: the manifest, and the sidecar files SQLite leaves beside a
# database in WAL mode. Counting a -wal file as a backup would report three
# copies where there is one, and a retention policy that believes it would
# delete two real ones.
SKIP_SUFFIXES = (MANIFEST_SUFFIX, "-wal", "-shm", "-journal")


class BackupError(RuntimeError):
    """Something an operator has to know about before trusting a restore."""


@dataclass
class Snapshot:
    """One backup, and everything needed to decide whether to trust it."""

    path: str
    taken_at: str
    backend: str
    project_id: str = ""
    size_bytes: int = 0
    sha256: str = ""
    document_count: Optional[int] = None
    embedding_model: str = ""
    constitution_hash: str = ""
    constitution_version: str = ""
    source_path: str = ""
    verified: bool = False
    verify_error: str = ""
    remote_uri: str = ""
    upload_error: str = ""
    notes: List[str] = field(default_factory=list)

    @property
    def manifest_path(self) -> str:
        return self.path + MANIFEST_SUFFIX

    @property
    def trustworthy(self) -> bool:
        """Verified, and not empty. An empty archive restores to silence."""
        return self.verified and bool(self.document_count)

    def write_manifest(self) -> str:
        Path(self.manifest_path).write_text(
            json.dumps(asdict(self), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return self.manifest_path

    @classmethod
    def read_manifest(cls, path: str) -> "Snapshot":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


# --- helpers --------------------------------------------------------------


def utc_stamp(when: Optional[datetime] = None) -> str:
    return (when or datetime.now(timezone.utc)).strftime(TIMESTAMP_FORMAT)


def sha256_file(path: str, block_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def backup_root(project_id: str = "", root: str = "") -> Path:
    base = Path(root or os.getenv(BACKUP_ROOT_ENV) or DEFAULT_BACKUP_ROOT)
    return base / project_id if project_id else base


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}TB"


def constitution_stamp(project_id: str = "") -> Dict[str, str]:
    """Which rules were in force when this snapshot was taken.

    Best effort on purpose: a community that has not adopted a constitution
    yet still gets backups, and the absence is recorded as an empty string
    rather than an exception.
    """
    try:
        from community.constitution import load_constitution

        constitution = load_constitution()
        return {"constitution_hash": getattr(constitution, "content_hash", "") or "",
                "constitution_version": str(getattr(constitution, "version", "") or "")}
    except Exception:
        return {"constitution_hash": "", "constitution_version": ""}


# --- taking a snapshot ----------------------------------------------------


def snapshot_sqlite(source: str, destination: str) -> None:
    """Consistent copy of a live SQLite archive.

    Opened read-only through a URI so this cannot be the thing that writes to
    an archive it was asked to protect.
    """
    if not os.path.exists(source):
        raise BackupError(f"There is no archive at {source} to back up.")
    Path(destination).parent.mkdir(parents=True, exist_ok=True)

    uri = "file:" + str(Path(source).resolve()) + "?mode=ro"
    live = sqlite3.connect(uri, uri=True, timeout=30.0)
    target = sqlite3.connect(destination)
    try:
        live.backup(target)
        # The live archive runs in WAL mode, and the snapshot inherits it,
        # which leaves a -wal and a -shm file beside the copy. That quietly
        # breaks the promise this backend is built on: a backup that is three
        # files is one somebody will move with one of them left behind. Taking
        # the snapshot out of WAL checkpoints it into a single file.
        target.execute("PRAGMA journal_mode = DELETE")
        target.commit()
    finally:
        target.close()
        live.close()

    for sidecar in (destination + "-wal", destination + "-shm"):
        try:
            os.remove(sidecar)
        except OSError:
            pass


def snapshot_directory(source: str, destination: str) -> None:
    """Tarball, for the Qdrant backend, whose archive is a directory tree."""
    if not os.path.isdir(source):
        raise BackupError(f"There is no index directory at {source} to back up.")
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(destination, "w:gz") as tar:
        tar.add(source, arcname=Path(source).name)


def verify_sqlite(path: str) -> Dict[str, Any]:
    """Open the snapshot and ask the database whether it is sound."""
    result: Dict[str, Any] = {"verified": False, "document_count": None,
                              "verify_error": "", "embedding_model": ""}
    try:
        con = sqlite3.connect("file:" + str(Path(path).resolve()) + "?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                result["verify_error"] = f"integrity_check said: {integrity}"
                return result
            result["document_count"] = con.execute(
                "SELECT COUNT(*) AS n FROM chunks").fetchone()["n"]
            # The keyword index is the half most likely to be left behind by a
            # bad copy, so it is queried rather than assumed.
            con.execute("SELECT rowid FROM chunks_fts LIMIT 1").fetchall()
            row = con.execute(
                "SELECT value FROM meta WHERE key = 'embedding_model'").fetchone()
            result["embedding_model"] = row["value"] if row else ""
            result["verified"] = True
        finally:
            con.close()
    except sqlite3.DatabaseError as exc:
        result["verify_error"] = f"{type(exc).__name__}: {exc}"
    except OSError as exc:
        result["verify_error"] = f"{type(exc).__name__}: {exc}"
    return result


def verify_tarball(path: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"verified": False, "document_count": None,
                              "verify_error": "", "embedding_model": ""}
    try:
        with tarfile.open(path, "r:gz") as tar:
            members = tar.getmembers()
        result["document_count"] = len(members)
        result["verified"] = bool(members)
        if not members:
            result["verify_error"] = "the tarball is empty"
    except (tarfile.TarError, OSError) as exc:
        result["verify_error"] = f"{type(exc).__name__}: {exc}"
    return result


def verify(path: str) -> Dict[str, Any]:
    """Verify whichever kind of snapshot this is."""
    return verify_tarball(path) if path.endswith((".tar.gz", ".tgz")) else verify_sqlite(path)


def upload(snapshot: Snapshot, bucket: str = "") -> Snapshot:
    """Put a copy somewhere that is not this machine. Optional and non-fatal."""
    bucket = (bucket or os.getenv(BUCKET_ENV) or "").strip()
    if not bucket:
        return snapshot

    try:
        from cloud.storage import GCSStorage

        storage = GCSStorage(bucket, prefix="backups")
        with open(snapshot.path, "rb") as handle:
            snapshot.remote_uri = storage.save(
                snapshot.project_id or "community", Path(snapshot.path).name, handle.read())
        # The manifest goes too. A snapshot in a bucket with no manifest is a
        # file of unknown provenance, which is the thing this module exists to
        # prevent.
        storage.save(snapshot.project_id or "community",
                     Path(snapshot.manifest_path).name,
                     json.dumps(asdict(snapshot), indent=2, sort_keys=True).encode("utf-8"))
    except Exception as exc:
        snapshot.upload_error = f"{type(exc).__name__}: {exc}"
        snapshot.notes.append(
            "The offsite copy failed. The local snapshot is unaffected and is "
            "still the backup; fix the bucket and run upload again.")
    return snapshot


def create(source: str, project_id: str = "", root: str = "", bucket: str = "",
           label: str = "") -> Snapshot:
    """Take one snapshot of one archive, verify it, and write its manifest."""
    source = str(source)
    is_directory = os.path.isdir(source)
    stamp = label or utc_stamp()
    suffix = ".tar.gz" if is_directory else ".sqlite3"
    destination = backup_root(project_id, root) / f"archive-{stamp}{suffix}"

    if is_directory:
        snapshot_directory(source, str(destination))
        backend = "qdrant"
    else:
        snapshot_sqlite(source, str(destination))
        backend = "sqlite"

    snapshot = Snapshot(
        path=str(destination),
        taken_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        backend=backend,
        project_id=project_id,
        source_path=str(Path(source).resolve()) if os.path.exists(source) else source,
        size_bytes=os.path.getsize(destination),
        sha256=sha256_file(str(destination)),
        **constitution_stamp(project_id),
    )
    for key, value in verify(str(destination)).items():
        setattr(snapshot, key, value)

    if not snapshot.verified:
        snapshot.notes.append(
            "This snapshot did not verify. It is kept so it can be examined, "
            "but it will not be treated as a good copy and will not allow an "
            "older snapshot to be pruned.")
    elif not snapshot.document_count:
        snapshot.notes.append(
            "This snapshot verified but is empty. An empty archive restores to "
            "a system that answers nothing; check that the source is the "
            "archive you meant.")

    snapshot = upload(snapshot, bucket)
    snapshot.write_manifest()
    return snapshot


# --- reading what is there ------------------------------------------------


def list_snapshots(project_id: str = "", root: str = "") -> List[Snapshot]:
    """Newest first. A snapshot with no manifest is still reported."""
    directory = backup_root(project_id, root)
    if not directory.is_dir():
        return []

    snapshots: List[Snapshot] = []
    for path in sorted(directory.iterdir()):
        if path.is_dir() or path.name.endswith(SKIP_SUFFIXES):
            continue
        manifest = Path(str(path) + MANIFEST_SUFFIX)
        if manifest.exists():
            try:
                snapshots.append(Snapshot.read_manifest(str(manifest)))
                continue
            except (json.JSONDecodeError, TypeError, OSError):
                pass
        snapshots.append(Snapshot(
            path=str(path),
            taken_at=datetime.fromtimestamp(path.stat().st_mtime,
                                            timezone.utc).isoformat(timespec="seconds"),
            backend="sqlite" if path.suffix == ".sqlite3" else "qdrant",
            project_id=project_id,
            size_bytes=path.stat().st_size,
            notes=["No manifest. This file was not made by this tool, or the "
                   "manifest was deleted; it has not been verified."],
        ))
    snapshots.sort(key=lambda s: s.taken_at, reverse=True)
    return snapshots


def prune(project_id: str = "", root: str = "", keep: int = DEFAULT_KEEP,
          dry_run: bool = False) -> List[Snapshot]:
    """Delete the oldest snapshots past ``keep``. Returns what went.

    Two refusals, both of which exist because the failure mode of a retention
    policy is deleting the copy you needed:

    The newest trustworthy snapshot is never deleted, whatever ``keep`` says.
    If the only good copy is older than ``keep`` allows, the policy is wrong
    and the copy is right.

    Nothing is deleted at all unless there is at least one trustworthy
    snapshot to keep. Pruning down to a pile of files that failed verification
    is not retention, it is data loss on a schedule.
    """
    snapshots = list_snapshots(project_id, root)
    good = [s for s in snapshots if s.trustworthy]
    if not good:
        return []

    newest_good = good[0].path
    doomed = [s for s in snapshots[max(0, keep):] if s.path != newest_good]

    if not dry_run:
        for snapshot in doomed:
            for path in (snapshot.path, snapshot.manifest_path):
                try:
                    os.remove(path)
                except OSError:
                    pass
    return doomed


def restore(snapshot_path: str, destination: str, force: bool = False) -> Dict[str, Any]:
    """Put a snapshot back, after checking it and getting the current one out of the way.

    The existing archive is moved aside rather than overwritten. If the
    restore turns out to be the wrong snapshot, the archive that was there a
    minute ago is still on disk with a name saying when it was displaced.
    """
    if not os.path.exists(snapshot_path):
        raise BackupError(f"There is no snapshot at {snapshot_path}.")

    manifest_path = snapshot_path + MANIFEST_SUFFIX
    recorded = ""
    if os.path.exists(manifest_path):
        try:
            recorded = Snapshot.read_manifest(manifest_path).sha256
        except (json.JSONDecodeError, TypeError, OSError):
            recorded = ""

    actual = sha256_file(snapshot_path)
    if recorded and recorded != actual and not force:
        raise BackupError(
            f"This snapshot does not match its manifest.\n"
            f"  manifest says: {recorded}\n"
            f"  the file is:   {actual}\n"
            f"Something changed the file after it was taken. Restore it with "
            f"--force only if you know what changed it.")

    checked = verify(snapshot_path)
    if not checked["verified"] and not force:
        raise BackupError(
            f"This snapshot does not open cleanly ({checked['verify_error']}). "
            f"Restoring it would replace a working archive with a broken one. "
            f"Use --force only to recover what can be recovered from it.")

    displaced = ""
    if os.path.exists(destination):
        displaced = f"{destination}.superseded-{utc_stamp()}"
        shutil.move(destination, displaced)

    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    if snapshot_path.endswith((".tar.gz", ".tgz")):
        with tarfile.open(snapshot_path, "r:gz") as tar:
            tar.extractall(Path(destination).parent)
    else:
        shutil.copy2(snapshot_path, destination)

    return {"restored": destination, "from": snapshot_path,
            "documents": checked["document_count"], "displaced": displaced,
            "sha256": actual}


def archive_path_for(project_id: str) -> str:
    """Where this project's live archive is, according to the store factory."""
    from stores import select_backend

    choice = select_backend(project_id)
    if choice.is_postgres:
        raise BackupError(
            "This project's archive is in PostgreSQL. Back it up with pg_dump, "
            "which handles it properly:\n"
            f"  pg_dump '{choice.dsn}' --format=custom --file=archive.dump")
    return choice.path


# --- CLI ------------------------------------------------------------------


def print_snapshot(snapshot: Snapshot) -> None:
    mark = "ok  " if snapshot.trustworthy else ("EMPTY" if snapshot.verified else "BAD ")
    count = "?" if snapshot.document_count is None else f"{snapshot.document_count:,}"
    print(f"  {mark} {Path(snapshot.path).name}  {human_size(snapshot.size_bytes)}  "
          f"{count} passages  {snapshot.taken_at}")
    if snapshot.remote_uri:
        print(f"       offsite: {snapshot.remote_uri}")
    for note in snapshot.notes:
        print(f"       note: {note}")
    if snapshot.verify_error:
        print(f"       error: {snapshot.verify_error}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m stores.backup",
        description="Snapshot, verify, prune and restore a community archive.")
    sub = parser.add_subparsers(dest="command", required=True)

    make = sub.add_parser("create", help="take a snapshot")
    make.add_argument("--project", default="", help="project id")
    make.add_argument("--source", default="", help="archive path (default: from config)")
    make.add_argument("--root", default="", help=f"where snapshots go (default {DEFAULT_BACKUP_ROOT})")
    make.add_argument("--bucket", default="", help="also upload to this GCS bucket")
    make.add_argument("--keep", type=int, default=0,
                      help="prune to this many snapshots afterwards")

    listing = sub.add_parser("list", help="show snapshots")
    listing.add_argument("--project", default="")
    listing.add_argument("--root", default="")

    checking = sub.add_parser("verify", help="check a snapshot opens and is sound")
    checking.add_argument("path")

    putting = sub.add_parser("restore", help="put a snapshot back")
    putting.add_argument("path")
    putting.add_argument("--project", default="")
    putting.add_argument("--destination", default="")
    putting.add_argument("--force", action="store_true",
                         help="restore despite a failed check")
    putting.add_argument("--yes", action="store_true", help="do not ask")

    pruning = sub.add_parser("prune", help="delete old snapshots")
    pruning.add_argument("--project", default="")
    pruning.add_argument("--root", default="")
    pruning.add_argument("--keep", type=int, default=DEFAULT_KEEP)
    pruning.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)

    try:
        if args.command == "create":
            source = args.source or archive_path_for(args.project)
            started = time.time()
            snapshot = create(source, project_id=args.project, root=args.root,
                              bucket=args.bucket)
            print(f"Snapshot of {source} taken in {time.time() - started:.1f}s")
            print_snapshot(snapshot)
            print(f"  sha256: {snapshot.sha256}")
            print(f"  manifest: {snapshot.manifest_path}")
            if args.keep:
                gone = prune(args.project, args.root, keep=args.keep)
                print(f"  pruned {len(gone)} older snapshot(s), keeping {args.keep}")
            return 0 if snapshot.trustworthy else 1

        if args.command == "list":
            snapshots = list_snapshots(args.project, args.root)
            if not snapshots:
                print(f"No snapshots in {backup_root(args.project, args.root)}.")
                return 0
            print(f"{len(snapshots)} snapshot(s) in {backup_root(args.project, args.root)}:")
            for snapshot in snapshots:
                print_snapshot(snapshot)
            return 0

        if args.command == "verify":
            result = verify(args.path)
            digest = sha256_file(args.path)
            print(f"{args.path}")
            print(f"  opens cleanly: {'yes' if result['verified'] else 'no'}")
            print(f"  passages:      {result['document_count']}")
            print(f"  sha256:        {digest}")
            manifest = args.path + MANIFEST_SUFFIX
            if os.path.exists(manifest):
                recorded = Snapshot.read_manifest(manifest).sha256
                same = recorded == digest
                print(f"  matches manifest: {'yes' if same else 'NO - the file changed'}")
                if not same:
                    return 1
            if result["verify_error"]:
                print(f"  error: {result['verify_error']}")
            return 0 if result["verified"] else 1

        if args.command == "restore":
            destination = args.destination or archive_path_for(args.project)
            if not args.yes:
                print(f"This will replace {destination} with {args.path}.")
                print("The current archive will be moved aside, not deleted.")
                if not sys.stdin.isatty():
                    print("Refusing to restore without --yes when nothing can confirm.")
                    return 2
                if input("Type the word restore to continue: ").strip() != "restore":
                    print("Nothing was changed.")
                    return 2
            result = restore(args.path, destination, force=args.force)
            print(f"Restored {result['documents']} passages to {result['restored']}")
            if result["displaced"]:
                print(f"The archive that was there is at {result['displaced']}")
            return 0

        if args.command == "prune":
            gone = prune(args.project, args.root, keep=args.keep, dry_run=args.dry_run)
            verb = "would delete" if args.dry_run else "deleted"
            if not gone:
                print(f"Nothing to prune (keeping {args.keep}, and the newest good copy "
                      f"is never deleted).")
                return 0
            print(f"{verb} {len(gone)} snapshot(s):")
            for snapshot in gone:
                print(f"  {Path(snapshot.path).name}  {snapshot.taken_at}")
            return 0

    except BackupError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
