"""AWS S3 storage service for FastAPI."""
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

_s3_client = None


def get_s3_client():
    """Get or create S3 client."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
    return _s3_client


def upload_to_s3(file_data: bytes, family_id: str, filename: str, is_thumbnail: bool = False) -> str:
    """Upload file to S3."""
    try:
        s3_client = get_s3_client()
        
        if is_thumbnail:
            s3_key = f"families/{family_id}/thumbnails/{filename}"
        else:
            s3_key = f"families/{family_id}/originals/{filename}"
        
        s3_client.put_object(
            Bucket=settings.AWS_S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_data,
            ContentType='image/jpeg' if filename.endswith('.jpg') else 'application/pdf'
        )
        
        url = f"https://{settings.AWS_S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"
        logger.info(f"Uploaded file to S3: {s3_key}")
        return url
        
    except ClientError as e:
        logger.error(f"Error uploading to S3: {e}")
        raise


def delete_from_s3(family_id: str, filename: str, is_thumbnail: bool = False) -> bool:
    """Delete file from S3."""
    try:
        s3_client = get_s3_client()
        
        if is_thumbnail:
            s3_key = f"families/{family_id}/thumbnails/{filename}"
        else:
            s3_key = f"families/{family_id}/originals/{filename}"
        
        s3_client.delete_object(
            Bucket=settings.AWS_S3_BUCKET_NAME,
            Key=s3_key
        )
        
        logger.info(f"Deleted file from S3: {s3_key}")
        return True
        
    except ClientError as e:
        logger.error(f"Error deleting from S3: {e}")
        return False

