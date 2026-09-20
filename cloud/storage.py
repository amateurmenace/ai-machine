"""
Where an uploaded PDF actually lives.

A resident uploads the capital plan, the ingestion path reads it back, and the
citation for page 127 points at it a year later. On one machine that is a file
in ``data/<project>/uploads`` and nothing more needs saying. On Cloud Run the
filesystem is in memory and the instance is replaced whenever Google feels like
it, so the same code quietly loses the document, and ROADMAP.md 2.4 moves it to
Cloud Storage.

This is the seam between the two. Choices worth stating:

* **A URI, not a path, is what gets stored on the source.** ``file://`` and
  ``gs://`` both round-trip through :meth:`Storage.open`, which means a
  community that starts on a VM and later adds a bucket keeps every document it
  already ingested. :class:`GCSStorage` reads ``file://`` URIs off local disk
  for exactly that reason, rather than pretending the old uploads never existed.
* **Local is the default and is not a degraded mode.** No bucket configured is
  the supported deployment, not a missing feature.
* **Filenames from a browser are treated as hostile.** ``file.filename`` is
  whatever the client sent, and a name containing ``../`` would escape the
  project's directory. The name a resident sees is kept on the source record;
  the name on disk is sanitized.
* **Reads return a file-like object.** ``PdfReader`` takes one, so the
  ingestion path does not care which backend it got, and a Cloud Storage object
  never has to be written to a temporary file first.

google-cloud-storage is an optional import and is not in ``requirements.txt``.
"""

from __future__ import annotations

import io
import mimetypes
import os
import re
import threading
from pathlib import Path
from typing import Any, BinaryIO, Dict, Optional, Tuple

from cloud import CloudUnavailable

STORAGE_BUCKET_ENV = "COMMUNITY_STORAGE_BUCKET"
STORAGE_PREFIX_ENV = "COMMUNITY_STORAGE_PREFIX"
DATA_ROOT_ENV = "COMMUNITY_DATA_ROOT"

INSTALL_REMEDY = (
    "Install it with: pip install google-cloud-storage  (or unset "
    f"{STORAGE_BUCKET_ENV} to keep uploads on local disk)."
)

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_NAME = 120


class StorageError(RuntimeError):
    """An upload could not be stored or read back.

    The message is written for the operator who has to fix it, because the
    resident on the other end of it only ever sees "that document could not be
    read".
    """


def safe_filename(filename: str) -> str:
    """A filename that cannot escape its directory or surprise a bucket."""
    name = os.path.basename((filename or "").strip().replace("\\", "/"))
    name = _UNSAFE.sub("_", name).strip("._") or "upload"
    if len(name) > _MAX_NAME:
        stem, dot, suffix = name.rpartition(".")
        keep = _MAX_NAME - len(suffix) - 1 if dot else _MAX_NAME
        name = f"{stem[:keep]}.{suffix}" if dot else name[:_MAX_NAME]
    return name


def parse_gs_uri(uri: str) -> Tuple[str, str]:
    """Split ``gs://bucket/key`` into its two halves."""
    rest = uri[len("gs://"):]
    bucket, _, key = rest.partition("/")
    if not bucket or not key:
        raise StorageError(f"not a Cloud Storage object URI: {uri!r}")
    return bucket, key


def local_path(uri: str) -> Path:
    """The path a ``file://`` URI or a bare path names.

    Bare paths are accepted because sources created before this module stored
    one, and an archive does not get re-ingested just because the code changed.
    """
    text = str(uri or "")
    if text.startswith("file://"):
        text = text[len("file://"):]
    return Path(text)


class Storage:
    """The interface both backends implement."""

    backend = "storage"

    def save(self, project_id: str, filename: str, data: bytes) -> str:
        raise NotImplementedError

    def open(self, uri: str) -> BinaryIO:
        raise NotImplementedError

    def delete(self, uri: str) -> bool:
        raise NotImplementedError

    def exists(self, uri: str) -> bool:
        raise NotImplementedError

    def status(self) -> Dict[str, Any]:
        raise NotImplementedError


class LocalStorage(Storage):
    """Uploads on the machine's own disk. The default, and the supported one."""

    backend = "local"

    def __init__(self, data_root: str = "") -> None:
        self.data_root = data_root or os.getenv(DATA_ROOT_ENV) or "./data"

    def directory(self, project_id: str) -> Path:
        return Path(self.data_root) / project_id / "uploads"

    def save(self, project_id: str, filename: str, data: bytes) -> str:
        path = self.directory(project_id) / safe_filename(filename)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except OSError as exc:
            raise StorageError(
                f"Could not write {path}: {exc}. Check the disk has space and "
                f"that the service can write to {self.data_root}."
            ) from exc
        return f"file://{path}"

    def open(self, uri: str) -> BinaryIO:
        self._refuse_remote(uri)
        path = local_path(uri)
        try:
            return path.open("rb")
        except OSError as exc:
            raise StorageError(
                f"Could not read {path}: {exc}. On Cloud Run the filesystem does "
                f"not survive a restart; set {STORAGE_BUCKET_ENV} so uploads go "
                f"to Cloud Storage instead."
            ) from exc

    def delete(self, uri: str) -> bool:
        self._refuse_remote(uri)
        try:
            local_path(uri).unlink()
            return True
        except OSError:
            return False

    def exists(self, uri: str) -> bool:
        if str(uri or "").startswith("gs://"):
            return False
        return local_path(uri).is_file()

    def status(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "configured": False,
            "active": True,
            "location": str(Path(self.data_root).resolve()),
            "detail": ("Uploaded PDFs are on this machine's disk. Correct for a "
                       "server with a persistent disk, and lost on every Cloud "
                       "Run restart."),
            "remedy": None,
        }

    @staticmethod
    def _refuse_remote(uri: str) -> None:
        if str(uri or "").startswith("gs://"):
            raise StorageError(
                f"{uri} is in Cloud Storage but this deployment is storing "
                f"uploads on local disk. Set {STORAGE_BUCKET_ENV} to the bucket "
                f"that holds it."
            )


class GCSStorage(Storage):
    """Uploads in a Cloud Storage bucket, for an instance with no disk of its own."""

    backend = "gcs"

    def __init__(self, bucket: str, prefix: str = "", client: Any = None,
                 data_root: str = "") -> None:
        if not bucket:
            raise CloudUnavailable(
                "Cloud Storage was asked for without a bucket name.",
                remedy=f"Set {STORAGE_BUCKET_ENV} to a bucket you have created.",
            )
        self.bucket_name = bucket.replace("gs://", "").strip("/")
        self.prefix = (prefix or os.getenv(STORAGE_PREFIX_ENV) or "uploads").strip("/")
        self._client = client
        self._lock = threading.Lock()
        # Documents ingested before the bucket existed still have file:// URIs.
        self.local = LocalStorage(data_root)

    @property
    def client(self) -> Any:
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._client = self._build_client()
        return self._client

    @staticmethod
    def _build_client() -> Any:
        try:
            from google.cloud import storage as gcs
        except ImportError as exc:
            raise CloudUnavailable(
                f"{STORAGE_BUCKET_ENV} is set but the 'google-cloud-storage' "
                f"package is not installed.",
                remedy=INSTALL_REMEDY,
            ) from exc
        try:
            return gcs.Client()
        except Exception as exc:
            raise CloudUnavailable(
                f"Could not open a Cloud Storage client: {type(exc).__name__}: {exc}",
                remedy=("Give the Cloud Run service account the Storage Object "
                        "Admin role on the bucket, or run `gcloud auth "
                        "application-default login` locally."),
            ) from exc

    def key_for(self, project_id: str, filename: str) -> str:
        return f"{self.prefix}/{project_id}/{safe_filename(filename)}"

    def _blob(self, uri: str) -> Any:
        bucket, key = parse_gs_uri(uri)
        return self.client.bucket(bucket).blob(key)

    def save(self, project_id: str, filename: str, data: bytes) -> str:
        key = self.key_for(project_id, filename)
        content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
        try:
            blob = self.client.bucket(self.bucket_name).blob(key)
            blob.upload_from_string(data, content_type=content_type)
        except CloudUnavailable:
            raise
        except Exception as exc:
            raise StorageError(
                f"Could not upload to gs://{self.bucket_name}/{key}: "
                f"{type(exc).__name__}: {exc}. Check the bucket exists and that "
                f"the service account may write to it."
            ) from exc
        return f"gs://{self.bucket_name}/{key}"

    def open(self, uri: str) -> BinaryIO:
        if not str(uri or "").startswith("gs://"):
            return self.local.open(uri)
        try:
            return io.BytesIO(self._blob(uri).download_as_bytes())
        except CloudUnavailable:
            raise
        except Exception as exc:
            raise StorageError(
                f"Could not read {uri}: {type(exc).__name__}: {exc}. The object "
                f"may have been deleted, or the service account may not read "
                f"this bucket."
            ) from exc

    def delete(self, uri: str) -> bool:
        if not str(uri or "").startswith("gs://"):
            return self.local.delete(uri)
        try:
            self._blob(uri).delete()
            return True
        except Exception:
            return False

    def exists(self, uri: str) -> bool:
        if not str(uri or "").startswith("gs://"):
            return self.local.exists(uri)
        try:
            return bool(self._blob(uri).exists())
        except Exception:
            return False

    def status(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "configured": True,
            "active": True,
            "location": f"gs://{self.bucket_name}/{self.prefix}",
            "detail": ("Uploaded PDFs go to Cloud Storage and survive an "
                       "instance restart. Documents ingested before the bucket "
                       "was configured are still read from local disk."),
            "remedy": None,
        }


def build_storage(bucket: Optional[str] = None, data_root: str = "",
                  prefix: str = "") -> Storage:
    """Pick a backend. A bucket that cannot be used falls back to local disk.

    Falling back rather than refusing to start is deliberate: a community whose
    bucket configuration is wrong should serve answers from the archive it
    already has while somebody fixes it.
    """
    bucket = bucket if bucket is not None else (os.getenv(STORAGE_BUCKET_ENV) or "").strip()
    if not bucket:
        return LocalStorage(data_root)

    try:
        storage = GCSStorage(bucket, prefix=prefix, data_root=data_root)
        storage.client  # fail now, in a boot log, rather than on an upload
        return storage
    except CloudUnavailable as exc:
        print(f"[cloud.storage] {exc.message} {exc.remedy} "
              f"Uploads are going to local disk.")
    except Exception as exc:                       # pragma: no cover - defensive
        print(f"[cloud.storage] Cloud Storage is unavailable "
              f"({type(exc).__name__}: {exc}). Uploads are going to local disk.")
    return LocalStorage(data_root)


_storage: Optional[Storage] = None
_storage_lock = threading.Lock()


def get_storage(data_root: str = "") -> Storage:
    """The process-wide storage backend, built once."""
    global _storage
    if _storage is None:
        with _storage_lock:
            if _storage is None:
                _storage = build_storage(data_root=data_root)
    return _storage


def reset_storage() -> None:
    """Forget the cached backend. For tests and for a configuration reload."""
    global _storage
    with _storage_lock:
        _storage = None


def storage_status() -> Dict[str, Any]:
    """What the upload path is actually doing, for ``/api/admin/cloud-status``."""
    bucket = (os.getenv(STORAGE_BUCKET_ENV) or "").strip()
    status = get_storage().status()
    if bucket and status["backend"] != "gcs":
        status = dict(status)
        status["configured"] = True
        status["active"] = False
        status["detail"] = (
            f"{STORAGE_BUCKET_ENV} names {bucket}, but uploads are going to "
            f"local disk, which Cloud Run does not keep."
        )
        status["remedy"] = INSTALL_REMEDY
    return status


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        store = LocalStorage(tmp)
        uri = store.save("brookline-ma", "Capital Plan FY26.pdf", b"%PDF-1.7 ...")
        print("saved:", uri)
        print("exists:", store.exists(uri))
        with store.open(uri) as handle:
            print("read back:", handle.read()[:8])
        print("sanitized:", safe_filename("../../etc/passwd"))
        print("deleted:", store.delete(uri), "exists now:", store.exists(uri))
        try:
            store.open("gs://a-bucket/uploads/x.pdf")
        except StorageError as exc:
            print("remote URI on a local backend:", exc)
