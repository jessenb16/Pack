"""Documents API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional, List
from werkzeug.utils import secure_filename

from app.core.database import get_db, get_org_filter
from app.api.auth import get_current_user_light, get_org_id_light
from app.models.document import DocumentResponse, DocumentFilter, DocumentCreate
from app.services.storage import upload_to_s3, delete_from_s3, get_signed_url, extract_s3_key_from_url
from app.services.document_processor import process_document, text_to_pdf, _sanitize_filename
from app.core.config import settings
from pymongo.database import Database
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in settings.ALLOWED_EXTENSIONS


@router.get("", response_model=List[DocumentResponse])
async def get_documents(
    sender: Optional[str] = None,
    event_type: Optional[str] = None,
    year: Optional[int] = None,
    current_user: dict = Depends(get_current_user_light),
    org_id: str = Depends(get_org_id_light),
    db: Database = Depends(get_db)
):
    """Get documents with optional filtering."""
    # Build filter using org_id
    filter_query = get_org_filter(org_id)
    
    if sender:
        filter_query["metadata.sender_name"] = sender
    if event_type:
        filter_query["metadata.event_type"] = event_type
    if year:
        start_date = datetime(year, 1, 1).isoformat()
        end_date = datetime(year + 1, 1, 1).isoformat()
        filter_query["metadata.doc_date"] = {"$gte": start_date, "$lt": end_date}
    
    # Get documents - limit to 100 for performance (frontend can paginate if needed)
    # Only fetch fields we need for better performance
    projection = {
        "_id": 1,
        "org_id": 1,
        "family_id": 1,
        "uploader_id": 1,
        "metadata": 1,
        "s3_original_url": 1,
        "s3_thumbnail_url": 1,
        "assets": 1,
        "created_at": 1
    }
    documents = list(db.documents.find(filter_query, projection).sort("created_at", -1).limit(100))
    
    # Convert to response models and generate signed URLs
    result = []
    for doc in documents:
        # Handle both old format (family_id) and new format (org_id)
        org_id_doc = doc.get("org_id") or doc.get("family_id", "")
        assets = doc.get("assets", {})
        
        # Extract S3 keys and generate signed URLs
        original_key = extract_s3_key_from_url(
            assets.get("s3_original_url") or doc.get("s3_original_url", "")
        )
        thumbnail_key = extract_s3_key_from_url(
            assets.get("s3_thumbnail_url") or doc.get("s3_thumbnail_url", "")
        )
        
        # Generate signed URLs (1 hour expiration)
        original_signed_url = get_signed_url(original_key) if original_key else ""
        thumbnail_signed_url = get_signed_url(thumbnail_key) if thumbnail_key else ""
        
        result.append(DocumentResponse(
            id=str(doc["_id"]),
            family_id=org_id_doc,  # Keep field name for API compatibility
            uploader_id=str(doc.get("uploader_id", "")),
            metadata={
                "sender_name": doc["metadata"]["sender_name"],
                "event_type": doc["metadata"]["event_type"],
                "doc_date": doc["metadata"]["doc_date"],
                "recipient_name": doc["metadata"].get("recipient_name"),
                "caption": doc["metadata"].get("caption")
            },
            file_type=assets.get("file_type") or doc.get("file_type", ""),
            s3_original_url=original_signed_url,
            s3_thumbnail_url=thumbnail_signed_url,
            created_at=doc.get("created_at", datetime.now(timezone.utc))
        ))
    
    return result


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: dict = Depends(get_current_user_light),
    org_id: str = Depends(get_org_id_light),
    db: Database = Depends(get_db)
):
    """Get a specific document."""
    # Support both org_id and family_id for backward compatibility
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
    
    org_id_doc = doc.get("org_id") or doc.get("family_id", "")
    assets = doc.get("assets", {})
    
    # Extract S3 keys and generate signed URLs
    original_key = extract_s3_key_from_url(
        assets.get("s3_original_url") or doc.get("s3_original_url", "")
    )
    thumbnail_key = extract_s3_key_from_url(
        assets.get("s3_thumbnail_url") or doc.get("s3_thumbnail_url", "")
    )
    
    # Generate signed URLs (1 hour expiration)
    original_signed_url = get_signed_url(original_key) if original_key else ""
    thumbnail_signed_url = get_signed_url(thumbnail_key) if thumbnail_key else ""
    
    return DocumentResponse(
        id=str(doc["_id"]),
        family_id=org_id_doc,
        uploader_id=str(doc.get("uploader_id", "")),
        metadata={
            "sender_name": doc["metadata"]["sender_name"],
            "event_type": doc["metadata"]["event_type"],
            "doc_date": doc["metadata"]["doc_date"],
            "recipient_name": doc["metadata"].get("recipient_name"),
            "caption": doc["metadata"].get("caption")
        },
        file_type=assets.get("file_type") or doc.get("file_type", ""),
        s3_original_url=original_signed_url,
        s3_thumbnail_url=thumbnail_signed_url,
        created_at=doc.get("created_at", datetime.now(timezone.utc))
    )


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    sender_name: str = Form(...),
    event_type: str = Form(...),
    doc_date: str = Form(...),
    caption: str = Form(...),
    recipient_name: Optional[str] = Form(None),
    custom_filename: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user_light),
    org_id: str = Depends(get_org_id_light),
    db: Database = Depends(get_db)
):
    """Upload a new document. Accepts either a file (image/PDF) or plain text (generates PDF)."""
    
    # Determine source: file or text
    file_data = None
    filename = None
    content_type = "application/pdf"

    if file and file.filename and file.filename not in ("", "undefined"):
        # File upload
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

    if file_data is None and text and text.strip():
        # Text upload - generate PDF
        filename_base = "text_upload"
        if custom_filename and custom_filename.strip():
            sanitized = _sanitize_filename(custom_filename.strip())
            if sanitized:
                filename_base = sanitized.rsplit(".", 1)[0]
        else:
            filename_base = f"text_upload_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        file_data, filename = text_to_pdf(text.strip(), filename_base)

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
        # Process document (thumbnail, extraction, embedding)
        processed = process_document(file_data, filename, caption=caption.strip())
        
        # Upload to S3 (returns S3 keys, not URLs)
        s3_original_key = upload_to_s3(file_data, org_id, filename, is_thumbnail=False)
        s3_thumbnail_key = upload_to_s3(
            processed['thumbnail_data'],
            org_id,
            processed['thumbnail_filename'],
            is_thumbnail=True
        )
        
        # Create document in MongoDB (store S3 keys, not URLs)
        document = {
            "org_id": org_id,  # Use org_id directly from Clerk token
            "uploader_id": current_user.get("clerk_user_id"),  # Use Clerk user ID
            "created_at": datetime.now(timezone.utc),
            "metadata": {
                "sender_name": sender_name,
                "event_type": event_type,
                "doc_date": doc_date,
                "recipient_name": recipient_name,
                "caption": caption.strip()
            },
            "assets": {
                "file_type": content_type,
                "s3_original_url": s3_original_key,  # Store key, not URL
                "s3_thumbnail_url": s3_thumbnail_key  # Store key, not URL
            },
            "ai_context": {
                "text_content": processed['text_content'],
                "embedding": processed['embedding']
            }
        }
        
        doc_id = db.documents.insert_one(document).inserted_id
        
        # Update org_settings event_types and recipient_names if new
        from app.services.org_settings import add_event_type, add_recipient_name
        add_event_type(org_id, event_type, db)
        if recipient_name:
            add_recipient_name(org_id, recipient_name, db)
        
        document["_id"] = doc_id
        
        # Generate signed URLs for the response
        original_signed_url = get_signed_url(s3_original_key)
        thumbnail_signed_url = get_signed_url(s3_thumbnail_key)
        
        return DocumentResponse(
            id=str(doc_id),
            family_id=document["org_id"],  # Use org_id for API compatibility
            uploader_id=document["uploader_id"],
            metadata={
                "sender_name": document["metadata"]["sender_name"],
                "event_type": document["metadata"]["event_type"],
                "doc_date": document["metadata"]["doc_date"],
                "recipient_name": document["metadata"].get("recipient_name"),
                "caption": document["metadata"].get("caption")
            },
            file_type=document["assets"]["file_type"],
            s3_original_url=original_signed_url,
            s3_thumbnail_url=thumbnail_signed_url,
            created_at=document["created_at"]
        )
        
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
    db: Database = Depends(get_db)
):
    """Delete a document."""
    # Find document and verify ownership (support both org_id and family_id)
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
    
    # Verify that the current user is the uploader
    doc_uploader_id = doc.get("uploader_id")
    current_user_id = current_user.get("clerk_user_id")
    
    if not doc_uploader_id or doc_uploader_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the document uploader can delete this document"
        )
    
    # Delete from S3 using stored keys
    assets = doc.get("assets", {})
    original_key = extract_s3_key_from_url(
        assets.get("s3_original_url") or doc.get("s3_original_url", "")
    )
    thumbnail_key = extract_s3_key_from_url(
        assets.get("s3_thumbnail_url") or doc.get("s3_thumbnail_url", "")
    )
    
    # Delete both original and thumbnail
    if original_key:
        delete_from_s3(original_key)
    if thumbnail_key:
        delete_from_s3(thumbnail_key)
    
    # Delete from MongoDB
    db.documents.delete_one({"_id": ObjectId(document_id)})
    
    return None

