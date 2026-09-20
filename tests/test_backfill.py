"""Tests for the five-hundred-meeting backfill.

Nothing here touches YouTube. The channel listing and the transcript collector
are replaced with doubles, and what is exercised is the part that decides
whether a decade of a town's meetings ends up in the archive or half of it
does: ordering, resumability, per-meeting writes, and what happens to a
meeting whose captions are switched off.

The last of those is the one worth being strict about. A backfill that ingests
463 of 500 meetings and reports success has told the community it has the
record when it does not, and the missing 37 will be the ones somebody asks
about.

Run with:  python3 -m tests.test_backfill     (no pytest required)
       or:  python3 -m pytest tests/
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import types
from pathlib import Path
from typing import Any, Dict, List, Optional

PASS: List[str] = []
FAIL: List[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  -> {detail}" if not condition else ""))


# --- doubles --------------------------------------------------------------


class RecordingStore:
    """A store that remembers what it was asked to write, and when."""

    def __init__(self) -> None:
        self.writes: List[List[Dict[str, Any]]] = []
        self.fail_on: str = ""

    def add_documents_batch(self, documents, progress_callback=None):
        ids = [d["metadata"].get("video_id", "") for d in documents]
        if self.fail_on and self.fail_on in ids:
            raise RuntimeError("the disk filled up")
        self.writes.append(list(documents))
        return [str(i) for i in range(len(documents))]

    @property
    def all_documents(self) -> List[Dict[str, Any]]:
        return [d for batch in self.writes for d in batch]

    @property
    def video_ids(self) -> List[str]:
        return [d["metadata"].get("video_id", "") for d in self.all_documents]


TRANSCRIPTS = {
    "v2019": [{"text": "Chair Wilson: the meeting is called to order.",
               "start": 0.0, "speaker": "Chair Wilson"},
              {"text": "The motion to approve the minutes carries, five to zero.",
               "start": 40.0, "speaker": "Chair Wilson"}],
    "v2021": [{"text": "Member Ortiz: I move we table the sidewalk contract.",
               "start": 12.0, "speaker": "Member Ortiz"},
              {"text": "The motion is tabled until the engineering report arrives.",
               "start": 55.0, "speaker": "Member Ortiz"}],
    "v2023": [{"text": "The committee voted unanimously to adopt the budget.",
               "start": 8.0, "speaker": "Chair Nguyen"}],
    # No entry for v2022: that meeting's captions are off.
}


def install_collector_double(raises_on: str = "") -> None:
    """Stand in for collectors.youtube_collector, which needs two packages
    this machine does not have and a network this test must not use."""
    module = types.ModuleType("collectors.youtube_collector")

    class YouTubeCollector:
        def __init__(self, api_key=None) -> None:
            self.api_key = api_key

        def collect_video(self, url: str) -> Optional[Dict[str, Any]]:
            video_id = url.rsplit("=", 1)[-1]
            if raises_on and video_id == raises_on:
                raise ConnectionError("youtube hung up")
            segments = TRANSCRIPTS.get(video_id)
            if not segments:
                return {"transcript": None}
            return {"transcript": {"segments": [
                {"text": s["text"], "start_time": s["start"],
                 "speaker": s.get("speaker", "")} for s in segments]}}

    module.YouTubeCollector = YouTubeCollector
    sys.modules["collectors.youtube_collector"] = module


def make_videos():
    from collectors.youtube_channel import VideoRecord

    # Deliberately out of order: the script is supposed to sort them.
    return [
        VideoRecord(video_id="v2023", title="School Committee Meeting 6/4/2023",
                    url="https://youtube.com/watch?v=v2023",
                    published_at="2023-06-04", meeting_date="2023-06-04",
                    body="School Committee", date_source="title"),
        VideoRecord(video_id="v2019", title="Select Board Meeting 3/12/2019",
                    url="https://youtube.com/watch?v=v2019",
                    published_at="2019-03-12", meeting_date="2019-03-12",
                    body="Select Board", date_source="title"),
        VideoRecord(video_id="v2022", title="Select Board Meeting 11/2/2022",
                    url="https://youtube.com/watch?v=v2022",
                    published_at="2022-11-02", meeting_date="2022-11-02",
                    body="Select Board", date_source="title"),
        VideoRecord(video_id="v2021", title="Select Board Meeting 5/4/2021",
                    url="https://youtube.com/watch?v=v2021",
                    published_at="2021-05-04", meeting_date="2021-05-04",
                    body="Select Board", date_source="title"),
    ]


class FakePlan:
    def __init__(self, videos, not_meetings=()) -> None:
        self.new_videos = list(videos)
        self.skipped_not_meetings = list(not_meetings)
        self.skipped_low_confidence = []
        self.error = ""


def write_project(directory: str, project_id: str = "brookline-ma") -> None:
    path = Path(directory) / "data" / project_id
    path.mkdir(parents=True, exist_ok=True)
    (path / "config.json").write_text(json.dumps({
        "project_id": project_id,
        "municipality_name": "Brookline, MA",
        "project_name": "Brookline Civic AI",
        "data_sources": [{
            "id": "bigtv",
            "type": "youtube_channel",
            "url": "https://youtube.com/@brooklineinteractive",
            "name": "Brookline Interactive Group",
            "metadata": {"body": "Select Board"},
        }],
    }))


class Harness:
    """A temp directory, a project, a store, and the doubles wired in."""

    def __init__(self, videos=None, not_meetings=(), raises_on: str = "") -> None:
        self.videos = videos if videos is not None else make_videos()
        self.not_meetings = not_meetings
        self.raises_on = raises_on
        self.store = RecordingStore()

    def __enter__(self):
        import stores
        from scripts import backfill_archive

        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        write_project(self.tmp.name)

        install_collector_double(self.raises_on)
        self.saved_plan = backfill_archive.plan_sync
        self.saved_build = stores.build_store
        backfill_archive.plan_sync = lambda *a, **k: FakePlan(self.videos, self.not_meetings)
        stores.build_store = lambda *a, **k: self.store
        self.module = backfill_archive
        return self

    def __exit__(self, *exc):
        import stores

        self.module.plan_sync = self.saved_plan
        stores.build_store = self.saved_build
        self.module.stop_requested = False
        sys.modules.pop("collectors.youtube_collector", None)
        os.chdir(self.cwd)
        self.tmp.cleanup()
        return False

    def run(self, **kwargs):
        return self.module.backfill("brookline-ma", **kwargs)


# --- tests ----------------------------------------------------------------


def test_a_backfill_walks_the_catalogue_oldest_first() -> None:
    print("\nordering, so an interrupted run leaves no holes")
    with Harness() as h:
        tally = h.run()
        ingested = [vid for vid in dict.fromkeys(h.store.video_ids)]
        check("the meetings with transcripts were ingested",
              ingested == ["v2019", "v2021", "v2023"], str(ingested))
        check("oldest first, so stopping early leaves a contiguous archive",
              ingested == sorted(ingested), str(ingested))
        check("the tally counts them", tally.ingested == 3, str(tally.ingested))
        check("and counts the passages", tally.passages == len(h.store.all_documents),
              str(tally.passages))


def test_each_meeting_is_written_as_soon_as_it_is_read() -> None:
    print("\nper-meeting writes, so meeting 480 failing does not cost 479")
    with Harness() as h:
        h.run()
        check("there is one write per ingested meeting, not one at the end",
              len(h.store.writes) == 3, str(len(h.store.writes)))
        check("and each write is one meeting's passages",
              all(len({d["metadata"].get("video_id") for d in batch}) == 1
                  for batch in h.store.writes))


def test_a_meeting_without_captions_is_a_recorded_gap() -> None:
    print("\nthe 37 meetings nobody captioned")
    with Harness() as h:
        tally = h.run()
        check("it is not in the archive", "v2022" not in h.store.video_ids)
        check("it is counted as a gap, not passed over",
              tally.no_transcript == ["v2022"], str(tally.no_transcript))
        check("and the summary reports the number",
              tally.summary()["meetings_without_transcripts"] == 1)

        report = json.loads(
            Path("./data/brookline-ma/backfill-report.json").read_text()) \
            if Path("./data/brookline-ma/backfill-report.json").exists() else None
        check("the report is only written by the CLI, not the function", report is None)


def test_a_transcript_error_does_not_end_the_run() -> None:
    print("\none bad video out of five hundred")
    with Harness(raises_on="v2021") as h:
        tally = h.run()
        ingested = list(dict.fromkeys(h.store.video_ids))
        check("the run continued past it", ingested == ["v2019", "v2023"], str(ingested))
        check("the failure was recorded with its cause",
              len(tally.errors) == 1 and "ConnectionError" in tally.errors[0]["error"],
              str(tally.errors))


def test_running_it_twice_does_nothing_the_second_time() -> None:
    print("\nresumability, which is what makes it safe in cron")
    with Harness() as h:
        h.run()
        first = len(h.store.writes)

        from collectors.youtube_channel import load_state

        state = load_state("brookline-ma", "bigtv",
                           "https://youtube.com/@brooklineinteractive")
        check("state records what was ingested",
              set(state.ingested_video_ids) == {"v2019", "v2021", "v2023"},
              str(state.ingested_video_ids))
        check("and what was skipped", "v2022" in state.skipped_video_ids,
              str(state.skipped_video_ids))

        # The real plan_sync filters against state.seen. The double does not,
        # so this asserts the state a second run would consult rather than
        # re-testing plan_sync, which tests/test_archive.py already covers.
        check("a second run has nothing new to fetch",
              set(state.seen) >= {"v2019", "v2021", "v2022", "v2023"}, str(state.seen))
        check("the first run wrote what it wrote", first == 3, str(first))


def test_an_interrupt_stops_after_the_meeting_in_flight() -> None:
    print("\nCtrl-C in the middle of a six hour run")
    with Harness() as h:
        h.module.request_stop(2, None)
        tally = h.run()
        check("it stopped", tally.ingested <= 1, str(tally.ingested))
        check("and did not corrupt what it had",
              all(batch for batch in h.store.writes))
        h.module.stop_requested = False


def test_a_dry_run_writes_nothing() -> None:
    print("\n--dry-run")
    with Harness() as h:
        tally = h.run(dry_run=True)
        check("nothing was written", h.store.writes == [])
        check("and nothing was counted as ingested", tally.ingested == 0)


def test_since_narrows_the_backfill() -> None:
    print("\n--since, for the second pass over a long archive")
    with Harness() as h:
        h.run(since="2021-01-01")
        ingested = list(dict.fromkeys(h.store.video_ids))
        check("older meetings are left out", ingested == ["v2021", "v2023"], str(ingested))


def test_videos_that_are_not_meetings_are_counted_not_ingested() -> None:
    print("\nthe rest of a public access channel")
    from collectors.youtube_channel import VideoRecord

    concert = VideoRecord(video_id="vconcert", title="Summer Concert on the Common",
                          url="https://youtube.com/watch?v=vconcert")
    with Harness(not_meetings=[concert]) as h:
        tally = h.run()
        check("it is not in the archive", "vconcert" not in h.store.video_ids)
        check("it is counted", tally.not_meetings == 1, str(tally.not_meetings))
        check("and the summary says so",
              tally.summary()["videos_not_classified_as_meetings"] == 1)


def test_chunks_carry_what_a_citation_needs() -> None:
    print("\nwhat a passage looks like when it lands")
    with Harness() as h:
        h.run()
        passages = h.store.all_documents
        check("every passage has text", all(p["text"].strip() for p in passages))
        meta = passages[0]["metadata"]
        for field in ("body", "meeting_date", "url", "video_id", "source_type",
                      "collection_method", "date_source"):
            check(f"every passage carries {field}",
                  all(field in p["metadata"] for p in passages), field)
        check("the body came from the video, not a guess",
              meta.get("body") in {"Select Board", "School Committee"}, str(meta.get("body")))
        check("the collection method names this path, so provenance is auditable",
              meta.get("collection_method") == "youtube_channel_backfill",
              str(meta.get("collection_method")))
        check("a vote in the transcript was classified at ingestion",
              any(p["metadata"].get("vote_taken") for p in passages),
              "no passage was marked as a vote")
        check("and a tally was read off the words",
              any(p["metadata"].get("vote_tally") for p in passages),
              str([p["metadata"].get("vote_tally") for p in passages]))


def main() -> int:
    print("=" * 62)
    print("Archive backfill tests")
    print("=" * 62)
    for fn in [
        test_a_backfill_walks_the_catalogue_oldest_first,
        test_each_meeting_is_written_as_soon_as_it_is_read,
        test_a_meeting_without_captions_is_a_recorded_gap,
        test_a_transcript_error_does_not_end_the_run,
        test_running_it_twice_does_nothing_the_second_time,
        test_an_interrupt_stops_after_the_meeting_in_flight,
        test_a_dry_run_writes_nothing,
        test_since_narrows_the_backfill,
        test_videos_that_are_not_meetings_are_counted_not_ingested,
        test_chunks_carry_what_a_citation_needs,
    ]:
        fn()

    print("\n" + "=" * 62)
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    for name in FAIL:
        print(f"  FAILED: {name}")
    print("\nNot covered here: the real YouTube listing and transcript APIs,")
    print("which need a network and a key; tests/test_archive.py covers the")
    print("scan planning they feed.")
    return 1 if FAIL else 0


def test_all() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
