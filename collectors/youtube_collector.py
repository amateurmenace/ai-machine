"""
YouTube Transcript Collector
Collects transcripts from YouTube videos and playlists
Uses multiple fallback methods: youtube-transcript-api, yt-dlp
"""

import re
import subprocess
import json
import os
from typing import List, Dict, Optional, Tuple
from youtube_transcript_api import YouTubeTranscriptApi
from googleapiclient.discovery import build
from datetime import datetime


class TranscriptUnavailable(Exception):
    """The video has no captions. A gap in the public record, and a lasting one."""


class TranscriptFetchFailed(Exception):
    """The captions could not be fetched this time.

    This says nothing about whether they exist. YouTube refusing the request,
    a timeout and a dropped connection all end up here, and none of them is a
    fact about the meeting. The difference from TranscriptUnavailable is the
    whole point of having two: a caller that records this one as "the meeting
    has no transcript" turns a bad night on the network into a hole in the
    archive that nothing will ever go back and fill.
    """


class TranscriptBlocked(TranscriptFetchFailed):
    """YouTube is refusing this machine: IpBlocked, RequestBlocked, HTTP 429.

    A failure like any other as far as the record goes, and unlike any other in
    what to do next. A timeout is worth retrying in a minute. A block gets
    longer with every request made during it, so the only useful response is to
    stop asking and come back in hours.
    """


# What a refusal looks like from yt-dlp, which reports it as prose.
_BLOCK_SIGNS = ("429", "too many requests", "not a bot", "sign in to confirm",
                "ipblocked", "requestblocked", "rate limit", "rate-limit")


def _is_a_block(error: BaseException) -> bool:
    text = f"{type(error).__name__} {error}".lower()
    return any(sign in text for sign in _BLOCK_SIGNS)


class YouTubeCollector:
    """Collects transcripts from YouTube playlists and videos with data protection limits"""

    # Data protection limits
    MAX_BYTES = 120 * 1024 * 1024  # 120MB max per source
    MAX_WORDS = 10_000_000  # 10 million words max per source

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.youtube = None
        self.total_bytes = 0
        self.total_words = 0
        # Set when either reader was refused during the last fetch, even if the
        # other one got through. On Brookline's first backfill the first
        # refusal came two videos before the second reader was refused too; it
        # was a warning, and nothing was listening for it.
        self.last_block = ""
        if api_key:
            self.youtube = build('youtube', 'v3', developerKey=api_key)

    def check_limits(self) -> tuple[bool, str]:
        """Check if data protection limits have been reached"""
        if self.total_bytes >= self.MAX_BYTES:
            return True, f"Byte limit reached ({self.total_bytes / (1024*1024):.1f}MB / {self.MAX_BYTES / (1024*1024):.0f}MB)"
        if self.total_words >= self.MAX_WORDS:
            return True, f"Word limit reached ({self.total_words:,} / {self.MAX_WORDS:,} words)"
        return False, ""

    def reset_limits(self):
        """Reset tracking counters for a new source"""
        self.total_bytes = 0
        self.total_words = 0
    
    def extract_playlist_id(self, url: str) -> Optional[str]:
        """Extract playlist ID from YouTube URL"""
        patterns = [
            r'list=([a-zA-Z0-9_-]+)',
            r'playlist\?list=([a-zA-Z0-9_-]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL"""
        patterns = [
            r'(?:v=|/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed/)([0-9A-Za-z_-]{11})',
            r'(?:watch\?v=)([0-9A-Za-z_-]{11})'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def get_playlist_videos_ytdlp(self, playlist_url: str, max_results: int = 50) -> List[Dict]:
        """Get all videos from a playlist using yt-dlp (no API key needed)"""
        try:
            cmd = [
                "yt-dlp",
                "--flat-playlist",
                "--dump-json",
                "--playlist-end", str(max_results),
                playlist_url
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                print(f"yt-dlp error: {result.stderr}")
                return []

            videos = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        data = json.loads(line)
                        video_info = {
                            'video_id': data.get('id', ''),
                            'title': data.get('title', 'Unknown'),
                            'description': data.get('description', ''),
                            'published_at': data.get('upload_date', ''),
                            'thumbnail': data.get('thumbnail', '')
                        }
                        videos.append(video_info)
                    except json.JSONDecodeError:
                        continue

            return videos
        except subprocess.TimeoutExpired:
            print("yt-dlp timed out while fetching playlist")
            return []
        except Exception as e:
            print(f"Error fetching playlist with yt-dlp: {e}")
            return []

    def get_playlist_videos(self, playlist_id: str, max_results: int = 50) -> List[Dict]:
        """Get all videos from a playlist (tries API first, falls back to yt-dlp)"""
        # Try API method if available
        if self.youtube:
            try:
                videos = []
                next_page_token = None

                while len(videos) < max_results:
                    request = self.youtube.playlistItems().list(
                        part='snippet,contentDetails',
                        playlistId=playlist_id,
                        maxResults=min(50, max_results - len(videos)),
                        pageToken=next_page_token
                    )

                    response = request.execute()

                    for item in response['items']:
                        video_info = {
                            'video_id': item['contentDetails']['videoId'],
                            'title': item['snippet']['title'],
                            'description': item['snippet']['description'],
                            'published_at': item['snippet']['publishedAt'],
                            'thumbnail': item['snippet']['thumbnails']['default']['url']
                        }
                        videos.append(video_info)

                    next_page_token = response.get('nextPageToken')
                    if not next_page_token:
                        break

                return videos
            except Exception as e:
                print(f"YouTube API error: {e}, falling back to yt-dlp")

        # Fallback to yt-dlp method (no API key needed)
        print("Using yt-dlp to fetch playlist (no API key required)")
        playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
        return self.get_playlist_videos_ytdlp(playlist_url, max_results)
    
    @staticmethod
    def _items_from_json3(data: Dict) -> List[Dict]:
        """YouTube's json3 captions as text/start/duration items."""
        items = []
        for event in data.get('events', []):
            if 'segs' not in event:
                continue
            text = ''.join(seg.get('utf8', '') for seg in event['segs']).strip()
            if text:
                items.append({
                    'text': text,
                    'start': event.get('tStartMs', 0) / 1000,
                    'duration': event.get('dDurationMs', 0) / 1000,
                })
        return items

    def _captions_via_api(self, video_id: str) -> Tuple[List[Dict], str]:
        """Captions through youtube-transcript-api: one light request."""
        from youtube_transcript_api import _errors as errors

        try:
            api = YouTubeTranscriptApi()
            try:
                fetched = api.fetch(video_id, languages=['en', 'en-US', 'en-GB'])
            except errors.NoTranscriptFound:
                # No English track. Take what there is rather than nothing.
                tracks = list(api.list(video_id))
                if not tracks:
                    raise
                fetched = tracks[0].fetch()
            items = fetched.to_raw_data()
        except (errors.TranscriptsDisabled, errors.NoTranscriptFound) as exc:
            raise TranscriptUnavailable(type(exc).__name__) from exc
        except (errors.RequestBlocked, errors.IpBlocked) as exc:
            raise TranscriptBlocked(type(exc).__name__) from exc
        except Exception as exc:
            # IpBlocked, RequestBlocked, PoTokenRequired, a timeout, and an API
            # that changed underneath us (which is how this path once failed on
            # every video without anyone noticing) are all the same thing here:
            # not a fact about the video.
            raise TranscriptFetchFailed(f"{type(exc).__name__}: {str(exc)[:160]}") from exc

        if not items:
            raise TranscriptUnavailable("the caption track is empty")
        kind = 'auto' if fetched.is_generated else 'manual'
        return items, f'youtube_transcript_api-{fetched.language_code}-{kind}'

    def _captions_via_ytdlp(self, video_id: str) -> Tuple[List[Dict], str]:
        """Captions through yt-dlp, which keeps up with YouTube when the API lags."""
        from yt_dlp import YoutubeDL

        options = {'skip_download': True, 'quiet': True, 'no_warnings': True}
        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(f'https://www.youtube.com/watch?v={video_id}',
                                        download=False) or {}
                # A person's captions beat the machine's, and the language that
                # was spoken beats a translation of it.
                manual, auto = info.get('subtitles') or {}, info.get('automatic_captions') or {}
                formats, method = None, ''
                for tracks, kind in ((manual, 'manual'), (auto, 'auto')):
                    for language in ('en-orig', 'en', 'en-US', 'en-GB'):
                        if tracks.get(language):
                            formats, method = tracks[language], f'yt-dlp-{language}-{kind}'
                            break
                    if formats:
                        break
                if not formats:
                    raise TranscriptUnavailable('no English caption track')
                json3 = next((f for f in formats if f.get('ext') == 'json3'), None)
                if not json3:
                    raise TranscriptFetchFailed('captions exist, but not in a format this reads')
                data = json.loads(ydl.urlopen(json3['url']).read().decode('utf-8'))
        except (TranscriptUnavailable, TranscriptFetchFailed):
            raise
        except Exception as exc:
            kind = TranscriptBlocked if _is_a_block(exc) else TranscriptFetchFailed
            raise kind(f"{type(exc).__name__}: {str(exc)[:160]}") from exc

        items = self._items_from_json3(data)
        if not items:
            raise TranscriptUnavailable('the caption track is empty')
        return items, method

    def fetch_captions(self, video_id: str) -> Tuple[List[Dict], str]:
        """One video's captions, as the few-second items YouTube stores.

        Returns ``(items, method)``. Raises TranscriptUnavailable only when two
        independent readers both reached the video and both found no captions.
        Anything short of that is TranscriptFetchFailed, because "this meeting
        has no transcript" is a claim about the public record and one reader
        having a bad day is not evidence for it. yt-dlp in particular will
        report no caption tracks for a video that has them when YouTube decides
        to withhold them from it.
        """
        api_found_none = False
        self.last_block = ""
        try:
            return self._captions_via_api(video_id)
        except TranscriptUnavailable:
            api_found_none = True
        except TranscriptFetchFailed as exc:
            if isinstance(exc, TranscriptBlocked):
                self.last_block = f"youtube-transcript-api: {exc}"
            print(f"youtube-transcript-api could not read {video_id} "
                  f"({str(exc).splitlines()[0][:80]}); trying yt-dlp")

        try:
            return self._captions_via_ytdlp(video_id)
        except TranscriptBlocked as exc:
            self.last_block = f"yt-dlp: {exc}"
            raise
        except TranscriptUnavailable as exc:
            if api_found_none:
                raise
            raise TranscriptFetchFailed(
                f"yt-dlp saw no captions ({exc}), but the first reader never reached the "
                f"video, and one opinion is not enough to call it a gap") from exc

    def get_transcript(self, video_id: str, strict: bool = False) -> Optional[Dict]:
        """Get transcript for a single video.

        Returns None when there is nothing to return, which is what the
        playlist and single-video paths have always expected. ``strict`` raises
        TranscriptUnavailable or TranscriptFetchFailed instead, for callers that
        keep a record of what is missing and must not confuse the two.
        """
        try:
            transcript_list, method_used = self.fetch_captions(video_id)
        except (TranscriptUnavailable, TranscriptFetchFailed) as exc:
            if strict:
                raise
            print(f"No transcript for {video_id}: {type(exc).__name__}: {exc}")
            return None

        print(f"Got transcript for {video_id} using method: {method_used}")

        try:
            # Combine transcript segments
            full_text = ' '.join([segment['text'] for segment in transcript_list])

            # Get timestamps for sections
            segments = []
            current_segment = []
            current_start = 0

            for i, item in enumerate(transcript_list):
                current_segment.append(item['text'])

                # Create segment every ~2 minutes
                if i > 0 and i % 40 == 0:
                    segments.append({
                        'start_time': current_start,
                        'end_time': item['start'],
                        'text': ' '.join(current_segment)
                    })
                    current_segment = []
                    current_start = item['start']

            # Add final segment
            if current_segment:
                segments.append({
                    'start_time': current_start,
                    'end_time': transcript_list[-1]['start'] if transcript_list else 0,
                    'text': ' '.join(current_segment)
                })

            return {
                'video_id': video_id,
                'full_transcript': full_text,
                'segments': segments,
                # The captions as YouTube stores them, a few seconds each. The
                # two minute segments above are fine for reading and too coarse
                # for citing: a link that opens "where it was said" should not
                # open two minutes before it.
                'captions': transcript_list,
                'duration': transcript_list[-1]['start'] if transcript_list else 0,
                'method': method_used
            }

        except Exception as e:
            print(f"Error processing transcript for {video_id}: {e}")
            return None
    
    def collect_playlist(self, playlist_url: str, progress_callback=None) -> List[Dict]:
        """Collect all transcripts from a playlist with data protection limits"""
        playlist_id = self.extract_playlist_id(playlist_url)
        if not playlist_id:
            raise ValueError("Invalid playlist URL")

        # Reset limits for new collection
        self.reset_limits()

        # Get videos
        videos = self.get_playlist_videos(playlist_id)

        # Get transcripts
        results = []
        limit_message = None

        for i, video in enumerate(videos):
            # Check data protection limits
            limit_reached, limit_msg = self.check_limits()
            if limit_reached:
                limit_message = limit_msg
                print(f"Stopping playlist collection: {limit_msg}")
                break

            if progress_callback:
                mb_used = self.total_bytes / (1024 * 1024)
                progress_callback(i, len(videos), video['title'],
                                 f"{mb_used:.1f}MB / {self.total_words:,} words")

            transcript = self.get_transcript(video['video_id'])
            if transcript:
                # Track bytes and words
                transcript_text = transcript.get('full_transcript', '')
                self.total_bytes += len(transcript_text.encode('utf-8'))
                self.total_words += len(transcript_text.split())

                results.append({
                    **video,
                    'transcript': transcript,
                    'url': f"https://youtube.com/watch?v={video['video_id']}"
                })

        # Log final stats
        mb_used = self.total_bytes / (1024 * 1024)
        print(f"Playlist collection complete: {len(results)} videos, {mb_used:.1f}MB, {self.total_words:,} words")
        if limit_message:
            print(f"Note: {limit_message}")

        return results
    
    def collect_video(self, video_url: str, strict: bool = False) -> Optional[Dict]:
        """Collect transcript from a single video. See get_transcript for ``strict``."""
        video_id = self.extract_video_id(video_url)
        if not video_id:
            raise ValueError("Invalid video URL")

        transcript = self.get_transcript(video_id, strict=strict)
        if transcript:
            return {
                'video_id': video_id,
                'url': video_url,
                'transcript': transcript
            }
        return None


# Example usage
if __name__ == "__main__":
    collector = YouTubeCollector()
    
    # Test with a single video
    video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    result = collector.collect_video(video_url)
    
    if result:
        print(f"Collected transcript: {len(result['transcript']['full_transcript'])} characters")
