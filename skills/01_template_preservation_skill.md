# Skill: template_preservation_skill

> 이 시스템의 황제 스킬. 모든 문서 생성 작업에서 반드시 준수한다.

## Purpose

Ensure that all generated documents preserve the exact structure of the user-uploaded template.
The system must treat uploaded templates as immutable layout contracts.

## When to Use

- DOCX template upload
- template rendering
- document generation
- template preview
- template validation

## Core Rules

1. Never redesign or reformat a user-uploaded template.
2. Never change table structure, merged cells, paragraph order, headings, labels, or spacing intentionally.
3. If placeholder mapping fails, **block generation** instead of approximating.
4. Separate content generation from template rendering.
5. Treat the template file as the source of truth for output layout.

## Inputs

- uploaded template file
- extracted placeholders
- mapped field values
- document type
- category
- company_id
- program_profile_id

## Outputs

- rendered document preserving original layout
- template integrity check result
- blocking error if rendering cannot preserve structure

## Failure Conditions

- placeholder parsing failure
- missing required mapped fields
- document rendering error
- structure mismatch after rendering
- template corruption

## Forbidden Actions

- inventing missing placeholders
- moving sections
- collapsing or expanding tables
- changing labels to "improve" readability
- replacing the original format with a newly generated document

## Developer Guidance

- Prefer placeholder-based fill-in over regeneration.
- Preserve the original file and render into a copy.
- Add automated integrity checks after rendering where possible.
- Use `docxtpl` for template filling — never regenerate from scratch.
- If template rendering raises any structural warning, treat as blocking error.
