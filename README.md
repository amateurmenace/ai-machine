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
- 🤖 **Flexible AI** - Local models (LM Studio, Ollama) or cloud APIs (OpenAI/Claude)
- 📜 **Community Constitution** - Versioned public rules that govern the assistant
- 🔍 **Hybrid Search** - Semantic plus keyword retrieval with reranking
- 🔗 **Verifiable Citations** - Links to the exact meeting timestamp or document page
- 📊 **Evaluation Harness** - Measure retrieval and generation separately
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

### 🏛️ Community AI v0.1

The app now implements the *Community-Owned AI* guide: a locally governed
public-information service, not just a locally running chatbot.

- **A constitution in source control.** Twenty versioned principles, injected as
  their own system message on every request. Amend a file and behavior changes
  on the next question, no retraining.
- **Hybrid retrieval.** Dense search plus keyword search, fused and reranked.
  Asked about Article 8.4, dense-only search returns Article 8.1; keyword search
  does not.
- **Citations that point at the record.** `Select Board • March 12, 2026 •
  1:13:42`, linking to that moment in the video, or to page 73 of the PDF. If
  the model invents a citation, it gets stripped.
- **A community API.** OpenAI-compatible, so an existing app switches by
  changing a base URL, plus civic endpoints for meetings, documents and search.
  Per-application keys with scopes and rate limits.
- **"Why did you answer this way?"** Sources retrieved and used, corpus
  freshness, model, and constitution version. Operational facts, not the model's
  reasoning.
- **An evaluation harness** that scores retrieval separately from generation, so
  you fix search when search is broken and the prompt when the prompt is.
- **LM Studio support**, for running Gemma locally on hardware the community
  owns.

Start here: **[COMMUNITY_AI_SETUP.md](COMMUNITY_AI_SETUP.md)**
What's built and what's left: **[COMMUNITY_AI_SCOPE.md](COMMUNITY_AI_SCOPE.md)**

```bash
cp community.example.yaml community.yaml       # name your community
cp knowledge/sources.example.yaml knowledge/sources.yaml
python3 -m scripts.bootstrap_community community.yaml --dry-run
```

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
