# Neighborhood AI 🏘️

A browser-based platform to create AI assistants for local communities, towns, and neighborhoods.

## What It Does

Neighborhood AI helps you build a custom AI chatbot for your community that knows about:
- Local government meetings & decisions
- Town services & procedures  
- Community news & events
- Local businesses & resources

## Features

- 🧙 **Setup Wizard** - AI-assisted discovery of local data sources
- 📚 **Data Ingestion** - Automated collection from YouTube, websites, PDFs
- 🤖 **Flexible AI** - Use local models (Ollama) or cloud APIs (OpenAI/Claude)
- 🎨 **Customizable** - Configure personality, branding, and features
- 🚀 **One-Click Deploy** - Launch your community AI with ease

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt
npm install --prefix frontend

# Start backend
python app.py

# Start frontend (in another terminal)
cd frontend && npm start

# Open browser to http://localhost:3000
```

## Architecture

```
┌─────────────────┐
│  Landing Page   │  (Mission, values, education)
│      ↓          │
│  Console (/)    │  (Port 3000)
│  - Setup Wizard │
│  - Data Manager │
│  - Config UI    │
└────────┬────────┘
         │
         ▼ API
┌─────────────────┐
│  FastAPI Server │  (Port 8000)
│  - Data Pipeline│
│  - Ollama/OpenAI│
│  - Vector Store │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌──────┐
│ Qdrant │ │Ollama│
│        │ │/API  │
└────────┘ └──────┘
```

## What's New

### 🎨 Landing Page
Beautiful, educational landing page that explains:
- Why frontier models harm communities (environment, privacy, context)
- How Neighborhood AI solves these problems
- Our civic-minded design philosophy
- Real example: Brookline AI
- Click "Open Console" to access the app

See `LANDING_PAGE_GUIDE.md` for details on messaging and design.

## Made for Communities

Built for Brookline Interactive Group and civic technologists everywhere.

## License

MIT - Build amazing things for your community!
