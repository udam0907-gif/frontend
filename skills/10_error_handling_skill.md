# Skill: error_handling_skill

> 실무에서 엄청 중요하다. 에러가 나도 사람 말로 알아듣게 해야 한다.

## Purpose

Provide clear, actionable, non-destructive failure handling across template processing, generation, validation, and RAG.

## When to Use

- template upload errors
- field mapping errors
- document generation errors
- validation errors
- RCMS manual ingestion errors
- retrieval failures
- LLM service errors

## Core Rules

1. **Fail clearly, not silently.** Every failure must be logged and surfaced.
2. Distinguish user-fixable errors from system errors.
3. Preserve partial state safely when possible — do not rollback user data on non-critical failures.
4. Never replace a blocked output with a guessed/approximated output.
5. Return actionable next steps where possible.

## Error Type Classification

| Type | Code | HTTP | Who Fixes It |
|------|------|------|--------------|
| 사용자 입력 오류 | `user_input_error` | 400 | 사용자 |
| 서식 오류 | `template_error` | 422 | 사용자 (서식 재업로드) |
| 서식 구조 위반 | `template_structure_violation` | 422 | 사용자 (서식 확인) |
| 유효성 검사 오류 | `validation_error` | 422 | 사용자 (서류 추가) |
| 권한 오류 | `authorization_error` | 403 | 관리자 |
| RAG 근거 없음 | `rag_no_evidence` | 200 | 매뉴얼 업로드 필요 |
| LLM 서비스 오류 | `llm_service_error` | 502 | 시스템 (재시도) |
| 시스템 오류 | `system_error` | 500 | 개발팀 |

## Required Error Response Fields

```json
{
  "error": "template_error",
  "message": "플레이스홀더 {{VENDOR_NAME}}에 매핑된 값이 없습니다.",
  "details": {
    "unresolved_placeholders": ["VENDOR_NAME", "CONTRACT_DATE"],
    "template_id": "uuid",
    "document_type": "service_contract"
  }
}
```

## Outputs

- structured `error` code (snake_case)
- human-readable Korean `message`
- actionable next step where possible
- related object context (template_id, expense_item_id, etc.)

## Failure Conditions

- swallowed exception (silent failure)
- unclear error source (generic "error occurred")
- destructive rollback without user notice
- misleading success state (HTTP 200 with hidden failure)

## Forbidden Actions

- returning only "오류가 발생했습니다" without actionable detail
- silently ignoring broken field mappings
- hiding template preservation failures
- logging but not surfacing user-actionable errors to the UI

## Korean UI Messages (must be user-friendly)

| Error Code | UI 메시지 예시 |
|------------|---------------|
| `MISSING_DOC` | "비교견적서가 없습니다. 서류를 업로드해주세요." |
| `TEMPLATE_STRUCTURE_VIOLATION` | "서식 구조를 보존할 수 없습니다. 원본 서식을 확인해주세요." |
| `RAG_NO_EVIDENCE` | "업로드된 RCMS 매뉴얼에서 해당 내용을 찾을 수 없습니다." |
| `AMOUNT_MISMATCH` | "견적서와 거래명세서의 금액이 일치하지 않습니다." |
| `PERIOD_INVALID` | "집행일이 과제 수행 기간을 벗어났습니다." |

## Developer Guidance

- Design for debuggability: errors should help both end users and developers.
- Include `request_id` or `trace_id` in system errors for log correlation.
- Use the custom exception hierarchy in `app/core/exceptions.py`.
- Never let unhandled exceptions reach the user as HTTP 500 without logging.
