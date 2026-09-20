"""
Request records that outlive the instance that wrote them.

``api.audit`` writes one JSON line per request to
``data/<project>/logs/requests-YYYY-MM-DD.jsonl`` and prunes it on the
community's retention setting. On a machine with a disk that is the whole
answer. On Cloud Run the disk is memory, so the record of what the assistant
did disappears with the instance, which is a governance problem rather than an
operations one: ``constitution/governance.md`` promises the community aggregate
statistics about its own assistant.

This mirrors those records into Cloud Logging when it is configured. Decisions
worth stating:

* **The JSONL stays, always.** It is what ``usage_summary`` reads, so it stays
  the source of truth for the public statistics; Cloud Logging is the durable
  copy for an instance that will not survive the week. Nothing here replaces a
  local file.
* **The privacy rule is applied again here, not trusted.** The record arriving
  from ``api.audit`` already has the question replaced by a salted hash unless
  the community turned question text on. This sink drops the text again unless
  it is told the same thing, and re-runs the redaction, because this is the
  last point before the record leaves the community's own disk and a mistake
  upstream would otherwise become a mistake in someone else's datacenter.
* **Retention is reported, not claimed.** Cloud Logging enforces retention on
  the log bucket, which this process cannot set, so every entry carries the
  community's configured ``log_retention_days`` and the status endpoint prints
  the exact gcloud command that makes the bucket match it. Promising a
  retention policy the code does not enforce would be worse than saying so.
* **Emitting never raises.** A logging failure that took down an answer would
  invert the priority: the answer is the service, the log is the record of it.

google-cloud-logging is an optional import and is not in ``requirements.txt``.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Dict, Optional

from cloud import CloudUnavailable

CLOUD_LOGGING_ENV = "COMMUNITY_CLOUD_LOGGING"
LOG_NAME_ENV = "COMMUNITY_CLOUD_LOG_NAME"
DEFAULT_LOG_NAME = "community-ai-requests"

INSTALL_REMEDY = (
    "Install it with: pip install google-cloud-logging  (or unset "
    f"{CLOUD_LOGGING_ENV} to keep request logs in JSONL on disk)."
)

# Fields that are operational metadata and may always be written. Anything not
# in this list is dropped rather than forwarded, so a field added upstream
# cannot silently start leaving the community.
OPERATIONAL_FIELDS = (
    "ts", "endpoint", "client_id", "client_name", "status", "latency_ms",
    "question_hash", "question_length", "model", "provider",
    "constitution_version", "constitution_hash", "constitution_ratified",
    "system_version", "sources_retrieved", "sources_used", "corpus_size",
    "dense_hits", "sparse_hits", "reranked", "retrieval_ms",
    "invalid_citations", "warnings", "error",
)


def cloud_logging_enabled() -> bool:
    return (os.getenv(CLOUD_LOGGING_ENV) or "").strip().lower() in ("1", "true", "yes", "on")


def log_name() -> str:
    return (os.getenv(LOG_NAME_ENV) or "").strip() or DEFAULT_LOG_NAME


def retention_command(days: int, name: str = "") -> str:
    """The gcloud command that makes the log bucket match the community's policy."""
    if not days or days <= 0:
        return ("Retention is set to keep records indefinitely; Cloud Logging's "
                "default bucket keeps them for 30 days. Create a bucket with "
                "--retention-days and route this log to it.")
    return (f"gcloud logging buckets update _Default --location=global "
            f"--retention-days={int(days)}   # log: {name or log_name()}")


def scrub(record: Dict[str, Any], include_question_text: bool = False) -> Dict[str, Any]:
    """Keep the operational metadata, drop anything else.

    An allow-list rather than a deny-list: the failure mode of a deny-list is
    that a new field is published by default, and this is the one place in the
    system where that mistake is unrecoverable.
    """
    entry = {field: record[field] for field in OPERATIONAL_FIELDS if field in record}
    if include_question_text and record.get("question"):
        try:
            from api.audit import redact
            entry["question"] = redact(str(record["question"]))[:2000]
        except Exception:                          # pragma: no cover - defensive
            pass
    return entry


class CloudLoggingSink:
    """A mirror of the request log in Cloud Logging."""

    backend = "cloud-logging"

    def __init__(self, name: str = "", gcp_project: str = "", client: Any = None,
                 logger: Any = None) -> None:
        self.name = name or log_name()
        self.gcp_project = gcp_project or _gcp_project()
        self._client = client
        self._logger = logger
        self._lock = threading.Lock()
        self.entries_written = 0
        self.healthy = True
        self.last_error: Optional[str] = None

    @property
    def logger(self) -> Any:
        if self._logger is None:
            with self._lock:
                if self._logger is None:
                    self._logger = self._build_logger()
        return self._logger

    def _build_logger(self) -> Any:
        try:
            import google.cloud.logging as cloud_logging
        except ImportError as exc:
            raise CloudUnavailable(
                f"{CLOUD_LOGGING_ENV} is set but the 'google-cloud-logging' "
                f"package is not installed.",
                remedy=INSTALL_REMEDY,
            ) from exc
        try:
            client = self._client or cloud_logging.Client(
                **({"project": self.gcp_project} if self.gcp_project else {})
            )
            self._client = client
            return client.logger(self.name)
        except Exception as exc:
            raise CloudUnavailable(
                f"Could not open a Cloud Logging client: {type(exc).__name__}: {exc}",
                remedy=("Give the service account the Logs Writer role, or run "
                        "`gcloud auth application-default login` locally."),
            ) from exc

    def emit(self, project_id: str, record: Dict[str, Any], *,
             include_question_text: bool = False,
             retention_days: Optional[int] = None) -> bool:
        """Write one record. Returns whether it was written; never raises."""
        entry = scrub(record, include_question_text)
        entry["project_id"] = project_id
        if retention_days is not None:
            # The community's policy, carried with the record it applies to, so
            # a bucket that does not match it can be spotted from an entry.
            entry["retention_days"] = int(retention_days)

        try:
            self.logger.log_struct(
                entry,
                severity="ERROR" if record.get("status") not in (None, "ok") else "INFO",
                labels={"project_id": project_id,
                        "endpoint": str(record.get("endpoint", "")),
                        "component": "community-ai-gateway"},
            )
        except CloudUnavailable as exc:
            self._note_failure(f"{exc.message} {exc.remedy}".strip())
            return False
        except Exception as exc:
            self._note_failure(f"{type(exc).__name__}: {exc}")
            return False

        with self._lock:
            self.entries_written += 1
            self.healthy = True
        return True

    def _note_failure(self, detail: str) -> None:
        with self._lock:
            first = self.healthy
            self.healthy = False
            self.last_error = detail
        if first:
            print(f"[cloud.logging_sink] Request records are not reaching Cloud "
                  f"Logging: {detail} The local JSONL log is unaffected.")

    def status(self, retention_days: Optional[int] = None) -> Dict[str, Any]:
        return {
            "backend": self.backend if self.healthy else "jsonl",
            "configured": True,
            "active": bool(self.healthy),
            "log_name": self.name,
            "gcp_project": self.gcp_project,
            "entries_written": self.entries_written,
            "local_jsonl": True,
            "detail": (
                "Request records are written to JSONL and mirrored to Cloud "
                "Logging. Question text is still excluded unless the project "
                "enables it."
                if self.healthy else
                "Cloud Logging is not accepting records; they are still on "
                "local disk, which Cloud Run does not keep."
            ),
            "retention": retention_command(retention_days or 0, self.name),
            "last_error": self.last_error,
            "remedy": None if self.healthy else (
                "Check the Logs Writer role on the service account."),
        }


_sink: Optional[CloudLoggingSink] = None
_sink_lock = threading.Lock()


def get_sink() -> Optional[CloudLoggingSink]:
    """The process-wide sink, or None when the JSONL log is the whole story."""
    global _sink
    if not cloud_logging_enabled():
        return None
    if _sink is None:
        with _sink_lock:
            if _sink is None:
                _sink = CloudLoggingSink()
    return _sink


def reset_sink() -> None:
    """Forget the cached sink. For tests and for a configuration reload."""
    global _sink
    with _sink_lock:
        _sink = None


def logging_status(retention_days: Optional[int] = None) -> Dict[str, Any]:
    """Where request records are going, for ``/api/admin/cloud-status``."""
    if not cloud_logging_enabled():
        return {
            "backend": "jsonl",
            "configured": False,
            "active": True,
            "local_jsonl": True,
            "detail": ("Request records are JSON Lines under data/<project>/logs, "
                       "pruned on the project's retention setting."),
            "remedy": None,
        }

    sink = get_sink()
    if sink is None:                               # pragma: no cover - defensive
        return {"backend": "jsonl", "configured": True, "active": False,
                "detail": "Cloud Logging is configured but no sink was built.",
                "remedy": INSTALL_REMEDY}

    status = sink.status(retention_days)
    try:
        import google.cloud.logging  # noqa: F401
    except ImportError:
        status["active"] = False
        status["backend"] = "jsonl"
        status["detail"] = (
            f"{CLOUD_LOGGING_ENV} is set but the 'google-cloud-logging' package "
            f"is not installed, so records are only on local disk."
        )
        status["remedy"] = INSTALL_REMEDY
    return status


def _gcp_project() -> str:
    for name in ("COMMUNITY_GCP_PROJECT", "GOOGLE_CLOUD_PROJECT", "GCP_PROJECT"):
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return ""


if __name__ == "__main__":
    record = {
        "ts": "2026-09-20T10:00:00", "endpoint": "/community/ask",
        "client_id": "c1", "status": "ok", "latency_ms": 812.4,
        "question_hash": "8f14e45fceea167a", "question_length": 42,
        "question": "Call me at 617-555-0123 about Article 8.4",
        "model": "gemma-4-26b-a4b", "sources_used": 3,
        "resident_name": "should never be forwarded",
    }
    print("default:", sorted(scrub(record)))
    print("question kept out by default:", "question" not in scrub(record))
    with_text = scrub(record, include_question_text=True)
    print("with text, redacted:", with_text.get("question"))
    print("unknown fields dropped:", "resident_name" not in with_text)
    print("retention:", retention_command(30))
    print("status:", logging_status()["detail"])
