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
- **Open Source:** CC BY-NC-SA 4.0 license, fork and improve
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
- **API Client:** Centralized axios module (`src/api.js`)
- **Deployment:** Netlify (static hosting)

### Development
- **Package Management:** pip (Python), npm (Node.js)
- **Local AI:** Ollama (runs models locally)
- **API Communication:** Axios (centralized in `frontend/src/api.js`)
- **Development Servers:** Uvicorn (port 8000), Webpack Dev Server (port 3000)

### Deployment
- **Frontend Hosting:** Netlify (static site)
- **Backend Tunnel:** Cloudflare Tunnel (exposes local backend to internet)
- **Architecture:** Hybrid - cloud frontend + local backend with Ollama

## Architecture

### File Structure
```
neighborhood-ai/
├── app.py                      # FastAPI backend server
├── agent.py                    # RAG agent with LLM integration
├── models.py                   # Pydantic data models
├── vector_store.py             # Qdrant vector database interface
├── start-tunnel.sh             # Cloudflare tunnel startup script
├── DEPLOYMENT.md               # Cloud deployment guide
├── SERVER_MANAGEMENT.md        # Server start/stop/troubleshooting guide
├── collectors/                 # Data collection modules
│   ├── youtube_collector.py    # YouTube video/playlist transcripts (with yt-dlp fallback)
│   ├── website_collector.py    # Basic web scraping (BeautifulSoup)
│   ├── website_collector_advanced.py  # Advanced scraping (Playwright for JS sites)
│   ├── pdf_collector.py        # PDF text extraction
│   └── source_discovery.py     # AI-powered source finding
├── frontend/
│   ├── public/                 # Static assets
│   ├── netlify.toml            # Netlify deployment config
│   ├── src/
│   │   ├── App.js              # Main React app with routing
│   │   ├── App.css             # Global styles
│   │   ├── api.js              # Centralized axios API client
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
│   │       ├── Guide.js            # Comprehensive wiki-style documentation
│   │       ├── AboutUs.js          # About page with mission and team
│   │       └── Footer.js           # Site-wide footer component
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
/about                              # About Us page
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

> **📖 For detailed server management, see [SERVER_MANAGEMENT.md](./SERVER_MANAGEMENT.md)**
> Covers: starting/stopping services, troubleshooting, handling shutdowns, IP changes, and common scenarios.

### Prerequisites

**System Requirements:**
- **OS:** macOS, Linux, or Windows (WSL recommended)
- **RAM:** 8GB minimum (16GB recommended for larger models)
- **Storage:** 10GB minimum (more for multiple projects and models)
- **CPU:** Modern multi-core processor (Apple Silicon or x86_64)

**Software Requirements:**
```bash
# macOS (Homebrew)
brew install python@3.11
brew install node
brew install ollama

# Linux (Ubuntu/Debian)
sudo apt update
sudo apt install python3 python3-pip nodejs npm
curl -fsSL https://ollama.ai/install.sh | sh

# Windows (WSL)
# Install WSL2, then follow Linux instructions above
```

**Install and Start Ollama:**
```bash
# Start Ollama service
ollama serve

# Pull recommended model (in another terminal)
ollama pull llama3.1:8b

# Verify installation
ollama list
```

### Installation

**1. Clone Repository:**
```bash
git clone https://github.com/amateurmenace/ai-machine.git
cd ai-machine/neighborhood-ai
```

**2. Install Python Dependencies:**
```bash
pip3 install -r requirements.txt
```

**3. Install Frontend Dependencies:**
```bash
cd frontend
npm install
cd ..
```

**4. Configure API Keys (Optional):**

Only needed if using cloud models (Claude, GPT) or AI-powered source discovery.

```bash
# Create .env file
cp .env.example .env

# Edit with your keys
nano .env
```

Add your API keys:
```bash
# For Claude models and source discovery
ANTHROPIC_API_KEY=sk-ant-...

# For GPT models
OPENAI_API_KEY=sk-...

# Optional: for YouTube playlists
YOUTUBE_API_KEY=...
```

**5. Start All Services:**

You need **3 terminal windows** running simultaneously:

**Terminal 1 - Ollama:**
```bash
ollama serve
```
Keep this running. You'll see logs indicating Ollama is ready.

**Terminal 2 - Backend:**
```bash
python3 app.py
```
Keep this running. Wait for:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Terminal 3 - Frontend:**
```bash
cd frontend
npm start
```
Keep this running. Wait for:
```
Compiled successfully!
You can now view neighborhood-ai-frontend in the browser.
  Local:            http://localhost:3000
```

**6. Visit Application:**
```bash
open http://localhost:3000
```

### First-Time Usage

**Creating Your First Project:**

1. **Visit Landing Page:** http://localhost:3000
2. **Click "Console"** in the header
3. **Click "+ new"** to create a project
4. **Follow 4-Step Setup Wizard:**

   **Step 1: Location & Discovery**
   - Enter your municipality/neighborhood name
   - Choose AI provider for source discovery (Anthropic recommended)
   - Provide API key

   **Step 2: Discover & Select Sources**
   - Review AI-discovered data sources
   - Select/deselect sources (all selected by default)
   - Add custom sources:
     - YouTube videos/playlists
     - Websites
     - PDF documents

   **Step 3: Configure AI**
   - Choose AI provider:
     - **Ollama** (free, local, private) - recommended
     - **OpenAI** (cloud, API costs)
     - **Anthropic** (cloud, API costs)
   - Select model (llama3.1:8b recommended for Ollama)
   - Adjust temperature (0.3-0.5 for civic Q&A)
   - Configure thinking options
   - Auto-generate or customize personality

   **Step 4: Launch**
   - Review configuration summary
   - Click "Launch Project"
   - Data ingestion starts in background
   - Navigate to dashboard

5. **Chat with Your AI:**
   - Click "Chat" from dashboard
   - Ask questions about your community
   - AI answers using local data sources with citations

### Server Management

**Starting Services After Shutdown:**

If your computer shut down or you closed the terminals:

```bash
# Terminal 1
ollama serve

# Terminal 2
python3 app.py

# Terminal 3
cd frontend && npm start
```

Services start in **1-2 minutes** total.

**Stopping Services:**

Press `Ctrl+C` in each terminal, or kill all at once:
```bash
pkill ollama
pkill -f "python3 app.py"
pkill -f "react-scripts start"
```

**Checking Status:**
```bash
# Quick health check
curl http://localhost:8000/api/health

# Check if services are running
pgrep ollama && echo "✅ Ollama" || echo "❌ Ollama"
pgrep -f "python3 app.py" && echo "✅ Backend" || echo "❌ Backend"
pgrep -f "react-scripts" && echo "✅ Frontend" || echo "❌ Frontend"
```

**Common Issues:**

| Issue | Solution |
|-------|----------|
| Port already in use | `lsof -ti:8000 \| xargs kill -9` |
| Ollama not responding | `pkill ollama && ollama serve` |
| Frontend won't start | `cd frontend && rm -rf node_modules && npm install` |
| Chat returns errors | Check Ollama is running, verify project has data |

**See [SERVER_MANAGEMENT.md](./SERVER_MANAGEMENT.md) for:**
- Detailed startup/shutdown procedures
- Handling IP address changes
- Cloudflare tunnel management
- Running in production
- Troubleshooting all common scenarios

### Remote Access (Optional)

To access your local backend from the internet (e.g., for Netlify deployment):

**Start Cloudflare Tunnel:**
```bash
./start-tunnel.sh
```

The tunnel URL will be displayed:
```
https://random-words.trycloudflare.com
```

**Update Netlify (if deployed):**
1. Go to Netlify dashboard → Site settings → Environment variables
2. Update: `REACT_APP_API_URL = https://your-tunnel-url.trycloudflare.com`
3. Trigger redeploy

**Note:** Free tunnels get new URLs each restart. For production, use a named tunnel or dedicated server.

## Current State (January 2026)

### ✅ Completed Features

**Landing Page:**
- Terminal-style header with branding
- Animated background effects with urban planning aesthetic
- Energy comparison visualization
- Navigation to console and guide
- Projects showcase with embedded chat (shows online/offline status)
- Chat modal for trying out community AIs
- Community Constitution feature section
- Discovery Wizard feature explanation
- Local AI customization benefits (fine-tuning, community values)
- Modern, bold design with informative content

**Project Management:**
- Create multiple AI projects (supports duplicate locations with auto-numbered IDs)
- 6-step setup wizard with terminal aesthetics:
  1. Location - Define municipality/neighborhood
  2. Discover - AI-powered source discovery
  3. **Constitution - Define community values and ethics (NEW!)**
  4. Fine Tune - Add/manage data sources
  5. Configure - AI model and personality
  6. Launch - Deploy project
- Project list with folder view
- Individual project dashboards with quick action cards
- Raw config.json editor (Code button)
- Admin console with health monitoring
- Project deletion with full data cleanup
- Help page with setup guides
- Comprehensive wiki-style Guide

**Data Collection:**
- YouTube playlist transcript extraction (with multiple fallback methods)
- Single YouTube video support
- **Website scraping with BeautifulSoup (IMPROVED!)**
  - Fixed domain matching (www. prefix handling)
  - Fixed Qdrant file locking issues
  - Background processing support
  - Note: JavaScript-rendered sites not supported (static HTML only)
- PDF text extraction (URL and direct upload)
- AI-powered source discovery
- Source preview and selection
- Custom source addition
- Collection method tracking (how data was gathered)
- Document viewer (browse ingested chunks)
- Data protection limits (120MB or 10M words per source)
- Sync all sources feature with progress tracking

**AI Integration:**
- Local models via Ollama (includes OLMo 3)
- Cloud models via APIs (Claude, GPT-5.2, GPT-4o)
- Custom model input for any provider
- Hybrid approach: expensive model for discovery, free model for chat
- Model selection per project
- Show thinking toggle
- Extended thinking for Claude (beta)
- Personality auto-generation
- Better error handling with actionable messages
- Custom discovery search prompts
- **Community Constitution integration (NEW!)**
  - Define core values (e.g., Transparency, Privacy, Accuracy)
  - Set ethical guidelines (e.g., "Always cite sources")
  - Establish red lines (e.g., "Never provide medical advice")
  - Automatically injected into AI system prompts
  - Three modes: Online form, Workshop (coming soon), Skip

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
- Dashboard notifications for pending data syncs
- Real-time ingestion progress on dashboard
- Guide button on landing page
- Sync all sources button with animated loading
- Bold, modern landing page with informative content
- Visible blueprint/urban planning background patterns
- About Us page with mission, team, and licensing
- Footer component with organization logos and CC license

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
- **New deployment guides:**
  - TUNNEL_SETUP.md - Permanent Cloudflare tunnel setup (no more URL changes!)
  - SERVER_MANAGEMENT.md - Start/stop/troubleshoot all services
  - CONSTITUTION_FEATURE.md - Community Constitution implementation guide
  - ACTION_PLAN.md - Development roadmap and issue tracking

### 🚧 Known Limitations

**Current Issues:**
1. No streaming responses (answers appear all at once)
2. No conversation history persistence (refresh loses chat)
3. No authentication/multi-user support
4. No Docker containerization yet
5. No automated tests
6. **Website scraping limitation:** JavaScript-rendered sites (SPAs) return empty content

**Planned Features:**
- RSS feed collector
- Reddit collector
- Scheduled re-ingestion
- **Community Constitutions workshop materials** (in-person mode) - online form complete!
- Architectural diagram on landing page
- Conversation persistence
- User authentication
- Analytics dashboard
- Docker deployment
- Playwright/Selenium for JavaScript site scraping

## Roadmap

### Phase 1: Core Improvements (Next)
- **Streaming responses**: Show AI answers character-by-character
- **Conversation persistence**: Save chat history to localStorage or database
- ~~**Community Constitution workshop**: UI for collecting community values and ethics~~ ✅ DONE (online form)

### Phase 2: Advanced Features
- ~~**Community Constitutions**: Configurable ethical guidelines for AI behavior~~ ✅ DONE
- **Community Constitution workshop materials**: Printable guides for in-person meetings
- **RSS feed collector**: Ingest news from RSS/Atom feeds
- **Reddit collector**: Gather community discussions
- **Scheduled re-ingestion**: Automatic data updates on schedule

### Phase 3: Production Ready
- **Docker deployment**: Containerized setup for easy deployment
- **User authentication**: Multi-user support with roles
- **Analytics dashboard**: Usage metrics and insights
- **Architectural diagram**: Visual explanation on landing page

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

**License:** Creative Commons BY-NC-SA 4.0

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
**Version:** 1.0.5
**Status:** Active development

## Deployment

### Production URLs
- **Frontend:** https://neighborhood-ai.netlify.app
- **Backend API:** Via Cloudflare Tunnel (dynamic URL)

### Hybrid Architecture
The app uses a hybrid cloud/local architecture:
1. **Frontend** hosted on Netlify (static React build)
2. **Backend** runs locally on your Mac with Ollama
3. **Cloudflare Tunnel** exposes local backend to internet securely

### Starting the Tunnel
```bash
# Start the Cloudflare tunnel
./start-tunnel.sh

# The URL will be displayed, e.g.:
# https://random-words.trycloudflare.com

# Update Netlify env var with the new URL:
# REACT_APP_API_URL = https://your-tunnel-url.trycloudflare.com
```

### Monitoring the Tunnel
```bash
# Check if running
pgrep -fl cloudflared

# View logs
tail -f /tmp/tunnel.log

# Get current URL
cat /tmp/tunnel.log | grep trycloudflare

# Stop tunnel
pkill cloudflared
```

### Netlify Configuration
Environment variables needed in Netlify:
- `REACT_APP_API_URL` - Your Cloudflare tunnel URL

Build settings:
- Base directory: `frontend`
- Build command: `npm run build`
- Publish directory: `frontend/build`

## Session History

### January 6, 2026 - Session 8 (Current)
**Critical Fixes & Advanced Features:**

1. **Asyncio Event Loop Conflict - FIXED**
   - **Problem:** Playwright's async code conflicting with FastAPI's event loop
   - **Error:** `asyncio.run() cannot be called from a running event loop`
   - **Solution:** Threading with isolated event loop
     - Use `asyncio.new_event_loop()` in separate thread
     - `loop.run_until_complete()` instead of `asyncio.run()`
     - Complete isolation from FastAPI's event loop
   - **File:** collectors/website_collector_advanced.py:301-320
   - **Status:** JavaScript websites now scrape perfectly ✅

2. **Advanced Web Scraping with Playwright**
   - Headless browser automation for JavaScript-rendered sites
   - Async implementation with thread-based event loop isolation
   - Automatic fallback to BeautifulSoup for static sites
   - Same data protection limits (120MB, 10M words)
   - Performance: ~2-5 seconds per page (vs ~0.5-1 for BeautifulSoup)
   - **File:** collectors/website_collector_advanced.py (new, 328 lines)
   - **Integration:** app.py auto-detects Playwright availability
   - **Dependencies:** playwright>=1.40.0 (~250MB for Chromium)

3. **YouTube Playlist Without API Key**
   - Added yt-dlp fallback method
   - Works without YouTube Data API v3 key
   - Automatic transparent fallback
   - Backward compatible with API method
   - **File:** collectors/youtube_collector.py
   - **Method:** get_playlist_videos_ytdlp() using subprocess
   - **Dependencies:** yt-dlp>=2024.3.10

4. **Permanent Tunnel Configuration**
   - **Problem:** create.neighborhoodai.org already pointed to Netlify
   - **Solution:** Separated frontend and backend subdomains
     - Frontend: create.neighborhoodai.org → Netlify (static React)
     - Backend: api.neighborhoodai.org → Cloudflare Tunnel → Local Mac
   - **Tunnel ID:** 661c38c1-d69e-433c-9910-bc3ec80d6117
   - **Config:** ~/.cloudflared/config.yml updated with api subdomain
   - **Script:** start-tunnel-permanent.sh updated
   - **Status:** Tunnel running, DNS CNAME needs to be added manually

5. **Repository Sync & Commit**
   - Synced all 32 files from worktree to main repo
   - Committed all changes to GitHub (commits: 44d89bc, d2d60a0)
   - Updated documentation comprehensively

**Files Modified:**
- collectors/website_collector_advanced.py - NEW: Playwright scraper with threading fix
- collectors/youtube_collector.py - yt-dlp fallback added
- app.py - Playwright integration with graceful fallback
- requirements.txt - Added playwright and yt-dlp dependencies
- ~/.cloudflared/config.yml - Updated hostname to api.neighborhoodai.org
- start-tunnel-permanent.sh - Updated domain to api.neighborhoodai.org

**Documentation Created:**
- TUNNEL_DNS_SETUP.md - DNS configuration guide (397 lines)
- SESSION_COMPLETE.md - Comprehensive session summary (470 lines)
- FIXES_APPLIED.md - All fixes explained (229 lines)
- FINAL_STATUS.md - Feature delivery status (354 lines)
- NETLIFY_UPDATE.md - Netlify configuration guide (79 lines)
- ADVANCED_FEATURES.md - Playwright & yt-dlp documentation

**GitHub Commits:**
- 44d89bc: Fix: Asyncio event loop + DNS setup + Sync main folder
- d2d60a0: Docs: Add session completion summary with DNS setup instructions

**Installation Required:**
```bash
pip install playwright yt-dlp
playwright install chromium
```

**Testing Status:**
✅ Asyncio errors resolved (threading with isolated event loop)
✅ JavaScript websites scrape successfully (Playwright)
✅ YouTube playlists work without API key (yt-dlp)
✅ Tunnel configured and running (4 connections)
✅ All code committed and pushed to GitHub
⏳ DNS CNAME needs manual addition in Cloudflare dashboard

**User Action Required:**
1. Add CNAME record in Cloudflare dashboard:
   - Type: CNAME
   - Name: api
   - Target: 661c38c1-d69e-433c-9910-bc3ec80d6117.cfargotunnel.com
2. Update Netlify env var: REACT_APP_API_URL = https://api.neighborhoodai.org

### January 6, 2026 - Session 7
**Three Major Features Completed:**

1. **Permanent Cloudflare Tunnel Setup**
   - Created TUNNEL_SETUP.md with comprehensive setup guide
   - Created start-tunnel-permanent.sh script
   - Fixed URL stays permanent across restarts and IP changes
   - No more Netlify env var updates needed

2. **Website Scraping Fixes**
   - Fixed domain matching bug (www. prefix handling)
   - Fixed Qdrant file locking with global client cache
   - Fixed progress callback signature mismatch
   - Tested successfully: 2 items, 236 words ingested
   - Added proper error handling and logging
   - Background processing now works correctly
   - Known limitation documented: JS-rendered sites not supported (FIXED in Session 8)

3. **Community Constitution Feature (COMPLETE)**
   - Added Step 3 to setup wizard: "Constitution"
   - Online form mode fully functional:
     - Core values selection (6 presets + custom, min 3)
     - Ethical guidelines (free-form input)
     - Red lines (what AI should never do)
   - Workshop mode placeholder (shows "Coming Soon")
   - Skip option available
   - Automatically integrates into AI system prompts
   - Structured data format with backward compatibility
   - 280+ lines of frontend code, 30 lines backend

**Files Modified:**
- collectors/website_collector.py - Domain matching + logging
- vector_store.py - Global Qdrant client cache
- app.py - Vector store caching + progress callback fix
- agent.py - Constitution integration in system prompts
- frontend/src/components/SetupWizard.js - Constitution step UI

**Documentation Created:**
- SESSION_SUMMARY.md - Complete session overview
- CONSTITUTION_FEATURE.md - Feature implementation details
- TUNNEL_SETUP.md - Permanent tunnel guide
- ACTION_PLAN.md - Task breakdown and roadmap

### January 5, 2026 - Session 6
- Created comprehensive SERVER_MANAGEMENT.md guide:
  - Start/stop procedures for all services (3 methods)
  - Service status checking and health monitoring
  - 10 common scenarios with solutions (shutdown, IP change, tunnel URL change, etc.)
  - Port conflict resolution
  - Troubleshooting guides for all services
  - Quick restart script template
  - Background process and tmux/screen workflows
- Expanded CLAUDE.md Setup Instructions:
  - Added system requirements (RAM, storage, CPU)
  - Multi-OS installation (macOS, Linux, Windows/WSL)
  - Detailed 3-terminal workflow with expected outputs
  - First-time usage walkthrough
  - Server management quick reference
  - Common issues table
  - Remote access setup with tunnel management
- Restarted all services after location change/shutdown

### January 4, 2026 - Session 5
- Added yt-dlp fallback for YouTube transcript fetching (fixes "no captions" errors)
- Added toast notifications to DataManager for sync/upload feedback
- Fixed skip button in discovery wizard (now skips directly to Step 3)
- Made custom search terms always visible in discovery step
- Remade "Why Local?" section with accurate benefits:
  - Local Context, Less Impact, Community Owned
  - Privacy & Security, Local Jobs, $0/month
- Replaced emojis with Heroicons throughout landing page
- Improved Settings page with detailed descriptions:
  - AI provider explanations (local vs cloud trade-offs)
  - Temperature guidance (0.3-0.5 recommended for civic Q&A)
  - Model size explanations (RAM/VRAM requirements)
  - Enhanced thinking options descriptions

### January 4, 2026 - Session 4
- Deployed frontend to Netlify (https://neighborhood-ai.netlify.app)
- Set up Cloudflare Tunnel for backend access
- Created centralized API module (`frontend/src/api.js`) with configurable base URL
- Added `netlify.toml` with build config and SPA redirects
- Fixed ESLint warnings for CI build (removed unused imports/variables)
- Updated CORS to allow Netlify domain
- Created `start-tunnel.sh` for easy tunnel startup
- Created `DEPLOYMENT.md` with comprehensive deployment guide

### January 4, 2026 - Session 3
- Redesigned landing page with more informative content
- Added Community Constitution feature section with code example
- Added Discovery Wizard feature explanation
- Emphasized local AI benefits (fine-tuning, community customization)
- Updated Footer: removed extra text, increased logo sizes
- Created About Us page with mission, team, and licensing info
- Changed license from MIT to CC BY-NC-SA 4.0 throughout

### January 4, 2026 - Session 2
- Fixed chat 500 error (Qdrant API changed from `search()` to `query_points()`)
- Added guide button to landing page hero section
- Improved YouTube transcript collection with multiple fallback methods
- Added "Sync All" feature for batch data ingestion
- Added data protection limits (120MB or 10M words per source)
- Updated CLAUDE.md with roadmap
