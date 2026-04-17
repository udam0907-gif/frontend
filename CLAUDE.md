# R&D 비용 집행 관리 시스템 — 개발 규칙

## 스킬 참조 (필수)

이 프로젝트의 모든 코드 작업 전에 아래 스킬 파일을 반드시 읽고 준수한다.

```
skills/01_template_preservation_skill.md     — 서식 보존 (황제 스킬)
skills/02_template_field_mapping_skill.md    — 필드 매핑
skills/03_document_generation_skill.md       — 문서 생성 파이프라인
skills/04_validation_engine_skill.md         — 검증 엔진 (비목별 차단 기준)
skills/05_multitenant_isolation_skill.md     — 멀티테넌트 격리
skills/06_program_profile_inheritance_skill.md — 사업 프로필 상속
skills/07_rcms_rag_skill.md                  — RCMS 매뉴얼 RAG
skills/08_audit_traceability_skill.md        — 감사 로그 / 추적성
skills/09_api_contract_skill.md              — API 계약
skills/10_error_handling_skill.md            — 에러 처리
```

## 핵심 철학 (1줄 요약)

> **양식은 절대 안 깨고, 추측은 안 하고, 회사 데이터는 안 섞고, 검증 실패는 그냥 통과시키지 않고, 모든 결과는 근거와 로그를 남긴다.**

## 우선순위 규칙

코드를 작성하거나 수정할 때 아래 순서를 항상 따른다.

1. 사용자가 업로드한 서식 (최우선 — 절대 변경 불가)
2. 사용자 입력 데이터
3. 과제 정보 / 사업 프로필
4. 내부 비즈니스 규칙
5. 법령/규정 참고 자료
6. LLM 생성 텍스트 (최하위 — 서술 필드 한정)

## 절대 금지

- 서식 구조를 변경하거나 근사치로 생성하는 것
- RCMS 매뉴얼 근거 없이 답변을 생성하는 것
- blocking error가 있는 상태에서 내보내기를 허용하는 것
- 검증 실패를 조용히 무시하는 것
- 추적 로그 없이 문서를 생성하는 것
- company_id 스코프 없이 테넌트 데이터에 접근하는 것

## 기술 스택

- Backend: Python FastAPI + SQLAlchemy (async) + pgvector
- Frontend: Next.js 14 + TypeScript + Tailwind + shadcn/ui
- LLM: Anthropic Claude (claude-sonnet-4-6), prompt caching 적용
- DB: PostgreSQL 16 + pgvector
- Document: docxtpl (DOCX 서식 채움)

## 스킬 조합 가이드

| 작업 | 적용 스킬 |
|------|-----------|
| 템플릿 업로드/등록 | 01, 02, 10 |
| 문서 생성 | 01, 02, 03, 08 |
| 비용 항목 검증 | 04, 09, 10 |
| ZIP 내보내기 | 04, 08, 09 |
| RCMS Q&A | 07, 05, 08 |
| 프로젝트 생성 | 06, 05, 09 |
| API 설계 | 09, 05, 10 |
