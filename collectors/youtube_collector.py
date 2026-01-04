"""
YouTube Transcript Collector
Collects transcripts from YouTube videos and playlists
"""

import re
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
    
    def get_playlist_videos(self, playlist_id: str, max_results: int = 50) -> List[Dict]:
        """Get all videos from a playlist"""
        if not self.youtube:
            raise ValueError("YouTube API key required for playlist access")
        
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
    
    def get_transcript(self, video_id: str) -> Optional[Dict]:
        """Get transcript for a single video using multiple methods"""
        transcript_list = None
        method_used = None

        # Method 1: Try to get English transcript directly
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
            method_used = 'english'
        except Exception as e1:
            print(f"Method 1 (English) failed for {video_id}: {e1}")

            # Method 2: Try auto-generated English
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en-US', 'en-GB'])
                method_used = 'english-variant'
            except Exception as e2:
                print(f"Method 2 (English variants) failed for {video_id}: {e2}")

                # Method 3: List all available transcripts and pick the best one
                try:
                    transcript_list_obj = YouTubeTranscriptApi.list_transcripts(video_id)

                    # Try to get any generated or manual transcript
                    for transcript in transcript_list_obj:
                        try:
                            transcript_list = transcript.fetch()
                            method_used = f'{transcript.language_code}-{"manual" if not transcript.is_generated else "auto"}'
                            break
                        except Exception:
                            continue

                    # If still no transcript, try translation to English
                    if not transcript_list:
                        for transcript in transcript_list_obj:
                            try:
                                translated = transcript.translate('en')
                                transcript_list = translated.fetch()
                                method_used = f'{transcript.language_code}-translated'
                                break
                            except Exception:
                                continue
                except Exception as e3:
                    print(f"Method 3 (list/translate) failed for {video_id}: {e3}")

        if not transcript_list:
            print(f"No transcript available for {video_id} after trying all methods")
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
