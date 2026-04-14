#!/usr/bin/env python3
"""
Migrate legacy string metadata + org_settings to UUID label catalogs and document ids.

NOTE: This script exists for one-time migrations only. It supports legacy fields
from pre-ids versions of Pack.

Usage (from repo root):
  cd backend && python -m scripts.migrate_label_catalog

Uses MONGODB_URI and DATABASE_NAME from app settings (.env).
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

# Allow `python scripts/migrate_label_catalog.py` from backend/
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from pymongo import MongoClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.services.document_processor import create_embedding  # noqa: E402
from app.services.label_catalog import (  # noqa: E402
    build_metadata_prefix,
    compose_ai_text_content,
    normalize_doc_date,
)


def _label_cf(label: str) -> str:
    return str(label).strip().casefold()


def _normalize_catalog_mixed(raw: Any) -> List[Dict[str, str]]:
    """
    Accept pre-migration org_settings catalogs:
    - list[str] (legacy)
    - list[{"id","label"}] (partial)
    - list[{"id","label","label_cf"}] (current)
    Returns normalized entries with {id,label,label_cf}.
    Raises if duplicates exist with conflicting ids/sources, since silently
    dropping one could orphan documents that reference the dropped id.
    """
    if not raw:
        return []
    if not isinstance(raw, list):
        raise ValueError("org_settings catalog has invalid shape (expected list)")
    out: List[Dict[str, str]] = []
    seen_id_by_cf: dict[str, str] = {}
    for e in raw:
        if isinstance(e, str):
            lab = e.strip()
            if not lab:
                continue
            cf = _label_cf(lab)
            if cf in seen_id_by_cf:
                continue
            seen_id_by_cf[cf] = ""  # "string source" sentinel
            out.append({"id": str(uuid4()), "label": lab, "label_cf": cf})
            continue
        if isinstance(e, dict):
            lid = e.get("id")
            lab = e.get("label")
            if not (lid and lab is not None and str(lab).strip()):
                continue
            lid_s = str(lid)
            lab_s = str(lab).strip()
            cf = str(e.get("label_cf") or "").strip()
            expected = _label_cf(lab_s)
            if cf and cf != expected:
                raise ValueError("org_settings catalogs contain inconsistent label_cf; run scripts.backfill_label_cf")
            cf = cf or expected
            prev = seen_id_by_cf.get(cf)
            if prev is not None and prev != lid_s:
                raise ValueError(
                    "org_settings catalog contains duplicate normalized label with conflicting ids. "
                    f"label={lab_s!r} label_cf={cf!r} existing_id={prev!r} current_id={lid_s!r}. "
                    "Resolve duplicate catalog entries before running scripts.migrate_label_catalog."
                )
            seen_id_by_cf[cf] = lid_s
            out.append({"id": lid_s, "label": lab_s, "label_cf": cf})
            continue
        raise ValueError("org_settings catalog contains invalid entry type; run scripts.migrate_label_catalog")
    return out


def _infer_extracted(ai_ctx: Dict[str, Any], caption: str) -> str:
    tc = (ai_ctx.get("text_content") or "").strip()
    cap = (caption or "").strip()
    if cap and tc.startswith(cap):
        return tc[len(cap):].lstrip().lstrip("\n").strip()
    return tc


def _collect_org_ids(db) -> List[str]:
    ids = set()
    for x in db.documents.find({}, {"org_id": 1, "family_id": 1}):
        if x.get("org_id"):
            ids.add(x["org_id"])
        if x.get("family_id"):
            ids.add(x["family_id"])
    for x in db.org_settings.find({}, {"_id": 1}):
        ids.add(x["_id"])
    return sorted(ids)


def _merge_catalog(
    existing: Any,
    labels_seen: List[str],
) -> Tuple[List[Dict[str, str]], Dict[str, str]]:
    """Return (catalog_entries, casefold_key -> id)."""
    entries = _normalize_catalog_mixed(existing)
    by_cf: Dict[str, Dict[str, str]] = {}
    for e in entries:
        cf = e["label_cf"]
        by_cf[cf] = e

    for lab in labels_seen:
        if not lab or not str(lab).strip():
            continue
        cf = _label_cf(str(lab).strip())
        if cf not in by_cf:
            e = {"id": str(uuid4()), "label": str(lab).strip(), "label_cf": cf}
            by_cf[cf] = e
            entries.append(e)

    id_by_cf = {cf: e["id"] for cf, e in by_cf.items()}
    return entries, id_by_cf


def main() -> None:
    client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=10000)
    client.admin.command("ping")
    db = client[settings.DATABASE_NAME]

    for org_id in _collect_org_ids(db):
        print(f"Migrating org {org_id}...")
        settings_doc = db.org_settings.find_one({"_id": org_id}) or {"_id": org_id}

        q = {"$or": [{"org_id": org_id}, {"family_id": org_id}]}
        docs = list(db.documents.find(q))

        senders_labels: List[str] = []
        events_labels: List[str] = []
        recipients_labels: List[str] = []
        for d in docs:
            m = d.get("metadata") or {}
            if m.get("sender_name"):
                senders_labels.append(str(m["sender_name"]))
            if m.get("event_type"):
                events_labels.append(str(m["event_type"]))
            if m.get("recipient_name"):
                recipients_labels.append(str(m["recipient_name"]))

        cur_s = settings_doc.get("senders") or settings_doc.get("sender_names") or []
        cur_e = settings_doc.get("event_types") or []
        cur_r = settings_doc.get("recipients") or settings_doc.get("recipient_names") or []

        senders, sender_map = _merge_catalog(cur_s, senders_labels)
        events, event_map = _merge_catalog(cur_e, events_labels)
        recipients, recipient_map = _merge_catalog(cur_r, recipients_labels)

        db.org_settings.update_one(
            {"_id": org_id},
            {
                "$set": {
                    "senders": senders,
                    "event_types": events,
                    "recipients": recipients,
                },
                "$unset": {"sender_names": "", "recipient_names": ""},
            },
            upsert=True,
        )

        for d in docs:
            m = dict(d.get("metadata") or {})
            try:
                dd = normalize_doc_date(str(m.get("doc_date", "")))
            except Exception:
                dd = str(m.get("doc_date", ""))

            sid = m.get("sender_id")
            if not sid and m.get("sender_name"):
                cf = _label_cf(str(m["sender_name"]))
                sid = sender_map.get(cf)
            eid = m.get("event_type_id")
            if not eid and m.get("event_type"):
                cf = _label_cf(str(m["event_type"]))
                eid = event_map.get(cf)
            rid = m.get("recipient_id")
            if not rid and m.get("recipient_name"):
                cf = _label_cf(str(m["recipient_name"]))
                rid = recipient_map.get(cf)

            sender_label = m.get("sender_name") or ""
            event_label = m.get("event_type") or ""
            recipient_label = m.get("recipient_name")

            for e in senders:
                if e["id"] == sid:
                    sender_label = e["label"]
                    break
            for e in events:
                if e["id"] == eid:
                    event_label = e["label"]
                    break
            rlab: Optional[str] = None
            if rid:
                for e in recipients:
                    if e["id"] == rid:
                        rlab = e["label"]
                        break
            elif recipient_label:
                rlab = str(recipient_label)

            new_meta: Dict[str, Any] = {
                "sender_id": sid,
                "event_type_id": eid,
                "doc_date": dd,
                "caption": m.get("caption"),
            }
            if rid:
                new_meta["recipient_id"] = rid
            else:
                new_meta["recipient_id"] = None

            ai = dict(d.get("ai_context") or {})
            cap = (m.get("caption") or "").strip()
            extracted = (ai.get("extracted_text") or "").strip()
            if not extracted:
                extracted = _infer_extracted(ai, cap)
            prefix = build_metadata_prefix(sender_label, event_label, dd, rlab)
            text_content = compose_ai_text_content(prefix, cap, extracted)
            embedding = create_embedding(text_content)
            ai["extracted_text"] = extracted
            ai["metadata_prefix"] = prefix
            ai["text_content"] = text_content
            ai["embedding"] = embedding

            db.documents.update_one(
                {"_id": d["_id"]},
                {"$set": {"metadata": new_meta, "ai_context": ai}},
            )

    print("Done.")


if __name__ == "__main__":
    main()
