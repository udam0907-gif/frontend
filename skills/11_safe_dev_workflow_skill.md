# Skill: safe_dev_workflow_skill

> 이 스킬은 기능 구현 규칙이 아니라, 프로젝트 작업 방식과 git/핸드오프 흐름을 고정하기 위한 운영 스킬이다.

## Purpose

Keep development work scoped, reviewable, git-safe, and handoff-ready across Claude Code, GPT, Gemini, Codex, and multiple computers.

## When to Use

- any feature or bug fix task
- any multi-step refactor
- before commit/push
- when handing off to another AI or another machine
- when token budget is limited

## Core Rules

1. Work only within the requested scope.
2. Do not perform broad refactors unless explicitly requested.
3. Handle one task at a time.
4. Separate analysis, implementation, and verification.
5. Do not commit immediately after changes.
6. First report:
   - modified files
   - summary of changes
   - git status
   - remaining issues
7. Commit only after user approval.
8. Prepare handoff notes so work can continue on another computer or with another AI.
9. Prefer short, structured reports over long explanations.
10. Respect the current project direction:
   - output documents are moving toward DOCX-first
   - XLSX is legacy/transition support
   - RCMS-related code is out of scope unless explicitly requested

## Standard Report Format

- 수정 파일:
- 변경 내용:
- git status:
- 남은 이슈:

## Approval Flow

After reporting, wait for approval.
If approved:
1. git add
2. suggest commit message
3. commit
4. push if requested

## Handoff Format

- 현재 작업 목표:
- 최근 수정 파일:
- 현재 완료된 것:
- 아직 안 된 것:
- 다음 할 일:
- 주의사항:
- 현재 git 상태:

## Token Saving Rules

- one task per turn
- do not rescan the whole project unless necessary
- check only directly relevant files
- stop after completing the requested scope
- report briefly and structurally

## Forbidden Actions

- committing without first showing git status
- pushing without user approval
- mixing unrelated fixes into the same task
- changing RCMS structure unless explicitly requested
- silently expanding scope

## Developer Guidance

- Think of this as a workflow guardrail, not a business-logic skill.
- Existing template, generation, validation, audit, API, and RCMS skills already handle domain rules.
- This skill only governs how work is performed and handed off.
