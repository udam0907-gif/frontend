from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

from app.core.exceptions import ParseError
from app.core.logging import get_logger

logger = get_logger(__name__)

# ─── Korean section heading detection ────────────────────────────────────────
# Matches lines that look like section headings in RCMS / government manuals
_HEADING_RE = re.compile(
    r"""(?mx)                          # multiline, verbose
    ^[ \t]*                            # optional leading whitespace
    (?:
        \d{1,2}(?:\.\d{1,2}){0,3}\.?[ \t]+  # 1. / 1.1 / 1.1.1.
      | 제\s*\d+\s*[조절항목]           # 제1조 제2절 제3항 제4목
      | [가나다라마바사아자차카타파하]\.[ \t]+  # 가. 나.
      | [①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]      # circled numbers
      | [■□●○◆◇▶▷◉]\s+               # bullet symbols with space
      | [【\[]\s*\d+\s*[】\]]          # 【1】 [1]
    )
    [\w가-힣(（]                        # heading must continue with word char
    """,
)
_MIN_HEADING_LEN = 3
_MAX_HEADING_LEN = 80


class ParsedPage:
    def __init__(
        self,
        page_number: int,
        text: str,
        section_title: str | None = None,
    ) -> None:
        self.page_number = page_number
        self.text = text
        self.section_title = section_title


class ParserService:
    """
    Parses PDF and DOCX files into text chunks.
    Falls back to OCR for image-based PDFs via pytesseract.
    """

    def parse_file(self, file_path: str, filename: str) -> list[ParsedPage]:
        ext = Path(filename).suffix.lower()
        if ext == ".pdf":
            return self._parse_pdf(file_path)
        elif ext in (".docx", ".doc"):
            return self._parse_docx(file_path)
        elif ext in (".xlsx", ".xls"):
            return self._parse_xlsx(file_path)
        elif ext in (".jpg", ".jpeg", ".png"):
            return self._parse_image(file_path)
        else:
            raise ParseError(f"지원하지 않는 파일 형식: {ext}")

    def _parse_pdf(self, file_path: str) -> list[ParsedPage]:
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ParseError("PyMuPDF가 설치되지 않았습니다.")

        pages: list[ParsedPage] = []
        try:
            doc = fitz.open(file_path)
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text("text").strip()
                if not text:
                    # Try OCR for image-based pages
                    text = self._ocr_page(page)
                section_title = self._extract_section_title(text)
                pages.append(ParsedPage(
                    page_number=page_num,
                    text=text,
                    section_title=section_title,
                ))
            doc.close()
        except Exception as e:
            raise ParseError(f"PDF 파싱 실패: {e}") from e

        logger.info("pdf_parsed", file=file_path, pages=len(pages))
        return pages

    def _parse_docx(self, file_path: str) -> list[ParsedPage]:
        try:
            from docx import Document
        except ImportError:
            raise ParseError("python-docx가 설치되지 않았습니다.")

        try:
            doc = Document(file_path)
            full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            chunks = self._split_into_pages(full_text)
            pages = []
            for i, chunk in enumerate(chunks, start=1):
                section_title = self._extract_section_title(chunk)
                pages.append(ParsedPage(
                    page_number=i,
                    text=chunk,
                    section_title=section_title,
                ))
            return pages
        except Exception as e:
            raise ParseError(f"DOCX 파싱 실패: {e}") from e

    def _parse_xlsx(self, file_path: str) -> list[ParsedPage]:
        try:
            import openpyxl
        except ImportError:
            raise ParseError("openpyxl이 설치되지 않았습니다. pip install openpyxl")

        try:
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            pages: list[ParsedPage] = []
            for sheet_idx, sheet in enumerate(wb.worksheets, start=1):
                rows_text: list[str] = []
                for row in sheet.iter_rows(values_only=True):
                    cells = [str(cell).strip() if cell is not None else "" for cell in row]
                    if any(c for c in cells):
                        rows_text.append("\t".join(cells))
                if not rows_text:
                    continue
                text = f"[시트: {sheet.title}]\n" + "\n".join(rows_text)
                pages.append(ParsedPage(
                    page_number=sheet_idx,
                    text=text,
                    section_title=sheet.title,
                ))
            wb.close()
            if not pages:
                raise ParseError("XLSX 파일에서 읽을 수 있는 시트가 없습니다.")
            logger.info("xlsx_parsed", file=file_path, sheets=len(pages))
            return pages
        except ParseError:
            raise
        except Exception as e:
            raise ParseError(f"XLSX 파싱 실패: {e}") from e

    def _parse_image(self, file_path: str) -> list[ParsedPage]:
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            raise ParseError("pytesseract 또는 Pillow가 설치되지 않았습니다.")

        try:
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img, lang="kor+eng")
            return [ParsedPage(page_number=1, text=text.strip(), section_title=None)]
        except Exception as e:
            raise ParseError(f"이미지 OCR 실패: {e}") from e

    def _ocr_page(self, page: Any) -> str:
        """OCR a PyMuPDF page object."""
        try:
            import pytesseract
            from PIL import Image

            pix = page.get_pixmap(dpi=200)
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            return pytesseract.image_to_string(img, lang="kor+eng").strip()
        except Exception as e:
            logger.warning("ocr_failed", error=str(e))
            return ""

    def _split_into_pages(self, text: str, chars_per_page: int = 2000) -> list[str]:
        """Split long DOCX text into pseudo-pages."""
        words = text.split()
        chunks = []
        current: list[str] = []
        current_len = 0

        for word in words:
            current.append(word)
            current_len += len(word) + 1
            if current_len >= chars_per_page:
                chunks.append(" ".join(current))
                current = []
                current_len = 0

        if current:
            chunks.append(" ".join(current))

        return chunks

    def _extract_section_title(self, text: str) -> str | None:
        """Heuristically extract section title from first non-empty line."""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines:
            return None
        first_line = lines[0]
        # Title heuristic: short, may start with number
        if len(first_line) <= 100:
            return first_line
        return None

    def extract_sections(
        self,
        pages: list[ParsedPage],
        min_section_chars: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Detect logical sections within pages using Korean heading patterns.

        Returns a list of dicts:
            page_number, section_title, section_text, section_index

        A section spans from one heading to the next (or to the page boundary).
        Pages that contain no detectable headings are returned as one section
        with section_title = page.section_title (from first-line heuristic).
        """
        sections: list[dict[str, Any]] = []
        section_idx = 0

        for page in pages:
            text = page.text
            if not text.strip():
                continue

            lines = text.split("\n")
            heading_positions: list[int] = []  # line indices of headings

            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped:
                    continue
                if (
                    _HEADING_RE.match(line)
                    and _MIN_HEADING_LEN <= len(stripped) <= _MAX_HEADING_LEN
                ):
                    heading_positions.append(i)

            if not heading_positions:
                # No headings found — treat entire page as one section
                sections.append({
                    "page_number": page.page_number,
                    "section_title": page.section_title or f"p.{page.page_number}",
                    "section_text": text.strip(),
                    "section_index": section_idx,
                })
                section_idx += 1
                continue

            # Build sections between heading positions
            boundaries = heading_positions + [len(lines)]
            for k, start in enumerate(heading_positions):
                end = boundaries[k + 1]
                heading_line = lines[start].strip()
                body_lines = lines[start + 1: end]
                body = "\n".join(body_lines).strip()
                section_text = (heading_line + "\n" + body).strip()

                if len(section_text) < min_section_chars:
                    # Too short — merge with heading only
                    section_text = section_text or heading_line

                sections.append({
                    "page_number": page.page_number,
                    "section_title": heading_line[:_MAX_HEADING_LEN],
                    "section_text": section_text,
                    "section_index": section_idx,
                })
                section_idx += 1

        logger.info("sections_extracted", total_sections=len(sections))
        return sections

    def chunk_text(
        self,
        pages: list[ParsedPage],
        chunk_size: int = 800,
        chunk_overlap: int = 100,
    ) -> list[dict[str, Any]]:
        """Split pages into overlapping chunks for embedding."""
        chunks = []
        for page in pages:
            text = page.text
            if not text:
                continue

            # Split by characters with overlap
            start = 0
            chunk_idx = 0
            while start < len(text):
                end = min(start + chunk_size, len(text))
                chunk_text = text[start:end].strip()
                if chunk_text:
                    chunks.append({
                        "page_number": page.page_number,
                        "section_title": page.section_title,
                        "chunk_text": chunk_text,
                        "chunk_index": chunk_idx,
                    })
                    chunk_idx += 1
                if end >= len(text):
                    break
                start = end - chunk_overlap

        logger.info("text_chunked", total_chunks=len(chunks))
        return chunks
