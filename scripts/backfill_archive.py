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
import gzip
import json
import os
import random
import re
import signal
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.meeting_titles import community_bodies  # noqa: E402
from collectors.youtube_channel import (  # noqa: E402
    DEFAULT_SCAN_LIMIT, NO_TRANSCRIPT, NOT_A_MEETING, VideoRecord, advance_cursor,
    captions_may_be_pending, listing_path, load_state, plan_sync, save_state,
)
from knowledge.schemas import meeting_chunks  # noqa: E402

# Ingesting a thousand meetings should not hold a thousand meetings in memory.
# One meeting is a few hundred chunks, which is a sensible write.
WRITE_EVERY_MEETING = True

# One failed fetch is a bad video. This many in a row is YouTube refusing the
# machine, and carrying on would only add to the reasons it has for doing so.
MAX_FAILURES_IN_A_ROW = 5

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
    # Recent meetings YouTube has not captioned yet. Not gaps, and not marked.
    pending: List[str] = field(default_factory=list)
    # No captions were seen, but over a connection that was failing around
    # them. Not gaps, not marked, and looked at again by the next run.
    unsure: List[str] = field(default_factory=list)
    not_meetings: int = 0
    low_confidence: int = 0
    held_same_day: int = 0
    stopped_early: str = ""
    # Across every run so far, read back from sync state. A backfill that was
    # interrupted twice must not report only the gaps its last run found.
    archive_meetings: int = 0
    archive_gaps: List[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    @property
    def elapsed(self) -> float:
        return time.time() - self.started_at

    def summary(self) -> Dict[str, Any]:
        return {
            "meetings_ingested": self.ingested,
            "passages_written": self.passages,
            "meetings_without_transcripts": len(self.archive_gaps or self.no_transcript),
            "meetings_without_transcripts_found_this_run": len(self.no_transcript),
            "meetings_in_the_archive": self.archive_meetings,
            "meetings_that_errored": len(self.errors),
            "meetings_waiting_for_captions": len(self.pending),
            "meetings_with_an_untrusted_no_captions_verdict": len(self.unsure),
            "meetings_held_back_same_board_same_day": self.held_same_day,
            "stopped_early": self.stopped_early,
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


# Words that make a title worth a second look when no board was recognized.
_CIVIC_WORDS = re.compile(
    r"\b(meeting|hearing|committee|subcommittee|commission|board|council|authority|"
    r"task force|working group|trustees|caucus)\b", re.I)


def title_shape(title: str) -> str:
    """A title with its date and numbering taken out, so a series groups as one."""
    shape = re.sub(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sept?|oct|nov|dec)[a-z]*\b", " ",
                   (title or "").lower())
    shape = re.sub(r"\b(pt|part|night|day)\b\.?", " ", shape)
    shape = re.sub(r"[^a-z&' ]+", " ", shape)
    return re.sub(r"\s+", " ", shape).strip()


def describe_plan(plan, videos: List[VideoRecord], full: bool = False) -> None:
    """What a dry run is for: everything worth reading before hours of work.

    The count of meetings is the least useful number here. A channel's worth of
    subcommittees filed under no board, or a candidate forum filed under the
    Select Board, looks exactly like success in a total, and is only visible
    when what was kept and what was left out are both laid out to be read.
    """
    def table(counter: Counter, top: int = 0) -> None:
        for name, count in (counter.most_common(top) if top else counter.most_common()):
            print(f"    {count:>5}  {name[:70]}")

    print("\n  By board")
    undated = Counter((v.body or "(no board)") for v in videos if not v.meeting_date)
    for body, count in Counter((v.body or "(no board)") for v in videos).most_common():
        note = f"   {undated[body]} undated" if undated[body] else ""
        print(f"    {count:>5}  {body}{note}")

    print("\n  By year")
    years = Counter((v.meeting_date or "none")[:4] for v in videos)
    print("    " + "  ".join(f"{year}:{count}" for year, count in sorted(years.items())))

    skipped = plan.skipped_not_meetings + plan.skipped_low_confidence
    about = [v for v in skipped if any("programme about one" in n for n in v.notes)]
    unknown = [v for v in skipped if v not in about and not v.body
               and _CIVIC_WORDS.search(v.title or "")]
    weak = [v for v in plan.skipped_low_confidence if v.body and v not in about]
    print(f"\n  Left out: {len(skipped):,}")
    print(f"    {len(about):>5}  about a board rather than a meeting of it "
          f"(candidate forums, recaps, interviews)")
    print(f"    {len(weak):>5}  a board is named, but there is no date and no word like 'meeting'")
    print(f"    {len(unknown):>5}  read like civic meetings, but no board was recognized")
    print(f"    {len(skipped) - len(about) - len(weak) - len(unknown):>5}  everything else "
          f"on the channel")

    if unknown:
        print("\n  No board recognized. If one of these belongs in the record, add it to the\n"
              "  source's `bodies` and run this again:")
        table(Counter(title_shape(v.title) for v in unknown), top=0 if full else 30)
    if weak and full:
        print("\n  A board is named, but nothing says it is a meeting:")
        for video in weak:
            print(f"    {describe(video)}")
    if about and full:
        print("\n  About a board, not a meeting of it:")
        for video in about:
            print(f"    {describe(video)}")

    same_day: Dict[Any, List[VideoRecord]] = {}
    for video in videos:
        if video.body and video.meeting_date:
            same_day.setdefault((video.meeting_date, video.body), []).append(video)
    same_day = {key: group for key, group in same_day.items() if len(group) > 1}
    if same_day:
        print(f"\n  {len(same_day)} day(s) have more than one video for the same board. Some are a\n"
              f"  meeting in two parts, and some are the same meeting twice, which would put\n"
              f"  every passage in the archive twice:")
        for (day, body), group in sorted(same_day.items(), reverse=True)[:None if full else 8]:
            lengths = ", ".join(f"{(v.duration_seconds or 0) // 60}m" for v in group)
            print(f"    {day}  {body[:30]:<30} {len(group)} videos ({lengths})")

    print(f"\n  The meetings, oldest first{'' if full else ' (--full lists all of them)'}:")
    for video in videos if full else videos[:40]:
        print(f"    {describe(video)}")
    if not full and len(videos) > 40:
        print(f"    ... and {len(videos) - 40} more")


def keep_captions(project_id: str, video: VideoRecord, transcript: Dict[str, Any]) -> None:
    """Keep what YouTube sent, as it sent it, beside the archive.

    The archive holds passages, and a passage is a decision about where to cut.
    When that decision changes (a better chunker, speaker identification, a
    different passage length) the alternative to this file is asking YouTube
    for every meeting's captions again, and YouTube's patience is the scarcest
    thing in this whole process. A recording can also be taken down. About
    forty kilobytes a meeting.
    """
    captions = transcript.get("captions")
    if not captions:
        return
    path = Path("./data") / project_id / "captions" / f"{video.video_id}.json.gz"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump({
                "video_id": video.video_id, "url": video.url, "title": video.title,
                "body": video.body, "meeting_date": video.meeting_date,
                "method": transcript.get("method", ""),
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "captions": captions,
            }, handle)
    except OSError:
        pass        # a cache: losing it costs a re-fetch, never a meeting


def split_same_day(videos: List[VideoRecord]):
    """Separate the meetings that are alone on their board's day from the rest.

    Two videos for one board on one day are sometimes a meeting in two parts
    and sometimes the same meeting twice, once as the live stream and once as
    the edited upload. The first needs both and the second wants one, and a
    title cannot tell them apart. Returns ``(alone, shared)``.
    """
    days: Dict[Any, int] = Counter(
        (v.meeting_date, (v.body or "").lower()) for v in videos if v.meeting_date)
    alone, shared = [], []
    for video in videos:
        crowded = video.meeting_date and days[(video.meeting_date, (video.body or "").lower())] > 1
        (shared if crowded else alone).append(video)
    return alone, shared


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
             snapshot_every: int = 0, full: bool = False, delay: float = 0.0,
             boards: Optional[List[str]] = None, hold_same_day: bool = False,
             max_meetings: int = 0, rescan: bool = False) -> Tally:
    project = load_project(project_id)
    tally = Tally()

    from collectors.youtube_collector import (
        TranscriptBlocked, TranscriptFetchFailed, TranscriptUnavailable, YouTubeCollector,
    )
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
            bodies=community_bodies(meta.get("bodies")),
            body_override=meta.get("body", ""),
            listing_cache=listing_path(project.project_id, source.id),
            rescan=rescan,
        )
        if getattr(plan, "listing_was_cached", False):
            print("  (using the channel listing kept from an earlier scan; --rescan lists it again)")
        if plan.error:
            print(f"  scan failed: {plan.error}")
            tally.errors.append({"source": source.name, "error": plan.error})
            continue

        videos = list(plan.new_videos)
        if since:
            videos = [v for v in videos if (v.meeting_date or "") >= since]
        if boards:
            # A pass over some boards leaves the others exactly as it found
            # them: not ingested, and not marked, so the next pass has them.
            wanted = {board.lower() for board in boards}
            videos = [v for v in videos if (v.body or "").lower() in wanted]
        held: List[VideoRecord] = []
        if hold_same_day:
            videos, held = split_same_day(videos)
        # Oldest first, so an interrupted backfill leaves a contiguous archive
        # rather than a decade with holes in the middle.
        videos.sort(key=lambda v: (v.meeting_date or "", v.title))

        tally.not_meetings += len(plan.skipped_not_meetings)
        tally.low_confidence += len(plan.skipped_low_confidence)
        tally.held_same_day += len(held)

        print(f"  {plan.scanned:,} video(s) on the channel, {len(videos):,} meeting(s) to "
              f"ingest, {len(plan.skipped_not_meetings) + len(plan.skipped_low_confidence):,} "
              f"left out, {len(state.ingested_video_ids)} already in the archive")
        if held:
            print(f"  {len(held)} held back: they share a board and a day with another video, "
                  f"and nobody has said yet which are duplicates. Not marked; a run without "
                  f"--hold-same-day takes them.")

        if dry_run:
            describe_plan(plan, videos, full=full)
            continue

        handled: List[VideoRecord] = []
        failures_in_a_row = 0
        # A "no captions" verdict is only as good as the connection it was
        # reached over. While YouTube is turning a machine away it will also
        # serve a video's page with the caption tracks simply left out, and
        # every reader sees the same page, so two of them agreeing proves
        # nothing. A verdict therefore waits here until the fetch after it
        # succeeds, and is dropped, unrecorded, if what follows is a failure.
        unconfirmed: List[VideoRecord] = []
        last_fetch_was_healthy = False

        def confirm_gaps() -> None:
            for gap in unconfirmed:
                tally.no_transcript.append(gap.video_id)
                state.errors.append({"video_id": gap.video_id,
                                     "error": "no transcript available"})
                state.mark_skipped(gap.video_id, NO_TRANSCRIPT)
                handled.append(gap)
            if unconfirmed:
                save_state(project.project_id, state)
            del unconfirmed[:]

        for index, video in enumerate(videos, start=1):
            if stop_requested:
                break
            if max_meetings and tally.ingested >= max_meetings:
                print(f"\n  {max_meetings} meetings this run, as asked. "
                      f"Run the same command for the next {max_meetings}.")
                break
            if index > 1 and delay:
                # One town's archive is not worth a rate limit. Uneven, because
                # a request every N seconds exactly is what a script looks like.
                time.sleep(delay * random.uniform(0.6, 1.4))

            prefix = f"  [{index}/{len(videos)}]"
            try:
                result = collector.collect_video(video.url, strict=True)
                if not result or not result.get("transcript"):
                    # strict raises when there are no captions, so an empty
                    # answer is a fault in the fetching, not a fact about the
                    # meeting, and it is filed with the faults.
                    raise TranscriptFetchFailed("the collector returned nothing")
            except TranscriptUnavailable:
                failures_in_a_row = 0
                if captions_may_be_pending(video):
                    # Not marked, so the next run looks again.
                    tally.pending.append(video.video_id)
                    print(f"{prefix} WAIT   {describe(video)}  (no captions yet; it is recent)")
                elif last_fetch_was_healthy or unconfirmed:
                    unconfirmed.append(video)
                    print(f"{prefix} NO CC? {describe(video)}  (counts if the next fetch works)")
                else:
                    tally.unsure.append(video.video_id)
                    print(f"{prefix} UNSURE {describe(video)}  (no captions seen, but the fetch "
                          f"before it failed; not recorded)")
                last_fetch_was_healthy = False
                continue
            except Exception as exc:
                # Deliberately not marked as seen. Whatever went wrong, it was
                # not the meeting's fault, and the next run should try again.
                tally.errors.append({"video_id": video.video_id,
                                     "error": f"{type(exc).__name__}: {exc}"})
                print(f"{prefix} ERROR  {describe(video)}  ({type(exc).__name__})")
                last_fetch_was_healthy = False
                tally.unsure.extend(gap.video_id for gap in unconfirmed)
                del unconfirmed[:]
                if isinstance(exc, TranscriptBlocked):
                    tally.stopped_early = f"YouTube refused the request ({str(exc)[:120]})"
                    print(f"\n  Stopping: {tally.stopped_early}\n"
                          f"  A block gets longer with every request made during it, so this "
                          f"stops at the first one.\n  Nothing was recorded as missing. Leave it "
                          f"for some hours, then run the same command.")
                    break
                failures_in_a_row += 1
                if failures_in_a_row >= MAX_FAILURES_IN_A_ROW:
                    tally.stopped_early = (
                        f"{failures_in_a_row} fetches in a row failed, the last with "
                        f"{type(exc).__name__}: {str(exc)[:120]}")
                    print(f"\n  Stopping: {tally.stopped_early}\n"
                          f"  That pattern is YouTube refusing requests, not {failures_in_a_row} "
                          f"meetings without captions.\n  Nothing was recorded as missing. "
                          f"Wait a few hours and run the same command.")
                    break
                continue
            failures_in_a_row = 0
            last_fetch_was_healthy = True
            confirm_gaps()

            transcript = result["transcript"]
            keep_captions(project.project_id, video, transcript)
            documents = []
            for chunk in meeting_chunks(
                # Captions a few seconds long where the collector has them, so
                # a passage is ~220 words and its timestamp is its own.
                transcript.get("captions") or transcript["segments"],
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
                state.mark_skipped(video.video_id, NO_TRANSCRIPT + ": it produced no passages")
                handled.append(video)
                print(f"{prefix} EMPTY  {describe(video)}")
                save_state(project.project_id, state)
                continue

            store.add_documents_batch(documents)
            state.mark_ingested(video.video_id)
            handled.append(video)
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

            if getattr(collector, "last_block", ""):
                # One reader was refused and the other got through. Last time
                # that happened the second was refused two meetings later.
                tally.stopped_early = (f"one of the two caption readers was refused "
                                       f"({collector.last_block[:100]})")
                print(f"\n  Stopping: {tally.stopped_early}\n  The other reader got this "
                      f"meeting, so it is in. That is a warning and this takes it: leave it for "
                      f"some hours, then run the same command.")
                break

        # Verdicts still waiting for a healthy fetch to follow them never got one.
        tally.unsure.extend(gap.video_id for gap in unconfirmed)

        for video in plan.skipped_not_meetings + plan.skipped_low_confidence:
            state.mark_skipped(video.video_id, NOT_A_MEETING)
        # Only what was actually handled. An interrupted run that moved the
        # cursor past meetings it never reached would hide them from every
        # incremental sync afterwards.
        advance_cursor(state, handled)
        save_state(project.project_id, state)

        # The archive's totals, not this run's. A backfill is interrupted and
        # resumed, and the gaps found on Tuesday are still gaps on Thursday.
        tally.archive_meetings += len(state.ingested_video_ids)
        tally.archive_gaps.extend(state.without_transcripts)

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
    print(f"  {summary['meetings_in_the_archive']:,} meetings in the archive, counting "
          f"earlier runs")
    if summary["meetings_without_transcripts"]:
        print(f"  {summary['meetings_without_transcripts']} meeting(s) have no captions, "
              f"counting earlier runs. Two readers reached each one and neither found any. "
              f"These are real gaps in the archive, not missing work; the data card "
              f"should say so.")
    if summary["meetings_with_an_untrusted_no_captions_verdict"]:
        print(f"  {summary['meetings_with_an_untrusted_no_captions_verdict']} meeting(s) showed "
              f"no captions while the fetches around them were failing. That is not evidence, "
              f"so they were not recorded as gaps and the next run looks again.")
    if summary["meetings_waiting_for_captions"]:
        print(f"  {summary['meetings_waiting_for_captions']} recent meeting(s) are not "
              f"captioned yet. They were left unmarked and the next run will look again.")
    if summary["meetings_that_errored"]:
        print(f"  {summary['meetings_that_errored']} fetch(es) failed. They were not "
              f"recorded as gaps. Re-run this command to retry them.")
    if tally.stopped_early:
        print(f"  STOPPED EARLY: {tally.stopped_early}")
    if summary["videos_not_classified_as_meetings"]:
        print(f"  {summary['videos_not_classified_as_meetings']} video(s) were not "
              f"classified as meetings and were left alone.")

    path = Path("./data") / project_id / "backfill-report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**summary,
               "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               # The ids, and every one of them, from every run. The count is
               # above as meetings_without_transcripts_count.
               "meetings_without_transcripts_count": summary["meetings_without_transcripts"],
               "meetings_without_transcripts": tally.archive_gaps or tally.no_transcript,
               "meetings_waiting_for_captions": tally.pending,
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
    parser.add_argument("--board", action="append", default=[], metavar="NAME",
                        help="only this board, by its canonical name; repeat for several. "
                             "The others are left unmarked for a later pass")
    parser.add_argument("--hold-same-day", action="store_true",
                        help="leave out, unmarked, any meeting that shares its board and "
                             "day with another video, until someone has said which are "
                             "duplicates")
    parser.add_argument("--dry-run", action="store_true",
                        help="list what would be ingested and write nothing")
    parser.add_argument("--full", action="store_true",
                        help="with --dry-run, list every meeting and everything left out")
    parser.add_argument("--quiet", action="store_true", help="one line per error only")
    parser.add_argument("--snapshot-every", type=int, default=0,
                        help="take a backup every N meetings, for long runs")
    parser.add_argument("--delay", type=float, default=20.0,
                        help="seconds between transcript requests, give or take 40%% "
                             "(default 20). YouTube refused Brookline's first backfill after "
                             "about 25 meetings at 3 seconds apart")
    parser.add_argument("--max-meetings", type=int, default=0, metavar="N",
                        help="stop after ingesting N meetings, for a backfill fed a night "
                             "at a time")
    parser.add_argument("--rescan", action="store_true",
                        help="list the channel again even if a recent listing is cached")
    args = parser.parse_args(argv)

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    tally = backfill(args.project, source_name=args.source, limit=args.limit,
                     dry_run=args.dry_run, since=args.since, quiet=args.quiet,
                     snapshot_every=args.snapshot_every, full=args.full,
                     delay=args.delay, boards=args.board,
                     hold_same_day=args.hold_same_day, max_meetings=args.max_meetings,
                     rescan=args.rescan)
    report(tally, args.project, args.dry_run)
    return 0 if not tally.errors else 1


if __name__ == "__main__":
    sys.exit(main())
