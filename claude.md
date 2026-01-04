# Neighborhood AI - Project Documentation

## Project Overview

**Neighborhood AI** is an open-source platform for building privacy-respecting, energy-efficient, locally-run AI assistants for communities. It enables civic organizations, community media centers, local governments, and neighborhood groups to create AI chatbots that answer questions about their town using local data sources.

**Key Principle:** Run powerful AI on modest local hardware (like a Mac Mini M4) instead of relying on cloud-based frontier models. This approach offers 1000x better energy efficiency, zero ongoing costs, complete privacy, and 100% community ownership.

**Example:** Brookline AI - answers questions about Brookline, MA using Select Board meeting transcripts, local news, town documents, and community forums.

## Purpose & Values

- **Energy Efficient:** 1000x less energy than cloud AI (2W vs 100W per query)
- **Privacy First:** All data processed locally, zero surveillance
- **Community Owned:** Run by libraries, community centers, local government
- **Free to Operate:** $0/month after initial setup
- **Open Source:** MIT license, fork and improve
- **Civic Minded:** Cites sources, admits limitations, encourages participation

## Technical Stack

### Backend (Python/FastAPI)
- **Framework:** FastAPI with Uvicorn
- **Vector Store:** Qdrant (local instance)
- **Embeddings:** Sentence Transformers (all-MiniLM-L6-v2)
- **AI Models:**
  - Local: Ollama (llama3.1:8b recommended)
  - Cloud: Claude (Opus 4.5/Sonnet 4.5/Haiku 4), GPT-4o/Mini
- **Data Collection:** YouTube transcripts, web scraping, PDF/DOCX parsing
- **RAG Architecture:** Question → Embedding → Vector Search → Context + LLM → Answer

### Frontend (React)
- **Framework:** React 18 with React Router
- **Styling:** Tailwind CSS with terminal/coding aesthetic
- **UI Components:** Heroicons
- **State Management:** React hooks (useState, useEffect)
- **Build Tool:** Create React App (react-scripts)

### Development
- **Package Management:** pip (Python), npm (Node.js)
- **Local AI:** Ollama (runs models locally)
- **API Communication:** Axios
- **Development Servers:** Uvicorn (port 8000), Webpack Dev Server (port 3000)

## Architecture

### File Structure
```
neighborhood-ai/
├── app.py                      # FastAPI backend server
├── agent.py                    # RAG agent with LLM integration
├── models.py                   # Pydantic data models
├── vector_store.py             # Qdrant vector database interface
├── collectors/                 # Data collection modules
│   ├── youtube_collector.py    # YouTube video/playlist transcripts
│   ├── website_collector.py    # Web scraping
│   ├── pdf_collector.py        # PDF text extraction
│   └── source_discovery.py     # AI-powered source finding
├── frontend/
│   ├── public/                 # Static assets
│   ├── src/
│   │   ├── App.js              # Main React app with routing
│   │   ├── App.css             # Global styles
│   │   ├── index.css           # Tailwind imports
│   │   └── components/
│   │       ├── LandingPage.js      # Marketing/landing page + project showcase
│   │       ├── ProjectList.js      # Project management console
│   │       ├── SetupWizard.js      # 4-step project creation
│   │       ├── Dashboard.js        # Project overview + config editor
│   │       ├── DataManager.js      # Data source management + PDF upload
│   │       ├── ChatInterface.js    # AI chat interface
│   │       ├── Settings.js         # AI model & personality config
│   │       ├── AdminConsole.js     # Health monitoring & API keys
│   │       ├── HelpPage.js         # Setup guides & troubleshooting
│   │       └── Guide.js            # Comprehensive wiki-style documentation
│   └── package.json            # Frontend dependencies
├── data/                       # Project data storage
│   └── {project_id}/
│       ├── config.json         # Project configuration
│       ├── qdrant/             # Vector database files
│       └── uploads/            # Uploaded PDF files
├── requirements.txt            # Python dependencies
└── .env                        # Configuration (API keys)
```

### Data Flow

**1. Source Discovery (Optional)**
```
User provides location → Claude Opus analyzes → Finds relevant sources
→ User previews and selects sources → Custom sources can be added
```

**2. Data Ingestion**
```
Source URL → Collector extracts text → Chunk into passages
→ Generate embeddings → Store in Qdrant → Track progress
```

**3. Question Answering (RAG)**
```
User question → Generate query embedding → Search Qdrant for similar chunks
→ Retrieve top-5 relevant passages → Build context prompt
→ Send to LLM (Ollama/Claude/GPT) → Return answer with citations
```

## Key Features

### Setup Wizard (4 Steps)

**Step 1: Location (`./init`)**
- Enter municipality/neighborhood name
- Configure AI discovery provider (Anthropic recommended)
- Provide API key for intelligent source discovery

**Step 2: Discover Sources (`./discover`)**
- AI-powered web search for relevant data sources
- Preview discovered sources with thumbnails/descriptions
- Select/deselect sources (all selected by default)
- Add custom sources:
  - YouTube videos
  - YouTube playlists
  - Websites
  - PDF documents

**Step 3: Configure AI (`./config`)**
- Choose AI provider (Ollama for free local, OpenAI, Anthropic)
- Select specific model
- Adjust temperature (0.0 focused - 1.0 creative)
- Thinking options:
  - Show thinking (display AI reasoning)
  - Extended thinking (Claude only - beta)
- System prompt:
  - Auto-generate personality based on location
  - Or manually customize

**Step 4: Launch (`./launch`)**
- Review configuration summary
- Start background data ingestion
- Navigate to project dashboard

### Terminal-Style UI

The interface uses a developer/coding aesthetic:
- Dark gray backgrounds (`bg-gray-950`, `bg-gray-900`)
- Green accent for primary actions (`bg-green-500`)
- Cyan for secondary/informational (`text-cyan-400`)
- Monospace font throughout (`font-mono`)
- Terminal elements:
  - Traffic light window controls
  - Command-line prompts (`$`, `#`)
  - File path indicators (`~/projects/`)

### Data Sources

| Type | Description | Status |
|------|-------------|--------|
| `youtube_playlist` | YouTube playlist with transcripts | ✅ Working |
| `youtube_video` | Single YouTube video | ✅ Working |
| `website` | Web pages with crawling | ✅ Working |
| `pdf_url` | PDF documents from URLs | ✅ Working |
| `pdf_upload` | Direct PDF file upload | ✅ Working |
| `rss_feed` | RSS/Atom feeds | 🚧 Planned |
| `reddit` | Reddit communities | 🚧 Planned |

### AI Providers

| Provider | Models | Notes |
|----------|--------|-------|
| Ollama | llama3.1:8b, llama3.1:70b, llama3.2:3b, mistral:7b, mixtral:8x7b, phi3:medium | Free, local, private |
| OpenAI | gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo | Cloud, API key required |
| Anthropic | claude-opus-4-20250514, claude-sonnet-4-20250514, claude-haiku-4-20250514 | Cloud, API key required |

## API Endpoints

### Projects
```
POST /api/projects                          # Create new project
GET  /api/projects                          # List all projects
GET  /api/projects/{id}                     # Get project details
PUT  /api/projects/{id}                     # Update project config
```

### Sources
```
POST   /api/projects/{id}/sources                    # Add data source
DELETE /api/projects/{id}/sources/{source_id}        # Remove source
POST   /api/projects/{id}/sources/{source_id}/ingest # Start ingestion
```

### Discovery & Generation
```
POST /api/projects/{id}/discover-sources     # AI source discovery
POST /api/projects/{id}/generate-personality # Generate AI personality
```

### Chat & Jobs
```
POST /api/chat                # Send message with RAG
GET  /api/jobs/{job_id}       # Get ingestion job status
GET  /api/models/{provider}   # List available models
```

### Health & Admin
```
GET  /api/health                              # System health (Ollama, projects)
GET  /api/projects/{id}/health                # Project health check
GET  /api/admin/jobs                          # List all ingestion jobs
POST /api/projects/{id}/generate-api-key      # Generate project API key
DELETE /api/projects/{id}/revoke-api-key      # Revoke API key
```

### Documents & Config
```
GET  /api/projects/{id}/documents             # List vector store documents
GET  /api/projects/{id}/config                # Get raw config JSON
PUT  /api/projects/{id}/config                # Update raw config JSON
POST /api/projects/{id}/upload-pdf            # Upload PDF file directly
```

### Frontend Routes
```
/                                   # Landing page with project showcase
/guide                              # Comprehensive wiki-style guide
/console                            # Project list
/console/new                        # Setup wizard
/console/projects/:id               # Project dashboard
/console/projects/:id/chat          # Chat interface
/console/projects/:id/data          # Data management + PDF upload
/console/projects/:id/settings      # AI model configuration
/console/projects/:id/admin         # Admin console (health, API keys)
/console/projects/:id/help          # Help & documentation
```

## Configuration

### Project Config (`data/{project_id}/config.json`)
```json
{
  "project_id": "brookline-ma",
  "municipality_name": "Brookline, MA",
  "project_name": "Brookline AI",
  "ai_provider": "ollama",
  "model_name": "llama3.1:8b",
  "temperature": 0.7,
  "context_window": 8192,
  "max_tokens": 2000,
  "system_prompt": "You are a helpful AI assistant...",
  "personality_traits": ["helpful", "knowledgeable"],
  "tone": "professional but friendly",
  "enable_citations": true,
  "show_thinking": false,
  "extended_thinking": false,
  "data_sources": []
}
```

### Environment Variables (.env)
```bash
# Required for cloud models / source discovery
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Optional for YouTube playlist access
YOUTUBE_API_KEY=...

# Server settings
HOST=0.0.0.0
PORT=8000

# Frontend
REACT_APP_API_URL=http://localhost:8000
```

## Setup Instructions

### Prerequisites
```bash
# macOS (Homebrew)
brew install python@3.11
brew install node
brew install ollama

# Start Ollama
ollama serve

# Pull recommended model
ollama pull llama3.1:8b
```

### Installation
```bash
# Clone repository
git clone https://github.com/amateurmenace/ai-machine.git
cd ai-machine/neighborhood-ai

# Install Python dependencies
pip3 install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
cd ..

# Configure API keys (optional, only for cloud models)
cp .env.example .env
nano .env  # Add ANTHROPIC_API_KEY and/or OPENAI_API_KEY

# Start backend
python3 app.py

# In another terminal, start frontend
cd frontend
npm start

# Visit application
open http://localhost:3000
```

### Usage
1. Visit http://localhost:3000 (landing page)
2. Click "Console" to open the console
3. Click "+ new" to create a project
4. Follow 4-step wizard:
   - Step 1: Enter location and configure discovery AI
   - Step 2: Review/select discovered sources, add custom ones
   - Step 3: Choose AI model, configure personality
   - Step 4: Review and launch
5. Chat with your AI from the dashboard

## Current State (January 2026)

### ✅ Completed Features

**Landing Page:**
- Terminal-style header with branding
- Animated background effects
- Energy comparison visualization
- Navigation to console and guide
- Projects showcase with embedded chat (shows online/offline status)
- Chat modal for trying out community AIs

**Project Management:**
- Create multiple AI projects
- 4-step setup wizard with terminal aesthetics
- Project list with folder view
- Individual project dashboards with quick action cards
- Raw config.json editor (Code button)
- Admin console with health monitoring
- Help page with setup guides
- Comprehensive wiki-style Guide

**Data Collection:**
- YouTube playlist transcript extraction
- Single YouTube video support
- Website scraping with BeautifulSoup
- PDF text extraction (URL and direct upload)
- AI-powered source discovery
- Source preview and selection
- Custom source addition
- Collection method tracking (how data was gathered)
- Document viewer (browse ingested chunks)

**AI Integration:**
- Local models via Ollama
- Cloud models via APIs (Claude, GPT)
- Hybrid approach: expensive model for discovery, free model for chat
- Model selection per project
- Show thinking toggle
- Extended thinking for Claude (beta)
- Personality auto-generation
- Better error handling with actionable messages

**RAG Pipeline:**
- Sentence transformer embeddings
- Qdrant vector search
- Context-aware prompting
- Source citation in responses
- Relevance scores

**User Interface:**
- Terminal/coding aesthetic throughout
- Chat interface with role indicators
- Data source management with status badges
- Source ingestion progress tracking
- Word count and chunk count per source
- Loading animations and feedback
- Consistent back navigation on all pages
- Settings page for AI configuration

**Admin & Health:**
- System health monitoring (Ollama status, project count)
- Project health checks (AI provider, vector store, data sources)
- Actionable issue messages in health response
- API key generation for external access
- Ingestion job monitoring
- Server management instructions

**Documentation:**
- Comprehensive Guide page (/guide) covering:
  - System requirements (hardware recommendations)
  - Installation instructions (Mac/Windows/Linux)
  - Ollama setup and model selection
  - Starting the application (3-terminal workflow)
  - Creating first project walkthrough
  - Data source types and collection methods
  - Cloud AI providers setup
  - Deployment options (Docker, nginx, cloud hosting)
  - Troubleshooting common issues
  - FAQ

### 🚧 Known Limitations

**Current Issues:**
1. No streaming responses (answers appear all at once)
2. No conversation history persistence (refresh loses chat)
3. No authentication/multi-user support
4. No Docker containerization yet
5. No automated tests

**Planned Features:**
- RSS feed collector
- Reddit collector
- Scheduled re-ingestion
- Conversation persistence
- User authentication
- Analytics dashboard
- Docker deployment

## Troubleshooting

### Port conflicts
```bash
lsof -ti:3000 | xargs kill -9
lsof -ti:8000 | xargs kill -9
```

### Frontend won't start
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm start
```

### Backend errors
```bash
pip3 install -r requirements.txt
ollama list
ollama serve
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with clear commit messages
4. Test thoroughly
5. Submit pull request

**Commit Message Format:**
```
Type: Brief description

- Detailed change 1
- Detailed change 2

Types: Add, Fix, Update, Docs, Style, Refactor
```

## License & Attribution

**License:** MIT License

**Credits:**
- Project: A Community AI Project from Brookline Interactive Group
- Developer: Stephen Walter (https://weirdmachine.org) + AI
- BIG: Brookline Interactive Group (40+ years of community media)

## Contact & Resources

**GitHub:** https://github.com/amateurmenace/ai-machine
**Community:** https://community.weirdmachine.org
**Email:** stephen@weirdmachine.org

---

**Last Updated:** January 4, 2026
**Version:** 1.0.0
**Status:** Active development
