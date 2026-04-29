from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter(tags=["백업"])

BACKUP_DIR = Path(__file__).resolve().parents[4] / "backup"

TYPE_LABELS: dict[str, str] = {
    ".sql": "DB 백업",
    ".tar.gz": "파일 백업",
    ".gz": "파일 백업",
    ".md": "복원 가이드",
    ".zip": "ZIP 백업",
}


class BackupFile(BaseModel):
    name: str
    size_bytes: int
    size_label: str
    type_label: str
    suffix: str
    created_at: str


def _size_label(size: int) -> str:
    if size >= 1024 ** 3:
        return f"{size / 1024 ** 3:.1f} GB"
    if size >= 1024 ** 2:
        return f"{size / 1024 ** 2:.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def _type_label(name: str) -> tuple[str, str]:
    lower = name.lower()
    if lower.endswith(".tar.gz"):
        return ".tar.gz", TYPE_LABELS[".tar.gz"]
    p = Path(name)
    suffix = p.suffix.lower()
    return suffix, TYPE_LABELS.get(suffix, "기타")


@router.get("/files", response_model=list[BackupFile])
async def list_backup_files() -> list[BackupFile]:
    if not BACKUP_DIR.exists():
        return []

    result: list[BackupFile] = []
    for entry in sorted(BACKUP_DIR.iterdir()):
        if not entry.is_file():
            continue
        stat = entry.stat()
        suffix, label = _type_label(entry.name)
        import datetime
        created = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        result.append(BackupFile(
            name=entry.name,
            size_bytes=stat.st_size,
            size_label=_size_label(stat.st_size),
            type_label=label,
            suffix=suffix,
            created_at=created,
        ))
    return result


@router.get("/restore-guide")
async def get_restore_guide() -> dict:
    guide_path = BACKUP_DIR / "restore.md"
    if not guide_path.exists():
        return {"content": ""}
    return {"content": guide_path.read_text(encoding="utf-8")}


@router.get("/download/{filename}")
async def download_backup_file(filename: str) -> FileResponse:
    safe = Path(filename).name
    file_path = BACKUP_DIR / safe
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(path=str(file_path), filename=safe)
