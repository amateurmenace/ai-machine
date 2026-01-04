"""
AI Source Discovery
Uses frontier models (OpenAI/Anthropic) to intelligently discover data sources
"""

import os
from typing import List, Dict, Optional
import json


class SourceDiscovery:
    """AI-powered discovery of local data sources"""
    
    def __init__(self, api_key: Optional[str] = None, provider: str = "openai", model: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        self.provider = provider
        
        # Set default models if not specified
        if model:
            self.model = model
        elif provider == "openai":
            self.model = "gpt-4o"
        elif provider == "anthropic":
            self.model = "claude-opus-4-20250514"
        else:
            self.model = "gpt-4o"
        
        if provider == "openai":
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
        elif provider == "anthropic":
            from anthropic import Anthropic
            self.client = Anthropic(api_key=self.api_key)
    
    def discover_sources(self, municipality: str, neighborhood: Optional[str] = None) -> Dict:
        """Use AI to discover relevant data sources for a municipality"""
        
        location = f"{municipality}"
        if neighborhood:
            location = f"{neighborhood}, {municipality}"
        
        prompt = f"""You are helping set up a local AI assistant for {location}.
        
Your task is to identify the best data sources to train this AI. Think creatively about:

1. **Official Government Sources:**
   - Town/city website URL
   - YouTube channels with meeting videos
   - Document repositories
   - Public records

2. **Local News:**
   - Local news websites
   - Community newsletters
   - Blogs

3. **Community Resources:**
   - Reddit communities
   - Facebook groups (public)
   - Local business directories
   - Community calendars

4. **Civic Data:**
   - Open data portals
   - GIS/mapping data
   - Budget documents

For {location}, provide a JSON list of recommended data sources with this structure:

```json
[
  {{
    "name": "Source name",
    "type": "youtube_playlist|website|pdf_url|rss_feed|reddit",
    "url": "actual URL",
    "description": "Why this source is valuable",
    "priority": "high|medium|low",
    "estimated_content": "How much content (e.g., '50+ meeting videos', '200+ articles')"
  }}
]
```

Be specific with actual URLs when possible. Focus on official, public, and high-quality sources.
Return ONLY the JSON array, no other text."""

        try:
            if self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that finds local civic data sources. You return only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7
                )
                content = response.choices[0].message.content
                
            elif self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4000,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                content = response.content[0].text
            
            # Extract JSON from response
            # Remove markdown code blocks if present
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            sources = json.loads(content)
            
            return {
                "location": location,
                "sources": sources,
                "total_found": len(sources)
            }
            
        except Exception as e:
            print(f"Error discovering sources: {e}")
            return {
                "location": location,
                "sources": [],
                "error": str(e)
            }
    
    def validate_source(self, url: str, source_type: str) -> Dict:
        """Validate that a source is accessible and has content"""
        import requests
        from urllib.parse import urlparse
        
        result = {
            "url": url,
            "type": source_type,
            "valid": False,
            "error": None
        }
        
        try:
            # Basic URL validation
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                result["error"] = "Invalid URL format"
                return result
            
            # Try to access the URL
            response = requests.head(url, timeout=10, allow_redirects=True)
            
            if response.status_code < 400:
                result["valid"] = True
                result["content_type"] = response.headers.get('content-type', '')
                result["status_code"] = response.status_code
            else:
                result["error"] = f"HTTP {response.status_code}"
                
        except requests.exceptions.Timeout:
            result["error"] = "Request timeout"
        except requests.exceptions.RequestException as e:
            result["error"] = str(e)
        except Exception as e:
            result["error"] = f"Validation error: {str(e)}"
        
        return result
    
    def suggest_personality(self, municipality: str, sources: List[Dict]) -> str:
        """Use AI to suggest personality traits based on the community"""
        
        sources_summary = "\n".join([
            f"- {s['name']} ({s['type']}): {s.get('description', '')}"
            for s in sources[:10]
        ])
        
        prompt = f"""Based on the following data sources for {municipality}, suggest a personality and tone for a local AI assistant.

Data Sources:
{sources_summary}

Consider:
1. The community's character (urban/suburban/rural, size, demographics)
2. The types of content available
3. The likely user needs

Provide a system prompt (2-3 paragraphs) that defines:
- Personality traits
- Tone and communication style
- Key capabilities to emphasize
- How to handle uncertainty

Make it warm, helpful, and appropriate for a civic assistant."""

        try:
            if self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert in conversational AI design and civic technology."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.8
                )
                return response.choices[0].message.content
                
            elif self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                return response.content[0].text
                
        except Exception as e:
            print(f"Error generating personality: {e}")
            return f"You are a helpful AI assistant for {municipality}, focused on providing accurate information about local services, news, and community resources."


# Example usage
if __name__ == "__main__":
    discovery = SourceDiscovery(provider="openai")
    
    result = discovery.discover_sources("Brookline, MA")
    print(json.dumps(result, indent=2))
