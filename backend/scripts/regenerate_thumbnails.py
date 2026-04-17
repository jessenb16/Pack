#!/usr/bin/env python3
"""
Regenerate (and overwrite) S3 thumbnails for specific documents.

Use when a small number of existing thumbnails are incorrect (e.g., EXIF
orientation issues from older thumbnail generation).

Usage (from repo root):
  cd backend
  python -m scripts.regenerate_thumbnails <doc_id> <doc_id> <doc_id>

By default this runs as a dry-run (no writes). Add --apply to perform changes:
  python -m scripts.regenerate_thumbnails --apply <doc_id> ...

This script requires access to:
- MongoDB (MONGODB_URI / DATABASE_NAME)
- S3 (AWS_* and AWS_S3_BUCKET_NAME)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Allow `python scripts/regenerate_thumbnails.py` from backend/
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from bson import ObjectId  # noqa: E402
from pymongo import MongoClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.services.document_processor import generate_thumbnail  # noqa: E402
from app.services.storage import (  # noqa: E402
    extract_s3_key_from_url,
    get_s3_client,
    upload_to_s3,
)


def _basename(key: str) -> str:
    return str(key).rsplit("/", 1)[-1]


def _resolve_assets(doc: Dict[str, Any]) -> Tuple[str, str, str]:
    org_id = doc.get("org_id") or doc.get("family_id") or ""
    assets = doc.get("assets") or {}
    original_key = extract_s3_key_from_url(
        assets.get("s3_original_url") or doc.get("s3_original_url") or ""
    )
    thumbnail_key = extract_s3_key_from_url(
        assets.get("s3_thumbnail_url") or doc.get("s3_thumbnail_url") or ""
    )
    return org_id, original_key, thumbnail_key


def _download_s3_bytes(s3_key: str) -> bytes:
    s3 = get_s3_client()
    resp = s3.get_object(Bucket=settings.AWS_S3_BUCKET_NAME, Key=s3_key)
    body = resp.get("Body")
    if body is None:
        raise RuntimeError(f"S3 get_object returned no Body for key={s3_key!r}")
    return body.read()


def main() -> int:
    ap = argparse.ArgumentParser(description="Regenerate S3 thumbnails for specific documents.")
    ap.add_argument("document_ids", nargs="+", help="Mongo ObjectId strings for documents")
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Actually write changes (overwrite thumbnail objects in S3 and update DB only if needed).",
    )
    args = ap.parse_args()

    client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=10000)
    db = client[settings.DATABASE_NAME]

    changed = 0
    for raw_id in args.document_ids:
        try:
            oid = ObjectId(str(raw_id))
        except Exception:
            print(f"[skip] invalid ObjectId: {raw_id!r}")
            continue

        doc = db.documents.find_one({"_id": oid})
        if not doc:
            print(f"[skip] not found: {raw_id}")
            continue

        org_id, original_key, thumbnail_key = _resolve_assets(doc)
        if not org_id:
            print(f"[skip] missing org_id/family_id: {raw_id}")
            continue
        if not original_key:
            print(f"[skip] missing s3_original_url: {raw_id}")
            continue

        if not thumbnail_key:
            # Fallback: we can still generate and upload a new thumbnail,
            # but that requires updating the DB document assets.
            print(f"[warn] missing s3_thumbnail_url; will generate a new key: {raw_id}")

        filename = _basename(original_key) or "document"
        print(f"[info] doc={raw_id} org={org_id}")
        print(f"       original={original_key}")
        print(f"       thumbnail={thumbnail_key or '(missing)'}")

        file_data = _download_s3_bytes(original_key)
        thumb_bytes, generated_thumb_filename = generate_thumbnail(file_data, filename)

        if not args.apply:
            if thumbnail_key:
                print(f"[dry-run] would overwrite thumbnail object at existing key: {thumbnail_key}")
            else:
                print(
                    "[dry-run] would upload thumbnail for "
                    f"org={org_id} using filename={generated_thumb_filename}"
                )
                print("[dry-run] would update DB assets.s3_thumbnail_url to new key")
            continue

        # If the doc already has a thumbnail key, overwrite that exact S3 object so
        # legacy/custom keys remain valid without requiring a DB update.
        if thumbnail_key:
            s3 = get_s3_client()
            s3.put_object(
                Bucket=settings.AWS_S3_BUCKET_NAME,
                Key=thumbnail_key,
                Body=thumb_bytes,
            )
            print(f"[apply] overwrote thumbnail object at existing key: {thumbnail_key}")
        else:
            new_thumb_key = upload_to_s3(
                thumb_bytes, org_id, generated_thumb_filename, is_thumbnail=True
            )
            db.documents.update_one(
                {"_id": oid},
                {"$set": {"assets.s3_thumbnail_url": new_thumb_key}},
            )
            print(f"[apply] updated DB assets.s3_thumbnail_url -> {new_thumb_key}")

        changed += 1

    if not args.apply:
        print("\nDone (dry-run). Re-run with --apply to perform changes.")
    else:
        print(f"\nDone. Updated {changed} document(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

