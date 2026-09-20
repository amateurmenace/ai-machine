"""
Query preparation.

Section 18 puts a query rewriter between the user and the index: the question
"What has the town discussed about replacing gas heating in public buildings?"
becomes "municipal building gas heating replacement heat pumps electrification".

The rewrite matters most for the keyword half of retrieval, which matches
literal terms. A resident asks about "the dump"; the records say "Solid Waste
Transfer Station". No amount of reranking recovers a passage that neither
retriever surfaced.

Two mechanisms, in order of cost:

* **Rule-based expansion** — a civic vocabulary map, applied always, free.
* **Model rewrite** — optional, one extra call, used when a rewriter callable
  is supplied.

The expansion is additive. Original wording is always kept, so expansion can
help recall and cannot silently change what was asked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

# Everyday word -> the words municipal records actually use. Communities should
# extend this in their own config; these are the terms common to most US towns.
CIVIC_VOCABULARY: Dict[str, Sequence[str]] = {
    "dump": ("transfer station", "solid waste", "landfill"),
    "trash": ("solid waste", "refuse", "curbside collection"),
    "recycling": ("solid waste", "curbside collection"),
    "garbage": ("solid waste", "refuse"),
    "city hall": ("town hall", "municipal building"),
    "town hall": ("municipal building",),
    "mayor": ("town administrator", "town manager", "chief executive"),
    "council": ("select board", "city council", "town council"),
    "board": ("committee", "commission"),
    "zoning": ("zoning bylaw", "land use", "dimensional requirements"),
    "permit": ("permitting", "application", "license"),
    "budget": ("appropriation", "fiscal year", "operating budget"),
    "taxes": ("tax rate", "assessment", "levy", "property tax"),
    "school": ("school committee", "public schools", "district"),
    "police": ("public safety", "police department"),
    "fire": ("fire department", "public safety"),
    "road": ("roadway", "street", "public works"),
    "roads": ("roadway", "streets", "public works"),
    "sidewalk": ("pedestrian", "public works", "accessibility"),
    "bike lane": ("bicycle", "cycling", "complete streets"),
    "parking": ("parking regulations", "meters", "resident permit"),
    "bus": ("transit", "public transportation"),
    "train": ("transit", "commuter rail", "public transportation"),
    "housing": ("affordable housing", "residential", "inclusionary"),
    "rent": ("tenant", "rental", "housing"),
    "heat pump": ("electrification", "hvac", "decarbonization"),
    "heating": ("hvac", "heating system", "electrification"),
    "solar": ("renewable energy", "photovoltaic"),
    "climate": ("sustainability", "emissions", "climate action plan"),
    "park": ("open space", "recreation", "parks and recreation"),
    "library": ("public library", "library trustees"),
    "election": ("ballot", "polling", "town clerk"),
    "vote": ("motion", "roll call", "adopted"),
    "meeting": ("agenda", "minutes", "public hearing"),
    "hearing": ("public hearing", "testimony", "public comment"),
}

# Acronyms that appear constantly in municipal records and never in questions.
CIVIC_ACRONYMS: Dict[str, str] = {
    "adu": "accessory dwelling unit",
    "cpa": "community preservation act",
    "cpc": "community preservation committee",
    "zba": "zoning board of appeals",
    "dpw": "department of public works",
    "mbta": "massachusetts bay transportation authority",
    "rfp": "request for proposals",
    "tif": "tax increment financing",
    "eir": "environmental impact report",
    "cip": "capital improvement plan",
    "fy": "fiscal year",
}

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_CURRENT_WORDS = frozenset(
    {"current", "currently", "now", "today", "present", "latest", "these days"}
)


@dataclass
class PreparedQuery:
    """A question, expanded for retrieval, with what was noticed about it."""

    original: str
    search_text: str
    added_terms: List[str] = field(default_factory=list)
    years_mentioned: List[str] = field(default_factory=list)
    is_time_sensitive: bool = False
    rewritten_by_model: bool = False

    def diagnostics(self) -> Dict[str, object]:
        return {
            "original": self.original,
            "search_text": self.search_text,
            "added_terms": self.added_terms,
            "years_mentioned": self.years_mentioned,
            "is_time_sensitive": self.is_time_sensitive,
            "rewritten_by_model": self.rewritten_by_model,
        }


def expand_query(question: str, extra_vocabulary: Optional[Dict[str, Sequence[str]]] = None) -> PreparedQuery:
    """Expand a question with municipal vocabulary."""
    text = (question or "").strip()
    lowered = text.lower()

    vocabulary = dict(CIVIC_VOCABULARY)
    if extra_vocabulary:
        vocabulary.update(extra_vocabulary)

    added: List[str] = []
    for phrase, expansions in vocabulary.items():
        # Word-boundary match. A substring test would fire "rent" inside
        # "currently" and drag housing vocabulary into a question about trash.
        if not re.search(rf"\b{re.escape(phrase)}\b", lowered):
            continue
        for expansion in expansions:
            if expansion.lower() in lowered or expansion in added:
                continue
            added.append(expansion)

    for token in re.findall(r"\b[a-z]{2,5}\b", lowered):
        expansion = CIVIC_ACRONYMS.get(token)
        if expansion and expansion not in lowered and expansion not in added:
            added.append(expansion)

    years = sorted({match.group(0) for match in _YEAR_RE.finditer(text)})

    time_sensitive = any(word in lowered for word in _CURRENT_WORDS)

    # Cap the expansion. Past roughly a dozen added terms the keyword half
    # starts matching the expansion instead of the question.
    added = added[:12]
    search_text = text if not added else f"{text} {' '.join(added)}"

    return PreparedQuery(
        original=text,
        search_text=search_text,
        added_terms=added,
        years_mentioned=years,
        is_time_sensitive=time_sensitive,
    )


REWRITE_INSTRUCTION = (
    "Rewrite the question below as a search query for a municipal records "
    "archive. Use the formal terms a town would use in its own documents. "
    "Keep proper nouns, street names, article numbers and years exactly as "
    "written. Reply with the query only, no explanation, no quotes."
)


def prepare_query(
    question: str,
    rewriter: Optional[Callable[[str], str]] = None,
    extra_vocabulary: Optional[Dict[str, Sequence[str]]] = None,
) -> PreparedQuery:
    """Prepare a question for retrieval, optionally using a model rewriter.

    ``rewriter`` takes the instruction-plus-question string and returns a search
    query. Any failure falls back to rule-based expansion, because a rewrite is
    an optimization and must never cost the user an answer.
    """
    prepared = expand_query(question, extra_vocabulary=extra_vocabulary)

    if rewriter is None:
        return prepared

    try:
        rewritten = rewriter(f"{REWRITE_INSTRUCTION}\n\nQuestion: {question}")
    except Exception:
        return prepared

    rewritten = (rewritten or "").strip().strip('"').strip()
    if not rewritten or len(rewritten) > 500:
        return prepared

    # Keep the original wording alongside the rewrite: the rewrite may drop a
    # detail, and the dense retriever handles natural phrasing better anyway.
    prepared.search_text = f"{prepared.original} {rewritten}"
    prepared.rewritten_by_model = True
    return prepared


if __name__ == "__main__":
    for q in [
        "What has the town discussed about replacing gas heating in public buildings?",
        "Is an ADU allowed under Article 8.4?",
        "Who is currently responsible for the dump?",
        "What was the policy in 2019?",
    ]:
        p = expand_query(q)
        print(f"{q}\n  -> +{p.added_terms}\n  -> years={p.years_mentioned} "
              f"time_sensitive={p.is_time_sensitive}\n")
