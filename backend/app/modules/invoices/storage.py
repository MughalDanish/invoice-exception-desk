import hashlib
import io
import re
import warnings
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from app.core.errors import AppError

ALLOWED = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


@dataclass(frozen=True)
class ValidatedFile:
    filename: str
    mime_type: str
    sha256: str
    content: bytes


def validate_file(filename: str, content_type: str | None, content: bytes, limit: int):
    if not content:
        raise AppError(400, "EMPTY_FILE", "The invoice file is empty")
    if len(content) > limit:
        raise AppError(413, "FILE_TOO_LARGE", f"Invoice exceeds {limit} bytes")
    # Only the basename is retained for display; paths are generated independently.
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    extension = Path(basename).suffix.lower()
    expected_mime = ALLOWED.get(extension)
    if expected_mime is None:
        raise AppError(415, "UNSUPPORTED_FILE_TYPE", "Upload a PDF, JPG, or PNG invoice")
    declared = (content_type or "").split(";", 1)[0].lower()
    if declared != expected_mime:
        raise AppError(415, "MIME_MISMATCH", "File extension and declared MIME type must match")
    signatures = {
        "application/pdf": content.startswith(b"%PDF-"),
        "image/jpeg": content.startswith(b"\xff\xd8\xff"),
        "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
    }
    if not signatures[expected_mime]:
        raise AppError(415, "INVALID_SIGNATURE", "File content does not match its declared format")
    try:
        if extension == ".pdf":
            pdf = PdfReader(io.BytesIO(content), strict=True)
            if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 100:
                raise ValueError("Encrypted or unsupported page count")
            # Parse page content too: a PDF header alone is not enough.
            for page in pdf.pages:
                page.get_contents()
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(content)) as image:
                    if image.format != ("PNG" if extension == ".png" else "JPEG"):
                        raise ValueError("Wrong image format")
                    if image.width * image.height > 25_000_000:
                        raise ValueError("Image dimensions too large")
                    image.verify()
                with Image.open(io.BytesIO(content)) as image:
                    image.load()
    except Exception as exc:
        # Parser errors deliberately do not disclose document contents.
        raise AppError(400, "MALFORMED_FILE", "File is corrupt, encrypted, or unsupported") from exc
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(basename).stem)[:180] or "invoice"
    return ValidatedFile(
        filename=safe_name + extension,
        mime_type=expected_mime,
        sha256=hashlib.sha256(content).hexdigest(),
        content=content,
    )


def resolve_private_file(storage_dir: Path, relative_path: str) -> Path:
    root = storage_dir.resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise AppError(404, "FILE_NOT_FOUND", "Original file is unavailable")
    return path
