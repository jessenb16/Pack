"""AWS S3 storage service for FastAPI."""
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings
import logging
from urllib.parse import urlparse

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
    """
    Upload file to S3 and return the S3 key (not a URL).
    
    Returns:
        S3 key (path) like "families/{org_id}/originals/{filename}"
    """
    try:
        s3_client = get_s3_client()
        
        if is_thumbnail:
            s3_key = f"families/{family_id}/thumbnails/{filename}"
        else:
            s3_key = f"families/{family_id}/originals/{filename}"
        
        # Determine content type based on file extension
        file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
        content_type_map = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'pdf': 'application/pdf',
            'jfif': 'image/jpeg',  # JFIF is a JPEG variant
            'webp': 'image/webp'
        }
        content_type = content_type_map.get(file_ext, 'application/octet-stream')
        
        s3_client.put_object(
            Bucket=settings.AWS_S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_data,
            ContentType=content_type
        )
        
        logger.info(f"Uploaded file to S3: {s3_key}")
        return s3_key  # Return key, not URL
        
    except ClientError as e:
        logger.error(f"Error uploading to S3: {e}")
        raise


def get_signed_url(s3_key: str, expiration: int = 3600) -> str:
    """
    Generate a presigned URL for a private S3 object.
    
    Args:
        s3_key: S3 object key (path)
        expiration: URL expiration time in seconds (default: 1 hour)
    
    Returns:
        Presigned URL that expires after the specified time
    """
    try:
        s3_client = get_s3_client()
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_S3_BUCKET_NAME,
                'Key': s3_key
            },
            ExpiresIn=expiration
        )
        return url
    except ClientError as e:
        logger.error(f"Error generating signed URL for {s3_key}: {e}")
        raise


def extract_s3_key_from_url(url: str) -> str:
    """
    Extract S3 key from a full S3 URL.
    Handles both old format (full URL) and new format (just key).
    
    Args:
        url: Either a full S3 URL or just an S3 key
    
    Returns:
        S3 key (path)
    """
    if not url:
        return ""
    
    # If it's already just a key (no http://), return as-is
    if not url.startswith('http'):
        return url
    
    # Parse URL to extract key
    try:
        parsed = urlparse(url)
        # Remove leading slash from path
        key = parsed.path.lstrip('/')
        return key
    except Exception as e:
        logger.warning(f"Could not parse S3 URL {url}: {e}")
        # Try to extract key manually
        if '.s3.' in url:
            parts = url.split('.s3.')
            if len(parts) > 1:
                key_part = parts[1].split('.amazonaws.com/')
                if len(key_part) > 1:
                    return key_part[1]
        return url


def delete_from_s3(s3_key: str) -> bool:
    """
    Delete file from S3 using S3 key.
    
    Args:
        s3_key: S3 object key (path) or full URL (will extract key)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        s3_client = get_s3_client()
        
        # Extract key if URL is provided
        key = extract_s3_key_from_url(s3_key)
        
        s3_client.delete_object(
            Bucket=settings.AWS_S3_BUCKET_NAME,
            Key=key
        )
        
        logger.info(f"Deleted file from S3: {key}")
        return True
        
    except ClientError as e:
        logger.error(f"Error deleting from S3: {e}")
        return False

