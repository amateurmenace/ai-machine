"""
Privacy-aware request logging.

Section 13 lists "privacy-aware logging" as a gateway responsibility, and
``constitution/governance.md`` commits to a specific split: aggregate statistics
about the system are public, and the questions residents ask are not.

So the default record contains everything needed to debug retrieval and report
usage — which sources were retrieved, whether they were used, how long it took,
which constitution version applied — and, in place of the question, a salted
hash of it. The hash makes repeat questions countable without making any of them
readable.

Turning question text on is a deliberate, per-project decision
(``log_question_text``), and the setup guide says to write it in the published
privacy policy before doing so.

Logs are JSON Lines under ``data/<project_id>/logs/requests-YYYY-MM-DD.jsonl``,
pruned by ``log_retention_days``. That file is also what ``usage_summary``
reads, so it stays the source of truth for the public statistics even when
``COMMUNITY_CLOUD_LOGGING`` mirrors the same records into Cloud Logging for an
instance whose disk does not survive the night. See ``cloud/logging_sink.py``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

_write_lock = threading.Lock()

# A per-installation salt. Without it, hashed questions are trivially recovered
# by hashing a dictionary of likely questions and comparing.
_SALT_FILENAME = ".question_salt"


def _log_dir(project_id: str, data_root: str = "./data") -> Path:
    return Path(data_root) / project_id / "logs"


def _get_salt(project_id: str, data_root: str = "./data") -> str:
    path = _log_dir(project_id, data_root) / _SALT_FILENAME
    try:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
        path.parent.mkdir(parents=True, exist_ok=True)
        salt = os.urandom(16).hex()
        path.write_text(salt, encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return salt
    except OSError:
        # If the salt cannot be persisted, fall back to a process-lifetime one.
        # Counts will not survive a restart, which is better than a weak hash.
        return _PROCESS_SALT


_PROCESS_SALT = os.urandom(16).hex()


def hash_question(question: str, project_id: str, data_root: str = "./data") -> str:
    salt = _get_salt(project_id, data_root)
    return hashlib.sha256(f"{salt}:{question.strip().lower()}".encode("utf-8")).hexdigest()[:16]


# Patterns redacted from any text that does get stored. Not a guarantee, a
# reduction: a resident who types their phone number into a question should not
# have it sitting in a log file because the operator enabled question logging.
_REDACTIONS = [
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "[email]"),
    (re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[phone]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[ssn]"),
    (re.compile(r"\b(?:\d[ -]?){13,16}\b"), "[card]"),
]


def redact(text: str) -> str:
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def log_request(
    project_id: str,
    *,
    endpoint: str,
    client_id: str = "",
    client_name: str = "",
    question: str = "",
    log_question_text: bool = False,
    provenance: Optional[Dict[str, Any]] = None,
    status: str = "ok",
    error: Optional[str] = None,
    latency_ms: Optional[float] = None,
    data_root: str = "./data",
    retention_days: Optional[int] = None,
    enabled: bool = True,
) -> Optional[Dict[str, Any]]:
    """Append one request record. Returns the record, or None if disabled."""
    if not enabled:
        return None

    provenance = provenance or {}
    retrieval = provenance.get("retrieval", {}) or {}
    citation_check = provenance.get("citation_check", {}) or {}

    record: Dict[str, Any] = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "endpoint": endpoint,
        "client_id": client_id,
        "client_name": client_name,
        "status": status,
        "latency_ms": round(latency_ms, 1) if latency_ms is not None else None,
        # Identify the question without storing it.
        "question_hash": hash_question(question, project_id, data_root) if question else "",
        "question_length": len(question or ""),
        # Operational facts, which governance.md makes public in aggregate.
        "model": provenance.get("model"),
        "provider": provenance.get("provider"),
        "constitution_version": provenance.get("constitution_version"),
        # Which exact rules governed this answer. A version string is a label;
        # this is the claim an auditor can check against the ledger.
        "constitution_hash": provenance.get("constitution_hash"),
        "constitution_ratified": provenance.get("constitution_ratified"),
        "system_version": provenance.get("system_version"),
        "sources_retrieved": provenance.get("sources_retrieved"),
        "sources_used": provenance.get("sources_used"),
        "corpus_size": provenance.get("corpus_size"),
        "dense_hits": retrieval.get("dense_hits"),
        "sparse_hits": retrieval.get("sparse_hits"),
        "reranked": retrieval.get("reranked"),
        "retrieval_ms": retrieval.get("elapsed_ms"),
        "invalid_citations": len(citation_check.get("invalid_numbers") or []),
        "warnings": provenance.get("warnings") or [],
    }

    if error:
        record["error"] = str(error)[:500]

    if log_question_text and question:
        record["question"] = redact(question)[:2000]

    path = _log_dir(project_id, data_root) / f"requests-{datetime.now():%Y-%m-%d}.jsonl"
    try:
        with _write_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, default=str) + "\n")
    except OSError:
        # Logging must never take down an answer.
        _mirror_to_cloud(project_id, record, log_question_text, retention_days)
        return record

    _mirror_to_cloud(project_id, record, log_question_text, retention_days)
    return record


def _mirror_to_cloud(project_id: str, record: Dict[str, Any],
                     log_question_text: bool,
                     retention_days: Optional[int]) -> None:
    """Copy the record to Cloud Logging, if a community configured one.

    Imported here rather than at module scope so this module keeps working with
    no ``cloud`` package present at all, and wrapped because a log that cannot
    be written is not a reason a resident's question fails.
    """
    try:
        from cloud.logging_sink import get_sink

        sink = get_sink()
        if sink is None:
            return
        sink.emit(project_id, record, include_question_text=log_question_text,
                  retention_days=retention_days)
    except Exception:
        pass


def prune_logs(project_id: str, retention_days: int, data_root: str = "./data") -> int:
    """Delete request logs older than the retention window. Returns count."""
    if retention_days <= 0:
        return 0
    directory = _log_dir(project_id, data_root)
    if not directory.is_dir():
        return 0

    cutoff = datetime.now().date() - timedelta(days=retention_days)
    removed = 0
    for entry in directory.glob("requests-*.jsonl"):
        stamp = entry.stem.replace("requests-", "")
        try:
            file_date = datetime.strptime(stamp, "%Y-%m-%d").date()
        except ValueError:
            continue
        if file_date < cutoff:
            try:
                entry.unlink()
                removed += 1
            except OSError:
                pass
    return removed


def usage_summary(project_id: str, days: int = 30,
                  data_root: str = "./data") -> Dict[str, Any]:
    """Aggregate statistics, which governance.md makes public.

    Contains no question text and no per-resident detail.
    """
    directory = _log_dir(project_id, data_root)
    summary: Dict[str, Any] = {
        "days": days,
        "requests": 0,
        "errors": 0,
        "by_endpoint": {},
        "by_client": {},
        "answers_with_sources": 0,
        "answers_without_sources": 0,
        "invalid_citation_events": 0,
        "avg_latency_ms": None,
        "avg_sources_retrieved": None,
        "unique_questions": 0,
    }
    if not directory.is_dir():
        return summary

    cutoff = datetime.now().date() - timedelta(days=days)
    latencies: List[float] = []
    retrieved: List[int] = []
    question_hashes = set()

    for entry in sorted(directory.glob("requests-*.jsonl")):
        stamp = entry.stem.replace("requests-", "")
        try:
            if datetime.strptime(stamp, "%Y-%m-%d").date() < cutoff:
                continue
        except ValueError:
            continue

        try:
            lines = entry.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue

        for line in lines:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            summary["requests"] += 1
            if record.get("status") != "ok":
                summary["errors"] += 1

            endpoint = record.get("endpoint", "unknown")
            summary["by_endpoint"][endpoint] = summary["by_endpoint"].get(endpoint, 0) + 1

            client = record.get("client_name") or record.get("client_id") or "unknown"
            summary["by_client"][client] = summary["by_client"].get(client, 0) + 1

            used = record.get("sources_used")
            if used is not None:
                if used > 0:
                    summary["answers_with_sources"] += 1
                else:
                    summary["answers_without_sources"] += 1

            summary["invalid_citation_events"] += int(record.get("invalid_citations") or 0)

            if record.get("latency_ms") is not None:
                latencies.append(float(record["latency_ms"]))
            if record.get("sources_retrieved") is not None:
                retrieved.append(int(record["sources_retrieved"]))
            if record.get("question_hash"):
                question_hashes.add(record["question_hash"])

    if latencies:
        summary["avg_latency_ms"] = round(sum(latencies) / len(latencies), 1)
    if retrieved:
        summary["avg_sources_retrieved"] = round(sum(retrieved) / len(retrieved), 2)
    summary["unique_questions"] = len(question_hashes)
    return summary


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        rec = log_request(
            "demo", endpoint="/community/ask", client_id="c1", client_name="Test App",
            question="Call me at 617-555-0123 or me@example.org about Article 8.4",
            log_question_text=True, data_root=tmp, latency_ms=812.4,
            provenance={"model": "gemma-4-26b-a4b", "sources_retrieved": 8,
                        "sources_used": 3, "constitution_version": "1.0"},
        )
        print("logged question text:", rec["question"])
        print("question hash:", rec["question_hash"])

        rec2 = log_request(
            "demo", endpoint="/community/ask", question="Same private question",
            log_question_text=False, data_root=tmp,
            provenance={"sources_retrieved": 2, "sources_used": 0},
        )
        print("without text, keys:", "question" in rec2)
        print("summary:", json.dumps(usage_summary("demo", data_root=tmp), indent=2)[:300])
