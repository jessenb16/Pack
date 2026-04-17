"""Document processing pipeline for FastAPI."""
import io
import re
import unicodedata
from pathlib import Path

from fpdf import FPDF
from PIL import Image, ImageOps
from pypdf import PdfReader
from pdf2image import convert_from_bytes
from openai import OpenAI
from app.core.config import settings
import logging
from typing import Tuple, Optional

# SYSTEM REQUIREMENT: This module requires 'poppler-utils' to be installed.
# On Mac: brew install poppler
# On Linux/Render: sudo apt-get install poppler-utils

logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def _sanitize_filename(name: str, max_length: int = 80) -> str:
    """Sanitize user-provided filename: remove path chars, limit length, ensure .pdf."""
    if not name or not name.strip():
        return ""
    # Remove path components and invalid chars
    invalid = '<>:"/\\|?*'
    clean = "".join(c for c in name.strip() if c not in invalid)
    # Limit length (leave room for .pdf)
    if len(clean) > max_length - 4:
        clean = clean[: max_length - 4]
    # Ensure .pdf extension
    if not clean.lower().endswith(".pdf"):
        clean = clean + ".pdf" if clean else "document.pdf"
    return clean or "document.pdf"


# Unicode → ASCII mapping for PDF (Helvetica supports Latin-1 only)
_UNICODE_TO_ASCII = str.maketrans({
    "\u2018": "'",   # left single quote
    "\u2019": "'",   # right single quote (smart apostrophe)
    "\u201c": '"',   # left double quote
    "\u201d": '"',   # right double quote
    "\u2013": "-",   # en dash
    "\u2014": "-",   # em dash
    "\u2026": "...", # ellipsis
})

_UNICODE_FONT_FAMILY = "DejaVuSans"
_UNICODE_FONT_PATH = (
    Path(__file__).resolve().parents[1] / "assets" / "fonts" / "DejaVuSans.ttf"
)
_EMOJI_FONT_FAMILY = "NotoColorEmoji"
_EMOJI_FONT_PATH = (
    Path(__file__).resolve().parents[1] / "assets" / "fonts" / "NotoColorEmoji.ttf"
)


def _is_emoji_base_char(ch: str) -> bool:
    """Heuristic: True for most emoji codepoints."""
    o = ord(ch)
    return (
        0x1F000 <= o <= 0x1FAFF  # Misc symbols & pictographs, emoticons, transport, supplemental, etc.
        or 0x2600 <= o <= 0x27BF  # Misc symbols, dingbats (includes ✨)
    )


def _is_emoji_joiner_or_modifier(ch: str) -> bool:
    o = ord(ch)
    return (
        o == 0x200D  # ZWJ
        or 0xFE00 <= o <= 0xFE0F  # variation selectors
        or 0x1F3FB <= o <= 0x1F3FF  # skin tone modifiers
    )


def _split_text_runs_for_fonts(text: str) -> list[tuple[str, str]]:
    """Split text into (family, run) where family is unicode or emoji font.

    This groups emoji sequences (incl. ZWJ/VS/modifiers) to improve rendering.
    """
    runs: list[tuple[str, str]] = []
    buf: list[str] = []
    current_family: str | None = None

    def flush():
        nonlocal buf, current_family
        if buf:
            runs.append((current_family or _UNICODE_FONT_FAMILY, "".join(buf)))
            buf = []

    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if _is_emoji_base_char(ch):
            # Start an emoji sequence cluster: base + (joiners/modifiers + base)*
            cluster = [ch]
            i += 1
            while i < n:
                nxt = text[i]
                if _is_emoji_joiner_or_modifier(nxt):
                    cluster.append(nxt)
                    i += 1
                    continue
                # Some emoji sequences have another emoji base after a joiner
                if _is_emoji_base_char(nxt):
                    cluster.append(nxt)
                    i += 1
                    continue
                break

            flush()
            current_family = _EMOJI_FONT_FAMILY
            buf.append("".join(cluster))
            flush()
            current_family = None
            continue

        # Non-emoji char
        if current_family != _UNICODE_FONT_FAMILY:
            flush()
            current_family = _UNICODE_FONT_FAMILY
        buf.append(ch)
        i += 1

    flush()
    return runs


def _normalize_text_for_pdf(text: str) -> str:
    """Replace Unicode punctuation with ASCII so Helvetica can render it."""
    result = text.translate(_UNICODE_TO_ASCII)
    # Fallback: replace any remaining non-Latin-1 chars with closest ASCII or ?
    return "".join(
        c if ord(c) < 256 else unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode() or "?"
        for c in result
    )


def text_to_pdf(text: str, filename_base: str = "text_upload") -> Tuple[bytes, str]:
    """Generate a PDF from plain text using fpdf2."""
    if not text or not text.strip():
        raise ValueError("Text cannot be empty")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    # Preserve newlines from pasted input; only trim outer whitespace.
    text_value = text.strip("\n").strip()

    # Prefer bundled Unicode/emoji fonts so we preserve characters (instead of replacing with '?').
    # If fonts can't be loaded for any reason, fall back to core fonts + normalization.
    using_fallback = False
    try:
        if not _UNICODE_FONT_PATH.exists():
            raise FileNotFoundError(str(_UNICODE_FONT_PATH))
        if not _EMOJI_FONT_PATH.exists():
            raise FileNotFoundError(str(_EMOJI_FONT_PATH))
        pdf.add_font(
            family=_UNICODE_FONT_FAMILY,
            style="",
            fname=str(_UNICODE_FONT_PATH),
            uni=True,
        )
        pdf.add_font(
            family=_EMOJI_FONT_FAMILY,
            style="",
            fname=str(_EMOJI_FONT_PATH),
            uni=True,
        )
        # We'll switch fonts dynamically per run below.
        rendered_text = text_value
    except Exception as e:
        logger.warning(
            "Unicode/emoji font unavailable (%s, %s). Falling back to Helvetica with lossy normalization: %s",
            _UNICODE_FONT_PATH,
            _EMOJI_FONT_PATH,
            e,
            exc_info=True,
        )
        pdf.set_font("Helvetica", size=12)
        rendered_text = _normalize_text_for_pdf(text_value)
        using_fallback = True

    # If we're using Helvetica fallback, multi_cell is fine (single font).
    # If we're using Unicode+Emoji fonts, we do simple wrapping while switching fonts mid-line.
    if using_fallback:
        pdf.multi_cell(w=0, h=6, txt=rendered_text)
    else:
        font_size = 12
        line_h = 6
        # Write with basic word-wrapping, preserving explicit newlines.
        for para_idx, paragraph in enumerate(rendered_text.split("\n")):
            if para_idx > 0:
                pdf.ln(line_h)
            if not paragraph:
                continue

            # Split into whitespace / non-whitespace tokens to preserve spacing.
            parts = re.split(r"(\s+)", paragraph)
            for part in parts:
                if part == "":
                    continue
                if part.isspace():
                    # Collapse consecutive whitespace to a single space for layout stability.
                    token = " "
                    family_runs = [(_UNICODE_FONT_FAMILY, token)]
                else:
                    family_runs = _split_text_runs_for_fonts(part)

                # Measure token width (sum of runs with their respective fonts).
                token_w = 0.0
                for fam, run in family_runs:
                    pdf.set_font(fam, size=font_size)
                    token_w += pdf.get_string_width(run)

                max_x = pdf.w - pdf.r_margin
                # If token doesn't fit on this line (and it's not just a leading space), wrap.
                if pdf.get_x() + token_w > max_x and not (len(family_runs) == 1 and family_runs[0][1] == " "):
                    pdf.ln(line_h)

                # Avoid leading spaces after wrap.
                if (pdf.get_x() <= pdf.l_margin + 0.01) and (len(family_runs) == 1 and family_runs[0][1] == " "):
                    continue

                for fam, run in family_runs:
                    pdf.set_font(fam, size=font_size)
                    pdf.write(line_h, run)

    # fpdf2 returns a latin-1 string when dest="S"; convert to bytes explicitly.
    out = pdf.output(dest="S")
    pdf_bytes = out.encode("latin-1") if isinstance(out, str) else bytes(out)
    filename = f"{filename_base}.pdf" if not filename_base.lower().endswith(".pdf") else filename_base
    return pdf_bytes, filename


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
            # Many phone photos rely on EXIF Orientation for correct display.
            # Transpose here so the generated thumbnail pixels are upright.
            img = ImageOps.exif_transpose(img)
        
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
        # Normalize whitespace - pypdf often produces "word \n\n word \n\n word" for complex layouts
        text = re.sub(r"\s+", " ", text.strip())
        return text
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


def process_document(file_data: bytes, filename: str, caption: str = "") -> dict:
    """Generate thumbnail and extracted text (OCR/vision). No caption merge; no embedding.

    Callers build ai_context from metadata prefix + metadata.caption + extracted_text, then embed.
    """
    try:
        _ = caption  # unused; kept for backward-compatible call sites
        ext = filename.lower().split('.')[-1]
        
        thumbnail_data, thumbnail_filename = generate_thumbnail(file_data, filename)
        
        extracted_text: Optional[str] = None
        if ext == 'pdf':
            extracted_text = extract_text_from_pdf(file_data)
            
            if not extracted_text or len(extracted_text.strip()) < 10:
                images = convert_from_bytes(file_data, first_page=1, last_page=1, dpi=150)
                if images:
                    img_buffer = io.BytesIO()
                    images[0].save(img_buffer, format='JPEG')
                    img_buffer.seek(0)
                    import base64
                    img_base64 = base64.b64encode(img_buffer.read()).decode('utf-8')
                    extracted_text = extract_text_from_image(img_base64, filename)
        elif ext in {'png', 'jpg', 'jpeg', 'gif', 'jfif', 'webp'}:
            import base64
            img_base64 = base64.b64encode(file_data).decode('utf-8')
            extracted_text = extract_text_from_image(img_base64, filename)
        
        ext_clean = (extracted_text or "").strip()
        
        return {
            'thumbnail_data': thumbnail_data,
            'thumbnail_filename': thumbnail_filename,
            'extracted_text': ext_clean,
        }
        
    except Exception as e:
        logger.error(f"Error processing document {filename}: {e}")
        raise

