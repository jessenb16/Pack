"""Documents API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Body, BackgroundTasks
from fastapi.responses import StreamingResponse
from botocore.exceptions import ClientError
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional, List, Any, Dict

from werkzeug.utils import secure_filename

from app.core.database import get_db, get_org_filter
from app.api.auth import get_current_user_light, get_org_id_light
from app.models.document import DocumentResponse, DocumentMetadataPatch
from app.models.document import LabelRef, DocumentMetadata, DocumentPageResponse
from app.services.storage import (
    upload_to_s3,
    upload_document_page_to_s3,
    delete_document_assets_from_s3,
    delete_from_s3,
    get_signed_url,
    extract_s3_key_from_url,
    open_s3_object,
)
from app.services.document_processor import (
    process_document,
    process_multi_image_document,
    text_to_pdf,
    _sanitize_filename,
    create_embedding,
    IMAGE_EXTENSIONS,
)
from app.services.user_settings import get_document_uploaded_email_disabled
from app.services.email_client import send_email, EmailSendError
from app.services.notification_emails import build_document_uploaded_email
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
from app.core.clerk_org import get_organization_members
from app.core.config import settings
from pymongo.database import Database
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in settings.ALLOWED_EXTENSIONS


def is_image_file(filename: str) -> bool:
    """True if filename is an allowed image type (not PDF)."""
    if '.' not in filename:
        return False
    return filename.rsplit('.', 1)[1].lower() in IMAGE_EXTENSIONS


async def _read_ordered_upload_files(files: Optional[List[UploadFile]]) -> List[tuple[bytes, str]]:
    """Read non-empty uploads preserving multipart order."""
    if not files:
        return []
    result: List[tuple[bytes, str]] = []
    for upload in files:
        if not upload or not upload.filename or upload.filename in ("", "undefined"):
            continue
        data = await upload.read()
        if not data:
            continue
        result.append((data, secure_filename(upload.filename)))
    return result


def _cleanup_uploaded_keys(keys: List[str]) -> None:
    for key in keys:
        if key:
            delete_from_s3(key)
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

    pages_response: Optional[List[DocumentPageResponse]] = None
    raw_pages = assets.get("pages")
    if raw_pages and isinstance(raw_pages, list):
        pages_response = []
        for page in sorted(
            (p for p in raw_pages if isinstance(p, dict)),
            key=lambda p: p.get("page_number", 0),
        ):
            page_orig_key = extract_s3_key_from_url(page.get("s3_original_url", ""))
            page_thumb_key = extract_s3_key_from_url(page.get("s3_thumbnail_url", ""))
            pages_response.append(
                DocumentPageResponse(
                    page_number=int(page.get("page_number", 0)),
                    s3_original_url=get_signed_url(page_orig_key) if page_orig_key else "",
                    s3_thumbnail_url=get_signed_url(page_thumb_key) if page_thumb_key else "",
                )
            )
        if not pages_response:
            pages_response = None

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
        pages=pages_response,
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


async def _upload_multi_image_document(
    *,
    org_id: str,
    db: Database,
    current_user: dict,
    upload_files: List[tuple[bytes, str]],
    sender_entry: Dict[str, str],
    event_entry: Dict[str, str],
    recipient_entry: Optional[Dict[str, str]],
    doc_date: str,
    caption: str,
    background_tasks: Optional[BackgroundTasks],
) -> DocumentResponse:
    """Ingest 2+ ordered images as one multi-page document."""
    page_count = len(upload_files)
    if page_count < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Multi-image upload requires at least 2 images.",
        )
    if page_count > settings.MAX_MULTI_IMAGE_PAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many images. Maximum is {settings.MAX_MULTI_IMAGE_PAGES} pages per document.",
        )

    total_bytes = sum(len(data) for data, _ in upload_files)
    if total_bytes > settings.MAX_MULTI_IMAGE_TOTAL_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Total upload too large. Maximum size is "
                f"{settings.MAX_MULTI_IMAGE_TOTAL_BYTES / (1024 * 1024)}MB"
            ),
        )

    for _, filename in upload_files:
        if not is_image_file(filename):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Multi-image uploads must be images only. PDFs cannot be combined with images.",
            )

    doc_id = ObjectId()
    uploaded_keys: List[str] = []

    try:
        processed = process_multi_image_document(upload_files)
        assets_pages: List[Dict[str, Any]] = []

        for (file_data, _original_name), page in zip(upload_files, processed["pages"]):
            page_filename = page["page_filename"]
            thumb_filename = f"page_{page['page_number']:02d}.jpg"

            original_key = upload_document_page_to_s3(
                file_data, org_id, str(doc_id), page_filename, is_thumbnail=False
            )
            uploaded_keys.append(original_key)

            thumb_key = upload_document_page_to_s3(
                page["thumbnail_data"],
                org_id,
                str(doc_id),
                thumb_filename,
                is_thumbnail=True,
            )
            uploaded_keys.append(thumb_key)

            assets_pages.append(
                {
                    "page_number": page["page_number"],
                    "s3_original_url": original_key,
                    "s3_thumbnail_url": thumb_key,
                    "extracted_text": page.get("extracted_text", "") or "",
                }
            )

        first_page = assets_pages[0]
        extracted_text = processed.get("combined_extracted_text", "") or ""
        cap = caption.strip()
        metadata, ai_context = _apply_metadata_and_ai(
            org_id,
            db,
            sender_entry,
            event_entry,
            recipient_entry,
            doc_date,
            cap,
            extracted_text,
        )

        document = {
            "_id": doc_id,
            "org_id": org_id,
            "uploader_id": current_user.get("clerk_user_id"),
            "created_at": datetime.now(timezone.utc),
            "metadata": metadata,
            "assets": {
                "file_type": "image/multi",
                "s3_original_url": first_page["s3_original_url"],
                "s3_thumbnail_url": first_page["s3_thumbnail_url"],
                "pages": assets_pages,
            },
            "ai_context": ai_context,
        }

        db.documents.insert_one(document)
        saved = db.documents.find_one({"_id": doc_id})
        senders, events, recipients = get_catalog_for_org(org_id, db)

        try:
            if background_tasks is not None and saved:
                background_tasks.add_task(
                    _send_document_uploaded_emails_background,
                    org_id=org_id,
                    document_id=str(doc_id),
                    uploader_id=str(current_user.get("clerk_user_id") or ""),
                    db=db,
                )
        except Exception as e:
            logger.error("Failed to enqueue notification background task: %s", e)

        return _doc_to_response(saved, db, senders, events, recipients)

    except HTTPException:
        _cleanup_uploaded_keys(uploaded_keys)
        raise
    except Exception as e:
        _cleanup_uploaded_keys(uploaded_keys)
        logger.error(f"Error uploading multi-image document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing multi-image document: {str(e)}",
        )


def _send_document_uploaded_emails_background(
    *,
    org_id: str,
    document_id: str,
    uploader_id: str,
    db: Database,
) -> None:
    """
    Best-effort immediate notification emails.
    Runs in a BackgroundTask so it must not raise.
    """
    try:
        doc = db.documents.find_one({"_id": ObjectId(document_id)})
        if not doc:
            logger.warning("Notification: document not found: %s", document_id)
            return

        senders, events, recipients = get_catalog_for_org(org_id, db)
        s, e, r = resolve_display_triple(doc.get("metadata") or {}, senders, events, recipients)

        meta = doc.get("metadata") or {}
        caption = str(meta.get("caption") or "").strip()
        doc_date = str(meta.get("doc_date") or "").strip()

        memberships = get_organization_members(org_id, bypass_cache=False)

        uploader_name = "Someone"
        member_targets: list[str] = []

        for membership in memberships:
            pud = membership.get("public_user_data") or {}
            member_user_id = pud.get("user_id") or ""
            email = (pud.get("identifier") or "").strip()
            first = pud.get("first_name") or ""
            last = pud.get("last_name") or ""
            name = f"{first} {last}".strip() or email or member_user_id or "User"

            if member_user_id == uploader_id:
                uploader_name = name
                continue  # exclude uploader
            if not member_user_id or not email:
                continue
            if get_document_uploaded_email_disabled(
                org_id=org_id, clerk_user_id=member_user_id, db=db
            ):
                continue
            member_targets.append(email)

        if not member_targets:
            return

        base = (settings.FRONTEND_URL or "").rstrip("/")
        dashboard_url = f"{base}/dashboard?focus={document_id}"
        subject, html, text = build_document_uploaded_email(
            uploader_name=uploader_name,
            dashboard_url=dashboard_url,
            caption=caption,
            doc_date=doc_date,
            sender_label=s.get("label") if s else None,
            event_label=e.get("label") if e else None,
            recipient_label=r.get("label") if r else None,
        )

        for email in member_targets:
            try:
                send_email(to=[email], subject=subject, html=html, text=text)
            except EmailSendError as err:
                logger.error("Notification email failed to %s: %s", email, err)
            except Exception as err:
                logger.error("Notification email unexpected error to %s: %s", email, err)
    except Exception as err:
        logger.error("Notification background task failed: %s", err)


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


@router.get("/{document_id}/content")
async def get_document_content(
    document_id: str,
    current_user: dict = Depends(get_current_user_light),
    org_id: str = Depends(get_org_id_light),
    db: Database = Depends(get_db),
):
    """
    Stream document bytes through the API (auth-gated).

    PDF.js fetches via XHR/fetch, which requires CORS on S3; proxying here
    avoids bucket CORS while keeping the same access checks as get_document.
    """
    del current_user  # auth enforced by dependency
    try:
        doc = db.documents.find_one({
            "_id": ObjectId(document_id),
            "$or": [
                {"org_id": org_id},
                {"family_id": org_id},
            ],
        })
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    assets = doc.get("assets", {})
    original_key = extract_s3_key_from_url(
        assets.get("s3_original_url") or doc.get("s3_original_url", "")
    )
    if not original_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found",
        )

    file_type = (doc.get("file_type") or "").lower()
    if file_type != "application/pdf" and not original_key.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document is not a PDF",
        )

    try:
        obj = open_s3_object(original_key)
    except ClientError as e:
        logger.error(f"Error streaming document {document_id} from S3: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    content_type = obj.get("ContentType") or "application/pdf"
    body = obj["Body"]

    def iter_chunks():
        try:
            for chunk in body.iter_chunks(chunk_size=1024 * 1024):
                if chunk:
                    yield chunk
        finally:
            body.close()

    return StreamingResponse(
        iter_chunks(),
        media_type=content_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": "inline",
        },
    )


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
    files: Optional[List[UploadFile]] = File(None),
    background_tasks: BackgroundTasks = None,
    current_user: dict = Depends(get_current_user_light),
    org_id: str = Depends(get_org_id_light),
    db: Database = Depends(get_db),
):
    """Upload a new document. Accepts a file (image/PDF), multiple images, or plain text (PDF)."""

    ordered_files = await _read_ordered_upload_files(files)

    has_legacy_file = bool(
        file and file.filename and file.filename not in ("", "undefined")
    )
    if has_legacy_file and ordered_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either a single file or multiple images, not both.",
        )

    if len(ordered_files) >= 2:
        if not caption or not caption.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Caption is required. Please describe your document in one or two sentences.",
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

        return await _upload_multi_image_document(
            org_id=org_id,
            db=db,
            current_user=current_user,
            upload_files=ordered_files,
            sender_entry=sender_entry,
            event_entry=event_entry,
            recipient_entry=recipient_entry,
            doc_date=doc_date,
            caption=caption,
            background_tasks=background_tasks,
        )

    file_data = None
    filename = None
    content_type = "application/pdf"

    if len(ordered_files) == 1:
        file_data, filename = ordered_files[0]
        if not allowed_file(filename):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Allowed types: {', '.join(settings.ALLOWED_EXTENSIONS)}",
            )
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext == "pdf":
            content_type = "application/pdf"
        elif ext in ("jpg", "jpeg", "jfif"):
            content_type = "image/jpeg"
        else:
            content_type = f"image/{ext}"
    elif has_legacy_file:
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

        # Best-effort: notify other members by email without blocking the response.
        try:
            if background_tasks is not None and saved:
                background_tasks.add_task(
                    _send_document_uploaded_emails_background,
                    org_id=org_id,
                    document_id=str(doc_id),
                    uploader_id=str(current_user.get("clerk_user_id") or ""),
                    db=db,
                )
        except Exception as e:
            logger.error("Failed to enqueue notification background task: %s", e)

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

    assets = doc.get("assets", {}) or {}
    if not assets.get("s3_original_url") and doc.get("s3_original_url"):
        assets = {
            **assets,
            "s3_original_url": doc.get("s3_original_url"),
            "s3_thumbnail_url": doc.get("s3_thumbnail_url"),
        }
    delete_document_assets_from_s3(assets)

    db.documents.delete_one({"_id": ObjectId(document_id)})

    return None
