# Skill: document_generation_skill

> 실제 문서를 생성할 때 적용하는 스킬. 템플릿 없이는 생성 없다.

## Purpose

Generate expense execution documents strictly from registered templates, validated field mappings, and structured business data.

## When to Use

- expense item document generation
- package generation
- preview generation
- regeneration after data updates

## Core Rules

1. Generate only from uploaded templates and approved mappings.
2. Use LLM-generated text **only** for helper narrative fields — never for layout decisions.
3. Require validation of required inputs before generation.
4. Save generation logs and source trace for every document.
5. Support category-specific document generation flows.

## Priority Order (must follow strictly)

1. user-uploaded template (highest)
2. user input data
3. project / program profile data
4. internal business rules
5. Korean legal/regulatory references
6. LLM-generated helper text (lowest — narrative only)

## Inputs

- expense item
- project data
- program profile data
- template + field mapping
- user input
- legal/support references
- helper text generation request (if applicable)

## Outputs

- generated document file (DOCX)
- generation metadata (template_id, version, timestamp)
- generation log
- manifest entry

## Generation Pipeline (must follow this order)

1. Load template from registry
2. Resolve fields from project + expense + user input
3. Validate all required inputs are present
4. Generate LLM helper text only for narrative-tagged fields
5. Render template with `docxtpl`
6. Run post-render integrity check
7. Save file and write trace log

## Failure Conditions

- missing template
- invalid or unresolved field mapping
- unresolved required field
- rendering failure
- template integrity check fails after rendering
- unsupported document type for current MVP

## Forbidden Actions

- generating documents without registered templates
- replacing a blocked generation with approximate output
- using LLM to fabricate business facts (amounts, dates, vendor names)
- skipping trace logging
- modifying template structure during rendering

## Developer Guidance

- Treat generation as a pipeline with explicit stages.
- Each stage must succeed before the next runs.
- If any stage fails, block and return a structured error — do not approximate.
- Store the template version used at generation time in the trace.
