"""
Create or update a community deployment from a YAML configuration.

Section 20 of the guide: a new community provides configuration, a constitution,
and a source list rather than forking the platform. This script is the step that
turns those files into a running project.

    python3 -m scripts.bootstrap_community community.yaml
    python3 -m scripts.bootstrap_community community.yaml --ingest
    python3 -m scripts.bootstrap_community community.yaml --dry-run

Re-running is safe: it updates the existing project's configuration and adds any
sources that are not already present, matching on URL. It never deletes a source
and never drops an already-ingested corpus.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    import yaml
except ImportError:  # pragma: no cover
    raise SystemExit("PyYAML is required: pip install pyyaml")


# youtube_channel is the one scripts/backfill_archive.py walks. It was missing
# here, so the documented way to set up a backfill was refused by this script.
VALID_SOURCE_TYPES = {"youtube_channel", "youtube_playlist", "youtube_video",
                      "website", "pdf_url"}


def load_config(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise SystemExit(
            f"No configuration at {path}.\n"
            f"Copy the template first:  cp community.example.yaml community.yaml"
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if "community" not in data:
        raise SystemExit(f"{path}: missing the required 'community:' section.")
    return data


def load_sources(config: Dict[str, Any], config_path: Path) -> List[Dict[str, Any]]:
    """Read the source inventory, from a referenced file or inline."""
    inline = config.get("sources")
    if inline:
        return list(inline)

    sources_file = config.get("sources_file")
    if not sources_file:
        return []

    path = (config_path.parent / sources_file).resolve()
    if not path.is_file():
        print(f"  note: no source inventory at {path}; continuing with no sources.")
        print(f"        copy knowledge/sources.example.yaml to create one.")
        return []

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(data.get("sources") or [])


def validate(config: Dict[str, Any], sources: List[Dict[str, Any]]) -> List[str]:
    """Return a list of problems. Empty means the configuration is usable."""
    problems: List[str] = []
    community = config.get("community", {})

    for field in ("name", "project_id"):
        if not community.get(field):
            problems.append(f"community.{field} is required")

    project_id = str(community.get("project_id", ""))
    if project_id and not project_id.replace("-", "").replace("_", "").isalnum():
        problems.append(
            f"community.project_id {project_id!r} should contain only letters, "
            f"digits, hyphens and underscores"
        )

    provider = (config.get("model") or {}).get("provider", "lmstudio")
    if provider not in {"lmstudio", "ollama", "openai", "anthropic"}:
        problems.append(f"model.provider {provider!r} is not a supported provider")

    for i, source in enumerate(sources):
        label = source.get("name") or f"sources[{i}]"
        if not source.get("url"):
            problems.append(f"{label}: url is required")
        source_type = source.get("type")
        if source_type not in VALID_SOURCE_TYPES:
            problems.append(
                f"{label}: type {source_type!r} must be one of "
                f"{', '.join(sorted(VALID_SOURCE_TYPES))}"
            )
        if "REPLACE_ME" in str(source.get("url", "")):
            problems.append(f"{label}: url still contains the template placeholder")

    return problems


def build_project(config: Dict[str, Any], sources: List[Dict[str, Any]],
                  existing: Optional[Any] = None) -> Any:
    from models import AIProvider, DataSource, DataSourceType, ProjectConfig

    community = config["community"]
    model = config.get("model") or {}
    retrieval = config.get("retrieval") or {}
    privacy = config.get("privacy") or {}
    provenance = config.get("provenance") or {}
    constitution = config.get("constitution") or {}
    api = config.get("api") or {}

    project_id = str(community["project_id"])

    settings: Dict[str, Any] = {
        "project_id": project_id,
        "municipality_name": community["name"],
        "project_name": community.get("assistant_name") or f"{community['name']} AI",
        "tagline": community.get("tagline") or "Your local AI assistant",
        "ai_provider": AIProvider(model.get("provider", "lmstudio")),
        "model_name": model.get("name") or "gemma-4-26b-a4b",
        "lmstudio_base_url": model.get("base_url"),
        "temperature": float(model.get("temperature", 0.3)),
        "max_tokens": int(model.get("max_tokens", 2000)),
        "context_window": int(model.get("context_window", 8192)),
        "constitution_version": str(constitution.get("version", "latest")),
        "enable_hybrid_search": bool(retrieval.get("hybrid", True)),
        "enable_reranking": bool(retrieval.get("reranking", True)),
        "enable_query_expansion": bool(retrieval.get("query_expansion", True)),
        "enable_model_query_rewrite": bool(retrieval.get("model_query_rewrite", False)),
        "retrieval_top_k": int(retrieval.get("top_k", 8)),
        "retrieval_candidate_pool": int(retrieval.get("candidate_pool", 24)),
        "require_citations": bool(provenance.get("require_citations", True)),
        "log_requests": bool(privacy.get("log_requests", True)),
        "log_question_text": bool(privacy.get("log_question_text", False)),
        "log_retention_days": int(privacy.get("log_retention_days", 30)),
        "api_enabled": bool(api.get("enabled", False)),
    }

    if existing is not None:
        # Preserve everything the config file does not speak to: issued API
        # keys, ingestion statistics, branding, creation time.
        merged = existing.model_dump()
        merged.update(settings)
        merged["updated_at"] = datetime.now()
        project = ProjectConfig(**merged)
    else:
        project = ProjectConfig(**settings)

    # Add sources that are not already configured, matched on URL.
    known = {s.url: s for s in project.data_sources}
    for entry in sources:
        url = str(entry["url"])
        # Channel scan settings. Compared with None because meetings_only: false
        # is a real choice and a falsy one.
        scan_settings = {
            key: entry[key]
            for key in ("min_confidence", "meetings_only", "scan_limit", "bodies")
            if entry.get(key) is not None
        }
        if url in known:
            # How a channel is read is configuration, and a board list gets
            # edited many times before a backfill: look at the dry run, add the
            # subcommittee it missed, look again. So these follow the file.
            # Nothing else about an existing source is touched.
            known[url].metadata = {**(known[url].metadata or {}), **scan_settings}
            continue
        metadata = {
            key: entry[key]
            for key in ("body", "department", "document_type", "status",
                        "date", "meeting_date")
            if entry.get(key)
        }
        metadata.update(scan_settings)
        project.data_sources.append(
            DataSource(
                id=str(uuid.uuid4()),
                type=DataSourceType(entry["type"]),
                url=url,
                name=entry.get("name") or url,
                description=entry.get("description"),
                metadata=metadata,
            )
        )
        known[url] = project.data_sources[-1]

    return project


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("config", nargs="?", default="community.yaml")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate and print, write nothing")
    parser.add_argument("--ingest", action="store_true",
                        help="ingest every configured source after saving")
    args = parser.parse_args(argv)

    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    sources = load_sources(config, config_path)

    print(f"Configuration: {config_path}")
    print(f"Community:     {config['community'].get('name')}")
    print(f"Project id:    {config['community'].get('project_id')}")
    print(f"Sources:       {len(sources)}")
    print()

    problems = validate(config, sources)
    if problems:
        print("Configuration problems:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("Configuration is valid.")

    # Report which constitution will govern this deployment.
    from community.constitution import load_constitution
    constitution_cfg = config.get("constitution") or {}
    constitution = load_constitution(
        version=str(constitution_cfg.get("version", "latest")),
        directory=constitution_cfg.get("directory"),
    )
    if constitution:
        print(f"Constitution:  v{constitution.version} "
              f"({len(constitution.principles)} principles, {constitution.status})")
    else:
        print("Constitution:  NONE FOUND. The assistant will run without "
              "community rules.")
        print("               Create constitution/constitution-v1.0.md before "
              "serving residents.")

    if args.dry_run:
        print("\nDry run: nothing written.")
        return 0

    import app as application

    project_id = str(config["community"]["project_id"])
    existing = application.load_project(project_id)
    project = build_project(config, sources, existing=existing)
    application.save_project(project)

    action = "Updated" if existing else "Created"
    print(f"\n{action} project '{project_id}' with {len(project.data_sources)} sources.")
    print(f"  data/{project_id}/config.json")

    if args.ingest:
        import asyncio

        from models import DataIngestionJob

        print("\nIngesting sources. This can take a long time for video archives.")
        for source in project.data_sources:
            if not source.enabled:
                continue
            print(f"  {source.name} ({source.type.value}) ...", flush=True)
            job = DataIngestionJob(
                job_id=str(uuid.uuid4()), project_id=project_id,
                source_id=source.id, status="pending",
            )
            asyncio.run(application.ingest_source_background(job, project))
            if job.status == "completed":
                print(f"    {job.total_items} passages indexed")
            else:
                print(f"    FAILED: {job.error}")

    print("\nNext:")
    print(f"  python3 -m evals.run_evals --project {project_id} --retrieval-only")
    print(f"  curl http://localhost:8000/community/{project_id}/stats")
    return 0


if __name__ == "__main__":
    sys.exit(main())
