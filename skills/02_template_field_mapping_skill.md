# Skill: template_field_mapping_skill

> 양식과 데이터를 연결하는 스킬. 여기서 삐끗하면 나중에 다 삐끗한다.

## Purpose

Map structured application data to placeholders in uploaded document templates safely and explicitly.

## When to Use

- template registration
- field mapping UI
- template inspection
- generation pre-check

## Core Rules

1. Extract placeholders from templates in a deterministic way.
2. Store mappings explicitly in the database — never assume mappings.
3. Do not silently ignore unmapped placeholders.
4. Do not automatically guess business meaning from placeholder names unless confirmed by user.
5. Support required/optional field distinction.

## Inputs

- template file
- detected placeholders
- field mapping configuration
- available project/program fields

## Outputs

- placeholder list
- saved mapping configuration
- unresolved placeholder report
- required field checklist

## Failure Conditions

- placeholder parsing returns inconsistent results
- duplicate placeholder conflicts
- required placeholder has no mapping
- mapping references unavailable source fields

## Forbidden Actions

- auto-filling unknown placeholders with guessed values
- dropping unresolved placeholders without warning
- mixing company/program-specific fields into global mappings

## Developer Guidance

- Use explicit placeholder syntax: `{{FIELD_NAME}}`
- Keep mapping versioned alongside template version.
- Allow re-validation after template updates.
- Expose unresolved placeholder list in the UI before allowing generation.
- Distinguish system fields (project_name, date) from user-input fields (description, narrative).
