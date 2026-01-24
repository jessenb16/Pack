"""Document processing pipeline for FastAPI."""
import io
from PIL import Image
from pypdf import PdfReader
from pdf2image import convert_from_bytes
from openai import OpenAI
from app.core.config import settings
import logging
from typing import Tuple

# SYSTEM REQUIREMENT: This module requires 'poppler-utils' to be installed.
# On Mac: brew install poppler
# On Linux/Render: sudo apt-get install poppler-utils

logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def generate_thumbnail(file_data: bytes, filename: str) -> Tuple[bytes, str]:
    """Generate thumbnail for image or PDF."""
    try:
        ext = filename.lower().split('.')[-1]
        
        if ext == 'pdf':
            images = convert_from_bytes(file_data, first_page=1, last_page=1, dpi=150)
            if not images:
                raise ValueError("Could not extract image from PDF")
            img = images[0]
        else:
            img = Image.open(io.BytesIO(file_data))
        
        # Resize to 300px width
        if img.width > 300:
            ratio = 300 / img.width
            new_height = int(img.height * ratio)
            img = img.resize((300, new_height), Image.Resampling.LANCZOS)
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = rgb_img
        
        # Save to bytes
        thumbnail_buffer = io.BytesIO()
        img.save(thumbnail_buffer, format='JPEG', quality=85)
        thumbnail_data = thumbnail_buffer.getvalue()
        thumbnail_filename = f"thumb_{filename.rsplit('.', 1)[0]}.jpg"
        
        return thumbnail_data, thumbnail_filename
        
    except Exception as e:
        logger.error(f"Error generating thumbnail: {e}")
        raise


def extract_text_from_pdf(file_data: bytes) -> str:
    """Extract text from PDF using pypdf."""
    try:
        reader = PdfReader(io.BytesIO(file_data))
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return ""


def extract_text_from_image(file_data_base64: str, filename: str) -> str:
    """Extract text from image using GPT-4o Vision."""
    try:
        image_ext = filename.split('.')[-1].lower() if '.' in filename else 'jpeg'
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please transcribe any handwritten or typed text in this image. If there is no text, describe what you see in the image. Be detailed and include any meaningful content."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{image_ext};base64,{file_data_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error extracting text from image: {e}")
        return ""


def create_embedding(text: str) -> list:
    """
    Create vector embedding using OpenAI.
    
    Returns empty list if text is empty/None to avoid creating meaningless
    "garbage vectors" that sit in the center of embedding space.
    """
    try:
        # Skip embedding for empty text - better to have no embedding than a meaningless one
        if not text or not text.strip():
            logger.debug("Skipping embedding creation for empty text")
            return []
        
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Error creating embedding: {e}")
        return []


def process_document(file_data: bytes, filename: str) -> dict:
    """Process document: generate thumbnail, extract content, create embedding."""
    try:
        ext = filename.lower().split('.')[-1]
        
        # Generate thumbnail
        thumbnail_data, thumbnail_filename = generate_thumbnail(file_data, filename)
        
        # Extract text content
        text_content = None
        if ext == 'pdf':
            # Try PDF extraction first
            text_content = extract_text_from_pdf(file_data)
            
            # If no text (scanned PDF), use GPT-4o Vision
            if not text_content or len(text_content.strip()) < 10:
                images = convert_from_bytes(file_data, first_page=1, last_page=1, dpi=150)
                if images:
                    img_buffer = io.BytesIO()
                    images[0].save(img_buffer, format='JPEG')
                    img_buffer.seek(0)
                    # Convert to base64 for API
                    import base64
                    img_base64 = base64.b64encode(img_buffer.read()).decode('utf-8')
                    text_content = extract_text_from_image(img_base64, filename)
        elif ext in {'png', 'jpg', 'jpeg', 'gif', 'jfif', 'webp'}:
            # Convert image to base64 for API
            import base64
            img_base64 = base64.b64encode(file_data).decode('utf-8')
            # text_content = extract_text_from_image(img_base64, filename)
            text_content = ""
        
        # Generate embedding
        # embedding = create_embedding(text_content or "")
        embedding = []
        
        return {
            'thumbnail_data': thumbnail_data,
            'thumbnail_filename': thumbnail_filename,
            'text_content': text_content,
            'embedding': embedding
        }
        
    except Exception as e:
        logger.error(f"Error processing document {filename}: {e}")
        raise

