"""Query normalization utilities for document fetch and search."""
import re
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


# TODO(legacy-catalog): After migrate_label_catalog is verified on all envs, simplify to id-only:
#   - *_metadata_filter: only {"metadata.*_id": id} from resolve_*_to_id; drop $or + sender_name /
#     event_type / recipient_name branches and trim sender_query_value / event_type_query_value if unused.
#   - documents GET string query params (sender, event_type) and frontend filters can go id-only.
# Used by documents API list filters and agent_service tools until then.


def sender_metadata_filter(
    sender: Optional[str],
    catalog: List[Dict[str, Any]],
    org_sender_labels: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Mongo fragment for sender: prefer metadata.sender_id; OR legacy metadata.sender_name
    for documents not yet migrated off string caches.
    """
    if not sender or not str(sender).strip():
        return None
    labels = org_sender_labels if org_sender_labels is not None else _catalog_labels(catalog)
    sid = resolve_sender_to_id(sender, catalog)
    resolved = resolve_sender(sender, labels) or sender.strip()
    qv = sender_query_value(resolved)
    or_parts: List[Dict[str, Any]] = []
    if sid:
        or_parts.append({"metadata.sender_id": sid})
    if qv:
        or_parts.append({"metadata.sender_name": qv})
    if not or_parts:
        return None
    if len(or_parts) == 1:
        return or_parts[0]
    return {"$or": or_parts}


def event_metadata_filter(
    event_type: Optional[str],
    catalog: List[Dict[str, Any]],
    org_event_labels: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    if not event_type or not str(event_type).strip():
        return None
    labels = org_event_labels if org_event_labels is not None else _catalog_labels(catalog)
    eid = resolve_event_type_to_id(event_type, catalog)
    resolved = resolve_event_type(event_type, labels) or event_type.strip()
    qv = event_type_query_value(resolved)
    or_parts: List[Dict[str, Any]] = []
    if eid:
        or_parts.append({"metadata.event_type_id": eid})
    if qv:
        or_parts.append({"metadata.event_type": qv})
    if not or_parts:
        return None
    if len(or_parts) == 1:
        return or_parts[0]
    return {"$or": or_parts}


def recipient_metadata_filter(
    receiver: Optional[str],
    catalog: List[Dict[str, Any]],
    org_recipient_labels: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    if not receiver or not str(receiver).strip():
        return None
    labels = org_recipient_labels if org_recipient_labels is not None else _catalog_labels(catalog)
    rid = resolve_recipient_to_id(receiver, catalog)
    resolved = resolve_sender(receiver, labels) or receiver.strip()
    qv = sender_query_value(resolved)
    or_parts: List[Dict[str, Any]] = []
    if rid:
        or_parts.append({"metadata.recipient_id": rid})
    if qv:
        or_parts.append({"metadata.recipient_name": qv})
    if not or_parts:
        return None
    if len(or_parts) == 1:
        return or_parts[0]
    return {"$or": or_parts}
