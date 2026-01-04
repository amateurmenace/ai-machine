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
    """Collects transcripts from YouTube playlists and videos"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.youtube = None
        if api_key:
            self.youtube = build('youtube', 'v3', developerKey=api_key)
    
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
        """Get transcript for a single video"""
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            
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
                    'end_time': transcript_list[-1]['start'],
                    'text': ' '.join(current_segment)
                })
            
            return {
                'video_id': video_id,
                'full_transcript': full_text,
                'segments': segments,
                'duration': transcript_list[-1]['start'] if transcript_list else 0
            }
            
        except Exception as e:
            print(f"Error getting transcript for {video_id}: {e}")
            return None
    
    def collect_playlist(self, playlist_url: str, progress_callback=None) -> List[Dict]:
        """Collect all transcripts from a playlist"""
        playlist_id = self.extract_playlist_id(playlist_url)
        if not playlist_id:
            raise ValueError("Invalid playlist URL")
        
        # Get videos
        videos = self.get_playlist_videos(playlist_id)
        
        # Get transcripts
        results = []
        for i, video in enumerate(videos):
            if progress_callback:
                progress_callback(i, len(videos), video['title'])
            
            transcript = self.get_transcript(video['video_id'])
            if transcript:
                results.append({
                    **video,
                    'transcript': transcript,
                    'url': f"https://youtube.com/watch?v={video['video_id']}"
                })
        
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
