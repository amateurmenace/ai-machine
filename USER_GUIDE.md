# Neighborhood AI User Guide

## Quick Start Guide

### Prerequisites

- **Python 3.8+** - [Download here](https://www.python.org/downloads/)
- **Node.js 16+** - [Download here](https://nodejs.org/)
- **Ollama** (optional, for local AI) - [Download here](https://ollama.ai)

### Installation

1. **Clone or download the project**
   ```bash
   cd neighborhood-ai
   ```

2. **Run the installation script**
   ```bash
   chmod +x install.sh
   ./install.sh
   ```

3. **Set up API keys (optional)**
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

4. **Start the application**
   ```bash
   chmod +x start.sh
   ./start.sh
   ```

5. **Open your browser**
   - Navigate to `http://localhost:3000`

## Creating Your First Project

### Step 1: Location Setup

1. Click "New Project" in the top right
2. Enter your municipality name (e.g., "Brookline, MA")
3. Optionally give it a custom name (e.g., "Brookline AI")
4. If you have an OpenAI API key, enter it to enable AI source discovery

### Step 2: Discover Data Sources

The AI will automatically find relevant sources for your community:

- **Official sources**: Town websites, YouTube channels
- **News sources**: Local news sites, community blogs  
- **Civic data**: Meeting minutes, public records
- **Community**: Reddit, local forums

**Review and select** which sources you want to use.

### Step 3: Configure Your AI

Choose your AI provider:

**Option A: Ollama (Local & Free)**
- Install Ollama: `curl -fsSL https://ollama.com/install.sh | sh`
- Pull a model: `ollama pull llama3.1:8b`
- Select "ollama" as provider
- Model name: `llama3.1:8b`

**Option B: OpenAI (Cloud)**
- Get API key from [OpenAI](https://platform.openai.com/api-keys)
- Select "openai" as provider
- Model name: `gpt-4o` or `gpt-4o-mini`
- Enter your API key

**Option C: Anthropic Claude (Cloud)**
- Get API key from [Anthropic](https://console.anthropic.com/)
- Select "anthropic" as provider
- Model name: `claude-sonnet-4-20250514`
- Enter your API key

**Customize the personality:**
- Adjust temperature (0.0 = focused, 1.0 = creative)
- Write a custom system prompt for unique personality

### Step 4: Launch!

Click "Launch My AI" to:
- Save your configuration
- Start data ingestion from all sources
- Create your vector database
- Make your AI available for chatting

## Using Your AI

### Chat Interface

1. Navigate to your project
2. Click "Chat Interface"
3. Ask questions about your community!

**Example questions:**
- "When is trash day?"
- "What happened at the last Select Board meeting?"
- "How do I get a parking permit?"
- "What local events are happening this week?"

### Managing Data

**Add new sources:**
1. Go to "Manage Data"
2. Click "Add Source"
3. Choose type (YouTube, Website, PDF, etc.)
4. Enter URL and description
5. Click "Sync" to start ingestion

**Sync existing sources:**
- Click the refresh icon next to any source
- Data will be re-ingested and updated

**Remove sources:**
- Click the trash icon to remove
- Associated data will be deleted

## Data Source Types

### YouTube Playlists

Best for: Government meeting recordings, town events

**How to find playlist URL:**
1. Go to YouTube
2. Find the playlist
3. Copy URL like: `https://www.youtube.com/playlist?list=PL_xxxxx`

**What gets collected:**
- Video transcripts
- Titles and descriptions
- Timestamps for context

### Websites

Best for: Town websites, local news, community blogs

**Tips:**
- Start with the homepage or sitemap
- Crawler will find linked pages automatically
- Respects robots.txt

**What gets collected:**
- Main content text
- Page titles and descriptions
- Links to other pages

### PDF Documents

Best for: Meeting minutes, reports, policy documents

**How to use:**
- Direct URL to PDF file
- Or URL to page that lists PDFs

**What gets collected:**
- Full text content
- Document metadata
- Page-by-page breakdown

### RSS Feeds

Best for: News updates, blog posts

**How to find RSS URL:**
- Look for RSS icon on website
- Common paths: `/feed`, `/rss`, `/feed.xml`

### Reddit Communities

Best for: Community discussions, local sentiment

**Format:** `https://reddit.com/r/brookline`

## Advanced Configuration

### Customizing Personality

Edit the system prompt to make your AI unique:

```
You are [Name], an AI assistant for [Community].

Your personality:
- Warm and welcoming
- Expert in local history
- Passionate about civic engagement
- Always cite your sources

Special features:
- You can quote from recent town meetings
- You know the context behind local decisions
- You connect people with the right departments
```

### Temperature Settings

- **0.0-0.3**: Very focused, factual, consistent
- **0.4-0.7**: Balanced, natural conversation
- **0.8-1.0**: More creative, varied responses

### Model Selection

**For Ollama (Local):**
- `llama3.1:8b` - Good balance (4GB RAM)
- `llama3.1:70b` - Best quality (40GB RAM, needs GPU)
- `mistral:7b` - Faster, less RAM (4GB)

**For OpenAI:**
- `gpt-4o` - Best quality, more expensive
- `gpt-4o-mini` - Fast and affordable
- `gpt-3.5-turbo` - Cheapest option

**For Anthropic:**
- `claude-sonnet-4-20250514` - Best balance
- `claude-haiku-4-20250322` - Fastest and cheapest

## Troubleshooting

### Backend won't start

**Error: "Port 8000 in use"**
```bash
# Find and kill process
lsof -ti:8000 | xargs kill -9

# Or change port
export PORT=8001
python3 app.py
```

**Error: "Module not found"**
```bash
pip3 install -r requirements.txt --break-system-packages
```

### Frontend won't start

**Error: "Port 3000 in use"**
```bash
# Kill process
lsof -ti:3000 | xargs kill -9
```

**Error: "npm install fails"**
```bash
# Clear cache and retry
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Ollama connection issues

**Error: "Connection refused"**
```bash
# Make sure Ollama is running
ollama serve

# In another terminal, test
ollama list
```

**Error: "Model not found"**
```bash
# Pull the model first
ollama pull llama3.1:8b
```

### Data ingestion fails

**YouTube transcripts not found:**
- Video might not have captions
- Try different videos in playlist
- Check if transcript is auto-generated or manual

**Website scraping blocked:**
- Check robots.txt compliance
- Add rate limiting
- Some sites block automated access

**PDF extraction errors:**
- PDF might be image-based (needs OCR)
- Try different PDF viewer/converter
- Check file isn't password protected

## Deployment

### Local Network Access

**Using Cloudflare Tunnel (easiest):**
```bash
# Install
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared

# Run tunnel
./cloudflared tunnel --url http://localhost:3000
# You'll get a public URL like: https://xxx.trycloudflare.com
```

### Production Deployment

**Option 1: VPS (DigitalOcean, Linode)**
```bash
# Install on server
ssh user@your-server
git clone your-repo
cd neighborhood-ai
./install.sh

# Use PM2 for process management
npm install -g pm2
pm2 start app.py --name neighborhood-ai
pm2 startup
pm2 save

# Nginx reverse proxy
sudo apt install nginx
# Configure nginx to proxy port 8000
```

**Option 2: Docker**
```bash
# Coming soon!
docker-compose up -d
```

## Best Practices

### Data Quality

1. **Start with high-quality sources**
   - Official town websites
   - Verified news outlets
   - Primary documents (not summaries)

2. **Regular updates**
   - Sync weekly for news sources
   - Monthly for stable content
   - After major events or meetings

3. **Verify information**
   - Test your AI with known questions
   - Check citations are accurate
   - Update system prompt if needed

### Privacy & Ethics

1. **Public data only**
   - Don't scrape private information
   - Respect copyright and terms of service
   - Follow robots.txt

2. **Transparency**
   - Make it clear this is an AI
   - Provide source citations
   - Admit limitations

3. **Community focused**
   - Emphasize civic engagement
   - Connect people with real officials
   - Encourage participation

## API Reference

### Create Project
```bash
curl -X POST "http://localhost:8000/api/projects?municipality_name=Brookline,%20MA"
```

### Add Data Source
```bash
curl -X POST "http://localhost:8000/api/projects/brookline-ma/sources" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "source1",
    "type": "youtube_playlist",
    "url": "https://youtube.com/playlist?list=...",
    "name": "Town Meetings",
    "enabled": true
  }'
```

### Chat
```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "brookline-ma",
    "message": "When is trash day?"
  }'
```

## Getting Help

- **GitHub Issues**: Report bugs or request features
- **Documentation**: Check README.md
- **Community**: Share your civic AI projects!

## Contributing

We welcome contributions! Areas where you can help:

- Additional data source types
- Improved UI/UX
- Better personality templates
- Deployment guides
- Translation/i18n

---

**Built for communities by civic technologists 🏘️**
