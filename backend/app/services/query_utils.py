"""Query normalization utilities for document fetch and search."""
import re
from typing import List, Optional

# Words that describe the document format, not the event type.
# "birthday card" and "birthday documents" should both match event type "Birthday".
DOCUMENT_WORDS = frozenset({
    "card", "cards", "document", "documents", "photo", "photos",
    "image", "images", "letter", "letters", "note", "notes",
    "picture", "pictures", "postcard", "postcards",
})


def normalize_event_type(raw: str) -> str:
    """
    Strip document-type words and normalize for matching.
    'birthday card' -> 'birthday', 'Christmas documents' -> 'Christmas'
    """
    if not raw or not raw.strip():
        return ""
    words = raw.strip().lower().split()
    filtered = [w for w in words if w not in DOCUMENT_WORDS]
    return " ".join(filtered).strip() if filtered else raw.strip()


def resolve_event_type(
    raw: str,
    org_event_types: List[str],
) -> Optional[str]:
    """
    Resolve LLM's event_type guess to canonical org value.
    Returns the exact string to use in the query, or None if no match.
    """
    if not raw or not raw.strip():
        return None
    normalized = normalize_event_type(raw)
    if not normalized:
        return None
    normalized_lower = normalized.lower()
    for canonical in org_event_types or []:
        if canonical and canonical.lower() == normalized_lower:
            return canonical
    # No match in org list - return normalized for case-insensitive regex fallback
    return normalized


def resolve_sender(raw: str, org_sender_names: List[str]) -> Optional[str]:
    """
    Resolve sender to canonical org value (case-insensitive).
    Returns the exact string to use in the query, or None if no match.
    """
    if not raw or not raw.strip():
        return None
    raw_clean = raw.strip()
    raw_lower = raw_clean.lower()
    for canonical in org_sender_names or []:
        if canonical and canonical.lower() == raw_lower:
            return canonical
    return raw_clean


def event_type_query_value(value: str):
    """Return MongoDB query value for metadata.event_type (case-insensitive)."""
    if not value:
        return None
    return {"$regex": f"^{re.escape(value)}$", "$options": "i"}


def sender_query_value(value: str):
    """Return MongoDB query value for metadata.sender_name (case-insensitive)."""
    if not value:
        return None
    return {"$regex": f"^{re.escape(value)}$", "$options": "i"}
