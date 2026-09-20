"""
Answering the questions everyone asks, before they ask.

Section 1.4 of the roadmap. A town's questions have a long head: "when is trash
day", "how do I get a parking permit", "what happened at the last Select Board
meeting". On a local model those cost thirty seconds of GPU each, every time,
for an answer that has not changed since yesterday.

Precomputing them overnight, when the hardware is idle anyway, turns latency
from the local model's weakness into a non-issue for exactly the questions that
matter most. A resident asking a common question gets an answer in the time it
takes to read a database row.

The whole design hinges on **when a cached answer stops being valid**, and the
cache key is the interesting part:

* the **corpus fingerprint**, because a new meeting can change the answer
* the **constitution hash**, because amended rules can change what the answer is
  allowed to say, and serving an answer produced under superseded rules would
  quietly undo the ledger's entire point
* the **model and provider**, because a different model is a different answer
* the **question**, normalized

Any of those changing invalidates the entry. That is strict, and it should be:
the failure mode of a stale civic answer is a resident acting on a repealed
bylaw.

Where the questions come from, honestly: a curated list an operator maintains,
plus the app's own suggested questions. Mining them from request logs is
supported but only works when a community has deliberately turned on question
text logging, because otherwise the logs hold salted hashes and nothing else.
That is the privacy promise working as intended, and it costs this feature some
automation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

DEFAULT_DATA_ROOT = os.getenv("COMMUNITY_DATA_ROOT", "./data")

# Questions worth precomputing for any municipality. An operator replaces these
# with what people actually ask at the counter, which is always better.
STARTER_QUESTIONS = [
    "When is trash and recycling collected?",
    "How do I get a resident parking permit?",
    "What happened at the most recent Select Board meeting?",
    "How do I apply for a building permit?",
    "When is the next Town Meeting?",
    "How do I register to vote?",
    "What are the town hall hours?",
    "How do I report a pothole or a streetlight that is out?",
    "What is the snow removal policy for sidewalks?",
    "How do I speak at a public meeting?",
    "What is the current property tax rate?",
    "Where can I find the town budget?",
]


def normalize_question(question: str) -> str:
    """Collapse the differences that do not change the answer."""
    text = (question or "").strip().lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


@dataclass
class CacheKey:
    """Everything that, if changed, makes a stored answer wrong."""

    question: str
    corpus_fingerprint: str
    constitution_hash: str
    model: str
    provider: str

    def digest(self) -> str:
        basis = "|".join([
            normalize_question(self.question),
            self.corpus_fingerprint,
            self.constitution_hash,
            self.model,
            self.provider,
        ])
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class CachedAnswer:
    key: str
    question: str
    answer: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)
    computed_at: str = ""
    corpus_fingerprint: str = ""
    constitution_hash: str = ""
    model: str = ""
    provider: str = ""
    hits: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def age_days(self) -> Optional[float]:
        try:
            computed = datetime.fromisoformat(self.computed_at)
        except (TypeError, ValueError):
            return None
        return (datetime.now() - computed).total_seconds() / 86400


class AnswerCache:
    """Precomputed answers for one community.

    Stored as one JSON file per project rather than in the vector database,
    because it is small, it is not searched, and an operator should be able to
    read it and delete a wrong entry with a text editor.
    """

    def __init__(self, project_id: str, data_root: str = DEFAULT_DATA_ROOT) -> None:
        self.project_id = project_id
        self.data_root = data_root
        self._lock = threading.Lock()
        self._entries: Dict[str, CachedAnswer] = {}
        self._loaded = False

    @property
    def path(self) -> Path:
        return Path(self.data_root) / self.project_id / "precomputed.json"

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self.path.is_file():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        known = set(CachedAnswer.__dataclass_fields__)  # type: ignore[attr-defined]
        for raw in data.get("answers", []):
            entry = CachedAnswer(**{k: v for k, v in raw.items() if k in known})
            self._entries[entry.key] = entry

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({
                "project_id": self.project_id,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "note": (
                    "Precomputed answers. An entry is used only when the corpus, "
                    "the constitution, the model and the provider all still match "
                    "what produced it. Delete an entry to force a recompute."
                ),
                "answers": [e.to_dict() for e in self._entries.values()],
            }, indent=2, default=str), encoding="utf-8")
        except OSError:
            # A cache that cannot be written is a slow system, not a broken one.
            pass

    def get(self, key: CacheKey) -> Optional[CachedAnswer]:
        with self._lock:
            self._load()
            entry = self._entries.get(key.digest())
            if entry is None:
                return None
            entry.hits += 1
            return entry

    def put(self, key: CacheKey, answer: str, sources: List[Dict[str, Any]],
            provenance: Dict[str, Any]) -> CachedAnswer:
        entry = CachedAnswer(
            key=key.digest(),
            question=key.question,
            answer=answer,
            sources=sources,
            provenance=provenance,
            computed_at=datetime.now().isoformat(timespec="seconds"),
            corpus_fingerprint=key.corpus_fingerprint,
            constitution_hash=key.constitution_hash,
            model=key.model,
            provider=key.provider,
        )
        with self._lock:
            self._load()
            self._entries[entry.key] = entry
            self._save()
        return entry

    def prune(self, corpus_fingerprint: str = "", constitution_hash: str = "",
              max_age_days: int = 30) -> int:
        """Drop entries that can no longer be served. Returns how many."""
        with self._lock:
            self._load()
            before = len(self._entries)
            keep: Dict[str, CachedAnswer] = {}
            for key, entry in self._entries.items():
                if corpus_fingerprint and entry.corpus_fingerprint != corpus_fingerprint:
                    continue
                if constitution_hash and entry.constitution_hash != constitution_hash:
                    continue
                age = entry.age_days()
                if age is not None and max_age_days and age > max_age_days:
                    continue
                keep[key] = entry
            self._entries = keep
            if len(keep) != before:
                self._save()
            return before - len(keep)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            self._load()
            entries = list(self._entries.values())
        return {
            "entries": len(entries),
            "total_hits": sum(e.hits for e in entries),
            "oldest": min((e.computed_at for e in entries), default=None),
            "newest": max((e.computed_at for e in entries), default=None),
            "models": sorted({e.model for e in entries if e.model}),
        }

    def clear(self) -> int:
        with self._lock:
            self._load()
            count = len(self._entries)
            self._entries = {}
            self._save()
            return count


# --- choosing what to precompute ------------------------------------------


def question_list(project_id: str, data_root: str = DEFAULT_DATA_ROOT
                  ) -> Tuple[List[str], str]:
    """The questions to precompute, and where they came from."""
    path = Path(data_root) / project_id / "common_questions.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            questions = [str(q) for q in data.get("questions", []) if str(q).strip()]
            if questions:
                return questions, str(path)
        except (OSError, json.JSONDecodeError):
            pass
    return list(STARTER_QUESTIONS), "built-in starter list"


def save_question_list(project_id: str, questions: List[str],
                       data_root: str = DEFAULT_DATA_ROOT) -> Path:
    path = Path(data_root) / project_id / "common_questions.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "project_id": project_id,
        "note": (
            "Questions precomputed when the hardware is idle. Replace these with "
            "what residents actually ask at the counter; that list is always "
            "better than a generic one."
        ),
        "questions": questions,
    }, indent=2), encoding="utf-8")
    return path


def mine_questions_from_logs(project_id: str, days: int = 30, minimum: int = 3,
                             data_root: str = DEFAULT_DATA_ROOT) -> List[Tuple[str, int]]:
    """Find repeated questions in the request log.

    Only works when a community has turned on question text logging. Otherwise
    the logs hold salted hashes, which reveal that a question repeats without
    revealing what it was. That is the privacy promise working as designed, and
    it costs this feature its automation rather than costing residents their
    privacy.
    """
    directory = Path(data_root) / project_id / "logs"
    if not directory.is_dir():
        return []

    cutoff = datetime.now().date() - timedelta(days=days)
    counts: Dict[str, int] = {}
    originals: Dict[str, str] = {}

    for entry in sorted(directory.glob("requests-*.jsonl")):
        stamp = entry.stem.replace("requests-", "")
        try:
            if datetime.strptime(stamp, "%Y-%m-%d").date() < cutoff:
                continue
        except ValueError:
            continue
        try:
            lines = entry.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            question = record.get("question")
            if not question:
                continue
            normalized = normalize_question(question)
            if len(normalized) < 8:
                continue
            counts[normalized] = counts.get(normalized, 0) + 1
            originals.setdefault(normalized, question)

    ranked = [(originals[k], v) for k, v in counts.items() if v >= minimum]
    ranked.sort(key=lambda pair: pair[1], reverse=True)
    return ranked


# --- running a pass --------------------------------------------------------


@dataclass
class PrecomputeResult:
    project_id: str
    computed: int = 0
    reused: int = 0
    failed: int = 0
    pruned: int = 0
    questions: int = 0
    source: str = ""
    errors: List[str] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def corpus_fingerprint(agent: Any) -> str:
    """A cheap identity for the corpus as it stands right now."""
    try:
        stats = agent.vector_store.get_stats()
        return f"{stats.get('total_documents', 0)}:{stats.get('embedding_model', '')}"
    except Exception:
        return "unknown"


def run_precompute(project_id: str, agent: Any, questions: Optional[List[str]] = None,
                   data_root: str = DEFAULT_DATA_ROOT,
                   max_questions: int = 50,
                   on_progress: Optional[Callable[[int, int, str], None]] = None
                   ) -> PrecomputeResult:
    """Answer the common questions and store the results.

    Intended for a scheduled overnight run. Safe to interrupt: each answer is
    written as it is produced, so a run that dies halfway leaves the answers it
    did compute.
    """
    result = PrecomputeResult(
        project_id=project_id,
        started_at=datetime.now().isoformat(timespec="seconds"),
    )

    if questions is None:
        questions, result.source = question_list(project_id, data_root)
    else:
        result.source = "supplied by the caller"
    questions = questions[:max_questions]
    result.questions = len(questions)

    cache = AnswerCache(project_id, data_root)
    fingerprint = corpus_fingerprint(agent)
    constitution_hash = getattr(agent.constitution, "content_hash", "")
    model = getattr(agent.config, "model_name", "")
    provider = getattr(agent, "client_type", "")

    result.pruned = cache.prune(fingerprint, constitution_hash)

    for index, question in enumerate(questions, start=1):
        if on_progress:
            on_progress(index, len(questions), question)

        key = CacheKey(question, fingerprint, constitution_hash, model, provider)
        if cache.get(key) is not None:
            result.reused += 1
            continue

        try:
            response = agent.chat(question)
        except Exception as exc:
            result.failed += 1
            result.errors.append(f"{question[:48]!r}: {type(exc).__name__}: {exc}")
            continue

        if response.get("error"):
            result.failed += 1
            result.errors.append(f"{question[:48]!r}: {response['error']}")
            continue

        # An answer that found nothing is not worth caching. The archive may
        # have the record tomorrow, and a cached "I do not have that" would
        # outlive the gap it describes.
        provenance = response.get("provenance", {}) or {}
        if not provenance.get("sources_used"):
            result.failed += 1
            result.errors.append(f"{question[:48]!r}: answered with no sources; not cached")
            continue

        cache.put(key, response.get("answer", ""), response.get("sources", []),
                  provenance)
        result.computed += 1

    result.finished_at = datetime.now().isoformat(timespec="seconds")
    return result


def lookup(project_id: str, question: str, agent: Any,
           data_root: str = DEFAULT_DATA_ROOT) -> Optional[Dict[str, Any]]:
    """Serve a precomputed answer, if one is still valid for this question."""
    cache = AnswerCache(project_id, data_root)
    key = CacheKey(
        question,
        corpus_fingerprint(agent),
        getattr(agent.constitution, "content_hash", ""),
        getattr(agent.config, "model_name", ""),
        getattr(agent, "client_type", ""),
    )
    entry = cache.get(key)
    if entry is None:
        return None

    provenance = dict(entry.provenance)
    provenance["precomputed"] = True
    provenance["precomputed_at"] = entry.computed_at
    # Say so on the answer. A resident told an answer was prepared earlier can
    # judge for themselves whether to ask again, and hiding it would be the
    # kind of small dishonesty this project cannot afford.
    return {
        "answer": entry.answer,
        "sources": entry.sources,
        "context_used": bool(entry.sources),
        "provenance": provenance,
        "cached": True,
    }
