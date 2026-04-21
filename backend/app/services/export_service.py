from __future__ import annotations

import io
import json
import os
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.exceptions import StorageError
from app.core.logging import get_logger

logger = get_logger(__name__)


class ExportService:
    """
    Packages generated documents into a zip with manifest.json,
    validation report, and generation trace for auditability.
    """

    def __init__(self) -> None:
        self._exports_path = Path(settings.storage_exports_path)
        self._exports_path.mkdir(parents=True, exist_ok=True)

    def create_export_package(
        self,
        expense_item_id: str,
        expense_title: str,
        generated_documents: list[dict[str, Any]],
        validation_result: dict[str, Any],
        expense_documents: list[dict[str, Any]],
    ) -> str:
        """
        Create a zip package containing:
        - All generated DOCX files
        - manifest.json
        - validation_report.json
        - generation_trace.json
        Returns path to the zip file.
        """
        package_id = uuid.uuid4().hex[:12]
        zip_filename = f"expense_{expense_item_id[:8]}_{package_id}.zip"
        zip_path = str(self._exports_path / zip_filename)

        manifest = {
            "package_id": package_id,
            "expense_item_id": expense_item_id,
            "expense_title": expense_title,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "generated_documents": [],
            "source_documents": [],
            "validation_passed": validation_result.get("is_valid", False),
        }

        generation_traces = []

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # Add generated documents
                for doc in generated_documents:
                    output_path = doc.get("output_path", "")
                    if output_path and Path(output_path).exists():
                        arcname = f"generated/{Path(output_path).name}"
                        zf.write(output_path, arcname)
                        manifest["generated_documents"].append({
                            "filename": Path(output_path).name,
                            "path_in_zip": arcname,
                            "template_id": str(doc.get("template_id", "")),
                            "is_valid": doc.get("is_valid", False),
                        })
                        generation_traces.append(doc.get("generation_trace", {}))

                # Add source documents (references only — large files skipped)
                for src_doc in expense_documents:
                    file_path = src_doc.get("file_path", "")
                    if file_path and Path(file_path).exists():
                        file_size = Path(file_path).stat().st_size
                        if file_size <= 10 * 1024 * 1024:  # Only include files < 10MB
                            arcname = f"source/{Path(file_path).name}"
                            zf.write(file_path, arcname)
                            manifest["source_documents"].append({
                                "document_type": src_doc.get("document_type", ""),
                                "filename": src_doc.get("filename", ""),
                                "path_in_zip": arcname,
                            })
                        else:
                            manifest["source_documents"].append({
                                "document_type": src_doc.get("document_type", ""),
                                "filename": src_doc.get("filename", ""),
                                "note": "파일 크기 초과로 패키지에서 제외됨",
                            })

                # Write manifest.json
                zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

                # Write validation_report.json
                zf.writestr(
                    "validation_report.json",
                    json.dumps(validation_result, ensure_ascii=False, indent=2),
                )

                # Write generation_trace.json
                zf.writestr(
                    "generation_trace.json",
                    json.dumps(generation_traces, ensure_ascii=False, indent=2),
                )

        except OSError as e:
            raise StorageError(f"내보내기 패키지 생성 실패: {e}") from e

        logger.info(
            "export_package_created",
            expense_item_id=expense_item_id,
            zip_path=zip_path,
            documents=len(generated_documents),
        )

        return zip_path
