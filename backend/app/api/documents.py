"""Documents API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from bson import ObjectId
from datetime import datetime
from typing import Optional, List
from werkzeug.utils import secure_filename

from app.core.database import get_db, get_family_filter
from app.api.auth import get_current_user
from app.models.document import DocumentResponse, DocumentFilter, DocumentCreate
from app.services.storage import upload_to_s3, delete_from_s3
from app.services.document_processor import process_document
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
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Get documents with optional filtering."""
    if not current_user.get("family_id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not part of a family"
        )
    
    family_id = current_user["family_id"]
    
    # Build filter
    filter_query = get_family_filter(family_id)
    
    if sender:
        filter_query["metadata.sender_name"] = sender
    if event_type:
        filter_query["metadata.event_type"] = event_type
    if year:
        start_date = datetime(year, 1, 1).isoformat()
        end_date = datetime(year + 1, 1, 1).isoformat()
        filter_query["metadata.doc_date"] = {"$gte": start_date, "$lt": end_date}
    
    # Get documents
    documents = list(db.documents.find(filter_query).sort("created_at", -1))
    
    # Convert to response models
    result = []
    for doc in documents:
        result.append(DocumentResponse(
            id=str(doc["_id"]),
            family_id=doc["family_id"],
            uploader_id=str(doc.get("uploader_id", "")),
            metadata={
                "sender_name": doc["metadata"]["sender_name"],
                "event_type": doc["metadata"]["event_type"],
                "doc_date": doc["metadata"]["doc_date"]
            },
            file_type=doc.get("file_type", ""),
            s3_original_url=doc.get("s3_original_url", ""),
            s3_thumbnail_url=doc.get("s3_thumbnail_url", ""),
            created_at=doc.get("created_at", datetime.utcnow())
        ))
    
    return result


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Get a specific document."""
    if not current_user.get("family_id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not part of a family"
        )
    
    family_id = current_user["family_id"]
    
    doc = db.documents.find_one({
        "_id": ObjectId(document_id),
        "family_id": family_id
    })
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return DocumentResponse(
        id=str(doc["_id"]),
        family_id=doc["family_id"],
        uploader_id=str(doc.get("uploader_id", "")),
        metadata={
            "sender_name": doc["metadata"]["sender_name"],
            "event_type": doc["metadata"]["event_type"],
            "doc_date": doc["metadata"]["doc_date"]
        },
        file_type=doc.get("file_type", ""),
        s3_original_url=doc.get("s3_original_url", ""),
        s3_thumbnail_url=doc.get("s3_thumbnail_url", ""),
        created_at=doc.get("created_at", datetime.utcnow())
    )


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    sender_name: str = Form(...),
    event_type: str = Form(...),
    doc_date: str = Form(...),
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Upload a new document."""
    if not current_user.get("family_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be part of a family to upload documents"
        )
    
    family_id = current_user["family_id"]
    
    # Validate file
    if not allowed_file(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )
    
    # Read file data
    file_data = await file.read()
    
    if len(file_data) > settings.MAX_CONTENT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {settings.MAX_CONTENT_LENGTH / (1024*1024)}MB"
        )
    
    filename = secure_filename(file.filename)
    
    try:
        # Process document (thumbnail, extraction, embedding)
        processed = process_document(file_data, filename)
        
        # Upload to S3
        s3_original_url = upload_to_s3(file_data, family_id, filename, is_thumbnail=False)
        s3_thumbnail_url = upload_to_s3(
            processed['thumbnail_data'],
            family_id,
            processed['thumbnail_filename'],
            is_thumbnail=True
        )
        
        # Create document in MongoDB
        document = {
            "family_id": family_id,
            "uploader_id": str(current_user["_id"]),
            "created_at": datetime.utcnow(),
            "metadata": {
                "sender_name": sender_name,
                "event_type": event_type,
                "doc_date": doc_date
            },
            "file_type": file.content_type or f"application/{filename.split('.')[-1]}",
            "s3_original_url": s3_original_url,
            "s3_thumbnail_url": s3_thumbnail_url,
            "ai_context": {
                "text_content": processed['text_content'],
                "embedding": processed['embedding']
            }
        }
        
        doc_id = db.documents.insert_one(document).inserted_id
        
        # Update family event_types if new
        family = db.families.find_one({"_id": ObjectId(family_id)})
        if family:
            event_types = family.get('event_types', [])
            if event_type not in event_types:
                db.families.update_one(
                    {"_id": ObjectId(family_id)},
                    {"$addToSet": {"event_types": event_type}}
                )
        
        document["_id"] = doc_id
        
        return DocumentResponse(
            id=str(doc_id),
            family_id=document["family_id"],
            uploader_id=document["uploader_id"],
            metadata=document["metadata"],
            file_type=document["file_type"],
            s3_original_url=document["s3_original_url"],
            s3_thumbnail_url=document["s3_thumbnail_url"],
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
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Delete a document."""
    if not current_user.get("family_id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not part of a family"
        )
    
    family_id = current_user["family_id"]
    
    # Find document and verify ownership
    doc = db.documents.find_one({
        "_id": ObjectId(document_id),
        "family_id": family_id
    })
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Delete from S3
    filename = doc['s3_original_url'].split('/')[-1]
    delete_from_s3(family_id, filename, is_thumbnail=False)
    
    thumbnail_filename = doc['s3_thumbnail_url'].split('/')[-1]
    delete_from_s3(family_id, thumbnail_filename, is_thumbnail=True)
    
    # Delete from MongoDB
    db.documents.delete_one({"_id": ObjectId(document_id)})
    
    return None

