from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from datetime import datetime


class AIProvider(str, Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


# Model presets for easy selection
AVAILABLE_MODELS = {
    "ollama": [
        {"name": "llama3.1:8b", "display": "Llama 3.1 8B (Recommended)", "description": "Fast and efficient, 8GB RAM"},
        {"name": "llama3.1:70b", "display": "Llama 3.1 70B", "description": "Best quality, needs GPU"},
        {"name": "llama3.2:3b", "display": "Llama 3.2 3B", "description": "Lightweight, 4GB RAM"},
        {"name": "olmo3:8b", "display": "OLMo 3 8B", "description": "Allen AI's open model, research-focused"},
        {"name": "olmo3:13b", "display": "OLMo 3 13B", "description": "Allen AI's larger open model"},
        {"name": "mistral:7b", "display": "Mistral 7B", "description": "Fast inference"},
        {"name": "mixtral:8x7b", "display": "Mixtral 8x7B", "description": "High quality"},
        {"name": "phi3:medium", "display": "Phi-3 Medium", "description": "Microsoft's efficient model"},
        {"name": "custom", "display": "Custom Model...", "description": "Enter any Ollama model name"},
    ],
    "openai": [
        {"name": "gpt-5.2", "display": "GPT-5.2 (Latest)", "description": "OpenAI's most advanced model"},
        {"name": "gpt-4o", "display": "GPT-4o (Recommended)", "description": "Best quality, multimodal"},
        {"name": "gpt-4o-mini", "display": "GPT-4o Mini", "description": "Fast and affordable"},
        {"name": "gpt-4-turbo", "display": "GPT-4 Turbo", "description": "Previous generation"},
        {"name": "gpt-3.5-turbo", "display": "GPT-3.5 Turbo", "description": "Fast and cheap"},
        {"name": "custom", "display": "Custom Model...", "description": "Enter any OpenAI model name"},
    ],
    "anthropic": [
        {"name": "claude-opus-4-20250514", "display": "Claude Opus 4.5 (Recommended)", "description": "Highest intelligence"},
        {"name": "claude-sonnet-4-20250514", "display": "Claude Sonnet 4.5", "description": "Best balance"},
        {"name": "claude-haiku-4-20250514", "display": "Claude Haiku 4", "description": "Fast and affordable"},
        {"name": "claude-3-5-sonnet-20241022", "display": "Claude 3.5 Sonnet", "description": "Previous generation"},
        {"name": "custom", "display": "Custom Model...", "description": "Enter any Anthropic model name"},
    ]
}


class DataSourceType(str, Enum):
    YOUTUBE_PLAYLIST = "youtube_playlist"
    YOUTUBE_VIDEO = "youtube_video"
    WEBSITE = "website"
    PDF_URL = "pdf_url"
    PDF_UPLOAD = "pdf_upload"
    RSS_FEED = "rss_feed"
    REDDIT = "reddit"


class DataSource(BaseModel):
    id: str
    type: DataSourceType
    url: str
    name: str
    description: Optional[str] = None
    enabled: bool = True
    last_synced: Optional[datetime] = None
    word_count: int = 0
    document_count: int = 0
    metadata: Dict[str, Any] = {}


class ProjectConfig(BaseModel):
    """Main configuration for a neighborhood AI project"""

    # Project Identity
    project_id: str
    municipality_name: str  # e.g., "Brookline, MA"
    project_name: str  # e.g., "Brookline AI"
    tagline: Optional[str] = "Your local AI assistant"

    # AI Configuration
    ai_provider: AIProvider = AIProvider.OLLAMA
    model_name: str = "llama3.1:8b"
    api_key: Optional[str] = None  # For OpenAI/Anthropic

    # Project API Access
    project_api_key: Optional[str] = None  # API key for external access to this project
    api_enabled: bool = False  # Whether API access is enabled
    
    # Model Parameters
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, ge=100, le=8000)
    context_window: int = Field(default=8192, ge=2048, le=32768)
    
    def model_post_init(self, __context):
        """Set appropriate model defaults based on provider"""
        if self.ai_provider == AIProvider.OPENAI and self.model_name == "llama3.1:8b":
            self.model_name = "gpt-4o"
        elif self.ai_provider == AIProvider.ANTHROPIC and self.model_name == "llama3.1:8b":
            self.model_name = "claude-opus-4-20250514"
    
    # Personality & Behavior
    system_prompt: str = ""
    personality_traits: List[str] = [
        "helpful", "knowledgeable", "friendly", "civic-minded"
    ]
    tone: str = "professional but friendly"

    # Community Constitution - ethical guidelines and constraints for AI behavior
    # Supports both old format (List[str]) and new format (Dict with mode, values, etc.)
    community_constitution: Union[List[str], Dict[str, Any]] = []
    
    # Data Sources
    data_sources: List[DataSource] = []
    
    # Features
    enable_citations: bool = True
    enable_web_search: bool = False
    enable_feedback: bool = True
    show_thinking: bool = False
    extended_thinking: bool = False
    
    # Branding
    primary_color: str = "#3B82F6"  # Blue
    logo_url: Optional[str] = None
    
    # Deployment
    public_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    sources: Optional[List[Dict[str, str]]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ChatRequest(BaseModel):
    message: str
    project_id: str
    conversation_history: List[ChatMessage] = []


class DataIngestionJob(BaseModel):
    job_id: str
    project_id: str
    source_id: str
    status: str  # "pending", "running", "completed", "failed"
    progress: float = 0.0
    total_items: int = 0
    processed_items: int = 0
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class WizardStep(BaseModel):
    """Wizard steps for initial setup"""
    step: int
    title: str
    completed: bool = False
    data: Dict[str, Any] = {}
