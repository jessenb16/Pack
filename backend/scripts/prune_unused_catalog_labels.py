#!/usr/bin/env python3
"""
Audit: list org_settings catalog entries (senders / event_types / recipients) that no
document in that org references by id.

Does not modify the database. Use the report to decide manual cleanup or a custom migration.

Usage:
  cd backend && python -m scripts.prune_unused_catalog_labels
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from pymongo import MongoClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.services.label_catalog import normalize_label_entries  # noqa: E402


def _used_ids_for_org(db, org_id: str) -> Tuple[Set[str], Set[str], Set[str]]:
    q = {"$or": [{"org_id": org_id}, {"family_id": org_id}]}
    senders: Set[str] = set()
    events: Set[str] = set()
    recipients: Set[str] = set()
    for d in db.documents.find(q, {"metadata": 1}):
        m = d.get("metadata") or {}
        if m.get("sender_id"):
            senders.add(str(m["sender_id"]))
        if m.get("event_type_id"):
            events.add(str(m["event_type_id"]))
        if m.get("recipient_id"):
            recipients.add(str(m["recipient_id"]))
    return senders, events, recipients


def _unused(entries: List[Dict[str, str]], used: Set[str]) -> List[Dict[str, str]]:
    return [e for e in entries if e.get("id") and str(e["id"]) not in used]


def main() -> None:
    client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=10000)
    client.admin.command("ping")
    db = client[settings.DATABASE_NAME]

    for row in db.org_settings.find({}):
        org_id = row.get("_id")
        if not org_id:
            continue
        used_s, used_e, used_r = _used_ids_for_org(db, org_id)
        try:
            senders = normalize_label_entries(row.get("senders") or [])
            events = normalize_label_entries(row.get("event_types") or [])
            recipients = normalize_label_entries(row.get("recipients") or [])
        except ValueError as e:
            print(
                f"org {org_id} — cannot normalize org_settings catalogs ({e}). "
                "Run scripts.migrate_label_catalog and/or scripts.backfill_label_cf first."
            )
            continue

        u_s = _unused(senders, used_s)
        u_e = _unused(events, used_e)
        u_r = _unused(recipients, used_r)
        if not u_s and not u_e and not u_r:
            continue
        print(f"org {org_id} — unused catalog entries (not referenced by any document id):")
        for kind, arr in ("senders", u_s), ("event_types", u_e), ("recipients", u_r):
            if arr:
                for e in arr:
                    print(f"  {kind}: id={e.get('id')} label={e.get('label')!r}")


if __name__ == "__main__":
    main()
