# Skill: api_contract_skill

> 백엔드가 무너지지 않게 하는 스킬. 명시적이고 예측 가능한 API를 유지한다.

## Purpose

Keep backend APIs explicit, versioned, predictable, and safe for frontend and automation use.

## When to Use

- FastAPI endpoint design
- request/response schema design
- frontend-backend integration
- error response design

## Core Rules

1. Every endpoint must have explicit request and response Pydantic schemas.
2. Validation errors must return structured responses (never raw exceptions).
3. Multi-tenant endpoints must enforce `company_id` scope — always.
4. Use consistent naming conventions and category enums throughout.
5. Do not return partial success silently for critical operations (generation, validation, export).

## Standard Error Response Schema

```json
{
  "error": "VALIDATION_ERROR",
  "message": "비교견적서가 없습니다.",
  "details": {
    "field": "comparative_quote",
    "expense_item_id": "uuid"
  }
}
```

## HTTP Status Code Convention

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 201 | Created |
| 204 | Deleted (no content) |
| 400 | Bad request (user input error) |
| 401 | Unauthorized |
| 403 | Forbidden (tenant mismatch) |
| 404 | Not found |
| 409 | Conflict (duplicate) |
| 422 | Validation / template error |
| 500 | System error |
| 502 | LLM/embedding service error |

## Endpoint Naming Convention

```
GET    /api/v1/{resource}             → list
POST   /api/v1/{resource}             → create
GET    /api/v1/{resource}/{id}        → get one
PATCH  /api/v1/{resource}/{id}        → update
DELETE /api/v1/{resource}/{id}        → delete (soft or hard)
POST   /api/v1/{resource}/{id}/{action} → specific action
```

## Outputs

- stable, versioned API contracts
- consistent error schema across all endpoints
- permission-aware, tenant-scoped endpoints

## Failure Conditions

- inconsistent response format between endpoints
- missing tenant scope check in tenant-owned endpoints
- untyped or loosely typed payloads
- returning HTTP 200 when a blocking validation error exists

## Forbidden Actions

- hidden implicit behavior in endpoints
- mixed error response formats
- returning success status when blocking validation exists
- unversioned breaking changes to endpoint contracts

## Developer Guidance

- Use Pydantic models consistently for all request and response schemas.
- Separate shared/global endpoints from tenant-owned endpoints clearly.
- Version the API (`/api/v1/`) — prepare for v2 without breaking v1.
- All endpoints must be tested with both success and failure cases.
