"""OCR and scanned document ingestion engine for Kavach.

Credit: adapted from teammate Nehar's OCR engine (_incoming/ocr_engine.py).
"""
import io
import logging
import os
import re
import shutil
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from app.config import (
    OCR_DEFAULT_LANGUAGE,
    OCR_MAX_FILE_SIZE,
    OCR_MAX_PAGES,
    OCR_MIN_NATIVE_CHARS,
    OCR_MIN_NATIVE_WORDS,
    OCR_TIMEOUT_SECONDS,
    TESSERACT_WINDOWS_DEFAULT,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class OCRError(Exception):
    """Base exception for OCR and document ingestion errors."""
    pass


class UnsupportedDocumentError(OCRError, ValueError):
    """Raised when the document format or file signature is unsupported."""
    pass


class MalformedDocumentError(OCRError, ValueError):
    """Raised when a document is corrupted or cannot be parsed."""
    pass


class EncryptedDocumentError(OCRError, ValueError):
    """Raised when a PDF is password-protected or encrypted."""
    pass


class OversizedDocumentError(OCRError, ValueError):
    """Raised when file size or page count exceeds configured limits."""
    pass


class TesseractNotFoundError(OCRError):
    """Raised when Tesseract OCR binary is required but not installed or in PATH."""
    pass


class LanguageNotInstalledError(OCRError, ValueError):
    """Raised when requested Tesseract language data (.traineddata) is missing."""
    pass


class UnsupportedLanguageError(OCRError, ValueError):
    """Raised when an unrecognized language code is requested."""
    pass


# ---------------------------------------------------------------------------
# Magic Byte Signatures & Language Mappings
# ---------------------------------------------------------------------------
FILE_SIGNATURES: Dict[str, List[bytes]] = {
    "PDF": [b"%PDF-"],
    "PNG": [b"\x89PNG\r\n\x1a\n"],
    "JPEG": [b"\xff\xd8\xff"],
    "TIFF": [b"II*\x00", b"MM\x00*"],
}

SUPPORTED_OCR_LANGUAGES: Dict[str, str] = {
    "en": "eng",
    "eng": "eng",
    "english": "eng",
    "hi": "hin",
    "hin": "hin",
    "hindi": "hin",
    "kn": "kan",
    "kan": "kan",
    "kannada": "kan",
}

WINDOWS_TESSERACT_PATHS = [
    TESSERACT_WINDOWS_DEFAULT,
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
]


# ---------------------------------------------------------------------------
# Tesseract Path & Availability Resolution
# ---------------------------------------------------------------------------
def resolve_tesseract_cmd() -> Optional[str]:
    """Finds the Tesseract executable on the host system:

    1. TESSERACT_CMD env var
    2. PATH lookup via shutil.which('tesseract')
    3. C:\\Program Files\\Tesseract-OCR\\tesseract.exe
    4. Common Windows installation locations
    Configures pytesseract.pytesseract.tesseract_cmd if found.
    """
    # 1. TESSERACT_CMD env var
    env_cmd = os.environ.get("TESSERACT_CMD")
    if env_cmd and os.path.exists(env_cmd):
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = env_cmd
        except ImportError:
            pass
        return env_cmd

    # 2. PATH lookup
    in_path = shutil.which("tesseract")
    if in_path:
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = in_path
        except ImportError:
            pass
        return in_path

    # 3. C:\Program Files\Tesseract-OCR\tesseract.exe
    if os.path.exists(TESSERACT_WINDOWS_DEFAULT):
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_WINDOWS_DEFAULT
        except ImportError:
            pass
        return TESSERACT_WINDOWS_DEFAULT

    # 4. Common Windows installation locations
    if os.name == "nt":
        for win_path in WINDOWS_TESSERACT_PATHS:
            if os.path.exists(win_path):
                try:
                    import pytesseract
                    pytesseract.pytesseract.tesseract_cmd = win_path
                except ImportError:
                    pass
                return win_path

    return None


def ocr_available() -> Dict[str, Any]:
    """Return availability status and human-readable reason for OCR ingestion."""
    try:
        import pymupdf  # noqa: F401
    except ImportError as exc:
        return {"available": False, "reason": f"pymupdf library not installed: {exc}"}

    try:
        from PIL import Image  # noqa: F401
    except ImportError as exc:
        return {"available": False, "reason": f"Pillow library not installed: {exc}"}

    try:
        import pytesseract  # noqa: F401
    except ImportError as exc:
        return {"available": False, "reason": f"pytesseract library not installed: {exc}"}

    cmd = resolve_tesseract_cmd()
    if not cmd:
        return {
            "available": False,
            "reason": "Tesseract OCR binary not found. Set TESSERACT_CMD or install Tesseract OCR.",
        }

    return {"available": True, "reason": f"OCR engine ready (Tesseract at {cmd})"}


def get_available_tesseract_languages() -> List[str]:
    """Return list of installed Tesseract language codes, or empty list if unavailable."""
    cmd = resolve_tesseract_cmd()
    if not cmd:
        return []
    try:
        import pytesseract
        tessdata = os.environ.get("TESSDATA_PREFIX")
        config_arg = f'--tessdata-dir "{tessdata}"' if tessdata else ""
        return pytesseract.get_languages(config=config_arg)
    except Exception as exc:
        logger.debug("Failed to query Tesseract languages: %s", exc)
        return []


def normalize_and_validate_language(lang_hint: Optional[str]) -> str:
    """Normalize language code and verify presence in Tesseract tessdata."""
    raw = (lang_hint or OCR_DEFAULT_LANGUAGE).strip().lower()
    parts = [p.strip() for p in raw.split("+") if p.strip()]
    normalized_parts = []
    for p in parts:
        if p not in SUPPORTED_OCR_LANGUAGES:
            raise UnsupportedLanguageError(
                f"Unsupported OCR language '{p}'. Permitted languages: English ('eng'), "
                f"Hindi ('hin'), Kannada ('kan')."
            )
        normalized_parts.append(SUPPORTED_OCR_LANGUAGES[p])

    target_code = "+".join(normalized_parts)

    available = get_available_tesseract_languages()
    if available:
        for code in normalized_parts:
            if code not in available:
                raise LanguageNotInstalledError(
                    f"Tesseract language data for '{code}' is not installed in tessdata. "
                    f"Available languages: {available}."
                )
    return target_code


# ---------------------------------------------------------------------------
# Preprocessing & Language Scripts
# ---------------------------------------------------------------------------
def preprocess_image_for_ocr(image):
    """Preprocess image: grayscale, invert if dark-mode, autocontrast, upscale small images."""
    from PIL import ImageOps, ImageStat

    gray = image.convert("L")

    # Invert if dark-mode (mean brightness below 100)
    stat = ImageStat.Stat(gray)
    mean_brightness = stat.mean[0] if stat.mean else 128.0
    if mean_brightness < 100.0:
        gray = ImageOps.invert(gray)

    # Auto-contrast enhancement
    gray = ImageOps.autocontrast(gray)

    # Upscale small images (minimum width 1200 px)
    orig_w, orig_h = gray.size
    scale = 1.0
    if orig_w < 1200:
        scale = 1200.0 / orig_w
        new_w = 1200
        new_h = int(round(orig_h * scale))
        from PIL import Image
        gray = gray.resize((new_w, new_h), Image.Resampling.LANCZOS)

    return gray, scale


def is_non_latin(text: str) -> bool:
    """Check if text contains Indic / non-Latin scripts (e.g. Devanagari, Kannada)."""
    for ch in text:
        # Devanagari (\u0900-\u097f), Bengali, Gurmukhi, Gujarati, Oriya, Tamil, Telugu, Kannada (\u0c80-\u0cff), Malayalam
        if "\u0900" <= ch <= "\u0d7f":
            return True
    return False


def is_native_text_sufficient(
    page_text: str,
    min_chars: int = OCR_MIN_NATIVE_CHARS,
    min_words: int = OCR_MIN_NATIVE_WORDS,
) -> Tuple[bool, str]:
    """Determine whether native PDF text extraction is sufficient or if OCR is required."""
    cleaned = (page_text or "").strip()
    if not cleaned:
        return False, "Page contains 0 characters of native text."

    alpha_chars = sum(1 for c in cleaned if c.isalnum())
    words = [w for w in re.split(r"\s+", cleaned) if len(w) >= 2 and any(ch.isalnum() for ch in w)]

    if alpha_chars >= min_chars and len(words) >= min_words:
        return True, f"Native text sufficient ({alpha_chars} chars, {len(words)} words >= threshold {min_chars})."

    return (
        False,
        f"Native text insufficient ({alpha_chars} chars < {min_chars} or {len(words)} words < {min_words}). Attempting OCR.",
    )


# ---------------------------------------------------------------------------
# Pluggable OCR Runner (for mock injection in tests)
# ---------------------------------------------------------------------------
_CUSTOM_OCR_RUNNER: Optional[Callable[[Any, str], Any]] = None


def set_custom_ocr_runner(runner: Optional[Callable[[Any, str], Any]]) -> None:
    """Inject a custom OCR runner for deterministic testing without Tesseract."""
    global _CUSTOM_OCR_RUNNER
    _CUSTOM_OCR_RUNNER = runner


def default_tesseract_ocr_runner(image, lang: str = "eng") -> Any:
    """Execute Tesseract OCR on a PIL Image and return structured data."""
    cmd = resolve_tesseract_cmd()
    if not cmd:
        raise TesseractNotFoundError(
            "Tesseract OCR executable is not installed or configured on the system. "
            "Please install Tesseract OCR and set TESSERACT_CMD or add it to your PATH."
        )

    import pytesseract
    tessdata = os.environ.get("TESSDATA_PREFIX")
    config_arg = f'--tessdata-dir "{tessdata}"' if tessdata else ""

    return pytesseract.image_to_data(
        image,
        lang=lang,
        config=config_arg,
        output_type=pytesseract.Output.DICT,
        timeout=OCR_TIMEOUT_SECONDS,
    )


def run_ocr_on_image(image, lang: str = "eng") -> Any:
    """Dispatch OCR to configured or mocked runner."""
    if _CUSTOM_OCR_RUNNER is not None:
        return _CUSTOM_OCR_RUNNER(image, lang)
    return default_tesseract_ocr_runner(image, lang)


def _extract_text_from_ocr_data(ocr_data: Union[dict, str]) -> str:
    """Extract newline-delimited text from OCR dictionary or string."""
    if isinstance(ocr_data, str):
        return ocr_data
    if isinstance(ocr_data, dict):
        texts = ocr_data.get("text", [])
        line_nums = ocr_data.get("line_num", [])
        block_nums = ocr_data.get("block_num", [])

        if line_nums and block_nums and len(line_nums) == len(texts):
            lines: Dict[Tuple[int, int], List[str]] = {}
            for idx, w in enumerate(texts):
                w_str = str(w).strip()
                if w_str:
                    lines.setdefault((block_nums[idx], line_nums[idx]), []).append(w_str)
            return "\n".join(" ".join(words) for _, words in sorted(lines.items()))
        else:
            return " ".join(str(w) for w in texts if str(w).strip())
    return ""


# ---------------------------------------------------------------------------
# Format Sniffing & Validation
# ---------------------------------------------------------------------------
def detect_document_format_from_bytes(header_bytes: bytes) -> Optional[str]:
    """Matches leading bytes against magic byte signatures for PDF, PNG, JPEG, TIFF."""
    for fmt, sigs in FILE_SIGNATURES.items():
        for sig in sigs:
            if header_bytes.startswith(sig):
                return fmt
    return None


def validate_document_file(file_path: str, max_size_bytes: int = OCR_MAX_FILE_SIZE) -> str:
    """Validate file existence, size, and magic byte signatures."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Document file not found: {file_path}")

    file_size = os.path.getsize(file_path)
    if file_size == 0:
        raise MalformedDocumentError(f"Document file is empty (0 bytes): {os.path.basename(file_path)}")
    if file_size > max_size_bytes:
        raise OversizedDocumentError(
            f"Document file size ({file_size} bytes) exceeds maximum limit of {max_size_bytes} bytes."
        )

    with open(file_path, "rb") as f:
        header = f.read(16)

    detected = detect_document_format_from_bytes(header)
    if not detected:
        ext = os.path.splitext(file_path)[1].lower()
        raise UnsupportedDocumentError(
            f"Unsupported or corrupted file '{os.path.basename(file_path)}' (extension: {ext}). "
            f"File signature did not match PDF, PNG, JPEG, or TIFF."
        )
    return detected


# ---------------------------------------------------------------------------
# Document Ingestion Generator for Kavach Pipeline
# ---------------------------------------------------------------------------
def read_ocr_document(file_path: str, lang: Optional[str] = None):
    """Yield (location, text, metadata) units from PDF or image document.

    location: "page N"
    metadata: {"method": "native" | "ocr", "page": N, optional "low_confidence": True}
    """
    ocr_lang = normalize_and_validate_language(lang) if lang else OCR_DEFAULT_LANGUAGE
    doc_format = validate_document_file(file_path)
    filename = os.path.basename(file_path)

    if doc_format == "PDF":
        import pymupdf
        from PIL import Image

        try:
            doc = pymupdf.open(file_path)
        except Exception as exc:
            raise MalformedDocumentError(f"Malformed or corrupted PDF file '{filename}': {exc}")

        try:
            if doc.is_encrypted:
                raise EncryptedDocumentError(
                    f"Encrypted or password-protected PDF '{filename}' cannot be processed."
                )

            total_pages = doc.page_count
            if total_pages == 0:
                raise MalformedDocumentError(f"PDF file '{filename}' contains 0 pages.")
            if total_pages > OCR_MAX_PAGES:
                raise OversizedDocumentError(
                    f"PDF page count ({total_pages}) exceeds configured limit of {OCR_MAX_PAGES} pages."
                )

            has_content = False
            for p_idx in range(total_pages):
                page_num = p_idx + 1
                page = doc[p_idx]
                location = f"page {page_num}"

                # 1. Check native text sufficiency
                native_text = page.get_text("text").strip()
                sufficient, _ = is_native_text_sufficient(native_text)

                if sufficient:
                    has_content = True
                    yield location, native_text, {"method": "native", "page": page_num}
                else:
                    # 2. Render page image and run OCR
                    pix = page.get_pixmap(dpi=200)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    preprocessed, _ = preprocess_image_for_ocr(img)
                    ocr_data = run_ocr_on_image(preprocessed, lang=ocr_lang)
                    ocr_text = _extract_text_from_ocr_data(ocr_data)
                    del pix

                    if ocr_text.strip():
                        has_content = True
                        is_low = is_non_latin(ocr_text) or (ocr_lang != "eng")
                        meta: Dict[str, Any] = {"method": "ocr", "page": page_num}
                        if is_low:
                            meta["low_confidence"] = True
                        yield location, ocr_text.strip(), meta

            if not has_content:
                raise ValueError(f"Document '{filename}' contains no readable text.")
        finally:
            doc.close()

    else:
        # PNG, JPEG, TIFF images
        from PIL import Image
        try:
            img = Image.open(file_path)
        except Exception as exc:
            raise MalformedDocumentError(f"Malformed or corrupted image '{filename}': {exc}")

        location = "page 1"
        preprocessed, _ = preprocess_image_for_ocr(img)
        ocr_data = run_ocr_on_image(preprocessed, lang=ocr_lang)
        ocr_text = _extract_text_from_ocr_data(ocr_data)

        if not ocr_text.strip():
            raise ValueError(f"Image '{filename}' contains no readable text.")

        is_low = is_non_latin(ocr_text) or (ocr_lang != "eng")
        meta = {"method": "ocr", "page": 1}
        if is_low:
            meta["low_confidence"] = True
        yield location, ocr_text.strip(), meta
