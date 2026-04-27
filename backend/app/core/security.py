from __future__ import annotations

import hashlib
import secrets
from pathlib import Path


def generate_safe_filename(original: str) -> str:
    """Generate a safe, unique filename preserving extension."""
    path = Path(original)
    suffix = path.suffix.lower()
    random_part = secrets.token_hex(16)
    return f"{random_part}{suffix}"


def validate_file_extension(filename: str, allowed: set[str]) -> bool:
    suffix = Path(filename).suffix.lower()
    return suffix in allowed


def compute_file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".jpg", ".jpeg", ".png"}
ALLOWED_TEMPLATE_EXTENSIONS = {".docx", ".xlsx", ".xls"}
ALLOWED_MANUAL_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".jpg", ".jpeg", ".png"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
