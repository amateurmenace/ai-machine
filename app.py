"""
Main FastAPI Application
Serves the Neighborhood AI backend API
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import json
import os
import uuid
from datetime import datetime

from models import (
    ProjectConfig, DataSource, ChatRequest, ChatMessage,
    DataIngestionJob, AIProvider, DataSourceType, APIClient
)
from agent import NeighborhoodAgent
from vector_store import VectorStore
from collectors.youtube_collector import YouTubeCollector
from collectors.website_collector import WebsiteCollector
from collectors.pdf_collector import PDFCollector
from collectors.source_discovery import SourceDiscovery
from collectors.youtube_channel import (
    DEFAULT_SCAN_LIMIT, advance_cursor, load_state, plan_sync, save_state,
)

from api.auth import ALL_SCOPES, DEFAULT_SCOPES, new_client_record
from api.gateway import GatewayContext, configure_gateway, router as community_router
from community.constitution import (
    list_constitution_versions,
    load_constitution,
    resolve_for_project,
)
from providers import (
    LM_STUDIO_BASE_URL, PROVIDER_LABELS, build_provider_for, discover_models,
    list_lmstudio_models,
)
from knowledge.schemas import (
    RecordStatus, SourceType, document_chunks, meeting_chunks,
)
from rag.hybrid import HybridRetriever

# Try to import advanced scraper (requires playwright)
try:
    from collectors.website_collector_advanced import AdvancedWebsiteCollector
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Playwright not available, using basic web scraper")


app = FastAPI(
    title="Neighborhood AI API",
    description="Backend API for creating community AI assistants",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "https://neighborhood-ai.netlify.app",  # Production Netlify
        "https://neighborhood.weirdmachine.org",  # Custom domain
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (use database in production)
projects: Dict[str, ProjectConfig] = {}
ingestion_jobs: Dict[str, DataIngestionJob] = {}
agents: Dict[str, NeighborhoodAgent] = {}
vector_stores: Dict[str, VectorStore] = {}  # Cache to avoid Qdrant locking issues


# Helper functions
def get_project_path(project_id: str) -> str:
    """Get file path for project"""
    return f"./data/{project_id}"


def save_project(project: ProjectConfig):
    """Save project to disk"""
    path = get_project_path(project.project_id)
    os.makedirs(path, exist_ok=True)

    # Create subdirectories for vector store and uploads
    os.makedirs(f"{path}/qdrant", exist_ok=True)
    os.makedirs(f"{path}/uploads", exist_ok=True)

    with open(f"{path}/config.json", 'w') as f:
        json.dump(project.model_dump(), f, indent=2, default=str)

    projects[project.project_id] = project


def load_project(project_id: str) -> Optional[ProjectConfig]:
    """Load project from disk"""
    if project_id in projects:
        return projects[project_id]
    
    path = f"./data/{project_id}/config.json"
    if os.path.exists(path):
        with open(path, 'r') as f:
            data = json.load(f)
            project = ProjectConfig(**data)
            projects[project_id] = project
            return project
    
    return None


def list_project_ids() -> List[str]:
    """Every project id on disk, so the gateway can resolve a key to a project."""
    ids = set(projects.keys())
    if os.path.exists("./data"):
        for folder in os.listdir("./data"):
            if os.path.isfile(f"./data/{folder}/config.json"):
                ids.add(folder)
    return sorted(ids)


def get_or_create_agent(project_id: str) -> NeighborhoodAgent:
    """Get or create agent for a project"""
    if project_id in agents:
        return agents[project_id]

    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get or create shared vector store
    if project_id not in vector_stores:
        vector_stores[project_id] = VectorStore(
            path=f"./data/{project_id}/qdrant",
            collection_name=project_id
        )

    # Create agent with shared vector store
    agent = NeighborhoodAgent(project, vector_store=vector_stores[project_id])
    agents[project_id] = agent
    return agent


@app.on_event("startup")
async def start_archive_sync():
    """Begin scanning channel sources for new meetings on an interval."""
    import scheduler

    scheduler.start(
        list_project_ids=list_project_ids,
        load_project=load_project,
        ingest=ingest_source_background,
    )


@app.on_event("shutdown")
async def stop_archive_sync():
    import scheduler

    scheduler.shutdown()


@app.get("/api/admin/sync-runs")
async def list_sync_runs():
    """What the last scheduled archive sync did, per project."""
    import scheduler

    return {
        "enabled": scheduler.SYNC_ENABLED,
        "interval_minutes": scheduler.SYNC_INTERVAL_MINUTES,
        "last_runs": scheduler.last_runs(),
    }


# The Community AI gateway: OpenAI-compatible /v1 endpoints plus the civic
# knowledge API. See api/gateway.py and COMMUNITY_AI_SCOPE.md.
configure_gateway(
    GatewayContext(
        load_project=load_project,
        list_project_ids=list_project_ids,
        get_agent=get_or_create_agent,
        save_project=save_project,
        data_root="./data",
    )
)
app.include_router(community_router)


# API Routes

@app.get("/api")
async def api_root():
    """API root. What used to live at `/` before the console shared this service."""
    return {
        "status": "healthy",
        "service": "Neighborhood AI API",
        "version": "1.0.0",
        "docs": "/docs",
        "community_api": "/community",
        "openai_compatible": "/v1",
    }


@app.get("/")
async def root():
    """The console when it is built into this service, the API status otherwise.

    In a container the built console is served from here, so `/` is the app a
    resident sees. In local development the console runs on its own port and
    this returns the status JSON it always did.
    """
    index = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "frontend", "build", "index.html")
    if os.path.isfile(index):
        from fastapi.responses import FileResponse
        return FileResponse(index)

    return {
        "status": "healthy",
        "service": "Neighborhood AI API",
        "version": "1.0.0"
    }


@app.post("/api/projects")
async def create_project(
    municipality_name: str,
    project_name: Optional[str] = None
):
    """Create a new project"""
    base_project_id = municipality_name.lower().replace(" ", "-").replace(",", "")

    # Check if base project ID exists, if so add a number suffix
    project_id = base_project_id
    counter = 2
    while load_project(project_id):
        project_id = f"{base_project_id}-{counter}"
        counter += 1

    project = ProjectConfig(
        project_id=project_id,
        municipality_name=municipality_name,
        project_name=project_name or f"{municipality_name} AI"
    )

    save_project(project)

    return {
        "project_id": project_id,
        "message": "Project created successfully"
    }


@app.get("/api/projects")
async def list_projects():
    """List all projects"""
    # Load all projects from disk
    if os.path.exists("./data"):
        for folder in os.listdir("./data"):
            project_id = folder
            if project_id not in projects:
                load_project(project_id)
    
    return {
        "projects": [
            {
                "project_id": p.project_id,
                "municipality_name": p.municipality_name,
                "project_name": p.project_name,
                "created_at": p.created_at.isoformat() if isinstance(p.created_at, datetime) else p.created_at
            }
            for p in projects.values()
        ]
    }


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    """Get project details"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return project.model_dump()


@app.put("/api/projects/{project_id}")
async def update_project(project_id: str, updates: Dict):
    """Update project configuration"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Update fields
    for key, value in updates.items():
        if hasattr(project, key):
            setattr(project, key, value)

    project.updated_at = datetime.now()
    save_project(project)

    # Invalidate caches
    if project_id in agents:
        del agents[project_id]
    if project_id in vector_stores:
        del vector_stores[project_id]

    return {"message": "Project updated successfully"}


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project and all its data"""
    import shutil

    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Remove from memory caches
    if project_id in projects:
        del projects[project_id]
    if project_id in agents:
        del agents[project_id]
    if project_id in vector_stores:
        del vector_stores[project_id]

    # Remove project data directory
    project_path = get_project_path(project_id)
    if os.path.exists(project_path):
        try:
            shutil.rmtree(project_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete project data: {str(e)}")

    return {"message": "Project deleted successfully", "project_id": project_id}


@app.post("/api/projects/{project_id}/discover-sources")
async def discover_sources(
    project_id: str,
    provider: str = "anthropic",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    custom_prompt: Optional[str] = None
):
    """Use AI to discover data sources for a municipality"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        discovery = SourceDiscovery(api_key=api_key, provider=provider, model=model)
        result = discovery.discover_sources(project.municipality_name, custom_prompt=custom_prompt)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects/{project_id}/sources")
async def add_data_source(project_id: str, source: DataSource):
    """Add a data source to the project"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Generate ID if not provided
    if not source.id:
        source.id = str(uuid.uuid4())
    
    project.data_sources.append(source)
    save_project(project)
    
    return {"message": "Data source added", "source_id": source.id}


@app.delete("/api/projects/{project_id}/sources/{source_id}")
async def remove_data_source(project_id: str, source_id: str):
    """Remove a data source"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project.data_sources = [s for s in project.data_sources if s.id != source_id]
    save_project(project)
    
    return {"message": "Data source removed"}


def _source_body(source: DataSource) -> str:
    """The board or committee a source belongs to.

    Set ``body`` in a source's metadata to name it explicitly (for example
    "Select Board"); otherwise the source's own name is the best available
    signal, and is better than leaving the field empty.
    """
    return (source.metadata or {}).get("body") or source.name or ""


def _pdf_pages(pdf_data: Dict) -> List[Dict]:
    """Normalize the PDF collector's page list for the document chunker."""
    pages = pdf_data.get("pages") or []
    normalized = [
        {"text": page.get("text", ""), "page": page.get("page_number")}
        for page in pages
        if page.get("text")
    ]
    if normalized:
        return normalized
    # Older collector output, or a PDF that yielded no per-page text.
    return [{"text": pdf_data.get("full_text", ""), "page": None}]


async def ingest_source_background(job: DataIngestionJob, project: ProjectConfig):
    """Background task for data ingestion"""
    ingestion_jobs[job.job_id] = job
    job.status = "running"
    job.started_at = datetime.now()
    
    try:
        # Find the source
        source = next((s for s in project.data_sources if s.id == job.source_id), None)
        if not source:
            job.status = "failed"
            job.error = "Source not found"
            return
        
        # Get or create vector store (cached to avoid locking issues)
        if project.project_id not in vector_stores:
            vector_stores[project.project_id] = VectorStore(
                path=f"./data/{project.project_id}/qdrant",
                collection_name=project.project_id
            )
        vector_store = vector_stores[project.project_id]
        
        documents = []
        
        # Collect data based on source type
        collection_method = "unknown"

        if source.type == DataSourceType.YOUTUBE_PLAYLIST:
            collection_method = "youtube_transcript_api"
            collector = YouTubeCollector()

            def progress(current, total, title):
                job.processed_items = current
                job.total_items = total
                job.progress = (current / total) * 100 if total > 0 else 0

            results = collector.collect_playlist(source.url, progress_callback=progress)

            # Build structured meeting records rather than loose caption lines.
            # Grouping by speaker and agenda item keeps each passage citable and
            # keeps the timestamp that lets a resident jump to the moment.
            for result in results:
                for chunk in meeting_chunks(
                    result['transcript']['segments'],
                    community=project.municipality_name,
                    body=_source_body(source),
                    meeting_date=result.get('published_at', ''),
                    video_url=result['url'],
                    title=result['title'],
                    source=source.name,
                    collection_method=collection_method,
                ):
                    documents.append({'text': chunk.text, 'metadata': chunk.to_payload()})

        elif source.type == DataSourceType.YOUTUBE_CHANNEL:
            # A channel is scanned, not downloaded: figure out which meetings
            # are new, then pull a transcript for each one. State on disk is
            # what makes the second run cheap and the hundredth run free.
            collection_method = "youtube_channel_sync"
            meta = source.metadata or {}
            state = load_state(project.project_id, source.id, source.url)

            plan = plan_sync(
                source.url,
                state,
                api_key=os.getenv("YOUTUBE_API_KEY"),
                limit=int(meta.get("scan_limit") or DEFAULT_SCAN_LIMIT),
                incremental=bool(meta.get("incremental", True)),
                min_confidence=float(meta.get("min_confidence") or 0.0),
                meetings_only=bool(meta.get("meetings_only", True)),
                body_override=meta.get("body", ""),
            )

            if plan.error:
                job.status = "failed"
                job.error = f"channel scan failed: {plan.error}"
                job.completed_at = datetime.now()
                return

            job.total_items = len(plan.new_videos)
            collector = YouTubeCollector()

            for index, video in enumerate(plan.new_videos):
                job.processed_items = index
                job.progress = (index / max(len(plan.new_videos), 1)) * 50

                try:
                    result = collector.collect_video(video.url)
                except Exception as exc:
                    state.errors.append({"video_id": video.video_id,
                                         "error": f"{type(exc).__name__}: {exc}"})
                    state.mark_skipped(video.video_id, "transcript error")
                    continue

                if not result or not result.get("transcript"):
                    # A meeting with captions disabled is a real gap in the
                    # archive. Recording it means the data card can say so
                    # rather than the absence looking like the meeting never
                    # happened.
                    state.errors.append({"video_id": video.video_id,
                                         "error": "no transcript available"})
                    state.mark_skipped(video.video_id, "no transcript")
                    continue

                for chunk in meeting_chunks(
                    result["transcript"]["segments"],
                    community=project.municipality_name,
                    body=video.body or _source_body(source),
                    meeting_date=video.meeting_date or video.published_at,
                    video_url=video.url,
                    title=video.title,
                    source=source.name,
                    collection_method=collection_method,
                ):
                    payload = chunk.to_payload()
                    payload["video_id"] = video.video_id
                    payload["date_source"] = video.date_source
                    documents.append({"text": chunk.text, "metadata": payload})

                state.mark_ingested(video.video_id)

            for video in plan.skipped_not_meetings + plan.skipped_low_confidence:
                state.mark_skipped(video.video_id, "not classified as a meeting")

            advance_cursor(state, plan.new_videos)
            save_state(project.project_id, state)

            source.metadata = {**meta, "last_sync": state.last_synced_at,
                               "videos_ingested": len(state.ingested_video_ids),
                               "videos_skipped": len(state.skipped_video_ids),
                               "scan_errors": len(state.errors)}
            job.processed_items = len(plan.new_videos)

        elif source.type == DataSourceType.YOUTUBE_VIDEO:
            collection_method = "youtube_transcript_api"
            collector = YouTubeCollector()
            job.total_items = 1

            result = collector.collect_video(source.url)
            if result and result.get('transcript'):
                job.processed_items = 1
                for chunk in meeting_chunks(
                    result['transcript']['segments'],
                    community=project.municipality_name,
                    body=_source_body(source),
                    meeting_date=(source.metadata or {}).get('meeting_date', '')
                                 or result.get('published_at', ''),
                    video_url=source.url,
                    title=result.get('title') or source.name,
                    source=source.name,
                    collection_method=collection_method,
                ):
                    documents.append({'text': chunk.text, 'metadata': chunk.to_payload()})
            else:
                job.status = "failed"
                job.error = "No transcript available for this video. The video may not have captions enabled."
                job.completed_at = datetime.now()
                return

        elif source.type == DataSourceType.WEBSITE:
            # Use advanced scraper if Playwright is available
            if PLAYWRIGHT_AVAILABLE:
                collection_method = "playwright_scraper"
                collector = AdvancedWebsiteCollector(use_browser=True)
                print(f"Using advanced Playwright scraper for {source.url}")
            else:
                collection_method = "web_scraper"
                collector = WebsiteCollector()
                print(f"Using basic BeautifulSoup scraper for {source.url}")

            def progress(current, total, title, extra_info=None):
                job.processed_items = current
                job.total_items = total
                job.progress = (current / total) * 100 if total > 0 else 0

            results = collector.crawl_website(source.url, max_pages=50, progress_callback=progress)

            for result in results:
                for chunk in document_chunks(
                    [{'text': result['content']}],
                    title=result['title'],
                    document_url=result['url'],
                    department=(source.metadata or {}).get('department', ''),
                    community=project.municipality_name,
                    body=_source_body(source),
                    source=source.name,
                    collection_method=result.get('method', collection_method),
                ):
                    payload = chunk.to_payload()
                    payload['source_type'] = SourceType.WEBSITE
                    documents.append({'text': chunk.text, 'metadata': payload})

        elif source.type == DataSourceType.PDF_URL:
            collection_method = "pdf_url_download"
            collector = PDFCollector()
            pdf_data = collector.extract_from_url(source.url)

            if pdf_data:
                job.total_items = 1
                # Chunk within each page so citations can name a page number.
                # "The budget says $4M somewhere" is not a citation a resident
                # can check; "p. 127" is.
                meta = source.metadata or {}
                for chunk in document_chunks(
                    _pdf_pages(pdf_data),
                    title=pdf_data.get('title') or source.name,
                    document_url=source.url,
                    department=meta.get('department', ''),
                    date=meta.get('date', ''),
                    document_type=meta.get('document_type', ''),
                    community=project.municipality_name,
                    body=_source_body(source),
                    status=meta.get('status', RecordStatus.UNKNOWN),
                    source=source.name,
                    collection_method=collection_method,
                ):
                    documents.append({'text': chunk.text, 'metadata': chunk.to_payload()})
                job.processed_items = 1

        # Store collection method in source metadata
        if not source.metadata:
            source.metadata = {}
        source.metadata['collection_method'] = collection_method
        
        # Add documents to vector store
        if documents:
            def vector_progress(current, total):
                job.progress = 50 + (current / total) * 50  # Second half of progress

            vector_store.add_documents_batch(documents, progress_callback=vector_progress)

        # Calculate word count
        total_words = sum(len(doc['text'].split()) for doc in documents)

        # Update source with stats
        source.last_synced = datetime.now()
        source.word_count = total_words
        source.document_count = len(documents)
        save_project(project)

        # The keyword half of hybrid retrieval holds an in-memory index of the
        # corpus. Without this, newly ingested records are findable by vector
        # search but invisible to keyword search until the cache expires.
        HybridRetriever(vector_store, cache_key=project.project_id).invalidate()
        agents.pop(project.project_id, None)

        job.status = "completed"
        job.completed_at = datetime.now()
        job.total_items = len(documents)
        
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        job.completed_at = datetime.now()


@app.post("/api/projects/{project_id}/sources/{source_id}/ingest")
async def ingest_source(project_id: str, source_id: str, background_tasks: BackgroundTasks):
    """Start data ingestion for a source"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Create ingestion job
    job = DataIngestionJob(
        job_id=str(uuid.uuid4()),
        project_id=project_id,
        source_id=source_id,
        status="pending"
    )
    
    # Start background task
    background_tasks.add_task(ingest_source_background, job, project)
    
    return {
        "job_id": job.job_id,
        "message": "Ingestion started"
    }


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get ingestion job status"""
    job = ingestion_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job.model_dump()


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Chat with the AI agent"""
    agent = get_or_create_agent(request.project_id)
    
    try:
        response = agent.chat(
            message=request.message,
            conversation_history=request.conversation_history
        )
        
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/stats")
async def get_stats(project_id: str):
    """Get project statistics"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get vector store stats without loading full agent (which loads SentenceTransformer)
    vector_docs = 0
    try:
        from qdrant_client import QdrantClient
        qdrant_path = f"./data/{project_id}/qdrant"
        if os.path.exists(qdrant_path):
            client = QdrantClient(path=qdrant_path)
            try:
                info = client.get_collection(project_id)
                vector_docs = info.points_count
            except:
                pass
    except Exception as e:
        print(f"Error getting vector stats: {e}")

    return {
        'project_name': project.project_name,
        'municipality': project.municipality_name,
        'ai_provider': project.ai_provider,
        'model': project.model_name,
        'total_documents': vector_docs,
        'data_sources': len(project.data_sources),
        'active_sources': len([s for s in project.data_sources if s.enabled])
    }


@app.get("/api/ollama/models")
async def list_ollama_models():
    """List available Ollama models"""
    try:
        import ollama
        models = ollama.list()
        return {
            "models": [
                {
                    "name": m['name'],
                    "size": m.get('size', 0),
                    "modified_at": m.get('modified_at', '')
                }
                for m in models.get('models', [])
            ]
        }
    except Exception as e:
        return {"models": [], "error": str(e)}


@app.get("/api/lmstudio/models")
async def list_lm_studio_models(base_url: Optional[str] = None,
                                auth_header: Optional[str] = None):
    """List models loaded in an LM Studio server, local or tunneled."""
    return list_lmstudio_models(base_url, auth_header)


@app.get("/api/providers")
async def list_providers():
    """Every provider this deployment can use, local ones first.

    The ordering is the product statement: a community runs its own model, and
    reaches for someone else's only when it chooses to.
    """
    from models import AVAILABLE_MODELS, FRONTIER_PROVIDERS, LOCAL_PROVIDERS
    from providers import PROVIDER_LABELS

    def describe(key: str, local: bool) -> Dict:
        return {
            "provider": key,
            "label": PROVIDER_LABELS.get(key, key),
            "local": local,
            "needs_api_key": not local,
            "models": AVAILABLE_MODELS.get(key, []),
        }

    return {
        "local": [describe(p, True) for p in LOCAL_PROVIDERS],
        "frontier": [describe(p, False) for p in FRONTIER_PROVIDERS],
        "default": "lmstudio",
        "note": (
            "Local providers run on hardware the community controls; a question "
            "answered locally never leaves the building. Frontier providers send "
            "the question and the retrieved records to that company's servers."
        ),
    }


@app.get("/api/providers/{provider}/discover")
async def discover_provider_models(provider: str, base_url: Optional[str] = None,
                                   api_key: Optional[str] = None,
                                   auth_header: Optional[str] = None):
    """Ask a provider what models it actually serves right now.

    The hardcoded registry goes stale; this does not. For a local server it
    reports what is loaded this minute, which is what an operator needs when a
    configured model name does not match.
    """
    return discover_models(provider, base_url=base_url, api_key=api_key,
                           auth_header=auth_header)


@app.post("/api/projects/{project_id}/test-connection")
async def test_provider_connection(project_id: str):
    """Check that this project's configured model server answers.

    Returns the operator-facing remedy when it does not, rather than a stack
    trace: a stopped LM Studio and an unreachable tunnel look identical from the
    outside and need different fixes.
    """
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        provider = build_provider_for(project)
    except Exception as exc:
        return {"reachable": False, "detail": str(exc)}

    health = provider.health()
    health["provider_label"] = PROVIDER_LABELS.get(provider.name, provider.name)
    health["tools_supported"] = provider.supports_tools
    health["tools_enabled"] = (
        list(project.enabled_tools) if getattr(project, "enable_tools", False) else []
    )
    return health


@app.get("/api/models/{provider}")
async def list_available_models(provider: str):
    """Get available models for a provider"""
    from models import AVAILABLE_MODELS

    if provider not in AVAILABLE_MODELS:
        raise HTTPException(status_code=400, detail="Invalid provider")

    return {
        "provider": provider,
        "models": AVAILABLE_MODELS[provider]
    }


@app.post("/api/projects/{project_id}/generate-personality")
async def generate_personality(
    project_id: str,
    provider: str = "anthropic",
    api_key: Optional[str] = None
):
    """Generate AI personality based on location and discovered sources"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        discovery = SourceDiscovery(api_key=api_key, provider=provider)
        personality = discovery.suggest_personality(
            project.municipality_name,
            [s.model_dump() for s in project.data_sources]
        )

        return {"personality": personality}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects/{project_id}/sources/{source_id}/preview-scan")
async def preview_channel_scan(project_id: str, source_id: str,
                               limit: int = 100, incremental: bool = False):
    """Show what a channel sync would ingest, without ingesting anything.

    A backfill of a decade of meetings is hours of work. Looking at the plan
    first, how many videos were found, which boards were recognized, what would
    be skipped and why, costs one scan and prevents a bad ingestion of
    thousands of records with the wrong board attached.
    """
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    source = next((s for s in project.data_sources if s.id == source_id), None)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    meta = source.metadata or {}
    state = load_state(project_id, source_id, source.url)
    plan = plan_sync(
        source.url,
        state,
        api_key=os.getenv("YOUTUBE_API_KEY"),
        limit=limit,
        incremental=incremental,
        min_confidence=float(meta.get("min_confidence") or 0.0),
        meetings_only=bool(meta.get("meetings_only", True)),
        body_override=meta.get("body", ""),
    )

    if plan.error:
        raise HTTPException(status_code=502, detail=plan.error)

    return {
        "source": {"id": source.id, "name": source.name, "url": source.url},
        "summary": plan.summary(),
        "would_ingest": [v.to_dict() for v in plan.new_videos[:50]],
        "would_skip": [
            {**v.to_dict(), "reason": "not classified as a meeting"}
            for v in plan.skipped_not_meetings[:20]
        ] + [
            {**v.to_dict(), "reason": "below the confidence threshold"}
            for v in plan.skipped_low_confidence[:20]
        ],
        "state": {
            "last_synced_at": state.last_synced_at,
            "last_published_at": state.last_published_at,
            "already_ingested": len(state.ingested_video_ids),
        },
    }


@app.get("/api/projects/{project_id}/sources/{source_id}/sync-state")
async def get_sync_state(project_id: str, source_id: str):
    """What previous scans of this channel have already handled."""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    state = load_state(project_id, source_id)
    return {
        "source_id": source_id,
        "last_synced_at": state.last_synced_at,
        "last_published_at": state.last_published_at,
        "videos_ingested": len(state.ingested_video_ids),
        "videos_skipped": len(state.skipped_video_ids),
        "total_scanned": state.total_scanned,
        # Gaps in the archive belong in the data card, so they are surfaced
        # rather than buried: a meeting with captions disabled is missing
        # evidence, not a missing meeting.
        "errors": state.errors[-50:],
        "error_count": len(state.errors),
    }


@app.post("/api/projects/{project_id}/sync-all")
async def sync_all_channels(project_id: str, background_tasks: BackgroundTasks):
    """Run an incremental sync of every channel source in this project.

    This is what a scheduler calls. It ingests only what is new, so running it
    every few hours costs one listing request per channel when nothing changed.
    """
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    channels = [s for s in project.data_sources
                if s.type == DataSourceType.YOUTUBE_CHANNEL and s.enabled]
    if not channels:
        return {"started": 0, "message": "No enabled channel sources in this project."}

    jobs = []
    for source in channels:
        job = DataIngestionJob(
            job_id=str(uuid.uuid4()), project_id=project_id,
            source_id=source.id, status="pending",
        )
        background_tasks.add_task(ingest_source_background, job, project)
        jobs.append({"job_id": job.job_id, "source": source.name})

    return {"started": len(jobs), "jobs": jobs}


@app.get("/api/projects/{project_id}/constitution")
async def get_project_constitution(project_id: str):
    """The constitution governing this project, and the versions available."""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    constitution = resolve_for_project(
        project, version=getattr(project, "constitution_version", "latest") or "latest"
    )
    return {
        "project_id": project_id,
        "pinned_version": getattr(project, "constitution_version", "latest"),
        "available_versions": list_constitution_versions(),
        "active": constitution.summary(),
        "text": constitution.text,
        "rendered_prompt": constitution.render_for_prompt(project.municipality_name),
    }


@app.put("/api/projects/{project_id}/constitution")
async def set_project_constitution_version(project_id: str, payload: Dict):
    """Pin this project to a constitution version.

    Amending the constitution is a governance action taken in source control,
    not an API call. What a project chooses here is which adopted version it
    runs, so a community can review a new version before switching to it.
    """
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    version = str(payload.get("version", "latest"))
    available = list_constitution_versions()
    if version != "latest" and version not in available:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown constitution version '{version}'. Available: "
                   f"{', '.join(available) or 'none on disk'}.",
        )

    project.constitution_version = version
    project.updated_at = datetime.now()
    save_project(project)
    agents.pop(project_id, None)  # rebuild the agent with the new constitution

    return {"project_id": project_id, "constitution_version": version}


@app.get("/api/constitution/ledger")
async def get_constitution_ledger():
    """The chain, with full verification detail, for operators."""
    from community.ledger import load_ledger

    ledger = load_ledger()
    payload = ledger.to_public()
    payload["verify_command"] = "python3 -m community.ledger verify"
    return payload


@app.post("/api/constitution/seal")
async def seal_constitution_version(payload: Dict):
    """Add a constitution version to the chain.

    Sealing records what the text is. Ratifying, which happens afterwards
    through signatures, records that the community adopted it. The two are kept
    separate because they are different acts and only one of them is technical.
    """
    from community.ledger import LedgerError, seal_version

    version = str(payload.get("version") or "").strip()
    if not version:
        raise HTTPException(status_code=400, detail="A version is required.")

    try:
        block = seal_version(
            version,
            status=str(payload.get("status", "draft")),
            adopted=str(payload.get("adopted", "")),
            summary=str(payload.get("summary", "")),
            threshold=int(payload.get("threshold", 0) or 0),
        )
    except LedgerError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Clear cached constitutions so the next request reads the sealed state.
    agents.clear()

    return {
        "index": block.index,
        "version": block.version,
        "content_hash": block.content_hash,
        "prev_hash": block.prev_hash,
        "block_hash": block.compute_hash(),
        "next_step": (
            "Ratifiers sign this block hash. Read the first eight characters "
            f"({block.compute_hash().split(':')[-1][:8]}) into the meeting "
            "minutes, so the town's own public record witnesses when it existed."
        ),
    }


@app.get("/api/projects/{project_id}/api-clients")
async def list_api_clients(project_id: str):
    """List the applications authorized to call this project's community API."""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return {
        "api_enabled": project.api_enabled,
        "legacy_project_key_active": bool(project.project_api_key),
        "clients": [
            {
                "client_id": c.client_id,
                "name": c.name,
                "key_prefix": c.key_prefix,
                "scopes": c.scopes,
                "rate_limit_per_minute": c.rate_limit_per_minute,
                "enabled": c.enabled,
                "created_at": c.created_at,
                "last_used": c.last_used,
                "request_count": c.request_count,
            }
            for c in (project.api_clients or [])
        ],
    }


@app.post("/api/projects/{project_id}/api-clients")
async def create_api_client(project_id: str, payload: Dict):
    """Issue an application key.

    The plaintext key is returned once and stored only as a hash, so a leaked
    config file does not hand out working credentials.
    """
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="An application name is required.")

    scopes = payload.get("scopes") or list(DEFAULT_SCOPES)
    unknown = [s for s in scopes if s not in ALL_SCOPES]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scopes: {', '.join(unknown)}. Valid: {', '.join(ALL_SCOPES)}.",
        )

    try:
        rate_limit = int(payload.get("rate_limit_per_minute", 60))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="rate_limit_per_minute must be a number.")

    record, plaintext = new_client_record(name, scopes, rate_limit)

    project.api_clients = list(project.api_clients or []) + [APIClient(**record)]
    project.api_enabled = True
    project.updated_at = datetime.now()
    save_project(project)

    return {
        "client_id": record["client_id"],
        "name": name,
        "api_key": plaintext,
        "scopes": scopes,
        "rate_limit_per_minute": rate_limit,
        "message": "Store this key now. It is hashed on the server and cannot be shown again.",
    }


@app.delete("/api/projects/{project_id}/api-clients/{client_id}")
async def revoke_api_client(project_id: str, client_id: str):
    """Revoke one application's key without affecting the others."""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    before = len(project.api_clients or [])
    project.api_clients = [c for c in (project.api_clients or []) if c.client_id != client_id]
    if len(project.api_clients) == before:
        raise HTTPException(status_code=404, detail="Application key not found")

    project.updated_at = datetime.now()
    save_project(project)
    return {"message": f"Revoked application key {client_id}."}


@app.post("/api/projects/{project_id}/generate-api-key")
async def generate_api_key(project_id: str):
    """Generate a new API key for project access"""
    import secrets

    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Generate a secure API key
    api_key = f"nai_{secrets.token_urlsafe(32)}"
    project.project_api_key = api_key
    project.api_enabled = True
    save_project(project)

    return {
        "api_key": api_key,
        "message": "API key generated successfully. Store it securely - it won't be shown again."
    }


@app.post("/api/projects/{project_id}/revoke-api-key")
async def revoke_api_key(project_id: str):
    """Revoke the project API key"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.project_api_key = None
    project.api_enabled = False
    save_project(project)

    return {"message": "API key revoked successfully"}


@app.get("/healthz", include_in_schema=False)
async def liveness():
    """Cheap liveness probe.

    Separate from /api/health on purpose: that one probes providers and the
    filesystem, which is useful to an operator and far too expensive to run
    every thirty seconds against a container.
    """
    return {"status": "ok"}


@app.get("/api/health")
async def health_check():
    """System health check"""
    health = {
        "status": "healthy",
        "service": "Neighborhood AI API",
        "version": "1.0.0",
        "checks": {}
    }

    # Check Ollama
    ollama_status = "not_running"
    ollama_models = 0
    try:
        import ollama
        models = ollama.list()
        ollama_status = "running"
        ollama_models = len(models.get('models', []))
        health["checks"]["ollama"] = {
            "status": "running",
            "models_available": ollama_models
        }
    except Exception as e:
        health["checks"]["ollama"] = {
            "status": "not_running",
            "error": str(e)
        }

    # Check project count
    project_count = 0
    try:
        if os.path.exists("./data"):
            project_count = len([d for d in os.listdir("./data") if os.path.isdir(f"./data/{d}") and not d.startswith('.')])
        health["checks"]["projects"] = {
            "status": "ok",
            "count": project_count
        }
    except Exception as e:
        health["checks"]["projects"] = {
            "status": "error",
            "error": str(e)
        }

    # Overall status
    ollama_ok = ollama_status == "running"
    if not ollama_ok:
        health["status"] = "degraded"

    # Return flattened response for easier frontend consumption
    health["ollama_status"] = ollama_status
    health["ollama_models"] = ollama_models
    health["projects_count"] = project_count

    return health


@app.get("/api/projects/{project_id}/health")
async def project_health(project_id: str):
    """Get health status for a specific project"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    issues = []
    ready = True

    # Check AI provider
    ai_provider_status = "ready"
    ai_provider_message = None
    if project.ai_provider == "ollama":
        try:
            import ollama
            models = ollama.list()
            model_names = [m['name'] for m in models.get('models', [])]
            model_available = any(project.model_name in name for name in model_names)
            if not model_available:
                ai_provider_status = "model_missing"
                ai_provider_message = f"Model '{project.model_name}' not found. Run: ollama pull {project.model_name}"
                issues.append(f"Model not installed: {project.model_name}")
                ready = False
        except Exception as e:
            ai_provider_status = "not_running"
            ai_provider_message = "Ollama not running. Run: ollama serve"
            issues.append("Ollama is not running")
            ready = False
    else:
        has_key = bool(project.api_key) or bool(os.getenv(f"{project.ai_provider.upper()}_API_KEY"))
        if not has_key:
            ai_provider_status = "missing_api_key"
            ai_provider_message = f"API key not configured for {project.ai_provider}"
            issues.append(f"Missing API key for {project.ai_provider}")
            ready = False

    # Check vector store
    vector_docs = 0
    vector_status = "ready"
    try:
        from vector_store import VectorStore
        vs = VectorStore(
            path=f"./data/{project_id}/qdrant",
            collection_name=project_id
        )
        stats = vs.get_stats()
        vector_docs = stats.get('total_documents', 0)
        if vector_docs == 0:
            vector_status = "empty"
    except Exception as e:
        vector_status = "error"

    # Check data sources
    total_sources = len(project.data_sources)
    synced_sources = len([s for s in project.data_sources if s.last_synced])

    # Calculate total words and docs from sources
    total_words = sum(s.word_count for s in project.data_sources if s.word_count)
    total_docs_from_sources = sum(s.document_count for s in project.data_sources if s.document_count)

    if synced_sources == 0 and total_sources > 0:
        issues.append("No data sources have been ingested")
        ready = False
    elif total_sources == 0:
        issues.append("No data sources configured")
        ready = False

    return {
        "project_id": project_id,
        "project_name": project.project_name,
        "status": "healthy" if ready else "needs_setup",
        "ready": ready,
        "issues": issues,
        "ai_provider": {
            "status": ai_provider_status,
            "provider": project.ai_provider,
            "model": project.model_name,
            "message": ai_provider_message
        },
        "vector_store": {
            "status": vector_status,
            "documents": vector_docs
        },
        "data_sources": {
            "total": total_sources,
            "active": synced_sources,
            "synced": synced_sources,
            "total_words": total_words,
            "total_chunks": total_docs_from_sources
        }
    }


@app.get("/api/projects/{project_id}/documents")
async def get_project_documents(
    project_id: str,
    limit: int = 50,
    offset: int = 0,
    source_id: Optional[str] = None
):
    """Get documents from the vector store for a project"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        client = QdrantClient(path=f"./data/{project_id}/qdrant")

        # Build filter if source_id provided
        query_filter = None
        if source_id:
            # Find source name by ID
            source = next((s for s in project.data_sources if s.id == source_id), None)
            if source:
                query_filter = Filter(
                    must=[FieldCondition(key="source", match=MatchValue(value=source.name))]
                )

        # Get collection info
        try:
            collection_info = client.get_collection(project_id)
            total_count = collection_info.points_count
        except:
            return {"documents": [], "total": 0, "limit": limit, "offset": offset}

        # Scroll through documents
        records, next_offset = client.scroll(
            collection_name=project_id,
            limit=limit,
            offset=offset,
            scroll_filter=query_filter,
            with_payload=True,
            with_vectors=False
        )

        documents = []
        for record in records:
            payload = record.payload or {}
            documents.append({
                "id": str(record.id),
                "text": payload.get("text", "")[:500] + ("..." if len(payload.get("text", "")) > 500 else ""),
                "full_text": payload.get("text", ""),
                "source": payload.get("source", "unknown"),
                "source_type": payload.get("source_type", "unknown"),
                "url": payload.get("url", ""),
                "title": payload.get("title", ""),
                "date": payload.get("date", ""),
                "word_count": payload.get("word_count", 0),
                "metadata": {k: v for k, v in payload.items() if k not in ["text", "source", "source_type", "url", "title", "date", "word_count"]}
            })

        return {
            "documents": documents,
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "next_offset": next_offset
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/config")
async def get_project_config(project_id: str):
    """Get raw project configuration file"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    config_path = f"./data/{project_id}/config.json"
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return {"config": f.read(), "path": config_path}

    return {"config": json.dumps(project.model_dump(), indent=2, default=str), "path": config_path}


@app.put("/api/projects/{project_id}/config")
async def save_project_config(project_id: str, config_content: Dict):
    """Save raw project configuration"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        config_data = config_content.get("config", "")
        if isinstance(config_data, str):
            config_dict = json.loads(config_data)
        else:
            config_dict = config_data

        # Validate and update project
        updated_project = ProjectConfig(**config_dict)
        save_project(updated_project)

        # Invalidate caches
        if project_id in agents:
            del agents[project_id]
        if project_id in vector_stores:
            del vector_stores[project_id]

        return {"message": "Configuration saved successfully"}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/projects/{project_id}/upload-pdf")
async def upload_pdf(
    project_id: str,
    file: UploadFile = File(...),
    name: Optional[str] = None,
    description: Optional[str] = None,
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Upload a PDF file and add it as a source"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    try:
        # Save the file
        upload_dir = f"./data/{project_id}/uploads"
        os.makedirs(upload_dir, exist_ok=True)

        file_path = f"{upload_dir}/{file.filename}"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Create a source for this PDF
        source = DataSource(
            id=str(uuid.uuid4()),
            type=DataSourceType.PDF_UPLOAD,
            url=f"file://{file_path}",
            name=name or file.filename,
            description=description or f"Uploaded PDF: {file.filename}",
            enabled=True,
            metadata={
                "file_path": file_path,
                "original_filename": file.filename,
                "collection_method": "pdf_upload",
                "file_size": len(content)
            }
        )

        project.data_sources.append(source)
        save_project(project)

        # Create ingestion job
        job = DataIngestionJob(
            job_id=str(uuid.uuid4()),
            project_id=project_id,
            source_id=source.id,
            status="pending"
        )

        # Start ingestion
        background_tasks.add_task(ingest_pdf_upload, job, project, file_path)

        return {
            "message": "PDF uploaded successfully",
            "source_id": source.id,
            "job_id": job.job_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def ingest_pdf_upload(job: DataIngestionJob, project: ProjectConfig, file_path: str):
    """Background task to ingest uploaded PDF"""
    ingestion_jobs[job.job_id] = job
    job.status = "running"
    job.started_at = datetime.now()

    try:
        from collectors.pdf_collector import PDFCollector

        collector = PDFCollector()
        pdf_data = collector.extract_from_file(file_path)

        if not pdf_data:
            job.status = "failed"
            job.error = "Failed to extract text from PDF"
            return

        # Get or create vector store (cached to avoid locking issues)
        if project.project_id not in vector_stores:
            vector_stores[project.project_id] = VectorStore(
                path=f"./data/{project.project_id}/qdrant",
                collection_name=project.project_id
            )
        vector_store = vector_stores[project.project_id]

        # Find the source
        source = next((s for s in project.data_sources if s.id == job.source_id), None)
        if not source:
            job.status = "failed"
            job.error = "Source not found"
            return

        # Chunk within each page so citations can name a page number.
        meta = source.metadata or {}
        chunks = document_chunks(
            _pdf_pages(pdf_data),
            title=pdf_data.get('title') or source.name,
            document_url=source.url,
            department=meta.get('department', ''),
            date=meta.get('date', ''),
            document_type=meta.get('document_type', ''),
            community=project.municipality_name,
            body=_source_body(source),
            status=meta.get('status', RecordStatus.UNKNOWN),
            source=source.name,
            collection_method='pdf_upload',
        )
        job.total_items = len(chunks)

        documents = []
        for i, chunk in enumerate(chunks):
            documents.append({'text': chunk.text, 'metadata': chunk.to_payload()})
            job.processed_items = i + 1
            job.progress = ((i + 1) / len(chunks)) * 50 if chunks else 50

        # Add to vector store
        if documents:
            def vector_progress(current, total):
                job.progress = 50 + (current / total) * 50

            vector_store.add_documents_batch(documents, progress_callback=vector_progress)

        # Update source stats
        source.last_synced = datetime.now()
        source.word_count = pdf_data.get('word_count', 0)
        source.document_count = len(documents)
        save_project(project)

        HybridRetriever(vector_store, cache_key=project.project_id).invalidate()
        agents.pop(project.project_id, None)

        job.status = "completed"
        job.completed_at = datetime.now()
        job.total_items = len(documents)

    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        job.completed_at = datetime.now()


@app.get("/api/admin/jobs")
async def list_jobs():
    """List all ingestion jobs"""
    return {
        "jobs": [
            {
                "job_id": job.job_id,
                "project_id": job.project_id,
                "source_id": job.source_id,
                "status": job.status,
                "progress": job.progress,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "error": job.error
            }
            for job in ingestion_jobs.values()
        ]
    }


# --- serving the console ---------------------------------------------------
#
# In a container the built React console is served by this same process. One
# service is simpler to operate than two, and at a town's traffic the static
# files cost nothing. In local development the console runs on its own port
# under `npm start` and this block does nothing.

_FRONTEND_BUILD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "frontend", "build")

if os.path.isdir(_FRONTEND_BUILD):
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    app.mount(
        "/static",
        StaticFiles(directory=os.path.join(_FRONTEND_BUILD, "static")),
        name="static",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_console(full_path: str):
        """Serve the console, falling back to index.html for client routes.

        Declared last so every API route matches first. A request for a file
        that exists is served; anything else is a React Router path and gets
        index.html, which is what makes a deep link like /console/projects/x
        work on a fresh page load.
        """
        candidate = os.path.normpath(os.path.join(_FRONTEND_BUILD, full_path))
        # Never serve outside the build directory, whatever the path contains.
        if candidate.startswith(_FRONTEND_BUILD) and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_FRONTEND_BUILD, "index.html"))


if __name__ == "__main__":
    import uvicorn

    # Cloud Run sets PORT. Everywhere else keeps the historical default.
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
