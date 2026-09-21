"""Tests for the meeting archive: title parsing, channel sync, video embeds.

No network. Channel listing is stubbed so the sync logic, which is where the
bugs live, is exercised directly.
"""

from __future__ import annotations

import sys
import tempfile
from typing import List

from collectors import youtube_channel as yc
from collectors.meeting_titles import extract_body, extract_date, parse_meeting_title
from collectors.youtube_channel import (
    SyncState, VideoRecord, advance_cursor, load_state, plan_sync, save_state,
)
from knowledge.schemas import CivicChunk, SourceType
from rag.citations import build_citations, embed_info

PASS: List[str] = []
FAIL: List[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  -> {detail}" if not condition else ""))


def test_title_parsing() -> None:
    print("\nreading board and date out of a title")
    cases = [
        ("Select Board Meeting 4/14/2026", "20260416", "Select Board", "2026-04-14", "title"),
        ("School Committee Meeting - April 14, 2026", None, "School Committee", "2026-04-14", "title"),
        ("Planning Board 2026-03-02", None, "Planning Board", "2026-03-02", "title"),
        ("ZBA Hearing 3.2.26", None, "Zoning Board of Appeals", "2026-03-02", "title"),
        ("Board of Health Special Session 12/1/2024", None, "Board of Health", "2024-12-01", "title"),
        ("Brookline Town Meeting Night 1 - May 28 2025", None, "Town Meeting", "2025-05-28", "title"),
    ]
    for title, upload, body, date, source in cases:
        parsed = parse_meeting_title(title, upload)
        check(f"{title[:38]!r} board", parsed.body == body, f"got {parsed.body!r}")
        check(f"{title[:38]!r} date", parsed.meeting_date == date, f"got {parsed.meeting_date!r}")
        check(f"{title[:38]!r} date source", parsed.date_source == source, parsed.date_source)


def test_title_date_beats_upload_date() -> None:
    print("\nthe title's date wins over the upload date")
    # Held the 14th, posted the 16th. Residents ask about the 14th.
    parsed = parse_meeting_title("Select Board Meeting 4/14/2026", "20260416")
    check("meeting date is the held date", parsed.meeting_date == "2026-04-14",
          parsed.meeting_date)
    check("recorded as coming from the title", parsed.date_source == "title")

    parsed = parse_meeting_title("Conservation Commission", "20260701")
    check("falls back to the upload date", parsed.meeting_date == "2026-07-01")
    check("fallback is labeled", parsed.date_source == "upload")
    check("fallback explains itself", any("upload date" in n for n in parsed.notes))


def test_year_inferred_when_title_omits_it() -> None:
    print("\ntitle with no year")
    parsed = parse_meeting_title("Advisory Committee Nov 12", "20251114")
    check("year taken from the upload", parsed.meeting_date == "2025-11-12",
          parsed.meeting_date)
    check("the guess is recorded", any("year taken" in n for n in parsed.notes))


def test_longest_board_alias_wins() -> None:
    print("\nboard matching")
    body, _ = extract_body("Zoning Board of Appeals Hearing")
    check("full name beats the short alias", body == "Zoning Board of Appeals", body)

    body, confidence = extract_body("ZBA Hearing")
    check("acronym still matches", body == "Zoning Board of Appeals", body)
    check("acronym is lower confidence", confidence < 0.95, str(confidence))

    body, _ = extract_body("Coolidge Corner Holiday Stroll")
    check("a non-meeting video matches no board", body == "", body)


def test_non_meetings_are_recognized() -> None:
    print("\nnon-meeting videos")
    parsed = parse_meeting_title("Coolidge Corner Holiday Stroll Highlights", "20251206")
    check("not classified as a meeting", parsed.is_meeting is False)
    check("confidence is low", parsed.confidence < 0.3, str(parsed.confidence))

    parsed = parse_meeting_title("Select Board Meeting 4/14/2026", "20260416")
    check("a real meeting is classified as one", parsed.is_meeting is True)
    check("and is high confidence", parsed.confidence > 0.9, str(parsed.confidence))


def test_iso_date_not_misread_as_month_day() -> None:
    print("\ndate ordering")
    found, _ = extract_date("Planning Board 2026-03-02")
    check("ISO date parsed as year-month-day", found == "2026-03-02", str(found))
    found, _ = extract_date("Planning Board 3/2/2026")
    check("US order parsed as month/day/year", found == "2026-03-02", str(found))
    found, _ = extract_date("Meeting 13/45/2026")
    check("an impossible date is rejected", found is None, str(found))


def test_titles_as_a_real_channel_writes_them() -> None:
    print("\ntitles from Brookline's channel, as written")
    # Every one of these is a real Select Board, School Committee or ZBA
    # meeting that the parser filed with no date, or under no board.
    for title, body, expected in [
        ("Brookline School  Committee Meeting - March 2, 2023", "School Committee", "2023-03-02"),
        ("School Committee Regular Meeting - May, 14, 2019", "School Committee", "2019-05-14"),
        ("Brookline Select Board Regular Meeting March 26,2019", "Select Board", "2019-03-26"),
        ("Select Board Meeting - entering Executive Session - May, 27 2022",
         "Select Board", "2022-05-27"),
        ("Brookline School Committee Meeting, Jan 7/21", "School Committee", "2021-01-07"),
        ("School Committee 4 /12/18", "School Committee", "2018-04-12"),
        ("Board of Selectmen 10 06 15", "Select Board", "2015-10-06"),
        ("Board of Selectmen 10:27:15", "Select Board", "2015-10-27"),
        ("Select Board 092419", "Select Board", "2019-09-24"),
        ("School Committee Regular Meeting  442019", "School Committee", "2019-04-04"),
        ("Zoning Board of Appeals Regular Meeting 8202019",
         "Zoning Board of Appeals", "2019-08-20"),
    ]:
        parsed = parse_meeting_title(title)
        check(f"{title[:44]!r}", parsed.body == body and parsed.meeting_date == expected,
              f"{parsed.body!r} {parsed.meeting_date!r}")

    print("\na date that could be two days is not a date")
    for title in ("Select Board 1112019",          # January 11th, or November 1st
                  "School Committee 10/02/014",    # a typo; 2014 is a guess
                  "Brookline Transportation Board Meeting June 2024"):   # no day
        parsed = parse_meeting_title(title)
        check(f"{title!r} is left undated", parsed.meeting_date == "" and parsed.is_meeting,
              parsed.meeting_date)

    found, _ = extract_date("Town Meeting Night 1 - May 28", fallback_year=2025)
    check("the first month-shaped words are not the only ones tried",
          found == "2025-05-28", str(found))
    found, _ = extract_date("Select Board Meeting at 7:00:00")
    check("a time of day is not a date", found is None, str(found))


def test_a_programme_about_a_board_is_not_the_board() -> None:
    print("\ncampaign events and highlight reels")
    for title in [
        "2024 BNA Select Board Candidate Forum",
        "TV on TV-Brookline Select Board Candidate Paul Warren",
        "Brookline Neighborhood Alliance Presents: 2025 Select Board Candidate Forum",
        "2025 Brookline Town Meeting in 3 Minutes - Night 2",
        "Brookline Town Meeting: Warrant Review 11/12/14",
        "Town Meeting May 2017 Recap",
        "SPOA Housing Policy, Episode 3: Medford City Council Candidate Fights Rent Control",
    ]:
        parsed = parse_meeting_title(title)
        check(f"not ingested: {title[:50]!r}", not parsed.is_meeting, str(parsed.to_dict()))
    check("and the reason is kept",
          any("programme about one" in n
              for n in parse_meeting_title("2024 BNA Select Board Candidate Forum").notes))
    check("a work session is still a meeting",
          parse_meeting_title("Select Board Work Session Pt. 2 - September 16, 2026").is_meeting)


def test_a_community_supplies_its_own_boards() -> None:
    print("\na community's own board list")
    from collectors.meeting_titles import community_bodies

    title = "School Finance Subcommittee Meeting - March 3, 2025"
    check("no default list knows a town's subcommittees",
          parse_meeting_title(title).body == "")

    bodies = community_bodies({
        "School Committee Finance Subcommittee": ["school finance subcommittee"],
        "Task Force to Reimagine Policing": "task force to reimagine policing",
    })
    check("the community's list does", parse_meeting_title(title, bodies=bodies).body
          == "School Committee Finance Subcommittee")
    check("an alias may be given as a bare string",
          parse_meeting_title("The Task Force to Reimagine Policing in Brookline 9/30/20",
                              bodies=bodies).body == "Task Force to Reimagine Policing")
    check("the defaults are still there",
          parse_meeting_title("Select Board Meeting 4/14/2026", bodies=bodies).body
          == "Select Board")
    bodies = community_bodies({
        "Town School Partnership Committee": ["town school partnership"],
        "School Committee DEIJ Subcommittee":
            ["school diversity equity inclusion and justice subcommittee"],
        "City Council": [],
    })
    for title in ("Brookline Town-School Partnership Meeting - April 4, 2025",
                  "Town - School Partnership Meeting: June 26, 2024",
                  "Town School Partnership Meeting - May 22, 2025"):
        check(f"punctuation is not part of a name: {title[:34]!r}",
              parse_meeting_title(title, bodies=bodies).body
              == "Town School Partnership Committee")
    for title in ("School Diversity, Equity, Inclusion, and Justice Subcommittee - June 6, 2022",
                  "School Diversity, Equity, Inclusion & Justice Subcommittee | January 16, 2024"):
        check(f"nor is an ampersand or a comma: {title[26:56]!r}",
              parse_meeting_title(title, bodies=bodies).body
              == "School Committee DEIJ Subcommittee")
    check("a board listed with no aliases is one this town does not have",
          parse_meeting_title("Medford City Council Meeting 4/14/2026", bodies=bodies).body == "")

    check("a subcommittee is not swallowed by its parent",
          parse_meeting_title("School Committee Finance Subcommittee 4/14/2026",
                              bodies=community_bodies({
                                  "School Committee Finance Subcommittee":
                                      ["school committee finance subcommittee"]})).body
          == "School Committee Finance Subcommittee")


def _stub_videos(entries):
    def fake_list(channel_url, api_key=None, limit=500, published_after=None, bodies=None):
        out = []
        for vid, title, published in entries:
            if published_after and published and published <= published_after:
                continue
            record = VideoRecord(video_id=vid, title=title,
                                 url=f"https://www.youtube.com/watch?v={vid}",
                                 published_at=published)
            record.apply(parse_meeting_title(title, published))
            out.append(record)
        return out[:limit]
    return fake_list


def test_sync_plan_skips_what_it_already_has() -> None:
    print("\nincremental sync")
    entries = [
        ("v1", "Select Board Meeting 4/14/2026", "2026-04-16"),
        ("v2", "School Committee Meeting 4/15/2026", "2026-04-17"),
        ("v3", "Coolidge Corner Holiday Stroll", "2026-04-18"),
    ]
    original = yc.list_channel_videos
    yc.list_channel_videos = _stub_videos(entries)
    try:
        state = SyncState(source_id="s1")
        plan = plan_sync("https://youtube.com/@bigtv", state, incremental=False)

        check("scanned everything", plan.scanned == 3, str(plan.scanned))
        check("two meetings queued", len(plan.new_videos) == 2, str(len(plan.new_videos)))
        check("the non-meeting was skipped",
              len(plan.skipped_not_meetings) == 1, str(plan.skipped_not_meetings))
        check("oldest first, so an interrupted backfill stays contiguous",
              plan.new_videos[0].video_id == "v1",
              str([v.video_id for v in plan.new_videos]))
        check("summary names the boards found",
              set(plan.summary()["bodies_found"]) == {"Select Board", "School Committee"},
              str(plan.summary()["bodies_found"]))

        # Second run, after the first ingested both.
        state.mark_ingested("v1")
        state.mark_ingested("v2")
        plan2 = plan_sync("https://youtube.com/@bigtv", state, incremental=False)
        check("nothing re-ingested", len(plan2.new_videos) == 0,
              str([v.video_id for v in plan2.new_videos]))
        check("already-ingested counted", plan2.already_ingested == 2,
              str(plan2.already_ingested))

        # Third run, with a new meeting posted.
        entries.append(("v4", "Planning Board Meeting 5/1/2026", "2026-05-02"))
        yc.list_channel_videos = _stub_videos(entries)
        plan3 = plan_sync("https://youtube.com/@bigtv", state, incremental=False)
        check("only the new meeting is queued",
              [v.video_id for v in plan3.new_videos] == ["v4"],
              str([v.video_id for v in plan3.new_videos]))
    finally:
        yc.list_channel_videos = original


def test_a_board_list_that_learns_finds_what_it_missed() -> None:
    print("\nadding a board after the first scan")
    from collectors.meeting_titles import community_bodies
    from collectors.youtube_channel import NO_TRANSCRIPT, NOT_A_MEETING

    entries = [
        ("osc", "Override Study Committee 9/30/2020", "2020-10-01"),
        ("nocc", "Select Board Meeting 4/14/2021", "2021-04-16"),
        ("show", "Drop In Demos: Flower Crowns", "2021-05-01"),
    ]
    original = yc.list_channel_videos

    def listing(bodies=None):
        def fake_list(channel_url, api_key=None, limit=500, published_after=None, bodies=bodies):
            out = []
            for vid, title, published in entries:
                record = VideoRecord(video_id=vid, title=title, published_at=published,
                                     url=f"https://www.youtube.com/watch?v={vid}")
                record.apply(parse_meeting_title(title, published, bodies))
                out.append(record)
            return out
        return fake_list

    try:
        state = SyncState(source_id="s5")
        yc.list_channel_videos = listing()
        first = plan_sync("https://youtube.com/@bigtv", state, incremental=False)
        check("the unknown committee is left out the first time",
              [v.video_id for v in first.skipped_not_meetings] == ["osc", "show"],
              str([v.video_id for v in first.skipped_not_meetings]))
        for video in first.skipped_not_meetings:
            state.mark_skipped(video.video_id, NOT_A_MEETING)
        state.mark_skipped("nocc", NO_TRANSCRIPT)

        bodies = community_bodies({"Override Study Committee": ["override study committee"]})
        yc.list_channel_videos = listing(bodies)
        second = plan_sync("https://youtube.com/@bigtv", state, incremental=False, bodies=bodies)
        check("and found once the list knows it",
              [v.video_id for v in second.new_videos] == ["osc"],
              str([v.video_id for v in second.new_videos]))
        check("a meeting with no captions is not fetched again",
              "nocc" not in [v.video_id for v in second.new_videos])
        check("why each was skipped survives a save",
              state.to_dict()["skip_reasons"]["nocc"] == NO_TRANSCRIPT
              and state.without_transcripts == ["nocc"], str(state.skip_reasons))
    finally:
        yc.list_channel_videos = original


def test_a_channel_is_listed_once_not_every_run() -> None:
    print("\nthe kept listing")
    import json
    from datetime import datetime, timedelta
    from pathlib import Path

    from collectors.meeting_titles import community_bodies

    scans: List[str] = []

    def lister(channel_url, api_key=None, limit=500, published_after=None, bodies=None):
        scans.append(channel_url)
        out = []
        for vid, title in (("sb", "Select Board Meeting 4/14/2026"),
                           ("osc", "Override Study Committee 9/30/2020")):
            record = VideoRecord(video_id=vid, title=title,
                                 url=f"https://www.youtube.com/watch?v={vid}")
            record.apply(parse_meeting_title(title, "", bodies))
            out.append(record)
        return out

    original = yc.list_channel_videos
    yc.list_channel_videos = lister
    try:
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "sync" / "s6.listing.json"
            url = "https://youtube.com/@bigtv"

            def plan(**kwargs):
                return plan_sync(url, SyncState(source_id="s6"), incremental=False, limit=6000,
                                 listing_cache=cache, **kwargs)

            first = plan()
            check("the first backfill run lists the channel", len(scans) == 1 and cache.is_file())
            check("and says it did", first.listing_was_cached is False)

            second = plan()
            check("the second does not ask YouTube again", len(scans) == 1, str(len(scans)))
            check("and plans the same work",
                  [v.video_id for v in second.new_videos] == [v.video_id for v in first.new_videos]
                  and second.listing_was_cached)

            learned = plan(bodies=community_bodies(
                {"Override Study Committee": ["override study committee"]}))
            check("a kept listing is still read with today's board list",
                  sorted(v.video_id for v in learned.new_videos) == ["osc", "sb"]
                  and len(scans) == 1, str([v.video_id for v in learned.new_videos]))

            plan(rescan=True)
            check("--rescan lists it again", len(scans) == 2, str(len(scans)))

            plan_sync(url, SyncState(source_id="s6"), incremental=True, listing_cache=cache)
            check("a sync looking for what is new never uses it", len(scans) == 3)

            plan_sync("https://youtube.com/@someoneelse", SyncState(source_id="s6"),
                      incremental=False, limit=6000, listing_cache=cache)
            check("nor does another channel", len(scans) == 4)

            kept = json.loads(cache.read_text())
            kept["listed_at"] = (datetime.now() - timedelta(days=3)).isoformat(timespec="seconds")
            kept["channel_url"] = url
            cache.write_text(json.dumps(kept))
            plan()
            check("and a listing three days old is not trusted", len(scans) == 5, str(len(scans)))
    finally:
        yc.list_channel_videos = original


def test_cursor_limits_the_scan() -> None:
    print("\npublished-after cursor")
    entries = [
        ("old", "Select Board Meeting 1/5/2020", "2020-01-06"),
        ("new", "Select Board Meeting 4/14/2026", "2026-04-16"),
    ]
    original = yc.list_channel_videos
    yc.list_channel_videos = _stub_videos(entries)
    try:
        state = SyncState(source_id="s2", last_published_at="2026-01-01")
        plan = plan_sync("https://youtube.com/@bigtv", state, incremental=True)
        check("older videos never listed",
              [v.video_id for v in plan.new_videos] == ["new"],
              str([v.video_id for v in plan.new_videos]))
    finally:
        yc.list_channel_videos = original


def test_body_override_beats_the_title() -> None:
    print("\nper-source board override")
    entries = [("v1", "Meeting of April 14 2026", "2026-04-16")]
    original = yc.list_channel_videos
    yc.list_channel_videos = _stub_videos(entries)
    try:
        state = SyncState(source_id="s3")
        plan = plan_sync("https://youtube.com/playlist?list=X", state,
                         incremental=False, body_override="Select Board")
        check("override applied", plan.new_videos[0].body == "Select Board",
              plan.new_videos[0].body)
        check("override raises confidence", plan.new_videos[0].confidence >= 0.9)
    finally:
        yc.list_channel_videos = original


def test_a_channel_scan_includes_its_live_streams() -> None:
    print("\nkeyless channel listing: /videos and /streams")
    import types

    tabs = {
        "https://www.youtube.com/@bigtv/videos": {"entries": [
            {"id": "work", "title": "Select Board Work Session - September 16, 2026"},
            {"id": "both", "title": "Planning Board Meeting 5/1/2026"},
        ]},
        "https://www.youtube.com/@bigtv/streams": {"entries": [
            {"id": "live", "title": "Brookline Select Board Meeting - August 31, 2026",
             "live_status": "was_live"},
            {"id": "both", "title": "Planning Board Meeting 5/1/2026"},
            {"id": "soon", "title": "Brookline Select Board Meeting - October 6, 2026",
             "live_status": "is_upcoming"},
            {"id": "now", "title": "Brookline School Committee Meeting - September 20, 2026",
             "live_status": "is_live"},
            None,
        ]},
        "https://www.youtube.com/playlist?list=PL1": {"entries": [
            {"id": "p1", "title": "School Committee Meeting 4/15/2026"},
        ]},
    }
    asked: List[str] = []

    class FakeYoutubeDL:
        def __init__(self, options): pass
        def __enter__(self): return self
        def __exit__(self, *exc): return False
        def extract_info(self, url, download=False):
            asked.append(url)
            return tabs.get(url)        # None is what a missing tab looks like

    original = sys.modules.get("yt_dlp")
    sys.modules["yt_dlp"] = types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)
    try:
        ids = [v.video_id for v in yc.list_via_ytdlp("https://www.youtube.com/@bigtv")]
        check("both tabs are asked for",
              asked == ["https://www.youtube.com/@bigtv/videos",
                        "https://www.youtube.com/@bigtv/streams"], str(asked))
        check("a meeting that was broadcast live is listed", "live" in ids, str(ids))
        check("a video on both tabs is listed once", ids.count("both") == 1, str(ids))
        check("a stream that has not happened yet is left for the next scan",
              "soon" not in ids and "now" not in ids, str(ids))

        del asked[:]
        ids = [v.video_id for v in yc.list_via_ytdlp("https://www.youtube.com/@nostreams")]
        check("a channel with neither tab lists nothing and does not raise",
              ids == [] and len(asked) == 2, f"{ids} {asked}")

        del asked[:]
        ids = [v.video_id for v in
               yc.list_via_ytdlp("https://www.youtube.com/playlist?list=PL1")]
        check("a playlist is listed as given, once",
              ids == ["p1"] and asked == ["https://www.youtube.com/playlist?list=PL1"],
              f"{ids} {asked}")
    finally:
        if original is not None:
            sys.modules["yt_dlp"] = original
        else:
            del sys.modules["yt_dlp"]


def test_a_gap_in_the_record_takes_two_witnesses() -> None:
    print("\nno captions, versus could not find out")
    try:
        from collectors.youtube_collector import (
            TranscriptFetchFailed, TranscriptUnavailable, YouTubeCollector,
        )
    except ImportError as exc:       # the collector's own dependencies
        print(f"  skipped: {exc}")
        return

    captions = [{"text": "the motion carries", "start": 754.2, "duration": 2.1}]

    def reader(outcome):
        def read(video_id):
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        return read

    def verdict(api, ytdlp):
        collector = YouTubeCollector()
        collector._captions_via_api = reader(api)
        collector._captions_via_ytdlp = reader(ytdlp)
        try:
            return collector.fetch_captions("abc")
        except (TranscriptUnavailable, TranscriptFetchFailed) as exc:
            return type(exc).__name__

    none, blocked = TranscriptUnavailable("TranscriptsDisabled"), TranscriptFetchFailed("IpBlocked")
    check("the first reader's captions are used", verdict((captions, "api"), blocked)[1] == "api")
    check("the second reader is asked when the first is refused",
          verdict(blocked, (captions, "yt-dlp"))[1] == "yt-dlp")
    check("the second reader can overrule a first that found nothing",
          verdict(none, (captions, "yt-dlp"))[1] == "yt-dlp")
    check("both finding none is a gap", verdict(none, none) == "TranscriptUnavailable")
    check("one finding none while the other was refused is not",
          verdict(blocked, none) == "TranscriptFetchFailed")
    check("nor is the other way round", verdict(none, blocked) == "TranscriptFetchFailed")
    check("both refused is a failure", verdict(blocked, blocked) == "TranscriptFetchFailed")

    collector = YouTubeCollector()
    collector.fetch_captions = reader(blocked)
    check("the old callers still get None", collector.get_transcript("abc") is None)
    try:
        collector.get_transcript("abc", strict=True)
        raised = False
    except TranscriptFetchFailed:
        raised = True
    check("and strict callers get the reason", raised)

    collector.fetch_captions = reader((captions, "api"))
    transcript = collector.get_transcript("abc")
    check("the captions are handed on as they came",
          transcript["captions"] == captions and transcript["segments"][0]["start_time"] == 0)


def test_state_survives_a_restart() -> None:
    print("\nsync state persistence")
    with tempfile.TemporaryDirectory() as tmp:
        state = SyncState(source_id="s4", channel_url="https://youtube.com/@bigtv")
        state.mark_ingested("a")
        state.mark_skipped("b")
        state.errors.append({"video_id": "c", "error": "no transcript available"})
        advance_cursor(state, [VideoRecord(video_id="a", title="t", url="u",
                                           published_at="2026-04-16")])
        save_state("proj", state, data_root=tmp)

        reloaded = load_state("proj", "s4", data_root=tmp)
        check("ingested ids survive", reloaded.ingested_video_ids == ["a"])
        check("skipped ids survive", reloaded.skipped_video_ids == ["b"])
        check("cursor survives", reloaded.last_published_at == "2026-04-16")
        check("errors survive, so gaps stay visible",
              len(reloaded.errors) == 1 and reloaded.errors[0]["video_id"] == "c")
        check("a video is not re-ingested after restart", "a" in reloaded.seen)

    missing = load_state("nope", "nope", data_root="/tmp/does-not-exist-at-all")
    check("a missing state file is an empty state, not a crash",
          missing.ingested_video_ids == [])


def test_video_embeds() -> None:
    print("\nplaying the cited moment")
    chunk = CivicChunk(
        text="the board voted", source_type=SourceType.MEETING_TRANSCRIPT,
        body="Select Board", meeting_date="2026-05-12",
        start_time=4422.0, end_time=4500.0,
        url="https://www.youtube.com/watch?v=abc123", speaker="Jane Smith",
    )
    embed = embed_info(chunk)
    check("embed produced", embed is not None)
    check("starts at the cited second", "start=4422" in embed["embed_url"], embed["embed_url"])
    check("uses the privacy-enhanced host",
          "youtube-nocookie.com" in embed["embed_url"], embed["embed_url"])
    check("suppresses related videos", "rel=0" in embed["embed_url"])
    check("human timestamp included", embed["start_label"] == "1:13:42", embed["start_label"])
    check("thumbnail for the click-to-load poster", "ytimg.com" in embed["thumbnail_url"])
    check("a watch link is offered too", "watch?v=abc123" in embed["watch_url"])

    document = CivicChunk(text="x", source_type=SourceType.MUNICIPAL_DOCUMENT,
                          title="Plan", page=7, url="https://e.org/p.pdf")
    check("documents produce no embed", embed_info(document) is None)

    no_video = CivicChunk(text="x", source_type=SourceType.MEETING_TRANSCRIPT,
                          body="Select Board", url="https://example.org/minutes.html")
    check("a meeting with no video produces no embed", embed_info(no_video) is None)

    citations = build_citations([chunk, document])
    check("citation carries the embed", citations[0].to_dict()["embed"] is not None)
    check("document citation has none", citations[1].to_dict()["embed"] is None)


def main() -> int:
    print("=" * 62)
    print("Meeting archive tests")
    print("=" * 62)
    for fn in [
        test_title_parsing,
        test_title_date_beats_upload_date,
        test_year_inferred_when_title_omits_it,
        test_longest_board_alias_wins,
        test_non_meetings_are_recognized,
        test_iso_date_not_misread_as_month_day,
        test_titles_as_a_real_channel_writes_them,
        test_a_programme_about_a_board_is_not_the_board,
        test_a_community_supplies_its_own_boards,
        test_sync_plan_skips_what_it_already_has,
        test_a_board_list_that_learns_finds_what_it_missed,
        test_a_channel_is_listed_once_not_every_run,
        test_cursor_limits_the_scan,
        test_body_override_beats_the_title,
        test_a_channel_scan_includes_its_live_streams,
        test_a_gap_in_the_record_takes_two_witnesses,
        test_state_survives_a_restart,
        test_video_embeds,
    ]:
        fn()
    print("\n" + "=" * 62)
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    for name in FAIL:
        print(f"  FAILED: {name}")
    return 1 if FAIL else 0


def test_all() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
