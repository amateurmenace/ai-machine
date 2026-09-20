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
        test_sync_plan_skips_what_it_already_has,
        test_cursor_limits_the_scan,
        test_body_override_beats_the_title,
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
