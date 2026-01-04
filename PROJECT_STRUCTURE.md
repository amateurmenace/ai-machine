# Neighborhood AI - Project Structure

## Overview

Neighborhood AI is a complete browser-based platform for creating AI assistants for local communities. It features:

- **Setup Wizard** - AI-powered discovery of local data sources
- **Data Ingestion** - Automated collection from YouTube, websites, PDFs, RSS feeds
- **Flexible AI** - Support for Ollama (local), OpenAI, and Anthropic
- **Vector RAG** - Semantic search with citations
- **Chat Interface** - Test and use your community AI
- **Data Management** - Add/remove sources, monitor ingestion

## Directory Structure

```
neighborhood-ai/
├── README.md                    # Project overview
├── USER_GUIDE.md               # Comprehensive user guide
├── BROOKLINE_SETUP.md          # Brookline-specific setup guide
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
├── .gitignore                  # Git ignore rules
├── install.sh                  # Installation script
├── start.sh                    # Startup script (runs both backend & frontend)
│
├── Backend (Python/FastAPI)
│   ├── app.py                  # Main FastAPI application
│   ├── models.py               # Pydantic data models
│   ├── agent.py                # AI agent with RAG
│   ├── vector_store.py         # Qdrant vector database manager
│   │
│   └── collectors/             # Data collection modules
│       ├── youtube_collector.py       # YouTube transcript collector
│       ├── website_collector.py       # Website scraper
│       ├── pdf_collector.py           # PDF extractor
│       └── source_discovery.py        # AI-powered source discovery
│
└── Frontend (React/Tailwind)
    ├── package.json            # Node dependencies
    ├── tailwind.config.js      # Tailwind CSS configuration
    ├── postcss.config.js       # PostCSS configuration
    │
    ├── public/
    │   └── index.html          # HTML template
    │
    └── src/
        ├── index.js            # React entry point
        ├── index.css           # Global styles with Tailwind
        ├── App.js              # Main app component with routing
        ├── App.css             # App-specific styles
        │
        └── components/         # React components
            ├── LandingPage.js       # Marketing/educational landing page
            ├── SetupWizard.js       # 4-step project creation wizard
            ├── ProjectList.js       # List all projects
            ├── Dashboard.js         # Project overview & stats
            ├── DataManager.js       # Manage data sources
            └── ChatInterface.js     # Chat with your AI
```

## Routes

### Public Routes
- `/` - Landing page (marketing, mission, values)

### Console Routes (App)
- `/console` - Project list
- `/console/new` - Setup wizard
- `/console/projects/:id` - Project dashboard
- `/console/projects/:id/data` - Data management
- `/console/projects/:id/chat` - Chat interface

## Key Technologies

### Backend
- **FastAPI** - Modern Python web framework
- **Qdrant** - Vector database for semantic search
- **Sentence Transformers** - Text embeddings (all-MiniLM-L6-v2)
- **Ollama** - Local LLM inference
- **OpenAI/Anthropic SDKs** - Cloud AI providers
- **BeautifulSoup4** - Web scraping
- **youtube-transcript-api** - YouTube caption extraction
- **pypdf** - PDF text extraction

### Frontend
- **React 18** - UI framework
- **React Router** - Client-side routing
- **Tailwind CSS** - Utility-first styling
- **Heroicons** - Icon library
- **Axios** - HTTP client

## Data Flow

```
User Question
    ↓
Chat Interface (React)
    ↓
FastAPI Backend (/api/chat)
    ↓
AI Agent (agent.py)
    ↓
Vector Store Search (vector_store.py)
    ↓
Retrieve Top 5 Relevant Documents
    ↓
Build Context + System Prompt
    ↓
LLM (Ollama/OpenAI/Anthropic)
    ↓
Generate Answer with Citations
    ↓
Return to User
```

## Data Ingestion Flow

```
Add Data Source (React)
    ↓
POST /api/projects/{id}/sources
    ↓
Save to Project Config
    ↓
Start Ingestion Job (Background Task)
    ↓
Collector Module (youtube/website/pdf)
    ↓
Raw Data (transcripts/html/text)
    ↓
Chunk into Segments (~500 words)
    ↓
Generate Embeddings (SentenceTransformer)
    ↓
Store in Qdrant Vector DB
    ↓
Update Source Metadata
```

## API Endpoints

### Projects
- `POST /api/projects` - Create project
- `GET /api/projects` - List projects
- `GET /api/projects/{id}` - Get project
- `PUT /api/projects/{id}` - Update project

### Data Sources
- `POST /api/projects/{id}/discover-sources` - AI source discovery
- `POST /api/projects/{id}/sources` - Add source
- `DELETE /api/projects/{id}/sources/{source_id}` - Remove source
- `POST /api/projects/{id}/sources/{source_id}/ingest` - Start ingestion

### Chat & Status
- `POST /api/chat` - Chat with AI
- `GET /api/jobs/{job_id}` - Get ingestion job status
- `GET /api/projects/{id}/stats` - Get project stats
- `GET /api/ollama/models` - List Ollama models

## Configuration

Projects are stored in `./data/{project_id}/`:
```
data/
└── brookline-ma/
    ├── config.json         # Project configuration
    └── qdrant/            # Vector database files
```

### Project Config Structure
```json
{
  "project_id": "brookline-ma",
  "municipality_name": "Brookline, MA",
  "project_name": "Brookline AI",
  "ai_provider": "ollama",
  "model_name": "llama3.1:8b",
  "temperature": 0.7,
  "system_prompt": "You are Brookline AI...",
  "data_sources": [
    {
      "id": "source1",
      "type": "youtube_playlist",
      "url": "https://youtube.com/playlist?list=...",
      "name": "Town Meetings",
      "enabled": true
    }
  ]
}
```

## Component Details

### SetupWizard.js
4-step wizard for creating projects:
1. **Location** - Enter municipality name
2. **Discover** - AI finds relevant data sources
3. **Configure** - Choose AI provider and personality
4. **Launch** - Start data ingestion

### DataManager.js
Manage data sources:
- Add new sources (YouTube, websites, PDFs)
- Sync/refresh existing sources
- Monitor ingestion progress
- Remove sources

### ChatInterface.js
Interactive chat:
- Real-time conversation
- Source citations
- Conversation history
- Suggested questions

### agent.py
Core AI logic:
- RAG (Retrieval-Augmented Generation)
- Vector search for context
- LLM integration (Ollama/OpenAI/Anthropic)
- Source citation

### vector_store.py
Vector database management:
- Document chunking
- Embedding generation
- Semantic search
- Metadata filtering

## Collectors

### youtube_collector.py
- Extract playlist videos
- Download transcripts
- Segment by time
- Metadata extraction

### website_collector.py
- Respect robots.txt
- Extract main content
- Follow links (same domain)
- Rate limiting

### pdf_collector.py
- Download from URL
- Extract text
- Handle multi-page documents
- Chunk by page or size

### source_discovery.py
- Use GPT-4/Claude to find sources
- Municipality-specific search
- Validate URLs
- Suggest personality

## Deployment Scenarios

### Local Development
```bash
./start.sh
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
```

### Local Network (BIG Station)
```bash
# Find IP address
ip addr show

# Access from network
http://[IP-ADDRESS]:3000
```

### Public Access (Cloudflare Tunnel)
```bash
cloudflared tunnel --url http://localhost:3000
# Returns: https://random.trycloudflare.com
```

### Production (VPS)
```bash
# PM2 for backend
pm2 start app.py

# Build frontend
cd frontend && npm run build

# Nginx reverse proxy
# /etc/nginx/sites-available/neighborhood-ai
```

## Extension Points

### Adding New Collectors
Create `collectors/new_collector.py`:
```python
class NewCollector:
    def collect(self, url):
        # Return list of documents
        return [{
            'text': '...',
            'metadata': {
                'source': 'name',
                'url': 'url',
                'date': '...'
            }
        }]
```

Add to `app.py` ingestion logic.

### Custom AI Providers
Add to `agent.py`:
```python
elif config.ai_provider == "custom":
    from custom_llm import CustomLLM
    self.client = CustomLLM(api_key=config.api_key)
    self.client_type = "custom"
```

### Additional Frontend Pages
Create component, add to `App.js`:
```javascript
<Route path="/custom" element={<CustomPage />} />
```

## Performance Considerations

### Vector Search
- **Model**: all-MiniLM-L6-v2 (384 dimensions, fast)
- **Index**: HNSW for sub-second search
- **Top-K**: Default 5 documents per query

### Data Storage
- **Qdrant**: Local file-based (scales to millions)
- **Config**: JSON files (simple, portable)
- **Embeddings**: Cached, computed once

### LLM Performance
- **Ollama**: 20-40 tokens/sec on CPU, 60-100 on GPU
- **OpenAI**: 50-100 tokens/sec
- **Claude**: 40-80 tokens/sec

## Security Notes

### Current Implementation
- No authentication (suitable for local use)
- API keys stored in config (not ideal for production)
- CORS wide open (for development)

### Production Recommendations
- Add authentication (OAuth, JWT)
- Store API keys in secrets manager
- Restrict CORS origins
- Rate limiting
- Input validation
- HTTPS only

## Testing

### Manual Testing
1. Create project
2. Add known data sources
3. Verify ingestion completes
4. Ask test questions
5. Verify citations

### Automated Testing (TODO)
- Unit tests for collectors
- Integration tests for API
- E2E tests for wizard
- Load testing for vector search

## Roadmap / Future Features

- [ ] User authentication
- [ ] Multi-user projects
- [ ] Scheduled data syncing
- [ ] Analytics dashboard
- [ ] Export conversations
- [ ] API webhooks
- [ ] Mobile app
- [ ] Docker deployment
- [ ] Database migrations
- [ ] Admin panel
- [ ] Rate limiting
- [ ] Caching layer
- [ ] Sentiment analysis
- [ ] Topic modeling
- [ ] Document summaries
- [ ] Translation support

## License

MIT License - Feel free to use for your community!

## Credits

Built for Brookline Interactive Group and civic technologists everywhere.

Contact: stephen@weirdmachine.org
