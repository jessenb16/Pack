#!/usr/bin/env python3
"""
Backfill org_settings label catalogs with `label_cf` fields.

This is a one-time, idempotent script. Run it immediately after deploying code
that expects org_settings entries to contain {id, label, label_cf}.

Usage:
  cd backend && python -m scripts.backfill_label_cf
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from pymongo import MongoClient  # noqa: E402

from app.core.config import settings  # noqa: E402


def _label_cf(label: str) -> str:
    return str(label).strip().casefold()


def _normalize_list(raw: Any) -> List[Dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, str]] = []
    seen: set[str] = set()
    for e in raw:
        if not isinstance(e, dict):
            raise ValueError("Legacy or invalid catalog entry found (non-object). Run migrate_label_catalog first.")
        lid = e.get("id")
        lab = e.get("label")
        if not lid or lab is None:
            continue
        lab_s = str(lab).strip()
        if not lab_s:
            continue
        cf = _label_cf(lab_s)
        if cf in seen:
            continue
        seen.add(cf)
        out.append({"id": str(lid), "label": lab_s, "label_cf": cf})
    return out


def main() -> None:
    client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=10000)
    client.admin.command("ping")
    db = client[settings.DATABASE_NAME]

    updated = 0
    for row in db.org_settings.find({}):
        org_id = row.get("_id")
        if not org_id:
            continue

        senders = _normalize_list(row.get("senders"))
        events = _normalize_list(row.get("event_types"))
        recipients = _normalize_list(row.get("recipients"))

        # If already backfilled and normalized, skip.
        def _looks_done(lst: Any) -> bool:
            return (
                isinstance(lst, list)
                and all(isinstance(x, dict) and x.get("id") and x.get("label") and x.get("label_cf") for x in lst)
            )

        if _looks_done(row.get("senders")) and _looks_done(row.get("event_types")) and _looks_done(row.get("recipients")):
            continue

        db.org_settings.update_one(
            {"_id": org_id},
            {"$set": {"senders": senders, "event_types": events, "recipients": recipients}},
        )
        updated += 1

    print(f"Done. Updated {updated} org_settings docs.")


if __name__ == "__main__":
    main()

