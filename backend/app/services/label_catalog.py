"""Org label catalog: embedded {id, label, label_cf} lists in org_settings (senders, event_types, recipients)."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from pymongo.database import Database

KIND_SENDER = "sender"
KIND_EVENT = "event_type"
KIND_RECIPIENT = "recipient"


def _kind_field(kind: str) -> str:
    if kind == KIND_SENDER:
        return "senders"
    if kind == KIND_EVENT:
        return "event_types"
    if kind == KIND_RECIPIENT:
        return "recipients"
    raise ValueError(f"Unknown label kind: {kind}")


def normalize_label_entries(entries: Any) -> List[Dict[str, str]]:
    """Normalize org_settings catalog entries to [{id,label,label_cf}, ...] (strict)."""
    if not entries:
        return []
    out: List[Dict[str, str]] = []
    for e in entries:
        if not isinstance(e, dict):
            raise ValueError("org_settings catalogs must contain only object entries with id, label, and label_cf")
        lid = e.get("id")
        lab = e.get("label")
        lab_cf = e.get("label_cf")
        if not (lid and lab is not None and str(lab).strip()):
            continue
        if not (lab_cf and str(lab_cf).strip()):
            raise ValueError("org_settings catalogs must include label_cf; run scripts.backfill_label_cf")
        label_clean = str(lab).strip()
        label_cf_clean = str(lab_cf).strip()
        expected_label_cf = _label_cf(label_clean)
        if label_cf_clean != expected_label_cf:
            raise ValueError("org_settings catalogs contain inconsistent label_cf; run scripts.backfill_label_cf")
        out.append({"id": str(lid), "label": label_clean, "label_cf": label_cf_clean})
    return out


def catalog_lists(settings_doc: Dict) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]]]:
    doc = settings_doc or {}
    return (
        normalize_label_entries(doc.get("senders") or []),
        normalize_label_entries(doc.get("event_types") or []),
        normalize_label_entries(doc.get("recipients") or []),
    )


def find_entry_by_id(entries: List[Dict[str, str]], label_id: str) -> Optional[Dict[str, str]]:
    for e in entries:
        if e.get("id") == label_id:
            return e
    return None


def _label_cf(label: str) -> str:
    return str(label).strip().casefold()


def find_entry_by_label_cf(entries: List[Dict[str, str]], label_cf: str) -> Optional[Dict[str, str]]:
    if not label_cf or not str(label_cf).strip():
        return None
    for e in entries:
        if str(e.get("label_cf", "")).strip() == str(label_cf).strip():
            return e
    return None


def ensure_label(org_id: str, kind: str, label: Optional[str], db: Database) -> Optional[Dict[str, str]]:
    """
    Return {id, label} for this kind. Creates if missing (case-insensitive dedupe per kind).
    recipient may be None/empty -> returns None.
    """
    if kind not in (KIND_SENDER, KIND_EVENT, KIND_RECIPIENT):
        raise ValueError(f"Unknown kind {kind}")
    if kind == KIND_RECIPIENT and (not label or not str(label).strip()):
        return None
    if not label or not str(label).strip():
        raise ValueError("label required for this kind")
    label_clean = str(label).strip()
    label_cf = _label_cf(label_clean)

    field = _kind_field(kind)

    if db.org_settings.find_one({"_id": org_id, field: {"$elemMatch": {"label_cf": {"$exists": False}}}}, {"_id": 1}):
        raise ValueError("org_settings catalogs must include label_cf; run scripts.backfill_label_cf")

    # Atomic: only append if no entry with this label_cf exists.
    new_entry = {"id": str(uuid4()), "label": label_clean, "label_cf": label_cf}
    update_filter = {"_id": org_id, f"{field}.label_cf": {"$ne": label_cf}}
    res = db.org_settings.update_one(
        update_filter,
        {
            "$setOnInsert": {"_id": org_id, "senders": [], "event_types": [], "recipients": []},
            "$push": {field: new_entry},
        },
        upsert=True,
    )

    if res.upserted_id is not None or res.modified_count == 1:
        return {"id": new_entry["id"], "label": new_entry["label"]}

    # Already exists (or raced). Read and return existing entry.
    doc = db.org_settings.find_one({"_id": org_id}) or {}
    entries = normalize_label_entries(doc.get(field) or [])
    existing = find_entry_by_label_cf(entries, label_cf)
    if existing:
        return {"id": existing["id"], "label": existing["label"]}

    # Extremely unlikely: doc changed between queries or catalog corrupted.
    raise ValueError(f"Could not ensure {kind} label")


def resolve_label_from_id_or_text(
    org_id: str,
    kind: str,
    label_id: Optional[str],
    label_text: Optional[str],
    db: Database,
) -> Dict[str, str]:
    """Resolve (id, label) from explicit id (validated) or new/existing label text."""
    doc = db.org_settings.find_one({"_id": org_id}) or {"_id": org_id}
    field = _kind_field(kind)
    entries = normalize_label_entries(doc.get(field) or [])

    if label_id and str(label_id).strip():
        entry = find_entry_by_id(entries, str(label_id).strip())
        if not entry:
            raise ValueError(f"Unknown {kind} id for this organization")
        return entry

    if label_text and str(label_text).strip():
        return ensure_label(org_id, kind, str(label_text).strip(), db)  # type: ignore[arg-type]

    raise ValueError(f"Either id or label is required for {kind}")


def optional_recipient(
    org_id: str,
    label_id: Optional[str],
    label_text: Optional[str],
    db: Database,
) -> Optional[Dict[str, str]]:
    if label_id and str(label_id).strip():
        return resolve_label_from_id_or_text(org_id, KIND_RECIPIENT, label_id, None, db)
    if label_text and str(label_text).strip():
        return ensure_label(org_id, KIND_RECIPIENT, str(label_text).strip(), db)
    return None


def build_id_index(entries: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    return {e["id"]: e for e in entries if e.get("id")}


_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def normalize_doc_date(raw: str) -> str:
    """Normalize to YYYY-MM-DD for storage and comparisons."""
    if not raw or not str(raw).strip():
        raise ValueError("doc_date is required")
    s = str(raw).strip()
    if _DATE_RE.match(s):
        return s
    try:
        from datetime import datetime

        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        pass
    raise ValueError("doc_date must be YYYY-MM-DD")


def build_metadata_prefix(
    sender_label: str,
    event_label: str,
    doc_date: str,
    recipient_label: Optional[str],
) -> str:
    lines = [
        f"Sender: {sender_label}",
        f"Event: {event_label}",
        f"Date: {doc_date}",
    ]
    if recipient_label:
        lines.append(f"Recipient: {recipient_label}")
    return "\n".join(lines)


def compose_ai_text_content(metadata_prefix: str, caption: str, extracted_text: str) -> str:
    cap = (caption or "").strip()
    ext = (extracted_text or "").strip()
    parts: List[str] = []
    if metadata_prefix.strip():
        parts.append(metadata_prefix.strip())
    if cap:
        parts.append(cap)
    if ext:
        parts.append(ext)
    return "\n\n".join(parts) if parts else ""


def resolve_display_triple(
    metadata: Dict[str, Any],
    senders: List[Dict[str, str]],
    events: List[Dict[str, str]],
    recipients: List[Dict[str, str]],
) -> Tuple[Dict[str, str], Dict[str, str], Optional[Dict[str, str]]]:
    """Map stored metadata to {id,label} for API responses (id-only)."""
    sender_id = metadata.get("sender_id")
    event_id = metadata.get("event_type_id")
    recipient_id = metadata.get("recipient_id")

    sender_entry: Optional[Dict[str, str]] = None
    if sender_id:
        sender_entry = find_entry_by_id(senders, str(sender_id))
    if not sender_entry:
        sender_entry = {"id": "", "label": "Unknown"}

    event_entry: Optional[Dict[str, str]] = None
    if event_id:
        event_entry = find_entry_by_id(events, str(event_id))
    if not event_entry:
        event_entry = {"id": "", "label": "Unknown"}

    recipient_entry: Optional[Dict[str, str]] = None
    if recipient_id:
        recipient_entry = find_entry_by_id(recipients, str(recipient_id))

    return sender_entry, event_entry, recipient_entry
