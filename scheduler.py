"""
Periodic archive sync.

"Dynamically scan and bring in new meetings" means nobody presses a button. A
public-access station posts a meeting the morning after it is held; the archive
should have it before a resident asks about it.

The scheduler runs an incremental sync per channel source on an interval. When
nothing is new, a run costs one listing request and writes nothing, so a short
interval is cheap. When a meeting appeared overnight, the run pulls its
transcript and indexes it.

APScheduler is already a dependency. This is in-process, which suits one server
running one community. A multi-instance deployment needs one leader or an
external trigger, or every instance will ingest the same meeting; the roadmap
covers that under Cloud Scheduler.
"""

from __future__ import annotations

import asyncio
import os
import threading
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

SYNC_INTERVAL_MINUTES = int(os.getenv("COMMUNITY_SYNC_INTERVAL_MINUTES", "360"))
SYNC_ENABLED = os.getenv("COMMUNITY_SYNC_ENABLED", "true").lower() in ("1", "true", "yes")

_scheduler = None
_lock = threading.Lock()

# What the last run of each project did, for the admin console.
_last_runs: Dict[str, Dict[str, Any]] = {}


def last_runs() -> Dict[str, Dict[str, Any]]:
    return dict(_last_runs)


def _run_project_sync(project_id: str, load_project: Callable, ingest: Callable,
                      job_factory: Callable) -> Dict[str, Any]:
    """Sync every channel source of one project. Returns a run record."""
    from models import DataSourceType

    record: Dict[str, Any] = {
        "project_id": project_id,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "sources": [],
        "error": None,
    }

    try:
        project = load_project(project_id)
        if not project:
            record["error"] = "project not found"
            return record

        channels = [s for s in project.data_sources
                    if s.type == DataSourceType.YOUTUBE_CHANNEL and s.enabled]
        if not channels:
            record["skipped"] = "no enabled channel sources"
            return record

        for source in channels:
            job = job_factory(project_id, source.id)
            try:
                asyncio.run(ingest(job, project))
                record["sources"].append({
                    "source": source.name,
                    "status": job.status,
                    "new_items": job.total_items,
                    "error": job.error,
                })
            except Exception as exc:
                record["sources"].append({
                    "source": source.name, "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                })
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"

    record["finished_at"] = datetime.now().isoformat(timespec="seconds")
    _last_runs[project_id] = record
    return record


def sync_all_projects(list_project_ids: Callable, load_project: Callable,
                      ingest: Callable, job_factory: Callable) -> List[Dict[str, Any]]:
    """One pass over every project on disk."""
    runs = []
    for project_id in list_project_ids():
        runs.append(_run_project_sync(project_id, load_project, ingest, job_factory))
    return runs


def start(list_project_ids: Callable, load_project: Callable,
          ingest: Callable, interval_minutes: Optional[int] = None) -> Optional[Any]:
    """Start the background scheduler. Returns it, or None when disabled."""
    global _scheduler

    if not SYNC_ENABLED:
        print("Archive sync scheduler disabled (COMMUNITY_SYNC_ENABLED=false)")
        return None

    interval = interval_minutes or SYNC_INTERVAL_MINUTES
    if interval <= 0:
        return None

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        print("APScheduler is not installed; archive sync will not run "
              "automatically. Install it, or call /api/projects/{id}/sync-all "
              "from cron.")
        return None

    from models import DataIngestionJob

    def job_factory(project_id: str, source_id: str) -> Any:
        return DataIngestionJob(job_id=str(uuid.uuid4()), project_id=project_id,
                                source_id=source_id, status="pending")

    def tick() -> None:
        sync_all_projects(list_project_ids, load_project, ingest, job_factory)

    with _lock:
        if _scheduler is not None:
            return _scheduler
        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(
            tick,
            "interval",
            minutes=interval,
            id="community_archive_sync",
            max_instances=1,        # never start a second pass over the same archive
            coalesce=True,          # a missed run is caught up once, not N times
            misfire_grace_time=3600,
        )
        scheduler.start()
        _scheduler = scheduler

    print(f"Archive sync scheduler started: every {interval} minutes")
    return _scheduler


def shutdown() -> None:
    global _scheduler
    with _lock:
        if _scheduler is not None:
            try:
                _scheduler.shutdown(wait=False)
            except Exception:
                pass
            _scheduler = None
