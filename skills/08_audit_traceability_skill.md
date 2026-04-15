# Skill: audit_traceability_skill

> 정부지원사업이면 무조건 필요하다. "왜 이렇게 만들었냐"에 항상 답할 수 있어야 한다.

## Purpose

Make every generated document, validation result, and answer explainable and traceable for audit and review.

## When to Use

- document generation
- validation execution
- export/package creation
- RCMS Q&A
- legal reference sync
- any action that produces a system output

## Core Rules

1. Log all source inputs used for generation (template_id, mapping version, field values).
2. Log template version, mapping version, model version, and rule version at time of action.
3. Store legal basis snapshots or references used at the time.
4. Store validation outcomes and generation timestamps immutably.
5. Make all trace data exportable via `manifest.json` in every ZIP package.

## Trace Items (required on every generation)

| Field | Description |
|-------|-------------|
| `company_id` | Tenant identifier |
| `program_profile_id` | Program profile used |
| `project_id` | Project context |
| `template_id` + `template_version` | Exact template used |
| `mapping_version` | Field mapping version |
| `rule_set_version` | Validation rules version |
| `legal_set_version` | Legal references version (if used) |
| `generated_at` | Timestamp (ISO 8601) |
| `triggered_by` | User or system that triggered the action |
| `model_id` + `model_version` | LLM used (if applicable) |
| `prompt_version` | Prompt template version (if LLM used) |
| `referenced_chunks` | RAG chunks used (if RCMS Q&A) |

## manifest.json Structure

```json
{
  "expense_item_id": "uuid",
  "project_id": "uuid",
  "company_id": "uuid",
  "program_profile_id": "uuid",
  "generated_at": "2026-04-15T16:00:00+09:00",
  "triggered_by": "user@company.com",
  "documents": [
    {
      "filename": "견적서.docx",
      "template_id": "uuid",
      "template_version": 3,
      "mapping_version": 2
    }
  ],
  "validation": {
    "is_valid": true,
    "validated_at": "2026-04-15T15:58:00+09:00",
    "rule_set_version": "1.2.0"
  },
  "model_used": "claude-sonnet-4-6",
  "prompt_version": "rcms_qa_v1.0.0"
}
```

## Outputs

- `manifest.json` included in every export ZIP
- generation log record (stored in DB)
- validation log record (stored in DB)
- QA source trace (stored in `rcms_qa_sessions`)

## Failure Conditions

- generation executed without trace log → blocking error
- missing version references in trace
- export package created without manifest.json
- validation result not linked to expense item

## Forbidden Actions

- overwriting trace logs without version history
- generating files without source references in trace
- deleting trace data without an audit policy
- creating ZIP exports without manifest.json

## Developer Guidance

- Treat traceability as a first-class feature — implement from day 1, not as an afterthought.
- Keep audit logs queryable and exportable.
- Audit logs are immutable: insert only, never update/delete without policy.
- `manifest.json` must be auto-generated and included in every ZIP export.
