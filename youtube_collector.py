"""
YouTube Transcript Collector
Collects transcripts from YouTube videos and playlists
Uses multiple fallback methods: youtube-transcript-api, yt-dlp
"""

import re
import subprocess
import json
import tempfile
import os
from typing import List, Dict, Optional
from youtube_transcript_api import YouTubeTranscriptApi
from googleapiclient.discovery import build
from datetime import datetime


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
    
    def get_transcript_via_ytdlp(self, video_id: str) -> Optional[Dict]:
        """Fallback method using yt-dlp to get subtitles"""
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        try:
            # Create temp directory for subtitle files
            with tempfile.TemporaryDirectory() as tmpdir:
                output_template = os.path.join(tmpdir, "%(id)s")

                # Try to get subtitles using yt-dlp
                cmd = [
                    "yt-dlp",
                    "--skip-download",
                    "--write-subs",
                    "--write-auto-subs",
                    "--sub-langs", "en.*,en",
                    "--sub-format", "json3",
                    "--output", output_template,
                    video_url
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

                # Look for subtitle files
                subtitle_files = [f for f in os.listdir(tmpdir) if f.endswith('.json3')]

                if not subtitle_files:
                    # Try vtt format as fallback
                    cmd[7] = "vtt"  # Change sub-format
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                    subtitle_files = [f for f in os.listdir(tmpdir) if f.endswith('.vtt')]

                if not subtitle_files:
                    print(f"yt-dlp found no subtitles for {video_id}")
                    return None

                # Read the first available subtitle file
                subtitle_path = os.path.join(tmpdir, subtitle_files[0])

                if subtitle_path.endswith('.json3'):
                    with open(subtitle_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # Parse JSON3 format
                        segments = []
                        for event in data.get('events', []):
                            if 'segs' in event:
                                text = ''.join(seg.get('utf8', '') for seg in event['segs'])
                                if text.strip():
                                    segments.append({
                                        'text': text.strip(),
                                        'start': event.get('tStartMs', 0) / 1000,
                                        'duration': event.get('dDurationMs', 0) / 1000
                                    })
                        return segments if segments else None
                else:
                    # Parse VTT format
                    with open(subtitle_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Simple VTT parsing
                        segments = []
                        lines = content.split('\n')
                        current_text = []
                        current_start = 0

                        for line in lines:
                            if '-->' in line:
                                # Timestamp line
                                parts = line.split('-->')
                                time_str = parts[0].strip()
                                # Parse time (simplified)
                                try:
                                    time_parts = time_str.replace(',', '.').split(':')
                                    if len(time_parts) == 3:
                                        h, m, s = time_parts
                                        current_start = int(h) * 3600 + int(m) * 60 + float(s)
                                    elif len(time_parts) == 2:
                                        m, s = time_parts
                                        current_start = int(m) * 60 + float(s)
                                except:
                                    pass
                            elif line.strip() and not line.startswith('WEBVTT') and not line.strip().isdigit():
                                # Subtitle text
                                current_text.append(line.strip())
                            elif not line.strip() and current_text:
                                # End of segment
                                segments.append({
                                    'text': ' '.join(current_text),
                                    'start': current_start,
                                    'duration': 3  # Default duration
                                })
                                current_text = []

                        return segments if segments else None

        except subprocess.TimeoutExpired:
            print(f"yt-dlp timeout for {video_id}")
            return None
        except Exception as e:
            print(f"yt-dlp error for {video_id}: {e}")
            return None

    def get_transcript(self, video_id: str) -> Optional[Dict]:
        """Get transcript for a single video using multiple methods"""
        transcript_list = None
        method_used = None

        # Method 1: Try to get English transcript directly
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
            method_used = 'youtube_transcript_api-english'
        except Exception as e1:
            print(f"Method 1 (English) failed for {video_id}: {e1}")

            # Method 2: Try auto-generated English
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en-US', 'en-GB'])
                method_used = 'youtube_transcript_api-english-variant'
            except Exception as e2:
                print(f"Method 2 (English variants) failed for {video_id}: {e2}")

                # Method 3: List all available transcripts and pick the best one
                try:
                    transcript_list_obj = YouTubeTranscriptApi.list_transcripts(video_id)

                    # Try to get any generated or manual transcript
                    for transcript in transcript_list_obj:
                        try:
                            transcript_list = transcript.fetch()
                            method_used = f'youtube_transcript_api-{transcript.language_code}-{"manual" if not transcript.is_generated else "auto"}'
                            break
                        except Exception:
                            continue

                    # If still no transcript, try translation to English
                    if not transcript_list:
                        for transcript in transcript_list_obj:
                            try:
                                translated = transcript.translate('en')
                                transcript_list = translated.fetch()
                                method_used = f'youtube_transcript_api-{transcript.language_code}-translated'
                                break
                            except Exception:
                                continue
                except Exception as e3:
                    print(f"Method 3 (list/translate) failed for {video_id}: {e3}")

        # Method 4: Use yt-dlp as final fallback
        if not transcript_list:
            print(f"Trying yt-dlp fallback for {video_id}...")
            ytdlp_result = self.get_transcript_via_ytdlp(video_id)
            if ytdlp_result:
                transcript_list = ytdlp_result
                method_used = 'yt-dlp'
                print(f"yt-dlp succeeded for {video_id}")

        if not transcript_list:
            print(f"No transcript available for {video_id} after trying all methods (including yt-dlp)")
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
    
    def collect_video(self, video_url: str) -> Optional[Dict]:
        """Collect transcript from a single video"""
        video_id = self.extract_video_id(video_url)
        if not video_id:
            raise ValueError("Invalid video URL")
        
        transcript = self.get_transcript(video_id)
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
