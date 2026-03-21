import asyncio
import io
import os
import tempfile
from typing import Optional


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _extract_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ValueError("PDF support requires pypdf: pip install pypdf")

    reader = PdfReader(io.BytesIO(content))
    pages = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            pages.append(t)

    if not pages:
        raise ValueError("No extractable text found in PDF. The file may be scanned or image-based.")

    return "\n\n".join(pages)


def _extract_image(content: bytes) -> str:
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        raise ValueError("Image OCR support requires Pillow and pytesseract: pip install Pillow pytesseract")

    try:
        image = Image.open(io.BytesIO(content))
        text = pytesseract.image_to_string(image)
    except Exception as e:
        raise ValueError(f"OCR failed: {e}. Ensure tesseract-ocr is installed on the system.")

    if not text.strip():
        raise ValueError("No text could be extracted from the image via OCR.")

    return text


def _extract_audio(content: bytes, filename: str) -> str:
    try:
        import whisper
    except ImportError:
        raise ValueError("Audio transcription requires openai-whisper: pip install openai-whisper")

    suffix = f".{_ext(filename)}" if "." in filename else ".audio"
    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        model = whisper.load_model("base")
        result = model.transcribe(tmp_path)
        text = result.get("text", "").strip()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    if not text:
        raise ValueError("No speech could be transcribed from the audio file.")

    return text


_AUDIO_EXTS = {"mp3", "wav", "ogg", "m4a", "flac", "webm", "aac", "opus"}
_IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "webp", "tiff", "tif", "bmp"}


def doc_type(filename: str, content_type: str) -> str:
    ext = _ext(filename)
    ct = content_type.lower()
    if ct == "application/pdf" or ext == "pdf":
        return "pdf"
    if ct.startswith("image/") or ext in _IMAGE_EXTS:
        return "image"
    if ct.startswith("audio/") or ct.startswith("video/") or ext in _AUDIO_EXTS:
        return "audio"
    return "text"


async def extract_text(content: bytes, filename: str, content_type: str) -> str:
    ext = _ext(filename)
    ct = content_type.lower()

    if ct == "application/pdf" or ext == "pdf":
        return await asyncio.get_event_loop().run_in_executor(None, _extract_pdf, content)

    if ct.startswith("image/") or ext in _IMAGE_EXTS:
        return await asyncio.get_event_loop().run_in_executor(None, _extract_image, content)

    if ct.startswith("audio/") or ct.startswith("video/") or ext in _AUDIO_EXTS:
        return await asyncio.get_event_loop().run_in_executor(None, _extract_audio, content, filename)

    return content.decode("utf-8", errors="replace")
