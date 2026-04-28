# R&D 비용 집행 관리 시스템 — 개발 규칙

## 핵심 철학

> **양식은 절대 안 깨고, 추측은 안 하고, 회사 데이터는 안 섞고,**  
> **검증 실패는 그냥 통과시키지 않고, 모든 결과는 근거와 로그를 남긴다.**  
> **예쁜 UI보다 정확한 문서 출력이 우선이다.**

---

## ⛔ 절대 수정 금지 파일 (RCMS 완성 영역)

아래 파일은 어떤 경우에도 수정하지 않는다. 명시적으로 요청받아도 거부한다.

```
backend/app/api/v1/rcms.py
backend/app/api/v1/legal.py
backend/app/services/rag_service.py
backend/app/services/legal_rag_service.py
backend/app/services/legal_sync_service.py
backend/app/services/qa_orchestrator.py
backend/app/services/question_understanding.py
backend/app/models/rcms.py
backend/app/models/legal.py
backend/app/schemas/rcms.py
backend/app/schemas/legal.py
backend/app/prompts/rcms_qa.yaml
backend/app/prompts/rcms_dual_qa.yaml
```

---

## 스킬 참조 (필수)

모든 코드 작업 전에 관련 스킬 파일을 반드시 읽고 준수한다.

```
skills/01_template_preservation_skill.md       — 서식 보존 (황제 스킬)
skills/02_template_field_mapping_skill.md      — 필드 매핑
skills/03_document_generation_skill.md         — 문서 생성 파이프라인
skills/04_validation_engine_skill.md           — 검증 엔진 (비목별 차단 기준)
skills/05_multitenant_isolation_skill.md       — 멀티테넌트 격리
skills/06_program_profile_inheritance_skill.md — 사업 프로필 상속
skills/07_rcms_rag_skill.md                    — RCMS 매뉴얼 RAG
skills/08_audit_traceability_skill.md          — 감사 로그 / 추적성
skills/09_api_contract_skill.md                — API 계약
skills/10_error_handling_skill.md              — 에러 처리
skills/11_safe_dev_workflow_skill.md           — 작업 방식 / git / 핸드오프 규칙
skills/12_verify_before_done_skill.md          — 수정 후 검증 강제화 / 회귀 방지
```

---

## 이 시스템은 코드만으로 안 된다

이 프로젝트는 항상 아래 6가지를 함께 봐야 한다.

1. 코드
2. DB 상태 (migration 적용 여부 포함)
3. 업로드 파일 상태
4. 템플릿 파일 상태
5. `.env` 환경설정
6. Docker / 볼륨 상태

다른 컴퓨터에서 안 되면 코드만 탓하지 않는다. 위 6가지를 모두 확인한다.

---

## 작업 원칙

### 1. "돌아간다"와 "정상이다"는 다르다
버튼이 눌리거나 파일이 생성됐다고 성공이 아니다.
항상 **실제 화면, 실제 출력 문서** 기준으로 성공 여부를 판단한다.

### 2. 한 번에 하나만 고친다
한 번에 여러 기능을 건드리면 원인을 알 수 없게 된다.
한 화면, 한 기능, 한 문서만 잡는다.

### 3. 수정 범위를 벗어나지 않는다
요청한 것만 수정한다. 리팩토링 욕심 금지.
기존에 잘 되던 기능이 수정 후 깨지면 그 수정은 실패다.

### 4. 수정 후 반드시 확인한다
파일을 수정했으면 다시 읽어서 실제로 반영됐는지 확인 후 "완료"라고 말한다.
가능하면 실행 결과로 증명한다.

### 5. 원인 분석 먼저
바로 수정하지 말고 먼저 정리한다.
문제가 프론트인지 / 백엔드인지 / DB인지 / 파일 경로인지 / 환경 차이인지.

### 6. 자동 추측보다 명시적 설정이 우선
AI가 알아서 잘할 거라고 믿지 않는다.
템플릿별 규칙을 저장하고 그 규칙대로 렌더링한다.

### 7. 큰 작업 전에는 반드시 백업한다
DB 구조 변경 / 문서 생성 엔진 수정 / 공통 로직 수정 전에는:
- git commit / branch
- DB + 업로드 파일 백업

---

## 절대 금지

- 확인 없이 "완료했습니다" 말하기
- 실제 출력물 검증 없이 "성공" 판단하기
- 요청 범위 밖 코드 변경 / 리팩토링
- DB 직접 수정 후 migration 없이 끝내기
- 이유 없이 임의로 구현 방향 선택하기
- 서식 구조를 변경하거나 근사치로 생성하기
- 절대 수정 금지 파일 수정하기
- company-settings 자동추출 시 애매한 값 강제 저장
  (예: `(480)` 같은 잡음값은 회사명으로 넣지 않는다. 빈칸이 틀린 값보다 낫다)

---

## 매 작업 절차

```
STEP 1. 작업 범위 확정 — 어떤 화면/기능/문서/파일만 수정할지 딱 정한다
STEP 2. 현재 상태 확인 — 브랜치, git status, Docker, migration, DB, 파일 존재 여부
STEP 3. 원인 분석 — 프론트/백엔드/DB/파일/환경 중 어디 문제인지
STEP 4. 최소 수정 — 한 번에 크게 뜯지 않는다
STEP 5. 실제 결과 확인 — 화면, 생성 문서, 값, 레이아웃
STEP 6. 보고
```

보고 형식:
```
수정 파일:
변경 내용:
실제 반영 여부:
영향 범위 (다른 기능 영향 없음 / 있으면 명시):
남은 이슈:
```

---

## 작업 요청 템플릿

AI에게 작업시킬 때 아래 형식을 기본으로 쓴다.

```
작업 목표: (한 줄)
현재 문제: (실제 현상 기준)
필수 요구사항: (반드시 지켜야 할 동작)
수정 범위: (어느 화면/파일/기능만)
성공 기준: (어떻게 되면 성공인지)
```

---

## 문서 출력 방향 (파일 형식별 역할)

| 형식 | 역할 | 비고 |
|------|------|------|
| XLSX | 업체 견적서·거래명세서 주력 포맷 | cell_map 기반 셀 자동 입력 |
| DOCX | 지출결의서·검수확인서 등 내부 서식 | docxtpl 변수 채우기 |
| XLS | XLSX 자동 변환 후 처리 | xlrd → openpyxl 변환 |
| PDF/JPG/PNG | 첨부용 passthrough_copy | 사업자등록증·통장사본 등 |

---

## 재료비 문서세트 구성 (7개)

| 순서 | 문서 | 출처 |
|------|------|------|
| 1 | 견적서 | 업체 XLSX/XLS + 셀 자동 매핑 |
| 2 | 비교견적서 | 비교업체 XLSX + 원금액 × 랜덤(1.1~1.5) 100원 단위 올림 |
| 3 | 거래명세서 | 업체 XLSX/XLS + 셀 자동 매핑 |
| 4 | 지출결의서 | 내부 DOCX 서식 |
| 5 | 검수확인서 | 내부 DOCX 서식 |
| 6 | 업체 사업자등록증 | 업체 등록 파일 passthrough |
| 7 | 업체 통장사본 | 업체 등록 파일 passthrough |

### 견적서 성공 기준 (이게 안 되면 전부 실패)

- 공급자 정보 / 수신처 / 작성일 / 품목명 / 수량 / 단가 / 금액 / 합계 정확
- 레이아웃 안 깨짐
- placeholder·샘플 문구 없음

---

## XLSX 셀 매핑 파이프라인

```
파일 확장자 확인
  ├── .xls → convert_xls_to_xlsx() → 임시 .xlsx
  └── .xlsx → 그대로
      ↓
XlsxCellMapper.analyze() — Claude API 호출
      ↓
cell_map 추출 (플랫 구조)
{"item_name": "A16", "quantity": "E15", "sheet_name": "시트명"}
      ↓
XlsxDocumentFiller.fill() — FIELD_ALIASES 3단계 탐색 → 셀 입력
      ↓
출력 파일 저장 (.xlsx)
```

cell_map 규칙:
- `sheet_name`, `_cell_map`, `_mapping_status` 키는 쓰기 제외
- 중첩 구조 감지 시 자동 플랫화

---

## 핵심 서비스 파일

```
backend/app/services/
├── document_set_service.py      — 문서세트 생성 오케스트레이터 (핵심)
├── document_generator.py        — DOCX/XLSX 렌더링 엔진
├── xlsx_cell_mapper.py          — Claude API로 XLSX 셀 자동 매핑
├── xlsx_document_filler.py      — cell_map 기반 XLSX 데이터 입력
└── company_setting_extractor.py — 사업자등록증 → 회사 기본 정보 추출
```

---

## 기술 스택

- Backend: Python FastAPI + SQLAlchemy (async) + pgvector
- Frontend: Next.js 14 + TypeScript + Tailwind + shadcn/ui
- LLM: Anthropic Claude (claude-sonnet-4-6), prompt caching 적용
- DB: PostgreSQL 16 + pgvector (DB명: rnd_expense_db)
- Document: docxtpl (DOCX), openpyxl + xlrd==1.2.0 (XLSX/XLS)
- Container: Docker Compose
  - rnd_backend — FastAPI 포트 8000
  - rnd_frontend — Next.js 포트 3001
  - rnd_postgres — PostgreSQL 포트 5432

---

## DB 주요 테이블

| 테이블 | 역할 |
|--------|------|
| vendors | 업체 정보 + 견적서/거래명세서 파일 경로 |
| company_settings | 우리 회사 기본 정보 (귀중/귀하에 사용) |
| vendor_template_pool | 업체별 XLSX 셀 매핑 공유 풀 |
| templates | 지출결의서/검수확인서 등 내부 서식 |
| generated_documents | 생성된 문서 이력 |
| expense_items | 비용 항목 |
| projects | 과제 정보 |

---

## 우선순위 (항상 이 순서)

1. 견적서가 실제 제출 가능 수준으로 정확하게 나오는가
2. 핵심 문서 매핑이 정확한가
3. 입력 데이터가 안정적으로 저장되는가
4. 자동입력이 틀린 값을 넣지 않는가
5. 화면이 보기 좋고 편한가

---

## 스킬 조합 가이드

| 작업 | 적용 스킬 |
|------|-----------|
| 템플릿 업로드/등록 | 01, 02, 10 |
| XLSX 셀 매핑 | 02, 03, 08, 12 |
| 문서세트 생성 | 01, 02, 03, 08, 12 |
| 비용 항목 검증 | 04, 09, 10 |
| ZIP 내보내기 | 04, 08, 09 |
| RCMS Q&A | 07, 05, 08 |
| 프로젝트 생성 | 06, 05, 09 |
| API 설계 | 09, 05, 10 |
| 회사 설정 | 05, 08, 09 |
| 모든 작업 공통 | 11, 12 |
