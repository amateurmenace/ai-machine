"""
Reading meeting metadata out of a video title.

A public-access archive is thousands of videos whose only structured metadata is
a title and an upload date. "Select Board Meeting 4/14/2026" carries the board
and the meeting date; recovering them is what turns a video into a citable civic
record instead of an undifferentiated transcript.

Two judgments here are worth stating, because they are not obvious:

**The date in the title beats the upload date.** A meeting held on the 14th is
often posted on the 16th. For an archive where residents ask "what did the board
decide on the 14th", the title date is the true one, and the upload date is a
fallback.

**Board names need a community's own list.** "ZBA", "Advisory", "TMMA" mean
nothing generic. The defaults below cover bodies common to New England municipal
government; a community sets its own in ``sources.yaml`` and the aliases are
matched longest-first so "School Committee Budget Subcommittee" does not match
as "School Committee".

Pure stdlib and no network, so it is cheap to test against a real title list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional, Sequence, Tuple

# Bodies common to New England municipal government. A community overrides this
# with its own list; these are only a starting point.
DEFAULT_BODIES: Dict[str, Sequence[str]] = {
    "Select Board": ("select board", "selectboard", "selectmen", "board of selectmen"),
    "School Committee": ("school committee", "schoolcommittee", "school comm"),
    "Planning Board": ("planning board",),
    "Zoning Board of Appeals": ("zoning board of appeals", "zba", "zoning board"),
    "Conservation Commission": ("conservation commission", "concom"),
    "Advisory Committee": ("advisory committee", "advisory comm", "finance committee",
                           "fincom", "warrant committee"),
    "Town Meeting": ("town meeting", "annual town meeting", "special town meeting"),
    "Board of Health": ("board of health",),
    "Housing Authority": ("housing authority",),
    "Historic District Commission": ("historic district commission", "historical commission"),
    "Library Trustees": ("library trustees", "board of library trustees"),
    "Parks and Recreation": ("parks and recreation", "park and recreation", "recreation commission"),
    "Transportation Board": ("transportation board", "traffic commission"),
    "Licensing Board": ("licensing board", "license board"),
    "Redevelopment Authority": ("redevelopment authority",),
    "City Council": ("city council", "town council", "common council"),
}

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

# Ordered most specific first: an ISO date must win before the slashed pattern
# gets a chance to misread it.
_DATE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?P<y>20\d{2})[-./](?P<m>\d{1,2})[-./](?P<d>\d{1,2})\b"), "ymd"),
    (re.compile(r"\b(?P<m>\d{1,2})[-./](?P<d>\d{1,2})[-./](?P<y>20\d{2})\b"), "mdy"),
    (re.compile(r"\b(?P<m>\d{1,2})[-./](?P<d>\d{1,2})[-./](?P<y>\d{2})\b"), "mdy2"),
    (re.compile(
        r"\b(?P<mon>[A-Za-z]{3,9})\.?\s+(?P<d>\d{1,2})(?:st|nd|rd|th)?,?\s+(?P<y>20\d{2})\b"
    ), "mon_d_y"),
    (re.compile(
        r"\b(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+(?P<mon>[A-Za-z]{3,9})\.?,?\s+(?P<y>20\d{2})\b"
    ), "d_mon_y"),
    # A month and day with no year, e.g. "Select Board 4-14". The year has to
    # come from the upload date; recorded separately so the caller knows.
    (re.compile(r"\b(?P<mon>[A-Za-z]{3,9})\.?\s+(?P<d>\d{1,2})(?:st|nd|rd|th)?\b(?!\s*,?\s*20\d{2})"),
     "mon_d"),
]

_MEETING_WORDS = re.compile(
    r"\b(meeting|hearing|session|workshop|forum|deliberation|public comment)\b",
    re.I,
)


@dataclass
class MeetingTitle:
    """What a title yielded."""

    raw: str
    body: str = ""
    meeting_date: str = ""            # YYYY-MM-DD
    date_source: str = "none"         # title | upload | none
    is_meeting: bool = False
    confidence: float = 0.0           # 0..1
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "raw": self.raw, "body": self.body, "meeting_date": self.meeting_date,
            "date_source": self.date_source, "is_meeting": self.is_meeting,
            "confidence": round(self.confidence, 2), "notes": self.notes,
        }


def _valid(year: int, month: int, day: int) -> Optional[str]:
    try:
        return date(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return None


def extract_date(title: str, fallback_year: Optional[int] = None
                 ) -> Tuple[Optional[str], bool]:
    """Find a date in a title. Returns ``(iso_date, year_was_guessed)``."""
    for pattern, kind in _DATE_PATTERNS:
        match = pattern.search(title)
        if not match:
            continue

        if kind == "ymd":
            found = _valid(int(match.group("y")), int(match.group("m")), int(match.group("d")))
        elif kind == "mdy":
            found = _valid(int(match.group("y")), int(match.group("m")), int(match.group("d")))
        elif kind == "mdy2":
            found = _valid(2000 + int(match.group("y")), int(match.group("m")),
                           int(match.group("d")))
        elif kind in ("mon_d_y", "d_mon_y"):
            month = _MONTHS.get(match.group("mon").lower().rstrip("."))
            if month is None:
                continue
            found = _valid(int(match.group("y")), month, int(match.group("d")))
        else:  # mon_d, no year
            month = _MONTHS.get(match.group("mon").lower().rstrip("."))
            if month is None or fallback_year is None:
                continue
            found = _valid(fallback_year, month, int(match.group("d")))
            if found:
                return found, True

        if found:
            return found, False

    return None, False


def extract_body(title: str, bodies: Optional[Dict[str, Sequence[str]]] = None
                 ) -> Tuple[str, float]:
    """Match a board name. Returns ``(canonical_name, confidence)``."""
    bodies = bodies or DEFAULT_BODIES
    lowered = title.lower()

    # Longest alias first, so a subcommittee is not swallowed by its parent.
    candidates: List[Tuple[str, str]] = []
    for canonical, aliases in bodies.items():
        for alias in aliases:
            candidates.append((alias.lower(), canonical))
    candidates.sort(key=lambda pair: len(pair[0]), reverse=True)

    for alias, canonical in candidates:
        if re.search(rf"\b{re.escape(alias)}\b", lowered):
            # A short acronym is a weaker signal than a spelled-out name.
            return canonical, 0.7 if len(alias) <= 4 else 0.95

    return "", 0.0


def parse_meeting_title(
    title: str,
    upload_date: Optional[str] = None,
    bodies: Optional[Dict[str, Sequence[str]]] = None,
) -> MeetingTitle:
    """Pull board and date out of one video title.

    ``upload_date`` supplies the year when the title has only a month and day,
    and the date itself when the title has none.
    """
    title = (title or "").strip()
    result = MeetingTitle(raw=title)
    if not title:
        return result

    upload_iso = ""
    if upload_date:
        text = str(upload_date)
        match = re.search(r"(20\d{2})[-]?(\d{2})[-]?(\d{2})", text)
        if match:
            upload_iso = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

    fallback_year = int(upload_iso[:4]) if upload_iso else None
    found_date, year_guessed = extract_date(title, fallback_year=fallback_year)

    if found_date:
        result.meeting_date = found_date
        result.date_source = "title"
        if year_guessed:
            result.notes.append("year taken from the upload date; the title had none")
        # A title date far from the upload date usually means a misparse.
        if upload_iso:
            try:
                delta = abs((datetime.strptime(found_date, "%Y-%m-%d")
                             - datetime.strptime(upload_iso, "%Y-%m-%d")).days)
                if delta > 365:
                    result.notes.append(
                        f"the title's date is {delta} days from the upload date; "
                        f"it may be a misread"
                    )
            except ValueError:
                pass
    elif upload_iso:
        result.meeting_date = upload_iso
        result.date_source = "upload"
        result.notes.append(
            "no date in the title, so the upload date is used; a meeting is often "
            "posted a day or two after it is held"
        )

    body, body_confidence = extract_body(title, bodies)
    result.body = body

    has_meeting_word = bool(_MEETING_WORDS.search(title))
    result.is_meeting = bool(body) or has_meeting_word

    confidence = 0.0
    if body:
        confidence += body_confidence * 0.6
    if result.date_source == "title":
        confidence += 0.4 if not year_guessed else 0.25
    elif result.date_source == "upload":
        confidence += 0.1
    if has_meeting_word:
        confidence += 0.05
    result.confidence = min(confidence, 1.0)

    if not body:
        result.notes.append(
            "no known board matched; set the source's body explicitly, or add "
            "the board's name to the community's body list"
        )

    return result


if __name__ == "__main__":
    samples = [
        ("Select Board Meeting 4/14/2026", "20260416"),
        ("School Committee Meeting - April 14, 2026", "20260415"),
        ("Planning Board 2026-03-02", None),
        ("ZBA Hearing 3.2.26", "20260303"),
        ("Brookline Town Meeting Night 1 - May 28 2025", None),
        ("Advisory Committee Budget Subcommittee Nov 12", "20251114"),
        ("Conservation Commission", "20260701"),
        ("Coolidge Corner Holiday Stroll Highlights", "20251206"),
        ("Board of Health Special Session 12/1/2024", "20241202"),
    ]
    print(f"{'title':<52} {'body':<26} {'date':<12} {'src':<7} conf")
    print("-" * 108)
    for title, upload in samples:
        parsed = parse_meeting_title(title, upload)
        print(f"{title[:50]:<52} {parsed.body[:24]:<26} "
              f"{parsed.meeting_date:<12} {parsed.date_source:<7} {parsed.confidence:.2f}")
        for note in parsed.notes:
            print(f"    note: {note}")
