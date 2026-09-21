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


def install_collector_double(raises_on: str = "", blocked_from: str = "",
                             returns_nothing_for: str = "", flaky=()) -> None:
    """Stand in for collectors.youtube_collector, which needs two packages
    this machine does not have and a network this test must not use.

    It keeps the real one's contract: no captions is TranscriptUnavailable,
    and not being able to find out is TranscriptFetchFailed.
    """
    module = types.ModuleType("collectors.youtube_collector")

    class TranscriptUnavailable(Exception):
        pass

    class TranscriptFetchFailed(Exception):
        pass

    class TranscriptBlocked(TranscriptFetchFailed):
        pass

    class YouTubeCollector:
        def __init__(self, api_key=None) -> None:
            self.api_key = api_key
            self.last_block = ""

        def collect_video(self, url: str, strict: bool = False) -> Optional[Dict[str, Any]]:
            video_id = url.rsplit("=", 1)[-1]
            if raises_on and video_id == raises_on:
                raise ConnectionError("youtube hung up")
            if blocked_from and video_id >= blocked_from:
                raise TranscriptBlocked("IpBlocked: YouTube is refusing this address")
            if video_id in flaky:
                raise TranscriptFetchFailed("ReadTimeout: the connection dropped")
            if video_id == returns_nothing_for:
                return None
            segments = TRANSCRIPTS.get(video_id)
            if not segments:
                raise TranscriptUnavailable("TranscriptsDisabled")
            return {"transcript": {"segments": [
                {"text": s["text"], "start_time": s["start"],
                 "speaker": s.get("speaker", "")} for s in segments]}}

    module.YouTubeCollector = YouTubeCollector
    module.TranscriptUnavailable = TranscriptUnavailable
    module.TranscriptFetchFailed = TranscriptFetchFailed
    module.TranscriptBlocked = TranscriptBlocked
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
        self.scanned = len(videos) + len(not_meetings)
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

    def __init__(self, videos=None, not_meetings=(), raises_on: str = "",
                 blocked_from: str = "", returns_nothing_for: str = "", flaky=()) -> None:
        self.videos = videos if videos is not None else make_videos()
        self.not_meetings = not_meetings
        self.raises_on = raises_on
        self.blocked_from = blocked_from
        self.returns_nothing_for = returns_nothing_for
        self.flaky = flaky
        self.store = RecordingStore()

    def __enter__(self):
        import stores
        from scripts import backfill_archive

        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        write_project(self.tmp.name)

        install_collector_double(self.raises_on, self.blocked_from, self.returns_nothing_for,
                                 self.flaky)
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


def _select_board(video_id: str, day: str):
    from collectors.youtube_channel import VideoRecord

    return VideoRecord(video_id=video_id, title=f"Select Board Meeting {day}",
                       url=f"https://youtube.com/watch?v={video_id}",
                       published_at=day, meeting_date=day,
                       body="Select Board", date_source="title")


def test_a_refused_request_is_not_a_missing_transcript() -> None:
    print("\nYouTube starts refusing requests at meeting two of four")
    from collectors.youtube_channel import load_state

    with Harness(blocked_from="v2021") as h:
        tally = h.run()
        check("nothing was recorded as a gap in the record",
              tally.no_transcript == [] and tally.summary()["meetings_without_transcripts"] == 0,
              str(tally.no_transcript))
        check("the refusal was recorded as a failure, with its cause",
              len(tally.errors) == 1 and "IpBlocked" in tally.errors[0]["error"],
              str(tally.errors))
        check("and the run stopped at the first one, because every request made "
              "during a block lengthens it", "refused" in tally.stopped_early,
              tally.stopped_early)
        state = load_state("brookline-ma", "bigtv")
        check("and none of them is marked as seen, so the next run tries again",
              not ({"v2021", "v2022", "v2023"} & state.seen), str(state.seen))
        check("what was fetched before the refusals is kept",
              list(dict.fromkeys(h.store.video_ids)) == ["v2019"], str(h.store.video_ids))


def test_it_stops_when_youtube_stops_answering() -> None:
    print("\nfive failures in a row that are not refusals")
    videos = [_select_board("v2019", "2019-03-12")] + [
        _select_board(f"v30{n}", f"2020-0{n + 1}-10") for n in range(8)]
    with Harness(videos=videos, flaky={f"v30{n}" for n in range(8)}) as h:
        tally = h.run()
        check("the meeting before the refusals was ingested", tally.ingested == 1,
              str(tally.ingested))
        check("the run stopped instead of failing four hundred more times",
              len(tally.errors) == h.module.MAX_FAILURES_IN_A_ROW, str(len(tally.errors)))
        check("and says why", "in a row" in tally.stopped_early, tally.stopped_early)
        check("still without inventing a single gap", tally.no_transcript == [])


def test_one_bad_video_among_good_ones_does_not_stop_the_run() -> None:
    print("\nfailures that are not in a row")
    with Harness(raises_on="v2021") as h:
        tally = h.run()
        check("it carried on", not tally.stopped_early and tally.ingested == 2,
              f"{tally.stopped_early!r} {tally.ingested}")
        from collectors.youtube_channel import load_state
        check("and the failure will be retried",
              "v2021" not in load_state("brookline-ma", "bigtv").seen)


def test_an_empty_answer_is_a_fault_not_a_gap() -> None:
    print("\na collector that returns nothing at all")
    with Harness(returns_nothing_for="v2021") as h:
        tally = h.run()
        check("it is not counted as a meeting without captions",
              "v2021" not in tally.no_transcript, str(tally.no_transcript))
        check("it is counted as a failure",
              any(e.get("video_id") == "v2021" for e in tally.errors), str(tally.errors))


def test_last_nights_meeting_is_not_a_gap() -> None:
    print("\na meeting YouTube has not captioned yet")
    from datetime import datetime, timedelta

    from collectors.youtube_channel import load_state

    last_night = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    with Harness(videos=[_select_board("vlastnight", last_night)]) as h:
        tally = h.run()
        check("it is waiting, not missing",
              tally.pending == ["vlastnight"] and tally.no_transcript == [],
              f"{tally.pending} {tally.no_transcript}")
        check("and the next run will look again",
              "vlastnight" not in load_state("brookline-ma", "bigtv").seen)


def test_the_report_counts_every_run_not_the_last_one() -> None:
    print("\ninterrupted on Tuesday, resumed on Thursday")
    with Harness() as h:
        first = h.run()
        check("the first run found the gap",
              first.summary()["meetings_without_transcripts"] == 1)

        h.videos[:] = []            # everything is handled; the second run has nothing to do
        second = h.run()
        summary = second.summary()
        check("the second run found no new gaps",
              summary["meetings_without_transcripts_found_this_run"] == 0)
        check("and still reports the one the archive has",
              summary["meetings_without_transcripts"] == 1 and second.archive_gaps == ["v2022"],
              f"{summary} {second.archive_gaps}")
        check("along with every meeting from both runs",
              summary["meetings_in_the_archive"] == 3, str(summary["meetings_in_the_archive"]))


def test_no_captions_seen_through_a_failing_connection_is_not_a_gap() -> None:
    print("\nwhat happened on Brookline's first night: NO CC, in the middle of a block")
    from collectors.youtube_channel import load_state

    # ok, failure, no captions, no captions, refused. While YouTube is turning a
    # machine away it serves pages with the caption tracks left out, so the two
    # in the middle look exactly like meetings without captions.
    videos = [_select_board("v2019", "2013-04-09"), _select_board("vflaky", "2013-04-23"),
              _select_board("vnone1", "2013-05-07"), _select_board("vnone2", "2013-05-09"),
              _select_board("w-blocked", "2013-05-14")]
    with Harness(videos=videos, flaky={"vflaky"}, blocked_from="w-") as h:
        tally = h.run()
        check("neither was recorded as a hole in the record",
              tally.no_transcript == [] and tally.summary()["meetings_without_transcripts"] == 0,
              str(tally.no_transcript))
        check("both are reported as verdicts nobody should trust",
              sorted(tally.unsure) == ["vnone1", "vnone2"], str(tally.unsure))
        check("and neither is marked, so a healthy night looks again",
              not ({"vnone1", "vnone2"} & load_state("brookline-ma", "bigtv").seen))

    print("\nthe same verdict with a working fetch on either side")
    videos = [_select_board("v2019", "2019-03-12"), _select_board("vnone", "2020-01-07"),
              _select_board("v2021", "2021-05-04")]
    with Harness(videos=videos) as h:
        tally = h.run()
        check("is a gap, and is recorded", tally.no_transcript == ["vnone"]
              and "vnone" in load_state("brookline-ma", "bigtv").without_transcripts,
              str(tally.no_transcript))

    print("\nand as the last thing a run did")
    with Harness(videos=[_select_board("v2019", "2019-03-12"),
                         _select_board("vnone", "2020-01-07")]) as h:
        tally = h.run()
        check("it waits for a run that can vouch for it",
              tally.no_transcript == [] and tally.unsure == ["vnone"],
              f"{tally.no_transcript} {tally.unsure}")


def test_one_reader_being_refused_is_a_warning_and_is_taken() -> None:
    print("\nthe first reader is refused, the second gets through")
    videos = [_select_board("v2019", "2019-03-12"), _select_board("v2021", "2021-05-04"),
              _select_board("v2023", "2023-06-04")]
    with Harness(videos=videos) as h:
        collector = sys.modules["collectors.youtube_collector"].YouTubeCollector
        fetch = collector.collect_video

        def warned(self, url, strict=False):
            self.last_block = "youtube-transcript-api: IpBlocked" if url.endswith("v2021") else ""
            return fetch(self, url, strict=strict)

        collector.collect_video = warned
        tally = h.run()
        check("the meeting the second reader fetched is kept",
              list(dict.fromkeys(h.store.video_ids)) == ["v2019", "v2021"],
              str(h.store.video_ids))
        check("and the run stops there instead of waiting to be refused outright",
              "refused" in tally.stopped_early and tally.ingested == 2, tally.stopped_early)


def test_a_backfill_can_be_fed_a_night_at_a_time() -> None:
    print("\n--max-meetings")
    from collectors.youtube_channel import load_state

    with Harness() as h:
        tally = h.run(max_meetings=1)
        check("it stops after the number asked for", tally.ingested == 1, str(tally.ingested))
        check("oldest first", list(dict.fromkeys(h.store.video_ids)) == ["v2019"])
        check("and the rest are untouched for tomorrow",
              load_state("brookline-ma", "bigtv").seen == {"v2019"},
              str(load_state("brookline-ma", "bigtv").seen))


def test_a_pass_over_some_boards_leaves_the_others_alone() -> None:
    print("\n--board, for building the archive a board at a time")
    from collectors.youtube_channel import load_state

    with Harness() as h:
        tally = h.run(boards=["school committee"])
        check("only that board was ingested",
              list(dict.fromkeys(h.store.video_ids)) == ["v2023"], str(h.store.video_ids))
        state = load_state("brookline-ma", "bigtv")
        check("and the other boards were not marked, so the next pass has them",
              not ({"v2019", "v2021", "v2022"} & state.seen), str(state.seen))
        check("nor counted as gaps", tally.no_transcript == [], str(tally.no_transcript))


def test_two_videos_for_one_board_on_one_day_can_wait() -> None:
    print("\n--hold-same-day, until someone says which are duplicates")
    from collectors.youtube_channel import load_state

    videos = make_videos() + [_select_board("v2019b", "2019-03-12")]
    with Harness(videos=videos) as h:
        alone, shared = h.module.split_same_day(videos)
        check("the day with two videos is found",
              sorted(v.video_id for v in shared) == ["v2019", "v2019b"],
              str([v.video_id for v in shared]))
        check("a different board on a different day is not part of it",
              "v2023" in [v.video_id for v in alone])

        tally = h.run(hold_same_day=True)
        check("neither of the pair was ingested",
              not ({"v2019", "v2019b"} & set(h.store.video_ids)), str(h.store.video_ids))
        check("the run says how many it held", tally.held_same_day == 2
              and tally.summary()["meetings_held_back_same_board_same_day"] == 2,
              str(tally.held_same_day))
        check("and they are not marked, so a later run takes them",
              not ({"v2019", "v2019b"} & load_state("brookline-ma", "bigtv").seen))

    undated = make_videos()
    for video in undated[:2]:
        video.meeting_date = ""
    alone, shared = h.module.split_same_day(undated)
    check("two undated videos are not 'the same day'", shared == [],
          str([v.video_id for v in shared]))


def test_a_recess_is_not_a_passage() -> None:
    print("\nwhat the captioner heard, as opposed to what was said")
    from knowledge.schemas import meeting_chunks

    captions = ([{"text": "[music]", "start": float(n), "duration": 3.0} for n in range(0, 600, 3)]
                + [{"text": "the meeting is called to order", "start": 612.0, "duration": 2.5},
                   {"text": "[applause] thank you [laughter]", "start": 615.0, "duration": 2.0},
                   {"text": "[Chair Wilson] is there a second", "start": 618.0, "duration": 2.0}])
    chunks = meeting_chunks(captions, community="Brookline, MA", body="Select Board",
                            meeting_date="2026-08-31", video_url="https://youtube.com/watch?v=x")
    check("ten minutes of [music] did not become a record of the Select Board",
          len(chunks) == 1 and "[music]" not in chunks[0].text, str([c.text[:60] for c in chunks]))
    check("the passage starts where the speaking does",
          chunks[0].to_payload().get("start_time") == 612.0,
          str(chunks[0].to_payload().get("start_time")))
    check("noise inside a sentence goes and the sentence stays",
          "thank you" in chunks[0].text and "applause" not in chunks[0].text, chunks[0].text)
    check("a person's speaker label is not noise", "[Chair Wilson]" in chunks[0].text,
          chunks[0].text)


def test_the_captions_are_kept_as_they_came() -> None:
    print("\nthe primary source, beside the archive")
    import gzip

    captions = [{"text": "the motion carries", "start": 754.2, "duration": 2.1}]
    with Harness(videos=[_select_board("vkept", "2024-02-06")]) as h:
        collector = sys.modules["collectors.youtube_collector"].YouTubeCollector
        collector.collect_video = lambda self, url, strict=False: {"transcript": {
            "segments": [{"text": "the motion carries", "start_time": 0.0}],
            "captions": captions, "method": "youtube_transcript_api-en-auto"}}
        h.run()
        path = Path("data/brookline-ma/captions/vkept.json.gz")
        check("a file per meeting", path.is_file())
        if path.is_file():
            kept = json.loads(gzip.open(path, "rt", encoding="utf-8").read())
            check("with the captions exactly as fetched", kept["captions"] == captions)
            check("and enough to know what they are without the archive",
                  kept["video_id"] == "vkept" and kept["meeting_date"] == "2024-02-06"
                  and kept["body"] == "Select Board" and kept["method"], str(kept)[:200])


def test_passages_are_cut_from_captions_when_there_are_captions() -> None:
    print("\ntimestamps a citation can use")
    with Harness(videos=[_select_board("vcaptions", "2024-02-06")]) as h:
        collector = sys.modules["collectors.youtube_collector"].YouTubeCollector
        collector.collect_video = lambda self, url, strict=False: {"transcript": {
            "segments": [{"text": "two minutes of talk, starting at the top", "start_time": 0.0}],
            "captions": [{"text": "the motion carries", "start": 754.2, "duration": 2.1},
                         {"text": "four to one", "start": 756.3, "duration": 1.8}],
        }}
        h.run()
        meta = h.store.all_documents[0]["metadata"]
        check("the passage starts where the words start, not where the block did",
              meta.get("start_time") == 754.2, str(meta.get("start_time")))


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
        test_a_refused_request_is_not_a_missing_transcript,
        test_it_stops_when_youtube_stops_answering,
        test_one_bad_video_among_good_ones_does_not_stop_the_run,
        test_an_empty_answer_is_a_fault_not_a_gap,
        test_last_nights_meeting_is_not_a_gap,
        test_the_report_counts_every_run_not_the_last_one,
        test_no_captions_seen_through_a_failing_connection_is_not_a_gap,
        test_one_reader_being_refused_is_a_warning_and_is_taken,
        test_a_backfill_can_be_fed_a_night_at_a_time,
        test_a_pass_over_some_boards_leaves_the_others_alone,
        test_two_videos_for_one_board_on_one_day_can_wait,
        test_a_recess_is_not_a_passage,
        test_the_captions_are_kept_as_they_came,
        test_passages_are_cut_from_captions_when_there_are_captions,
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
