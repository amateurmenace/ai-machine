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
    DataIngestionJob, AIProvider, DataSourceType
)
from agent import NeighborhoodAgent
from vector_store import VectorStore
from collectors.youtube_collector import YouTubeCollector
from collectors.website_collector import WebsiteCollector
from collectors.pdf_collector import PDFCollector
from collectors.source_discovery import SourceDiscovery


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


# API Routes

@app.get("/")
async def root():
    """Health check"""
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

            # Process into documents
            for result in results:
                # Chunk transcript into sections
                for segment in result['transcript']['segments']:
                    documents.append({
                        'text': segment['text'],
                        'metadata': {
                            'source': source.name,
                            'source_type': 'youtube',
                            'collection_method': collection_method,
                            'url': result['url'],
                            'title': result['title'],
                            'date': result.get('published_at', ''),
                            'video_id': result['video_id'],
                            'timestamp': segment['start_time']
                        }
                    })

        elif source.type == DataSourceType.YOUTUBE_VIDEO:
            collection_method = "youtube_transcript_api"
            collector = YouTubeCollector()
            job.total_items = 1

            result = collector.collect_video(source.url)
            if result and result.get('transcript'):
                job.processed_items = 1
                # Chunk transcript into sections
                for segment in result['transcript']['segments']:
                    documents.append({
                        'text': segment['text'],
                        'metadata': {
                            'source': source.name,
                            'source_type': 'youtube',
                            'collection_method': collection_method,
                            'url': source.url,
                            'title': source.name,
                            'date': '',
                            'video_id': result['video_id'],
                            'timestamp': segment['start_time']
                        }
                    })
            else:
                job.status = "failed"
                job.error = "No transcript available for this video. The video may not have captions enabled."
                job.completed_at = datetime.now()
                return

        elif source.type == DataSourceType.WEBSITE:
            collection_method = "web_scraper"
            collector = WebsiteCollector()

            def progress(current, total, title, extra_info=None):
                job.processed_items = current
                job.total_items = total
                job.progress = (current / total) * 100 if total > 0 else 0

            results = collector.crawl_website(source.url, max_pages=50, progress_callback=progress)

            for result in results:
                # Chunk content
                chunks = vector_store.chunk_text(result['content'])
                for chunk in chunks:
                    documents.append({
                        'text': chunk,
                        'metadata': {
                            'source': source.name,
                            'source_type': 'website',
                            'collection_method': collection_method,
                            'url': result['url'],
                            'title': result['title'],
                            'date': ''
                        }
                    })

        elif source.type == DataSourceType.PDF_URL:
            collection_method = "pdf_url_download"
            collector = PDFCollector()
            pdf_data = collector.extract_from_url(source.url)

            if pdf_data:
                job.total_items = 1
                # Chunk PDF text
                chunks = vector_store.chunk_text(pdf_data['full_text'])
                for chunk in chunks:
                    documents.append({
                        'text': chunk,
                        'metadata': {
                            'source': source.name,
                            'source_type': 'pdf',
                            'collection_method': collection_method,
                            'url': source.url,
                            'title': pdf_data['title'],
                            'date': ''
                        }
                    })
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

        # Chunk the PDF text
        chunks = vector_store.chunk_text(pdf_data['full_text'])
        job.total_items = len(chunks)

        documents = []
        for i, chunk in enumerate(chunks):
            documents.append({
                'text': chunk,
                'metadata': {
                    'source': source.name,
                    'source_type': 'pdf',
                    'collection_method': 'pdf_upload',
                    'url': source.url,
                    'title': pdf_data.get('title', source.name),
                    'date': '',
                    'page_count': pdf_data.get('num_pages', 0)
                }
            })
            job.processed_items = i + 1
            job.progress = ((i + 1) / len(chunks)) * 50

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
