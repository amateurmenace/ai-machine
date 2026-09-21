"""
Structured records for the community knowledge base.

Section 4 of the guide makes the case that the public-meeting archive is only
valuable if it is ingested *with structure*. A transcript stored as one
undifferentiated blob can be searched; it cannot be cited, filtered by board,
or linked back to the moment somebody said the thing.

Two record types cover almost everything a municipality publishes:

* :class:`MeetingTranscriptRecord` — one speaker turn within one agenda item.
* :class:`MunicipalDocumentRecord` — one passage on one page of one document.

Both normalize into :class:`CivicChunk`, which is what actually gets embedded
and stored. Every chunk keeps a durable pointer back to the public record so the
answer can offer "jump to the meeting at 1:13:42" rather than "trust me".

Pure stdlib, so ingestion scripts and the eval runner can import it without the
web stack.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional


class SourceType:
    """Stable source-type strings. Kept as constants, not an Enum, so values
    read back from existing Qdrant payloads never fail validation."""

    MEETING_TRANSCRIPT = "meeting_transcript"
    MUNICIPAL_DOCUMENT = "municipal_document"
    WEBSITE = "website"
    DATASET = "dataset"
    UNKNOWN = "unknown"

    # Source types written by the pre-existing collectors, mapped forward.
    LEGACY_MAP = {
        "youtube": MEETING_TRANSCRIPT,
        "pdf": MUNICIPAL_DOCUMENT,
        "website": WEBSITE,
        "meeting_transcript": MEETING_TRANSCRIPT,
        "municipal_document": MUNICIPAL_DOCUMENT,
    }


# Document classes that carry different authority. Principle 16 (Source
# Hierarchy) and Principle 4 (Public Record) both depend on this distinction,
# so it is recorded at ingestion rather than guessed at answer time.
class RecordStatus:
    ADOPTED = "adopted"          # a bylaw, an approved budget, a passed vote
    PROPOSED = "proposed"        # a warrant article, a draft, a recommendation
    DISCUSSION = "discussion"    # meeting talk, public comment
    INFORMATIONAL = "informational"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _iso_date(value: Any) -> str:
    """Coerce assorted date representations to YYYY-MM-DD, or "" if hopeless."""
    if not value:
        return ""
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if not text:
        return ""
    # Already ISO, possibly with a time component.
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # YouTube publishedAt and similar ISO timestamps.
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return ""


@dataclass
class CivicChunk:
    """One embeddable passage plus everything needed to cite it.

    The metadata list follows section 4 of the guide: board or department,
    meeting date, agenda item, speaker, speaker role, document type, page
    number, effective date, superseded status, geography, address, project name,
    docket or warrant number, source URL, and ingestion date.
    """

    text: str

    # Provenance
    source: str = ""                 # human name of the source feed
    source_type: str = SourceType.UNKNOWN
    url: str = ""                    # canonical record URL
    title: str = ""

    # Civic identity
    community: str = ""              # "Brookline"
    body: str = ""                   # "Select Board", "Planning Board"
    department: str = ""             # "Finance", "Public Works"

    # Meetings
    meeting_date: str = ""           # YYYY-MM-DD
    agenda_item: str = ""
    speaker: str = ""
    speaker_role: str = ""
    start_time: Optional[float] = None   # seconds into the recording
    end_time: Optional[float] = None
    video_url: str = ""

    # Documents
    document_type: str = ""          # "bylaw", "budget", "plan", "minutes"
    page: Optional[int] = None
    section: str = ""
    effective_date: str = ""
    status: str = RecordStatus.UNKNOWN
    # What the passage represents, decided at ingestion rather than inferred by
    # the model at answer time. See knowledge/status.py for why that matters.
    status_confidence: float = 0.0
    vote_taken: bool = False
    vote_outcome: str = ""       # passed | failed | tabled | none
    vote_tally: str = ""         # "4-1", "unanimous"
    # The words that decided it, so a wrong label can be traced to its cause.
    status_evidence: str = ""

    # Civic identifiers that keyword search handles better than embeddings
    docket_number: str = ""          # docket, warrant article, case number
    project_name: str = ""
    address: str = ""
    geography: str = ""              # precinct, ward, neighborhood

    # Operations
    collection_method: str = ""
    ingested_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    date: str = ""                   # legacy generic date, kept for compatibility

    def __post_init__(self) -> None:
        self.text = self.text.strip()
        self.meeting_date = _iso_date(self.meeting_date)
        self.effective_date = _iso_date(self.effective_date)
        self.date = _iso_date(self.date) or self.meeting_date or self.effective_date
        self.source_type = SourceType.LEGACY_MAP.get(self.source_type, self.source_type)
        if not self.video_url and self.source_type == SourceType.MEETING_TRANSCRIPT:
            self.video_url = self.url

    # --- derived ---------------------------------------------------------

    @property
    def record_date(self) -> str:
        """The date that matters for this record, whatever its type."""
        return self.meeting_date or self.effective_date or self.date

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    def chunk_id(self) -> str:
        """Deterministic id, so re-ingesting a source updates rather than duplicates."""
        basis = "|".join(
            [
                self.url,
                self.title,
                str(self.page or ""),
                str(int(self.start_time)) if self.start_time is not None else "",
                self.speaker,
                self.text[:200],
            ]
        )
        return hashlib.md5(basis.encode("utf-8")).hexdigest()

    def to_payload(self) -> Dict[str, Any]:
        """Flat dict for the vector store payload."""
        payload = asdict(self)
        payload["word_count"] = self.word_count
        return {k: v for k, v in payload.items() if v not in (None, "")or k == "text"}

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "CivicChunk":
        return normalize_payload(payload)


# --- record types ---------------------------------------------------------


@dataclass
class MeetingTranscriptRecord:
    """One speaker turn in a public meeting, per section 4 of the guide."""

    community: str
    body: str
    meeting_date: str
    text: str
    agenda_item: str = ""
    speaker: str = ""
    speaker_role: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    video_url: str = ""
    title: str = ""
    source: str = ""
    collection_method: str = ""
    # Left unknown so the classifier can read the passage. Its own default for
    # meeting text is discussion, so a transcript that says nothing about a vote
    # still ends up marked discussion; the difference is that one that does say
    # "the motion carries 4-1" is no longer overridden by this default.
    status: str = RecordStatus.UNKNOWN

    def to_chunk(self) -> CivicChunk:
        title = self.title or f"{self.body} — {self.meeting_date}"
        return CivicChunk(
            text=self.text,
            source=self.source or self.body,
            source_type=SourceType.MEETING_TRANSCRIPT,
            url=self.video_url,
            title=title,
            community=self.community,
            body=self.body,
            meeting_date=self.meeting_date,
            agenda_item=self.agenda_item,
            speaker=self.speaker,
            speaker_role=self.speaker_role,
            start_time=self.start_time,
            end_time=self.end_time,
            video_url=self.video_url,
            status=self.status,
            collection_method=self.collection_method,
        )


@dataclass
class MunicipalDocumentRecord:
    """One passage of a municipal document, per section 4 of the guide."""

    title: str
    text: str
    department: str = ""
    date: str = ""
    page: Optional[int] = None
    section: str = ""
    document_url: str = ""
    document_type: str = ""
    community: str = ""
    body: str = ""
    effective_date: str = ""
    status: str = RecordStatus.UNKNOWN
    docket_number: str = ""
    source: str = ""
    collection_method: str = ""

    def to_chunk(self) -> CivicChunk:
        return CivicChunk(
            text=self.text,
            source=self.source or self.department or self.title,
            source_type=SourceType.MUNICIPAL_DOCUMENT,
            url=self.document_url,
            title=self.title,
            community=self.community,
            body=self.body,
            department=self.department,
            document_type=self.document_type,
            page=self.page,
            section=self.section,
            effective_date=self.effective_date or self.date,
            status=self.status,
            docket_number=self.docket_number,
            collection_method=self.collection_method,
            date=self.date,
        )


# --- normalization of existing data ---------------------------------------

# Payload keys written by the collectors that predate this module.
_LEGACY_KEYS = {
    "source", "source_type", "url", "title", "date", "text", "word_count",
    "collection_method", "video_id", "timestamp",
}


def normalize_payload(payload: Dict[str, Any]) -> CivicChunk:
    """Upgrade any stored payload, old or new, into a :class:`CivicChunk`.

    The app already has ingested corpora whose payloads only carry
    ``source``/``source_type``/``url``/``title``/``date`` plus a YouTube
    ``timestamp``. Rather than requiring a re-index before hybrid retrieval and
    citations work, those payloads are mapped forward here: the YouTube
    timestamp becomes ``start_time``, the video id reconstructs ``video_url``,
    and a missing body is left blank rather than invented.
    """
    if not payload:
        return CivicChunk(text="")

    known = {f for f in CivicChunk.__dataclass_fields__}  # type: ignore[attr-defined]
    kwargs: Dict[str, Any] = {k: v for k, v in payload.items() if k in known}
    kwargs.setdefault("text", payload.get("text", ""))

    # Legacy YouTube transcript segments.
    if kwargs.get("start_time") is None and payload.get("timestamp") is not None:
        try:
            kwargs["start_time"] = float(payload["timestamp"])
        except (TypeError, ValueError):
            pass

    video_id = payload.get("video_id")
    if video_id and not kwargs.get("video_url"):
        kwargs["video_url"] = f"https://www.youtube.com/watch?v={video_id}"

    # Legacy source types map forward; anything unrecognized is left alone.
    raw_type = kwargs.get("source_type") or SourceType.UNKNOWN
    kwargs["source_type"] = SourceType.LEGACY_MAP.get(raw_type, raw_type)

    # A legacy transcript segment has a timestamp but no meeting_date; the
    # generic `date` field is the best available stand-in.
    if (
        kwargs["source_type"] == SourceType.MEETING_TRANSCRIPT
        and not kwargs.get("meeting_date")
        and payload.get("date")
    ):
        kwargs["meeting_date"] = payload["date"]

    # Drop an ingestion date we did not actually record, so the default
    # factory does not backdate old chunks to today.
    if "ingested_at" not in payload:
        kwargs.pop("ingested_at", None)

    try:
        return CivicChunk(**kwargs)
    except TypeError:
        return CivicChunk(text=str(payload.get("text", "")))


# --- chunking helpers ------------------------------------------------------


def apply_status(chunk: "CivicChunk") -> "CivicChunk":
    """Classify what a passage represents, unless the source already declared it.

    Imported lazily because knowledge.status reads the constants defined here,
    and a module-level import would be circular. The classifier is pure stdlib,
    so this costs nothing at ingestion.
    """
    if chunk.status and chunk.status != RecordStatus.UNKNOWN:
        return chunk

    try:
        from knowledge.status import classify_status
    except ImportError:
        return chunk

    assessment = classify_status(chunk.text, {
        "source_type": chunk.source_type,
        "document_type": chunk.document_type,
        "status": chunk.status,
    })
    chunk.status = assessment.status
    chunk.status_confidence = assessment.confidence
    chunk.vote_taken = assessment.vote.vote_taken
    chunk.vote_outcome = assessment.vote.outcome
    chunk.vote_tally = assessment.vote.tally
    chunk.status_evidence = "; ".join(assessment.evidence[:3])
    return chunk


def _split_words(text: str, chunk_size: int, overlap: int) -> List[str]:
    words = text.split()
    if not words:
        return []
    if len(words) <= chunk_size:
        return [" ".join(words)]
    step = max(1, chunk_size - overlap)
    chunks = []
    for i in range(0, len(words), step):
        piece = words[i:i + chunk_size]
        if len(piece) < 20 and chunks:
            # Fold a short tail into the previous chunk rather than emitting
            # a fragment too small to be worth citing.
            chunks[-1] = chunks[-1] + " " + " ".join(piece)
            break
        chunks.append(" ".join(piece))
        if i + chunk_size >= len(words):
            break
    return chunks


# Automatic captions record what was heard as well as what was said. A stream
# that opens ten minutes before the gavel is ten minutes of "[music]", which
# became a passage, got an embedding, and sat in the archive as a record of the
# Select Board. A closed list and not "anything in brackets", because a person
# captioning by hand writes "[Chair Wilson]" and that one is worth keeping.
_SOUND_TAGS = re.compile(
    r"\[\s*(music|applause|laughter|laughs|cheering|cheers|silence|noise|background noise|"
    r"inaudible|crosstalk|coughs?|coughing|clears throat|sighs?|snorts?|_+)\s*\]",
    re.I,
)


def meeting_chunks(
    segments: Iterable[Dict[str, Any]],
    community: str,
    body: str,
    meeting_date: str,
    video_url: str,
    title: str = "",
    source: str = "",
    collection_method: str = "",
    target_words: int = 220,
) -> List[CivicChunk]:
    """Group raw transcript segments into citable passages.

    Raw caption segments are a few seconds long, which is too short to answer
    anything. Consecutive segments are merged until they reach ``target_words``
    or the speaker changes, so each chunk stays attributable to one person and
    keeps the timestamp of the moment it starts.
    """
    chunks: List[CivicChunk] = []
    buffer: List[str] = []
    buf_start: Optional[float] = None
    buf_end: Optional[float] = None
    buf_speaker = ""
    buf_role = ""
    buf_item = ""

    def flush() -> None:
        nonlocal buffer, buf_start, buf_end, buf_speaker, buf_role, buf_item
        text = " ".join(buffer).strip()
        if text:
            chunks.append(
                MeetingTranscriptRecord(
                    community=community,
                    body=body,
                    meeting_date=meeting_date,
                    text=text,
                    agenda_item=buf_item,
                    speaker=buf_speaker,
                    speaker_role=buf_role,
                    start_time=buf_start,
                    end_time=buf_end,
                    video_url=video_url,
                    title=title,
                    source=source,
                    collection_method=collection_method,
                ).to_chunk()
            )
            apply_status(chunks[-1])
        buffer = []
        buf_start = buf_end = None
        buf_speaker = buf_role = buf_item = ""

    for segment in segments:
        seg_text = _clean(_SOUND_TAGS.sub(" ", str(segment.get("text") or "")))
        if not seg_text:
            continue
        speaker = _clean(segment.get("speaker"))
        item = _clean(segment.get("agenda_item"))

        speaker_changed = bool(buffer) and speaker and speaker != buf_speaker
        item_changed = bool(buffer) and item and item != buf_item
        if speaker_changed or item_changed:
            flush()

        if not buffer:
            buf_speaker = speaker
            buf_role = _clean(segment.get("speaker_role"))
            buf_item = item
            start = segment.get("start_time", segment.get("start"))
            try:
                buf_start = float(start) if start is not None else None
            except (TypeError, ValueError):
                buf_start = None

        buffer.append(seg_text)
        end = segment.get("end_time")
        if end is None and segment.get("start") is not None:
            try:
                end = float(segment["start"]) + float(segment.get("duration", 0) or 0)
            except (TypeError, ValueError):
                end = None
        try:
            buf_end = float(end) if end is not None else buf_end
        except (TypeError, ValueError):
            pass

        if sum(len(b.split()) for b in buffer) >= target_words:
            flush()

    flush()
    return chunks


def document_chunks(
    pages: Iterable[Dict[str, Any]],
    title: str,
    document_url: str,
    department: str = "",
    date: str = "",
    document_type: str = "",
    community: str = "",
    body: str = "",
    status: str = RecordStatus.UNKNOWN,
    source: str = "",
    collection_method: str = "",
    chunk_size: int = 350,
    overlap: int = 60,
) -> List[CivicChunk]:
    """Chunk a document while preserving page numbers.

    Page numbers are the difference between "the budget says $4M somewhere" and
    a citation a resident can check, so chunking happens *within* a page rather
    than across the whole document.
    """
    chunks: List[CivicChunk] = []
    for page in pages:
        page_text = page.get("text", "")
        if not page_text.strip():
            continue
        page_number = page.get("page")
        try:
            page_number = int(page_number) if page_number is not None else None
        except (TypeError, ValueError):
            page_number = None

        for piece in _split_words(page_text, chunk_size, overlap):
            chunks.append(
                MunicipalDocumentRecord(
                    title=title,
                    text=piece,
                    department=department,
                    date=date,
                    page=page_number,
                    section=_clean(page.get("section")),
                    document_url=document_url,
                    document_type=document_type,
                    community=community,
                    body=body,
                    status=status,
                    source=source,
                    collection_method=collection_method,
                ).to_chunk()
            )
            apply_status(chunks[-1])
    return chunks


if __name__ == "__main__":
    segs = [
        {"text": "Thank you Madam Chair.", "start": 4231.0, "duration": 3,
         "speaker": "Jane Smith", "speaker_role": "Transportation Director",
         "agenda_item": "Washington Street redesign"},
        {"text": "The redesign would narrow the roadway to one travel lane " * 12,
         "start": 4234.0, "duration": 120, "speaker": "Jane Smith",
         "speaker_role": "Transportation Director",
         "agenda_item": "Washington Street redesign"},
    ]
    out = meeting_chunks(
        segs, community="Brookline", body="Select Board",
        meeting_date="2026-04-14", video_url="https://youtube.com/watch?v=abc",
    )
    for c in out:
        print(f"{c.body} | {c.meeting_date} | {c.speaker} | t={c.start_time} | {c.word_count}w")

    doc = document_chunks(
        [{"text": "Public Works operating budget increases by 3.1 percent. " * 60,
          "page": 127, "section": "Public Works"}],
        title="FY2027 Recommended Budget", document_url="https://ex.org/b.pdf",
        department="Finance", date="2026-02-03", document_type="budget",
    )
    for c in doc:
        print(f"{c.title} | p.{c.page} | {c.section} | {c.word_count}w")

    legacy = normalize_payload({
        "text": "the board discussed parking", "source": "Town Meetings",
        "source_type": "youtube", "url": "https://youtube.com/watch?v=xyz",
        "title": "Select Board Jan 15", "date": "2024-01-15",
        "video_id": "xyz", "timestamp": 1234.5,
    })
    print(f"legacy -> type={legacy.source_type} start={legacy.start_time} "
          f"video={legacy.video_url} meeting_date={legacy.meeting_date}")
