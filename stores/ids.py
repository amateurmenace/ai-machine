"""
One id for a passage, whichever backend holds it.

The three stores have to agree. A corpus copied from Qdrant into SQLite and
the same corpus re-ingested from its sources must land on the same ids, or a
re-ingestion after a migration quietly doubles the archive. So the scheme lives
here, once, and each store calls it.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional


def passage_id(text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """A deterministic id: the same passage ingested twice replaces itself.

    The source url and the first hundred characters are enough for a document,
    where every page has its own words. They are not enough for a recording.
    Every passage of a meeting shares the meeting's url, and sooner or later
    two of them open alike: a roll call, a chair's "thank you, is there a
    second", ten minutes of "[music]" before the gavel and ten more at the
    recess. Those collided, and because the write is an upsert the earlier
    passage was replaced by the later one with nothing to show for it.

    So a passage that knows when it starts says so. A passage with no start
    time gets exactly the id it always did.
    """
    metadata = metadata or {}
    basis = str(metadata.get("url", "") or "") + (text or "")[:100]
    start = metadata.get("start_time")
    if start is not None and start != "":
        try:
            basis += f"@{float(start):.3f}"
        except (TypeError, ValueError):
            basis += f"@{start}"
    return hashlib.md5(basis.encode("utf-8")).hexdigest()
