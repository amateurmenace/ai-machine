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
    
    def discover_sources(self, municipality: str, neighborhood: Optional[str] = None, custom_prompt: Optional[str] = None) -> Dict:
        """Use AI to discover relevant data sources for a municipality"""

        location = f"{municipality}"
        if neighborhood:
            location = f"{neighborhood}, {municipality}"

        # Allow custom search instructions
        custom_instructions = ""
        if custom_prompt:
            custom_instructions = f"""
ADDITIONAL SEARCH INSTRUCTIONS FROM USER:
{custom_prompt}

Use these instructions to guide your search. For example, if the user mentions specific topics, organizations, or types of sources, prioritize finding those.
"""

        prompt = f"""You are helping set up a local AI assistant for {location}.
{custom_instructions}
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
        ]) if sources else "No sources provided yet"

        prompt = f"""Generate a system prompt for a local AI assistant for {municipality}.

Data Sources Available:
{sources_summary}

IMPORTANT: Return ONLY the system prompt text itself. Do NOT include any introduction like "Here's a system prompt..." or explanatory text. Start directly with "You are {municipality} AI..." or similar.

The system prompt should follow this structure:

You are [Name] AI, the virtual assistant for [Location].

PERSONALITY TRAITS:
- [Trait 1]
- [Trait 2]
- [Trait 3]
- [More traits...]

TONE:
- [Tone description 1]
- [Tone description 2]
- [More tone guidelines...]

CAPABILITIES YOU HIGHLIGHT:
- [Capability 1]
- [Capability 2]
- [More capabilities...]

LIMITATIONS YOU ACKNOWLEDGE:
- You're an AI assistant, not an official representative
- For legal/official matters, you direct people to proper departments
- You can't make decisions on behalf of residents
- You encourage people to verify critical information

SPECIAL FEATURES:
- [Feature 1 based on available data sources]
- [Feature 2]
- [More features...]

Make it warm, community-focused, and appropriate for a civic assistant. Return ONLY the system prompt, nothing else."""

        try:
            if self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You generate system prompts for AI assistants. Return ONLY the system prompt text, no explanations or introductions."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7
                )
                result = response.choices[0].message.content

            elif self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                result = response.content[0].text
            else:
                return self._default_personality(municipality)

            # Clean up the result - remove any intro text
            result = result.strip()

            # Remove common intro patterns
            intro_patterns = [
                "Here's a system prompt",
                "Here is a system prompt",
                "Below is a system prompt",
                "I've created a system prompt",
                "The following is a system prompt",
                "System prompt for",
            ]

            for pattern in intro_patterns:
                if result.lower().startswith(pattern.lower()):
                    # Find the first newline after the intro and skip to there
                    lines = result.split('\n')
                    for i, line in enumerate(lines):
                        if line.strip().lower().startswith('you are'):
                            result = '\n'.join(lines[i:])
                            break
                    break

            return result.strip()

        except Exception as e:
            print(f"Error generating personality: {e}")
            return self._default_personality(municipality)

    def _default_personality(self, municipality: str) -> str:
        """Return a default personality prompt"""
        return f"""You are {municipality} AI, the virtual assistant for {municipality}.

PERSONALITY TRAITS:
- Warm and approachable, like a helpful neighbor
- Knowledgeable about local government, services, and community
- Patient and clear when explaining procedures
- Always accurate - you admit when you don't know something
- You encourage civic participation and community involvement

TONE:
- Professional but friendly (not overly formal)
- Use "we" when talking about the community ("our town", "our community")
- Enthusiastic about local events and initiatives
- Respectful of all community members

CAPABILITIES YOU HIGHLIGHT:
- Information from town meetings and local news
- Practical help: schedules, permits, local services
- Community events and opportunities to get involved
- Local business information and support

LIMITATIONS YOU ACKNOWLEDGE:
- You're an AI assistant, not an official town representative
- For legal/official matters, you direct people to proper departments
- You can't make decisions or file things on behalf of residents
- You encourage people to verify critical information

SPECIAL FEATURES:
- You can reference information from ingested data sources
- You provide accurate, sourced answers about local topics
- You know the context of local decisions and can explain them"""


# Example usage
if __name__ == "__main__":
    discovery = SourceDiscovery(provider="openai")
    
    result = discovery.discover_sources("Brookline, MA")
    print(json.dumps(result, indent=2))
