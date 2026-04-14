"""Query normalization utilities for document fetch and search."""
from typing import List, Optional, Dict, Any

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


def _catalog_labels(catalog: List[Dict[str, Any]]) -> List[str]:
    return [str(e.get("label", "")) for e in catalog if e.get("label")]


def resolve_sender_to_id(raw: Optional[str], catalog: List[Dict[str, Any]]) -> Optional[str]:
    if not raw or not str(raw).strip():
        return None
    canonical = resolve_sender(str(raw).strip(), _catalog_labels(catalog))
    if not canonical:
        return None
    cl = canonical.casefold()
    for e in catalog:
        if str(e.get("label", "")).strip().casefold() == cl:
            return str(e.get("id", "")) or None
    return None


def resolve_event_type_to_id(raw: Optional[str], catalog: List[Dict[str, Any]]) -> Optional[str]:
    if not raw or not str(raw).strip():
        return None
    canonical = resolve_event_type(str(raw).strip(), _catalog_labels(catalog))
    if not canonical:
        return None
    cl = canonical.casefold()
    for e in catalog:
        if str(e.get("label", "")).strip().casefold() == cl:
            return str(e.get("id", "")) or None
    return None


def resolve_recipient_to_id(raw: Optional[str], catalog: List[Dict[str, Any]]) -> Optional[str]:
    return resolve_sender_to_id(raw, catalog)


def sender_metadata_filter(
    sender: Optional[str],
    catalog: List[Dict[str, Any]],
    org_sender_labels: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    if not sender or not str(sender).strip():
        return None
    sid = resolve_sender_to_id(sender, catalog)
    if not sid:
        return None
    return {"metadata.sender_id": sid}


def event_metadata_filter(
    event_type: Optional[str],
    catalog: List[Dict[str, Any]],
    org_event_labels: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    if not event_type or not str(event_type).strip():
        return None
    eid = resolve_event_type_to_id(event_type, catalog)
    if not eid:
        return None
    return {"metadata.event_type_id": eid}


def recipient_metadata_filter(
    receiver: Optional[str],
    catalog: List[Dict[str, Any]],
    org_recipient_labels: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    if not receiver or not str(receiver).strip():
        return None
    rid = resolve_recipient_to_id(receiver, catalog)
    if not rid:
        return None
    return {"metadata.recipient_id": rid}
