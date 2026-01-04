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
    allow_origins=["*"],  # Update this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (use database in production)
projects: Dict[str, ProjectConfig] = {}
ingestion_jobs: Dict[str, DataIngestionJob] = {}
agents: Dict[str, NeighborhoodAgent] = {}


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
    
    agent = NeighborhoodAgent(project)
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
    project_id = municipality_name.lower().replace(" ", "-").replace(",", "")
    
    # Check if exists
    if load_project(project_id):
        raise HTTPException(status_code=400, detail="Project already exists")
    
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
    
    # Invalidate agent cache
    if project_id in agents:
        del agents[project_id]
    
    return {"message": "Project updated successfully"}


@app.post("/api/projects/{project_id}/discover-sources")
async def discover_sources(
    project_id: str, 
    provider: str = "anthropic",
    model: Optional[str] = None,
    api_key: Optional[str] = None
):
    """Use AI to discover data sources for a municipality"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        discovery = SourceDiscovery(api_key=api_key, provider=provider, model=model)
        result = discovery.discover_sources(project.municipality_name)
        
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
        
        # Initialize vector store
        vector_store = VectorStore(
            path=f"./data/{project.project_id}/qdrant",
            collection_name=project.project_id
        )
        
        documents = []
        
        # Collect data based on source type
        if source.type == DataSourceType.YOUTUBE_PLAYLIST:
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
                            'url': result['url'],
                            'title': result['title'],
                            'date': result.get('published_at', ''),
                            'video_id': result['video_id'],
                            'timestamp': segment['start_time']
                        }
                    })

        elif source.type == DataSourceType.YOUTUBE_VIDEO:
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
                            'url': source.url,
                            'title': source.name,
                            'date': '',
                            'video_id': result['video_id'],
                            'timestamp': segment['start_time']
                        }
                    })
        
        elif source.type == DataSourceType.WEBSITE:
            collector = WebsiteCollector()
            
            def progress(current, total, title):
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
                            'url': result['url'],
                            'title': result['title'],
                            'date': ''
                        }
                    })
        
        elif source.type == DataSourceType.PDF_URL:
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
                            'url': source.url,
                            'title': pdf_data['title'],
                            'date': ''
                        }
                    })
                job.processed_items = 1
        
        # Add documents to vector store
        if documents:
            def vector_progress(current, total):
                job.progress = 50 + (current / total) * 50  # Second half of progress
            
            vector_store.add_documents_batch(documents, progress_callback=vector_progress)
        
        # Update source sync time
        source.last_synced = datetime.now()
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
    agent = get_or_create_agent(project_id)
    return agent.get_stats()


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
