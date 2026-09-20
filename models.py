from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from datetime import datetime


class AIProvider(str, Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    # A local LM Studio server, the deployment the community-owned AI guide is
    # written around. Speaks the OpenAI protocol on localhost:1234 by default,
    # or over a tunnel to a server the community runs elsewhere.
    LMSTUDIO = "lmstudio"
    GEMINI = "gemini"


# Model presets for easy selection
# Model presets per provider.
#
# These are starting points shown in the setup wizard, not a whitelist: every
# provider also accepts a custom identifier, and the app can query a provider's
# own /models endpoint at runtime (see providers.discover_models). Model
# lineups move faster than this file will, so live discovery is the reliable
# path and this table is the offline fallback.
#
# Checked against provider documentation: September 2026.
AVAILABLE_MODELS = {
    # --- Local, and the point of the project ---------------------------
    "lmstudio": [
        {"name": "gemma-4-26b-a4b", "display": "Gemma 4 26B-A4B (Recommended)",
         "description": "The local deployment the community AI guide is built around",
         "tools": True},
        {"name": "gemma-4-12b", "display": "Gemma 4 12B",
         "description": "Smaller Gemma, lower memory footprint", "tools": True},
        {"name": "qwen3-30b-a3b", "display": "Qwen 3 30B-A3B",
         "description": "Mixture of experts, strong tool calling, large context",
         "tools": True},
        {"name": "llama-3.3-70b", "display": "Llama 3.3 70B",
         "description": "Larger open model, needs substantial VRAM", "tools": True},
        {"name": "mistral-small-3.2-24b", "display": "Mistral Small 3.2 24B",
         "description": "Efficient, reliable function calling", "tools": True},
        {"name": "custom", "display": "Custom Model...",
         "description": "Any model identifier loaded in LM Studio"},
    ],
    "ollama": [
        {"name": "llama3.3:70b", "display": "Llama 3.3 70B", "description": "Best open quality, needs a GPU", "tools": True},
        {"name": "llama3.1:8b", "display": "Llama 3.1 8B (Recommended)", "description": "Fast and efficient, 8GB RAM", "tools": True},
        {"name": "qwen3:30b-a3b", "display": "Qwen 3 30B-A3B", "description": "Mixture of experts, strong tool calling", "tools": True},
        {"name": "gemma3:27b", "display": "Gemma 3 27B", "description": "Google's open model", "tools": False},
        {"name": "mistral-small:24b", "display": "Mistral Small 24B", "description": "Reliable function calling", "tools": True},
        {"name": "olmo3:13b", "display": "OLMo 3 13B", "description": "Allen AI, fully open training data", "tools": False},
        {"name": "phi4:14b", "display": "Phi-4 14B", "description": "Microsoft's efficient model", "tools": True},
        {"name": "custom", "display": "Custom Model...", "description": "Enter any Ollama model name"},
    ],

    # --- Frontier, for comparison and for tasks a local model cannot do ---
    "anthropic": [
        {"name": "claude-opus-5", "display": "Claude Opus 5 (Recommended)",
         "description": "Anthropic's balance of capability and cost", "tools": True},
        {"name": "claude-sonnet-5", "display": "Claude Sonnet 5",
         "description": "Cheaper, still strong on civic summarization", "tools": True},
        {"name": "claude-haiku-4-5", "display": "Claude Haiku 4.5",
         "description": "Fastest and cheapest, good for bulk extraction", "tools": True},
        {"name": "claude-fable-5-1", "display": "Claude Fable 5.1",
         "description": "Most capable, priced well above Opus", "tools": True},
        {"name": "custom", "display": "Custom Model...", "description": "Enter any Anthropic model name"},
    ],
    "openai": [
        {"name": "gpt-5.5", "display": "GPT-5.5 (Recommended)",
         "description": "OpenAI's production model for the Chat Completions API",
         "tools": True},
        {"name": "gpt-6-astra", "display": "GPT-6 Astra",
         "description": "Most capable. Tool calling needs the Responses API, so "
                        "web search is unavailable on this model here",
         "tools": False},
        {"name": "gpt-5.5-pro", "display": "GPT-5.5 Pro",
         "description": "Higher accuracy, higher cost", "tools": True},
        {"name": "custom", "display": "Custom Model...", "description": "Enter any OpenAI model name"},
    ],
    "gemini": [
        {"name": "gemini-3.1-pro", "display": "Gemini 3.1 Pro (Recommended)",
         "description": "Google's flagship for hard reasoning and multimodal work",
         "tools": True},
        {"name": "gemini-3.8-flash", "display": "Gemini 3.8 Flash",
         "description": "Fast and inexpensive, newest Flash generation", "tools": True},
        {"name": "gemini-3.5-flash", "display": "Gemini 3.5 Flash",
         "description": "Google's general default model", "tools": True},
        {"name": "gemini-3.1-flash-lite", "display": "Gemini 3.1 Flash-Lite",
         "description": "Cheapest, for bulk classification and extraction", "tools": True},
        {"name": "custom", "display": "Custom Model...", "description": "Enter any Gemini model name"},
    ],
}

# Providers that run on hardware the community controls. The distinction drives
# the setup wizard's ordering and the privacy language shown to residents: a
# question answered locally never leaves the building.
LOCAL_PROVIDERS = ("lmstudio", "ollama")
FRONTIER_PROVIDERS = ("anthropic", "openai", "gemini")


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


class APIClient(BaseModel):
    """One application authorized to use the community API.

    Section 13 lists "app permissions" as a gateway responsibility. A single
    shared key cannot be revoked for one misbehaving application without
    breaking every other one, so each application gets its own.
    """

    client_id: str
    name: str
    key_hash: str                      # sha256 of the key; the key is shown once
    key_prefix: str = ""               # first characters, for identification in a UI
    scopes: List[str] = ["ask", "search", "read"]
    rate_limit_per_minute: int = 60
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    last_used: Optional[datetime] = None
    request_count: int = 0


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
    # Per-application keys, so one application can be revoked without breaking
    # the rest. Populated by the community gateway; the single key above still
    # works for projects created before this existed.
    api_clients: List["APIClient"] = []
    
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
        elif self.ai_provider == AIProvider.LMSTUDIO and self.model_name == "llama3.1:8b":
            self.model_name = "gemma-4-26b-a4b"
        elif self.ai_provider == AIProvider.GEMINI and self.model_name == "llama3.1:8b":
            self.model_name = "gemini-3.1-pro"
    
    # Personality & Behavior
    system_prompt: str = ""
    personality_traits: List[str] = [
        "helpful", "knowledgeable", "friendly", "civic-minded"
    ]
    tone: str = "professional but friendly"

    # Community Constitution - ethical guidelines and constraints for AI behavior
    # Supports both old format (List[str]) and new format (Dict with mode, values, etc.)
    community_constitution: Union[List[str], Dict[str, Any]] = []
    
    # Community AI settings (see COMMUNITY_AI_SCOPE.md)
    #
    # The constitution lives in source control, not here. This records which
    # version this project runs so the transparency panel and the model card can
    # report it, and so a community can pin an older version while reviewing a
    # new one. `community_constitution` above is the pre-existing inline format
    # and is still honored when no constitution file is present.
    constitution_version: str = "latest"

    # Retrieval, per section 5 of the guide.
    retrieval_top_k: int = Field(default=8, ge=1, le=15)
    retrieval_candidate_pool: int = Field(default=24, ge=4, le=100)
    enable_hybrid_search: bool = True
    enable_reranking: bool = True
    enable_query_expansion: bool = True
    # A model-backed query rewrite (guide section 18) costs one extra
    # generation per question. On a local server that is real latency, so
    # the free rule-based expansion is the default and this is opt-in.
    enable_model_query_rewrite: bool = False

    # Provenance, per section 6.
    require_citations: bool = True

    # Privacy-aware logging, per section 13. Operational metadata is recorded so
    # the community can see usage and debug retrieval; the resident's question
    # text is not, unless the community turns it on deliberately. Governance
    # says aggregate statistics are public and question text is not.
    log_requests: bool = True
    log_question_text: bool = False
    log_retention_days: int = Field(default=30, ge=0, le=3650)

    # Local inference, per section 12.
    #
    # Points at LM Studio. For a server on the community's own network this is
    # a private address; for a server reached through a Cloudflare tunnel or
    # similar it is the public hostname, and `local_auth_header` carries
    # whatever the tunnel requires. The tunnel is what makes a machine in a
    # closet serve a whole town without a static IP or an open port.
    lmstudio_base_url: Optional[str] = None
    local_auth_header: Optional[str] = None   # e.g. "Authorization: Bearer ..."
    local_verify_tls: bool = True

    # Tools the assistant may use while answering (see tools/).
    #
    # Local models have no built-in web access and a fixed knowledge cutoff, so
    # tools are how a community model answers anything outside its archive.
    enable_tools: bool = False
    enabled_tools: List[str] = ["search_community_records", "web_search", "fetch_url"]
    max_tool_iterations: int = Field(default=4, ge=1, le=10)
    web_search_backend: str = "duckduckgo"    # duckduckgo | searxng | brave | tavily
    web_search_base_url: Optional[str] = None  # for a self-hosted SearXNG
    web_search_api_key: Optional[str] = None

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
