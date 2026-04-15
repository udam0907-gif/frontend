# Skill: program_profile_inheritance_skill

> 한 회사 안에 여러 정부지원사업이 있을 때 사업 프로필이 기본값을 상속한다.

## Purpose

Allow projects to inherit templates, rules, legal sets, manual sets, and export policies from a selected Program Profile.

## When to Use

- project creation
- project settings configuration
- document generation context resolution
- validation context resolution
- export policy resolution

## Core Rules

1. A Project must belong to exactly one Program Profile.
2. Program Profile defines all operational defaults for that program type.
3. Projects inherit defaults but may override selected settings explicitly.
4. Inheritance must be explicit (stored reference) and traceable.
5. Shared/global resources (RCMS manuals, legal library) may be referenced through the Program Profile.

## Configuration Resolution Order

```
company settings
  → program profile defaults
    → project overrides
```

Each level explicitly overrides the one above. No implicit inheritance.

## Program Profile Owns

- template set (비목별 서식 목록)
- required document rules (비목별 필수 서류 기준)
- validation rule set
- legal reference set
- RCMS manual set
- output/export policy

## Outputs

- resolved project configuration snapshot (used at generation and validation time)
- inherited settings record
- override log where project differs from program profile

## Failure Conditions

- project created without a program profile assignment
- missing required inherited rule set (e.g., no template set linked)
- conflicting overrides that cannot be resolved
- broken references to template/manual/legal sets (deleted or inactive)

## Forbidden Actions

- bypassing program profile during project creation
- implicit inheritance without stored database references
- silently mutating original program profile from project-level changes
- allowing generation or validation without resolved configuration

## Developer Guidance

- Create a `ConfigResolver` service that merges:
  `company_settings → program_profile_defaults → project_overrides`
- Store the resolved configuration snapshot used at generation time in the trace log.
- Program Profile updates should not retroactively change existing project configurations.
- Expose inherited vs overridden settings clearly in the project UI.
