# Skill: multitenant_isolation_skill

> SaaS로 다른 회사에 제공하려면 무조건 있어야 한다. 없으면 데이터 섞임 사고 발생.

## Purpose

Ensure that tenant/company-owned data is strictly isolated across companies while allowing controlled access to shared global resources.

## When to Use

- database modeling
- API endpoint design
- file storage path design
- query building
- logging
- search / list operations

## Core Rules

1. Every tenant-owned record must be scoped by `company_id`.
2. Shared/global resources must be explicitly marked as global.
3. Never return tenant-owned data without tenant scoping in the query.
4. Do not mix shared RCMS/manual data with tenant-owned outputs and logs.
5. Authorization must always verify tenant context before data access.

## Tenant-Owned Data (반드시 company_id로 격리)

- users
- program profiles
- projects
- templates and template mappings
- expense items
- attachments
- generated output files
- validation logs
- QA session logs

## Shared/Global Data (전사 공용, 별도 테이블)

- shared RCMS manuals (공통 매뉴얼)
- common legal reference library
- common FAQ content

## File Storage Isolation

```
storage/
  tenants/
    {company_id}/
      templates/
      documents/
      exports/
  global/
    manuals/
    legal/
```

## Failure Conditions

- missing `company_id` filter in tenant endpoint query
- cross-tenant data leak via unscoped SELECT
- attachment file path overlap between tenants
- unauthorized access to another tenant's template or expense data

## Forbidden Actions

- unscoped SELECT queries on tenant-owned tables
- storing tenant-owned files in shared/global paths
- using global IDs without tenant verification
- returning tenant data in shared/global endpoints

## Developer Guidance

- Add tenant context middleware early in the request lifecycle.
- Include `company_id` in relevant indexes and foreign keys.
- Add a test that verifies tenant A cannot access tenant B's data.
- Use row-level scoping — never application-level filtering alone.
