# Skill: validation_engine_skill

> 이 프로그램의 실무 생명줄. "생성"보다 "차단"이 더 중요할 때가 많다.

## Purpose

Validate expense execution data, supporting documents, and generated outputs before export or submission.

## When to Use

- expense item save
- pre-generation validation
- post-generation validation
- export/package approval

## Core Rules

1. Validate by expense category (비목별 검증).
2. Clearly distinguish **blocking errors** from **warnings**.
3. Log every validation result with timestamp and context.
4. Support cross-document consistency checks (금액, 업체명, 날짜).
5. Use company/program-specific rules where applicable.

## Required Document Sets by Category

| 비목 | 필수 서류 |
|------|-----------|
| outsourcing (외주비) | quote, comparative_quote, service_contract, work_order, transaction_statement, inspection_photos, vendor_business_registration, vendor_bank_copy |
| labor (인건비) | cash_expense_resolution, in_kind_expense_resolution, researcher_status_sheet |
| test_report (시험·검사비) | quote, expense_resolution, transaction_statement |
| materials (재료비) | quote, comparative_quote, expense_resolution, inspection_confirmation, vendor_business_registration, vendor_bank_copy |
| meeting (회의비) | receipt, meeting_minutes |
| other (기타) | admin-managed rules |

## Validation Types

- required docs by category
- project-period validity (집행일이 과제 기간 내인지)
- amount consistency (서류 간 금액 일치)
- vendor consistency (사업자등록증과 거래명세서 업체 일치)
- attachment completeness (파일 업로드 여부)
- template integrity (생성된 서식 구조 보존 여부)
- category-specific business rules

## Outputs

```json
{
  "is_valid": false,
  "blocking_errors": [
    { "code": "MISSING_DOC", "message": "비교견적서가 없습니다.", "field": "comparative_quote" }
  ],
  "warnings": [
    { "code": "AMOUNT_MISMATCH_WARNING", "message": "견적서와 거래명세서 금액 차이가 있습니다." }
  ],
  "passed_checks": [
    { "code": "PERIOD_VALID", "message": "집행일이 과제 기간 내에 있습니다." }
  ]
}
```

## Failure Conditions

- required document missing → blocking error
- amount mismatch across documents → blocking error
- vendor name mismatch → blocking error
- expense date outside project period → blocking error
- incomplete attachment set → blocking error

## Forbidden Actions

- treating blocking errors as warnings
- exporting packages with unresolved blocking errors
- silently suppressing validation failures
- allowing generation to proceed when pre-generation validation fails

## Developer Guidance

- Make validation rule-driven and configurable per program profile.
- Expose all validation results clearly in both API response and UI.
- Preserve historical validation logs — never overwrite.
- Validation must run before export; export must be blocked if `is_valid = false`.
