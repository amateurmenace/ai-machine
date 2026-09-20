"""
Scanning a public-access channel for meetings.

An organization like Brookline Interactive Group holds the recording of every
Select Board and School Committee meeting, plus subcommittees, going back years.
Two jobs follow from that, and they are different jobs:

* **Backfill** — walk the archive once, oldest to newest, and ingest it. Slow,
  large, run overnight.
* **Incremental sync** — every few hours, notice what is new and ingest only
  that. Fast, small, run on a schedule.

Both come from one listing function, and the difference is a cursor.

Two listing paths:

* **YouTube Data API** when a key is set. Exact publish dates, 50 items a page,
  and a cheap way to walk a whole channel. The uploads playlist is the trick:
  every channel has one, and paging it is far cheaper in quota than search.
* **yt-dlp** otherwise. No key and no quota, and it handles channels, playlists
  and handles alike. Flat extraction gives titles and ids quickly but not
  reliable publish dates, which is one more reason the date in the title matters.

Sync state lives next to the project so a restart does not re-ingest a thousand
meetings. It records the ids already seen, so a video re-uploaded under a new
title is picked up while an unchanged one is skipped.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from collectors.meeting_titles import DEFAULT_BODIES, MeetingTitle, parse_meeting_title

YOUTUBE_API_KEY_ENV = "YOUTUBE_API_KEY"

# yt-dlp gets slow on very large channels; this bounds a single scan. Backfill
# passes a higher limit deliberately.
DEFAULT_SCAN_LIMIT = 500


@dataclass
class VideoRecord:
    """One video, before any transcript work."""

    video_id: str
    title: str
    url: str
    published_at: str = ""          # YYYY-MM-DD when known
    duration_seconds: Optional[int] = None
    description: str = ""

    # Filled in by the title parser.
    body: str = ""
    meeting_date: str = ""
    date_source: str = "none"
    is_meeting: bool = False
    confidence: float = 0.0
    notes: List[str] = field(default_factory=list)

    def apply(self, parsed: MeetingTitle) -> "VideoRecord":
        self.body = parsed.body
        self.meeting_date = parsed.meeting_date
        self.date_source = parsed.date_source
        self.is_meeting = parsed.is_meeting
        self.confidence = parsed.confidence
        self.notes = list(parsed.notes)
        return self

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SyncState:
    """What a previous scan of this source already handled."""

    source_id: str
    channel_url: str = ""
    last_synced_at: str = ""
    last_published_at: str = ""
    seen_video_ids: List[str] = field(default_factory=list)
    ingested_video_ids: List[str] = field(default_factory=list)
    skipped_video_ids: List[str] = field(default_factory=list)
    total_scanned: int = 0
    errors: List[Dict[str, str]] = field(default_factory=list)

    @property
    def seen(self) -> set:
        return set(self.seen_video_ids)

    def mark_seen(self, video_id: str) -> None:
        if video_id not in self.seen_video_ids:
            self.seen_video_ids.append(video_id)

    def mark_ingested(self, video_id: str) -> None:
        self.mark_seen(video_id)
        if video_id not in self.ingested_video_ids:
            self.ingested_video_ids.append(video_id)

    def mark_skipped(self, video_id: str, reason: str = "") -> None:
        self.mark_seen(video_id)
        if video_id not in self.skipped_video_ids:
            self.skipped_video_ids.append(video_id)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def state_path(project_id: str, source_id: str, data_root: str = "./data") -> Path:
    return Path(data_root) / project_id / "sync" / f"{source_id}.json"


def load_state(project_id: str, source_id: str, channel_url: str = "",
               data_root: str = "./data") -> SyncState:
    path = state_path(project_id, source_id, data_root)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            known = {f for f in SyncState.__dataclass_fields__}  # type: ignore[attr-defined]
            return SyncState(**{k: v for k, v in data.items() if k in known})
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return SyncState(source_id=source_id, channel_url=channel_url)


def save_state(project_id: str, state: SyncState, data_root: str = "./data") -> None:
    path = state_path(project_id, state.source_id, data_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
    except OSError:
        # Losing sync state costs a re-scan, not data. Never fail a sync for it.
        pass


# --- listing --------------------------------------------------------------


_CHANNEL_ID_RE = re.compile(r"(?:channel/)(UC[\w-]{22})")
_HANDLE_RE = re.compile(r"youtube\.com/@([\w.-]+)")
_PLAYLIST_RE = re.compile(r"[?&]list=([\w-]+)")


def _iso_to_date(value: str) -> str:
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(value or ""))
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}" if match else ""


def list_via_data_api(channel_url: str, api_key: str, limit: int = DEFAULT_SCAN_LIMIT,
                      published_after: Optional[str] = None) -> List[VideoRecord]:
    """List a channel's uploads through the YouTube Data API."""
    from googleapiclient.discovery import build

    youtube = build("youtube", "v3", developerKey=api_key, cache_discovery=False)

    playlist_match = _PLAYLIST_RE.search(channel_url)
    if playlist_match:
        uploads_playlist = playlist_match.group(1)
    else:
        channel_match = _CHANNEL_ID_RE.search(channel_url)
        handle_match = _HANDLE_RE.search(channel_url)
        if channel_match:
            request = youtube.channels().list(part="contentDetails", id=channel_match.group(1))
        elif handle_match:
            request = youtube.channels().list(part="contentDetails",
                                              forHandle="@" + handle_match.group(1))
        else:
            raise ValueError(
                f"could not find a channel id, handle or playlist in {channel_url!r}"
            )
        items = request.execute().get("items", [])
        if not items:
            raise ValueError(f"YouTube returned no channel for {channel_url!r}")
        uploads_playlist = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    videos: List[VideoRecord] = []
    page_token = None
    while len(videos) < limit:
        response = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist,
            maxResults=min(50, limit - len(videos)),
            pageToken=page_token,
        ).execute()

        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            content = item.get("contentDetails", {})
            video_id = content.get("videoId") or snippet.get("resourceId", {}).get("videoId")
            if not video_id:
                continue
            published = _iso_to_date(
                content.get("videoPublishedAt") or snippet.get("publishedAt", "")
            )
            # The uploads playlist is newest-first, so once we are older than
            # the cursor every remaining page is older too.
            if published_after and published and published <= published_after:
                return videos
            videos.append(VideoRecord(
                video_id=video_id,
                title=snippet.get("title", ""),
                url=f"https://www.youtube.com/watch?v={video_id}",
                published_at=published,
                description=(snippet.get("description", "") or "")[:2000],
            ))

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return videos


def list_via_ytdlp(channel_url: str, limit: int = DEFAULT_SCAN_LIMIT) -> List[VideoRecord]:
    """List a channel or playlist with yt-dlp. No key, no quota."""
    from yt_dlp import YoutubeDL

    url = channel_url
    # A bare channel or handle URL resolves to the About tab; /videos is the list.
    if re.search(r"youtube\.com/(@[\w.-]+|channel/UC[\w-]{22}|c/[\w-]+|user/[\w-]+)/?$", url):
        url = url.rstrip("/") + "/videos"

    options = {
        "extract_flat": "in_playlist",
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "playlistend": limit,
        "ignoreerrors": True,
    }

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)

    videos: List[VideoRecord] = []
    for entry in (info or {}).get("entries", []) or []:
        if not entry:
            continue
        video_id = entry.get("id")
        if not video_id:
            continue
        duration = entry.get("duration")
        videos.append(VideoRecord(
            video_id=video_id,
            title=entry.get("title", "") or "",
            url=entry.get("url") or f"https://www.youtube.com/watch?v={video_id}",
            published_at=_iso_to_date(entry.get("upload_date", "") or ""),
            duration_seconds=int(duration) if duration else None,
            description=(entry.get("description") or "")[:2000],
        ))
    return videos


def list_channel_videos(
    channel_url: str,
    api_key: Optional[str] = None,
    limit: int = DEFAULT_SCAN_LIMIT,
    published_after: Optional[str] = None,
    bodies: Optional[Dict[str, Sequence[str]]] = None,
) -> List[VideoRecord]:
    """List a channel's videos with meeting metadata parsed from each title."""
    api_key = api_key or os.getenv(YOUTUBE_API_KEY_ENV)

    if api_key:
        try:
            videos = list_via_data_api(channel_url, api_key, limit, published_after)
        except Exception:
            # A bad key, an exhausted quota or a renamed channel should fall
            # back rather than stop a town's archive from syncing.
            videos = list_via_ytdlp(channel_url, limit)
    else:
        videos = list_via_ytdlp(channel_url, limit)

    for video in videos:
        video.apply(parse_meeting_title(video.title, video.published_at, bodies))

    return videos


# --- planning -------------------------------------------------------------


@dataclass
class SyncPlan:
    """What a scan decided to do, before any of it is done."""

    scanned: int = 0
    new_videos: List[VideoRecord] = field(default_factory=list)
    already_ingested: int = 0
    skipped_not_meetings: List[VideoRecord] = field(default_factory=list)
    skipped_low_confidence: List[VideoRecord] = field(default_factory=list)
    error: Optional[str] = None

    def summary(self) -> Dict[str, Any]:
        return {
            "scanned": self.scanned,
            "to_ingest": len(self.new_videos),
            "already_ingested": self.already_ingested,
            "skipped_not_meetings": len(self.skipped_not_meetings),
            "skipped_low_confidence": len(self.skipped_low_confidence),
            "error": self.error,
            "bodies_found": sorted({v.body for v in self.new_videos if v.body}),
            "date_range": (
                [min(v.meeting_date for v in self.new_videos if v.meeting_date),
                 max(v.meeting_date for v in self.new_videos if v.meeting_date)]
                if any(v.meeting_date for v in self.new_videos) else None
            ),
        }


def plan_sync(
    channel_url: str,
    state: SyncState,
    api_key: Optional[str] = None,
    limit: int = DEFAULT_SCAN_LIMIT,
    incremental: bool = True,
    min_confidence: float = 0.0,
    meetings_only: bool = True,
    bodies: Optional[Dict[str, Sequence[str]]] = None,
    body_override: str = "",
) -> SyncPlan:
    """Decide what to ingest without ingesting anything.

    Separating the decision from the work is what makes a backfill safe to look
    at first: an operator can see that a scan found 1,400 videos, classified
    1,190 as meetings across six boards, and is about to skip 210, before
    committing hours of transcript fetching.
    """
    plan = SyncPlan()

    cursor = state.last_published_at if (incremental and state.last_published_at) else None
    try:
        videos = list_channel_videos(channel_url, api_key=api_key, limit=limit,
                                     published_after=cursor, bodies=bodies)
    except Exception as exc:
        plan.error = f"{type(exc).__name__}: {exc}"
        return plan

    plan.scanned = len(videos)
    seen = state.seen

    for video in videos:
        if body_override:
            # A source pointed at one board's playlist knows its own body, and
            # that beats anything guessed from a title.
            video.body = body_override
            video.confidence = max(video.confidence, 0.9)

        if video.video_id in seen:
            plan.already_ingested += 1
            continue
        if meetings_only and not video.is_meeting and not body_override:
            plan.skipped_not_meetings.append(video)
            continue
        if video.confidence < min_confidence:
            plan.skipped_low_confidence.append(video)
            continue
        plan.new_videos.append(video)

    # Oldest first, so an interrupted backfill leaves a contiguous archive
    # rather than a scatter of recent meetings.
    plan.new_videos.sort(key=lambda v: v.meeting_date or v.published_at or "")
    return plan


def advance_cursor(state: SyncState, videos: Sequence[VideoRecord]) -> None:
    """Move the incremental cursor to the newest video handled."""
    dates = [v.published_at for v in videos if v.published_at]
    if dates:
        newest = max(dates)
        if newest > (state.last_published_at or ""):
            state.last_published_at = newest
    state.last_synced_at = datetime.now().isoformat(timespec="seconds")
    state.total_scanned += len(videos)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage: python3 -m collectors.youtube_channel <channel-or-playlist-url>")
        print("\nLists what a sync would ingest. Nothing is written.")
        raise SystemExit(2)

    url = sys.argv[1]
    state = SyncState(source_id="preview", channel_url=url)
    plan = plan_sync(url, state, limit=50, incremental=False)

    if plan.error:
        print(f"scan failed: {plan.error}")
        raise SystemExit(1)

    print(json.dumps(plan.summary(), indent=2))
    print()
    for video in plan.new_videos[:20]:
        print(f"  {video.meeting_date or '??????????'}  {video.body or '(no board)':<26} "
              f"{video.title[:50]}")
