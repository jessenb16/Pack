"""Documents API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Body
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional, List, Any, Dict

from werkzeug.utils import secure_filename

from app.core.database import get_db, get_org_filter
from app.api.auth import get_current_user_light, get_org_id_light
from app.models.document import DocumentResponse, DocumentMetadataPatch
from app.models.document import LabelRef, DocumentMetadata
from app.services.storage import upload_to_s3, delete_from_s3, get_signed_url, extract_s3_key_from_url
from app.services.document_processor import process_document, text_to_pdf, _sanitize_filename, create_embedding
from app.services.label_catalog import (
    KIND_SENDER,
    KIND_EVENT,
    KIND_RECIPIENT,
    resolve_label_from_id_or_text,
    optional_recipient,
    normalize_doc_date,
    build_metadata_prefix,
    compose_ai_text_content,
    resolve_display_triple,
)
from app.services.org_settings import get_catalog_for_org
from app.core.config import settings
from pymongo.database import Database
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in settings.ALLOWED_EXTENSIONS

def _doc_to_response(
    doc: Dict[str, Any],
    db: Database,
    senders: Optional[List[Dict[str, str]]] = None,
    events: Optional[List[Dict[str, str]]] = None,
    recipients: Optional[List[Dict[str, str]]] = None,
) -> DocumentResponse:
    org_id_doc = doc.get("org_id") or doc.get("family_id", "")
    assets = doc.get("assets", {})

    original_key = extract_s3_key_from_url(
        assets.get("s3_original_url") or doc.get("s3_original_url", "")
    )
    thumbnail_key = extract_s3_key_from_url(
        assets.get("s3_thumbnail_url") or doc.get("s3_thumbnail_url", "")
    )

    original_signed_url = get_signed_url(original_key) if original_key else ""
    thumbnail_signed_url = get_signed_url(thumbnail_key) if thumbnail_key else ""

    if senders is None or events is None or recipients is None:
        senders, events, recipients = get_catalog_for_org(org_id_doc, db)
    s, e, r = resolve_display_triple(doc.get("metadata") or {}, senders, events, recipients)
    meta = doc.get("metadata") or {}
    dd = meta.get("doc_date", "")
    try:
        dd_norm = normalize_doc_date(str(dd)) if dd else ""
    except Exception:
        dd_norm = str(dd)

    recipient_model = LabelRef(id=r["id"], label=r["label"]) if r else None

    return DocumentResponse(
        id=str(doc["_id"]),
        family_id=org_id_doc,
        uploader_id=str(doc.get("uploader_id", "")),
        metadata=DocumentMetadata(
            sender=LabelRef(id=s["id"], label=s["label"]),
            event_type=LabelRef(id=e["id"], label=e["label"]),
            recipient=recipient_model,
            doc_date=dd_norm or str(dd),
            caption=meta.get("caption"),
        ),
        file_type=assets.get("file_type") or doc.get("file_type", ""),
        s3_original_url=original_signed_url,
        s3_thumbnail_url=thumbnail_signed_url,
        created_at=doc.get("created_at", datetime.now(timezone.utc)),
    )


def _apply_metadata_and_ai(
    org_id: str,
    db: Database,
    sender_entry: Dict[str, str],
    event_entry: Dict[str, str],
    recipient_entry: Optional[Dict[str, str]],
    doc_date: str,
    caption: str,
    extracted_text: str,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    dd = normalize_doc_date(doc_date)
    rlab = recipient_entry["label"] if recipient_entry else None
    prefix = build_metadata_prefix(sender_entry["label"], event_entry["label"], dd, rlab)
    text_content = compose_ai_text_content(prefix, caption, extracted_text)
    embedding = create_embedding(text_content)
    metadata: Dict[str, Any] = {
        "sender_id": sender_entry["id"],
        "event_type_id": event_entry["id"],
        "doc_date": dd,
        "caption": caption.strip(),
    }
    if recipient_entry:
        metadata["recipient_id"] = recipient_entry["id"]
    else:
        metadata["recipient_id"] = None

    ai_context = {
        "extracted_text": extracted_text,
        "metadata_prefix": prefix,
        "text_content": text_content,
        "embedding": embedding,
    }
    return metadata, ai_context


@router.get("", response_model=List[DocumentResponse])
async def get_documents(
    sender_id: Optional[str] = None,
    event_type_id: Optional[str] = None,
    year: Optional[int] = None,
    current_user: dict = Depends(get_current_user_light),
    org_id: str = Depends(get_org_id_light),
    db: Database = Depends(get_db),
):
    """Get documents with optional filtering (prefer sender_id / event_type_id)."""
    senders, events, recipients = get_catalog_for_org(org_id, db)

    parts: List[Dict[str, Any]] = [get_org_filter(org_id)]

    if sender_id:
        parts.append({"metadata.sender_id": sender_id})

    if event_type_id:
        parts.append({"metadata.event_type_id": event_type_id})

    if year is not None:
        start_date = f"{year:04d}-01-01"
        end_date = f"{year + 1:04d}-01-01"
        parts.append({"metadata.doc_date": {"$gte": start_date, "$lt": end_date}})

    if len(parts) == 1:
        filter_query = parts[0]
    else:
        filter_query = {"$and": parts}

    projection = {
        "_id": 1,
        "org_id": 1,
        "family_id": 1,
        "uploader_id": 1,
        "metadata": 1,
        "s3_original_url": 1,
        "s3_thumbnail_url": 1,
        "assets": 1,
        "created_at": 1,
    }
    documents = list(db.documents.find(filter_query, projection).sort("created_at", -1).limit(100))

    return [_doc_to_response(doc, db, senders, events, recipients) for doc in documents]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: dict = Depends(get_current_user_light),
    org_id: str = Depends(get_org_id_light),
    db: Database = Depends(get_db),
):
    """Get a specific document."""
    doc = db.documents.find_one({
        "_id": ObjectId(document_id),
        "$or": [
            {"org_id": org_id},
            {"family_id": org_id}
        ]
    })

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    senders, events, recipients = get_catalog_for_org(org_id, db)
    return _doc_to_response(doc, db, senders, events, recipients)


@router.patch("/{document_id}", response_model=DocumentResponse)
async def patch_document_metadata(
    document_id: str,
    body: DocumentMetadataPatch = Body(...),
    current_user: dict = Depends(get_current_user_light),
    org_id: str = Depends(get_org_id_light),
    db: Database = Depends(get_db),
):
    """Update document metadata and re-embed (uploader only)."""
    doc = db.documents.find_one({
        "_id": ObjectId(document_id),
        "$or": [
            {"org_id": org_id},
            {"family_id": org_id}
        ]
    })
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if doc.get("uploader_id") != current_user.get("clerk_user_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the document uploader can edit this document"
        )

    try:
        sender_entry = resolve_label_from_id_or_text(
            org_id, KIND_SENDER, body.sender_id, body.sender_label, db
        )
        event_entry = resolve_label_from_id_or_text(
            org_id, KIND_EVENT, body.event_type_id, body.event_type_label, db
        )
        recipient_entry = optional_recipient(
            org_id, body.recipient_id, body.recipient_label, db
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    ai_ctx = doc.get("ai_context") or {}
    extracted = ai_ctx.get("extracted_text")
    if extracted is None:
        extracted = ""
    extracted = str(extracted)
    caption = body.caption.strip()
    metadata, ai_context = _apply_metadata_and_ai(
        org_id, db, sender_entry, event_entry, recipient_entry,
        body.doc_date, caption, extracted,
    )

    db.documents.update_one(
        {"_id": ObjectId(document_id)},
        {"$set": {"metadata": metadata, "ai_context": ai_context}},
    )
    updated = db.documents.find_one({"_id": ObjectId(document_id)})
    senders, events, recipients = get_catalog_for_org(org_id, db)
    return _doc_to_response(updated, db, senders, events, recipients)


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    doc_date: str = Form(...),
    caption: str = Form(...),
    sender_id: Optional[str] = Form(None),
    sender_label: Optional[str] = Form(None),
    event_type_id: Optional[str] = Form(None),
    event_type_label: Optional[str] = Form(None),
    recipient_id: Optional[str] = Form(None),
    recipient_label: Optional[str] = Form(None),
    custom_filename: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user_light),
    org_id: str = Depends(get_org_id_light),
    db: Database = Depends(get_db),
):
    """Upload a new document. Accepts either a file (image/PDF) or plain text (generates PDF)."""

    file_data = None
    filename = None
    content_type = "application/pdf"

    if file and file.filename and file.filename not in ("", "undefined"):
        if not allowed_file(file.filename):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Allowed types: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )
        file_data = await file.read()
        if len(file_data) == 0:
            file_data = None
        else:
            filename = secure_filename(file.filename)
            content_type = file.content_type or f"application/{filename.rsplit('.', 1)[-1]}"

    if file_data is None and text is not None and not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text cannot be empty."
        )

    if file_data is None and text and text.strip():
        text_value = text.strip()
        approx_bytes = len(text_value.encode("utf-8"))
        if approx_bytes > settings.MAX_CONTENT_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Text too large. Maximum size is {settings.MAX_CONTENT_LENGTH / (1024*1024)}MB"
            )
        timestamp_suffix = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
        filename_base = f"text_upload_{timestamp_suffix}"
        if custom_filename and custom_filename.strip():
            sanitized = _sanitize_filename(custom_filename.strip())
            if sanitized:
                base_name = sanitized.rsplit(".", 1)[0]
                filename_base = f"{base_name}_{timestamp_suffix}"
        file_data, filename = text_to_pdf(text_value, filename_base)

    if file_data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide either a file (image or PDF) or paste text to create a document."
        )

    if len(file_data) > settings.MAX_CONTENT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {settings.MAX_CONTENT_LENGTH / (1024*1024)}MB"
        )

    if not caption or not caption.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Caption is required. Please describe your document in one or two sentences."
        )

    try:
        sender_entry = resolve_label_from_id_or_text(
            org_id, KIND_SENDER, sender_id, sender_label, db
        )
        event_entry = resolve_label_from_id_or_text(
            org_id, KIND_EVENT, event_type_id, event_type_label, db
        )
        recipient_entry = optional_recipient(org_id, recipient_id, recipient_label, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    try:
        processed = process_document(file_data, filename, caption="")

        s3_original_key = upload_to_s3(file_data, org_id, filename, is_thumbnail=False)
        s3_thumbnail_key = upload_to_s3(
            processed['thumbnail_data'],
            org_id,
            processed['thumbnail_filename'],
            is_thumbnail=True
        )

        extracted_text = processed.get("extracted_text", "") or ""
        cap = caption.strip()
        metadata, ai_context = _apply_metadata_and_ai(
            org_id, db, sender_entry, event_entry, recipient_entry,
            doc_date, cap, extracted_text,
        )

        document = {
            "org_id": org_id,
            "uploader_id": current_user.get("clerk_user_id"),
            "created_at": datetime.now(timezone.utc),
            "metadata": metadata,
            "assets": {
                "file_type": content_type,
                "s3_original_url": s3_original_key,
                "s3_thumbnail_url": s3_thumbnail_key
            },
            "ai_context": ai_context,
        }

        doc_id = db.documents.insert_one(document).inserted_id
        saved = db.documents.find_one({"_id": doc_id})
        senders, events, recipients = get_catalog_for_org(org_id, db)
        return _doc_to_response(saved, db, senders, events, recipients)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing document: {str(e)}"
        )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: dict = Depends(get_current_user_light),
    org_id: str = Depends(get_org_id_light),
    db: Database = Depends(get_db),
):
    """Delete a document."""
    doc = db.documents.find_one({
        "_id": ObjectId(document_id),
        "$or": [
            {"org_id": org_id},
            {"family_id": org_id}
        ]
    })

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    doc_uploader_id = doc.get("uploader_id")
    current_user_id = current_user.get("clerk_user_id")

    if not doc_uploader_id or doc_uploader_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the document uploader can delete this document"
        )

    assets = doc.get("assets", {})
    original_key = extract_s3_key_from_url(
        assets.get("s3_original_url") or doc.get("s3_original_url", "")
    )
    thumbnail_key = extract_s3_key_from_url(
        assets.get("s3_thumbnail_url") or doc.get("s3_thumbnail_url", "")
    )

    if original_key:
        delete_from_s3(original_key)
    if thumbnail_key:
        delete_from_s3(thumbnail_key)

    db.documents.delete_one({"_id": ObjectId(document_id)})

    return None
