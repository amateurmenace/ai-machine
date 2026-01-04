# Neighborhood AI - Quick Reference Card

## Installation (One-time)
```bash
# 1. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1:8b

# 2. Install Neighborhood AI
./install.sh
```

## Daily Usage
```bash
# Start both backend and frontend
./start.sh

# Then open: http://localhost:3000
```

## Common Commands

### Ollama
```bash
# Start Ollama server
ollama serve

# List downloaded models
ollama list

# Pull a new model
ollama pull llama3.1:70b

# Test a model
ollama run llama3.1:8b "Hello!"
```

### Backend Only
```bash
python3 app.py
# Runs on http://localhost:8000
```

### Frontend Only
```bash
cd frontend
npm start
# Runs on http://localhost:3000
```

### Data Management
```bash
# View project data
ls -la data/

# Clear a project's vector database
rm -rf data/brookline-ma/qdrant/
```

## API Testing

### Create a Project
```bash
curl -X POST "http://localhost:8000/api/projects?municipality_name=Brookline,%20MA"
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

### Check Health
```bash
curl http://localhost:8000/
```

## Troubleshooting

### Port Already in Use
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Kill process on port 3000
lsof -ti:3000 | xargs kill -9
```

### Reinstall Dependencies
```bash
# Python
pip3 install -r requirements.txt --break-system-packages

# Node
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Reset Everything
```bash
# Stop all processes
pkill -f "python3 app.py"
pkill -f "react-scripts"

# Clear data
rm -rf data/

# Restart
./start.sh
```

## File Locations

- **Projects**: `./data/{project-id}/`
- **Config**: `./data/{project-id}/config.json`
- **Vector DB**: `./data/{project-id}/qdrant/`
- **Logs**: Check terminal output

## URLs

- **Landing Page**: http://localhost:3000 (Start here!)
- **Console**: http://localhost:3000/console
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (interactive Swagger UI)

## Navigation

The app has two main sections:

1. **Landing Page** (`/`)
   - Explains mission and values
   - Educational content
   - Click "Open Console" to build your AI

2. **Console** (`/console/`)
   - Project management
   - Setup wizard
   - Data sources
   - Chat interface

## Environment Variables

Create `.env` file:
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
YOUTUBE_API_KEY=...
```

## Deployment

### Public Access (Temporary)
```bash
# Install cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared

# Run tunnel
./cloudflared tunnel --url http://localhost:3000
```

### Network Access (Local)
```bash
# Get your IP
ip addr show

# Share URL: http://[YOUR-IP]:3000
```

## Data Source Examples

### YouTube Playlist
```
Type: youtube_playlist
URL: https://www.youtube.com/playlist?list=PL_kXbXA0-Qd7UxDoS9qZNcqOgbjdg5Duu
```

### Website
```
Type: website
URL: https://brookline.news
```

### PDF
```
Type: pdf_url
URL: https://brooklinema.gov/DocumentCenter/View/12345/Budget-2024
```

### RSS Feed
```
Type: rss_feed
URL: https://brookline.news/feed
```

## Model Recommendations

### For 8GB RAM (No GPU)
- `llama3.1:8b` - Best balance
- `mistral:7b` - Faster

### For 16GB+ RAM + GPU
- `llama3.1:70b` - Best quality
- `mixtral:8x7b` - Good balance

### Cloud (API Key Required)
**Anthropic Claude (Recommended):**
- `claude-opus-4-20250514` - Highest intelligence
- `claude-sonnet-4-20250514` - Best balance
- `claude-haiku-4-20250514` - Fast and cheap

**OpenAI:**
- `gpt-4o` - Best quality
- `gpt-4o-mini` - Fast and affordable

### Hybrid Strategy (Recommended)
- **Discovery:** Claude Opus 4.5 (~$0.50 one-time)
- **Chat:** Ollama llama3.1:8b (free forever)
- **Total Cost:** < $1 setup, $0/month

See FRONTIER_MODELS.md for complete guide.

## Support

- **Docs**: See USER_GUIDE.md
- **Brookline Setup**: See BROOKLINE_SETUP.md  
- **Project Structure**: See PROJECT_STRUCTURE.md
- **Contact**: stephen@weirdmachine.org

## License

MIT - Free for community use!

---
Built for Brookline Interactive Group 🏘️
