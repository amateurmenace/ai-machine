"""
Build a community's archive from a channel's back catalogue.

The web app can ingest a channel, and for the twelve meetings published since
the last sync that is the right tool. Five hundred meetings is a different
job, and doing it through an HTTP request fails for three reasons that have
nothing to do with the code being wrong:

* It takes hours. Requests do not.
* It accumulates every chunk in memory and writes once at the end, so an
  error at meeting 480 loses 479 meetings of work.
* Nothing tells you how it is going while it runs.

So this walks the channel oldest to newest, pulls one transcript at a time,
writes each meeting to the archive as soon as it has it, and records that it
did. Interrupt it and run it again and it picks up where it stopped. Run it
twice and the second run does nothing, which is the property that makes it
safe to put in cron.

    python3 -m scripts.backfill_archive --project brookline-ma --dry-run
    python3 -m scripts.backfill_archive --project brookline-ma --limit 500
    python3 -m scripts.backfill_archive --project brookline-ma --source bigtv

What it does not do is guess. A video whose title does not parse as a meeting
is skipped and counted, not ingested as "unknown body, unknown date"; a
meeting with captions disabled is recorded as a gap in the archive rather than
passed over silently. Both end up in the summary, because "we have 500
meetings" and "we have 500 meetings and 37 of them have no transcript" are
different claims and only one of them is true.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.youtube_channel import (  # noqa: E402
    DEFAULT_SCAN_LIMIT, VideoRecord, advance_cursor, load_state, plan_sync,
    save_state,
)
from knowledge.schemas import meeting_chunks  # noqa: E402

# Ingesting a thousand meetings should not hold a thousand meetings in memory.
# One meeting is a few hundred chunks, which is a sensible write.
WRITE_EVERY_MEETING = True

stop_requested = False


def request_stop(signum, frame) -> None:
    """Finish the meeting in flight, save state, and exit cleanly.

    A backfill killed mid-meeting is the one case where state and archive can
    disagree, so the signal is recorded rather than obeyed immediately.
    """
    global stop_requested
    if stop_requested:
        print("\nSecond interrupt. Stopping now; re-run to resume.")
        raise SystemExit(130)
    stop_requested = True
    print("\nInterrupt received. Finishing this meeting, then stopping. "
          "Re-run the same command to resume.")


@dataclass
class Tally:
    """What actually happened, in the terms the data card has to report."""

    ingested: int = 0
    passages: int = 0
    no_transcript: List[str] = field(default_factory=list)
    errors: List[Dict[str, str]] = field(default_factory=list)
    not_meetings: int = 0
    low_confidence: int = 0
    started_at: float = field(default_factory=time.time)

    @property
    def elapsed(self) -> float:
        return time.time() - self.started_at

    def summary(self) -> Dict[str, Any]:
        return {
            "meetings_ingested": self.ingested,
            "passages_written": self.passages,
            "meetings_without_transcripts": len(self.no_transcript),
            "meetings_that_errored": len(self.errors),
            "videos_not_classified_as_meetings": self.not_meetings,
            "videos_below_confidence_threshold": self.low_confidence,
            "elapsed_seconds": round(self.elapsed, 1),
        }


def load_project(project_id: str):
    """Read the project config without importing the web app."""
    from models import ProjectConfig

    path = Path("./data") / project_id / "config.json"
    if not path.exists():
        raise SystemExit(
            f"No project at {path}.\n"
            f"Create it first, either in the console or with:\n"
            f"  python3 -m scripts.bootstrap_community community.yaml")
    return ProjectConfig(**json.loads(path.read_text()))


def channel_sources(project, wanted: str = "") -> List[Any]:
    """The channel sources to walk. All of them unless one is named."""
    from models import DataSourceType

    sources = [s for s in (project.data_sources or [])
               if s.type == DataSourceType.YOUTUBE_CHANNEL]
    if wanted:
        sources = [s for s in sources if wanted in (s.id, s.name, s.url)]
        if not sources:
            raise SystemExit(f"No channel source matching {wanted!r} in this project.")
    if not sources:
        raise SystemExit(
            "This project has no YouTube channel sources.\n"
            "Add one in the console, or list the channel in community.yaml and run\n"
            "  python3 -m scripts.bootstrap_community community.yaml")
    return sources


def describe(video: VideoRecord) -> str:
    return (f"{video.meeting_date or '??????????'}  "
            f"{(video.body or '(unclassified)')[:24]:<24} {video.title[:46]}")


def estimate(done: int, total: int, elapsed: float) -> str:
    if not done:
        return ""
    remaining = (elapsed / done) * (total - done)
    if remaining < 90:
        return f"~{remaining:.0f}s left"
    if remaining < 5400:
        return f"~{remaining / 60:.0f}m left"
    return f"~{remaining / 3600:.1f}h left"


def backfill(project_id: str, source_name: str = "", limit: int = 1000,
             dry_run: bool = False, since: str = "", quiet: bool = False,
             snapshot_every: int = 0) -> Tally:
    project = load_project(project_id)
    tally = Tally()

    from collectors.youtube_collector import YouTubeCollector
    from stores import build_store, select_backend

    choice = select_backend(project)
    print(f"Archive:  {choice.backend} at {choice.location}")
    print(f"Project:  {project.project_id} ({project.municipality_name})")

    store = None if dry_run else build_store(project)
    collector = YouTubeCollector(api_key=os.getenv("YOUTUBE_API_KEY"))

    for source in channel_sources(project, source_name):
        meta = source.metadata or {}
        state = load_state(project.project_id, source.id, source.url)

        print(f"\nScanning {source.name} ({source.url})")
        plan = plan_sync(
            source.url,
            state,
            api_key=os.getenv("YOUTUBE_API_KEY"),
            limit=limit,
            incremental=False,          # backfill: the whole catalogue
            min_confidence=float(meta.get("min_confidence") or 0.0),
            meetings_only=bool(meta.get("meetings_only", True)),
            body_override=meta.get("body", ""),
        )
        if plan.error:
            print(f"  scan failed: {plan.error}")
            tally.errors.append({"source": source.name, "error": plan.error})
            continue

        videos = list(plan.new_videos)
        if since:
            videos = [v for v in videos if (v.meeting_date or "") >= since]
        # Oldest first, so an interrupted backfill leaves a contiguous archive
        # rather than a decade with holes in the middle.
        videos.sort(key=lambda v: (v.meeting_date or "", v.title))

        tally.not_meetings += len(plan.skipped_not_meetings)
        tally.low_confidence += len(plan.skipped_low_confidence)

        print(f"  {len(videos)} meeting(s) to ingest, "
              f"{len(plan.skipped_not_meetings)} not classified as meetings, "
              f"{len(state.ingested_video_ids)} already in the archive")

        if dry_run:
            for video in videos[:40]:
                print(f"    {describe(video)}")
            if len(videos) > 40:
                print(f"    ... and {len(videos) - 40} more")
            continue

        for index, video in enumerate(videos, start=1):
            if stop_requested:
                break

            prefix = f"  [{index}/{len(videos)}]"
            try:
                result = collector.collect_video(video.url)
            except Exception as exc:
                tally.errors.append({"video_id": video.video_id,
                                     "error": f"{type(exc).__name__}: {exc}"})
                state.mark_skipped(video.video_id, "transcript error")
                print(f"{prefix} ERROR  {describe(video)}  ({type(exc).__name__})")
                save_state(project.project_id, state)
                continue

            if not result or not result.get("transcript"):
                tally.no_transcript.append(video.video_id)
                state.errors.append({"video_id": video.video_id,
                                     "error": "no transcript available"})
                state.mark_skipped(video.video_id, "no transcript")
                print(f"{prefix} NO CC  {describe(video)}")
                save_state(project.project_id, state)
                continue

            documents = []
            for chunk in meeting_chunks(
                result["transcript"]["segments"],
                community=project.municipality_name,
                body=video.body or meta.get("body", ""),
                meeting_date=video.meeting_date or video.published_at,
                video_url=video.url,
                title=video.title,
                source=source.name,
                collection_method="youtube_channel_backfill",
            ):
                payload = chunk.to_payload()
                payload["video_id"] = video.video_id
                payload["date_source"] = video.date_source
                documents.append({"text": chunk.text, "metadata": payload})

            if not documents:
                tally.no_transcript.append(video.video_id)
                state.mark_skipped(video.video_id, "transcript produced no passages")
                print(f"{prefix} EMPTY  {describe(video)}")
                save_state(project.project_id, state)
                continue

            store.add_documents_batch(documents)
            state.mark_ingested(video.video_id)
            save_state(project.project_id, state)

            tally.ingested += 1
            tally.passages += len(documents)
            if not quiet:
                print(f"{prefix} ok     {describe(video)}  "
                      f"{len(documents)} passages  "
                      f"{estimate(index, len(videos), tally.elapsed)}")

            if snapshot_every and tally.ingested % snapshot_every == 0:
                from stores import backup as backup_module

                snapshot = backup_module.create(choice.path, project_id=project.project_id)
                print(f"         snapshot: {Path(snapshot.path).name} "
                      f"({snapshot.document_count:,} passages)")

        for video in plan.skipped_not_meetings + plan.skipped_low_confidence:
            state.mark_skipped(video.video_id, "not classified as a meeting")
        advance_cursor(state, videos)
        save_state(project.project_id, state)

        if stop_requested:
            break

    return tally


def report(tally: Tally, project_id: str, dry_run: bool) -> None:
    print("\n" + "=" * 62)
    if dry_run:
        print("Dry run. Nothing was written.")
        return

    summary = tally.summary()
    print(f"Backfill finished in {summary['elapsed_seconds'] / 60:.1f} minutes")
    print(f"  {summary['meetings_ingested']:,} meetings ingested")
    print(f"  {summary['passages_written']:,} passages written")
    if summary["meetings_without_transcripts"]:
        print(f"  {summary['meetings_without_transcripts']} meeting(s) had no captions. "
              f"These are real gaps in the archive, not missing work; the data card "
              f"should say so.")
    if summary["meetings_that_errored"]:
        print(f"  {summary['meetings_that_errored']} meeting(s) errored. "
              f"Re-run this command to retry only those.")
    if summary["videos_not_classified_as_meetings"]:
        print(f"  {summary['videos_not_classified_as_meetings']} video(s) were not "
              f"classified as meetings and were left alone.")

    path = Path("./data") / project_id / "backfill-report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**summary,
               "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "meetings_without_transcripts": tally.no_transcript,
               "errors": tally.errors[:100]}
    path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\nReport: {path}")
    print("Next:   python3 -m stores.backup create --project " + project_id)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m scripts.backfill_archive",
        description="Walk a channel's back catalogue into the archive, resumably.")
    parser.add_argument("--project", required=True, help="project id")
    parser.add_argument("--source", default="",
                        help="one channel source (default: every channel source)")
    parser.add_argument("--limit", type=int, default=1000,
                        help="how many videos to scan (default 1000)")
    parser.add_argument("--since", default="",
                        help="only meetings on or after this date, YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true",
                        help="list what would be ingested and write nothing")
    parser.add_argument("--quiet", action="store_true", help="one line per error only")
    parser.add_argument("--snapshot-every", type=int, default=0,
                        help="take a backup every N meetings, for long runs")
    args = parser.parse_args(argv)

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    tally = backfill(args.project, source_name=args.source, limit=args.limit,
                     dry_run=args.dry_run, since=args.since, quiet=args.quiet,
                     snapshot_every=args.snapshot_every)
    report(tally, args.project, args.dry_run)
    return 0 if not tally.errors else 1


if __name__ == "__main__":
    sys.exit(main())
