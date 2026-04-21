# Skill: rcms_manual_rag_skill

> RCMS 매뉴얼 업로드 기반 질의응답 핵심 스킬. 근거 없는 답변은 절대 불가.

## Purpose

Answer RCMS-related questions using uploaded manuals only, with retrieval-backed evidence.

## When to Use

- RCMS manual upload and ingestion
- embedding generation
- vector retrieval
- RCMS Q&A response generation
- contextual help inside expense workflows

## Core Rules

1. Answers must be grounded in uploaded RCMS manuals — no model guesswork.
2. If relevant evidence is not found, explicitly respond: **"업로드된 RCMS 매뉴얼에서 해당 내용을 찾을 수 없습니다."**
3. Every answer must include supporting evidence:
   - page number
   - section title (if available)
   - excerpt or source chunk
4. Chunk manuals by page + section + procedural step where possible.
5. Shared RCMS manuals are global; tenant question/answer logs are tenant-scoped.

## Response Structure (required)

```json
{
  "short_answer": "간단한 한 줄 답변",
  "detailed_explanation": "절차 상세 설명",
  "evidence": [
    {
      "chunk_id": "uuid",
      "page_number": 12,
      "section_title": "3.2 외주비 집행 절차",
      "excerpt": "비교견적서는 300만 원 이상...",
      "confidence": 0.91
    }
  ],
  "found_in_manual": true
}
```

If `found_in_manual = false`, `short_answer` must be the "not found" message above.

## Ingestion Pipeline

1. Parse PDF/DOCX → extract text per page
2. OCR fallback for image-based pages
3. Chunk by page + section heading + procedural step
4. Generate embedding per chunk
5. Store in `rcms_chunks` with `manual_id`, `page_number`, `section_title`
6. Update `rcms_manuals.parse_status = completed`

## Retrieval and Answer Pipeline

1. Generate embedding for user question
2. Vector similarity search against `rcms_chunks`
3. Filter by `min_confidence` threshold (default: 0.75)
4. If no chunk meets threshold → return "not found"
5. Pass retrieved chunks as cached context to LLM
6. LLM generates answer grounded only in provided chunks
7. Save QA session with retrieved chunks and source trace

## Inputs

- uploaded manual files (PDF, DOCX, image)
- extracted text and chunk metadata
- embeddings
- user question
- optional: manual_ids filter for scoped search

## Outputs

- short_answer
- detailed_explanation
- evidence block (page, section, excerpt, confidence)
- retrieval trace
- QA session log

## Failure Conditions

- no supporting chunk found above confidence threshold → "not found" response
- ingestion failure → parse_status = failed, error stored
- OCR failure on required pages → log warning, continue with available text
- retrieval returns only low-confidence unrelated chunks → "not found"

## Forbidden Actions

- answering from model guesswork alone (without retrieved chunks)
- citing non-existent page numbers or sections
- mixing tenant question logs into global RCMS manual data
- generating an answer when retrieved evidence confidence is below threshold

## Developer Guidance

- Keep ingestion pipeline and answering pipeline fully separate.
- Require at least 1 chunk above `min_confidence` before answer generation.
- Use prompt caching for RCMS system prompt and retrieved chunks (Anthropic ephemeral cache).
- Log `model_version`, `prompt_version`, `retrieved_chunk_ids`, `confidence_scores` per QA session.
