# HANDOFF — R&D 비용 집행 관리 시스템

최종 갱신: 2026-04-30

---

## 오늘 완료한 것 (2026-04-30)

- [x] **비목 Enum 3종 추가** — `research_activity`, `indirect_credit`, `entrusted_audit`
  - `backend/app/models/enums.py` + migration 013 적용
- [x] **document_set_specs 테이블 신설** (migration 013)
  - `backend/app/models/document_set_spec.py` — DocumentSetSpec ORM 모델
  - `backend/migrations/versions/013_document_set_specs.py`
  - `backend/app/data/document_set_seeds.py` — 비목별 문서세트 시드 데이터
  - `expense_items.category_payload JSONB` 컬럼 추가
- [x] **XLSX 셀 매핑 보강** (`xlsx_document_filler.py`)
  - `_anchor()` 헬퍼: 병합 셀에 값 쓸 때 앵커 좌표 자동 탐색
  - `_parse_date()` 헬퍼: 날짜 문자열 파싱 (YYYY-MM-DD 등)
- [x] **문서세트 서비스 수정** (`document_set_service.py`)
  - 비교견적 금액 100원 단위 올림 강제
  - 수신자 이름 `{company} 귀하` 자동 포맷팅
  - 업체 조회 로직: 전사 공통 업체(project_id=NULL) 포함, 프로젝트 전용 우선
- [x] **TemplatesPanel 드롭다운** (`frontend/components/company/TemplatesPanel.tsx`)
  - 서류 유형 텍스트 입력 → 선택 드롭다운으로 변경

---

## 아직 안 된 것 (다음 컴퓨터에서 이어서)

| 항목 | 비고 |
|------|------|
| migration 013 실제 DB 적용 확인 | Docker 시작 후 `alembic upgrade head` 실행 |
| document_set_specs 시드 데이터 INSERT | migration 013의 `upgrade()` 내 seed 삽입 코드 확인 |
| 비목별 문서세트 API 개발 | `document_set_specs` 기반 GET/POST endpoint |
| 비교견적 금액 UI 입력 연동 | expense 입력 폼 `compare_amount` 필드 추가 |
| 지출결의서/검수확인서 우리 회사 정보 반영 검증 | |
| `usage_purpose`/`purchase_purpose`/`delivery_date` 입력 | expense_items 컬럼 없음, 프론트 폼 필요 |
| `line_items` 복수 품목 UI | |

---

## 다른 컴퓨터에서 이어서 작업하는 법

### 1단계: 코드 받기
```bash
git clone https://github.com/udam0907-gif/frontend.git cm_app
cd cm_app
```

### 2단계: 환경 변수 설정
`backend/.env` 파일 생성 (`.env.example` 참고):
```bash
cp backend/.env.example backend/.env
# 필요한 값 입력: ANTHROPIC_API_KEY, POSTGRES_PASSWORD 등
```

### 3단계: Docker 실행
```bash
docker compose up -d
```

### 4단계: DB 복원 (신규 환경일 때만)
```bash
# DB가 비어있으면 backup에서 복원
docker exec -i rnd_postgres psql -U postgres rnd_expense_db < db_backup.sql
```

### 5단계: Migration 적용 확인
```bash
docker exec rnd_backend bash -c "alembic current"
docker exec rnd_backend bash -c "alembic upgrade head"
```

### 6단계: 접속 확인
- 백엔드: http://localhost:8000/docs
- 프론트엔드: http://localhost:3001

---

## 현재 git 상태

- 브랜치: `master`
- 최신 커밋: migration 013 (document_set_specs) + xlsx 병합셀 보강
- remote: `https://github.com/udam0907-gif/frontend.git`
- DB 백업: `db_backup.sql` (2026-04-29 16:24 기준)

---

## 기본 Docker 명령어

```bash
# 실행
docker compose up -d

# 로그 확인
docker logs rnd_backend -f
docker logs rnd_frontend -f

# Migration
docker exec rnd_backend bash -c "alembic current"
docker exec rnd_backend bash -c "alembic upgrade head"

# 템플릿 재생성
docker exec rnd_backend bash -c "python /app/make_docx_templates.py"

# DB 백업 새로 만들기
docker exec rnd_postgres pg_dump -U postgres rnd_expense_db > db_backup.sql
```

---

## 주의사항

- `quote` 문서는 `Vendor.quote_template_path` 사용 (시스템 템플릿 테이블 무시)
- `_find_template`: project-specific > global 우선순위
- `{%tr for item in line_items %}` 행과 content 행은 반드시 분리
- `test_*.py`, `test_outputs/`, `test_templates/` — 커밋 제외 (테스트용)
- migration 013은 `category_type` enum ADD VALUE를 포함 → 반드시 `alembic upgrade head` 필요

---

## RCMS 관련 금지사항

- RCMS 매뉴얼 연동 코드 수정 금지
- `skills/07_rcms_rag_skill.md` 범위 외 작업 금지
- RCMS 관련 API endpoint 변경 금지

---

## DB 주요 템플릿 (등록 현황)

| ID | 이름 | document_type | project_id |
|----|------|---------------|------------|
| `8a79a6a9` | 지출결의서 (DOCX) | expense_resolution | global |
| `fba83039` | 지출결의서 (DOCX) | expense_resolution | de8129c2 |
| `7c71ddc7` | 견적서 (DOCX) | quote | global |
| `2b5f3664` | 지출결의서 (원본) | expense_resolution | b315bd6b |
| `ec146f1d` | 유담 지출결의서 | expense_resolution | de8129c2 (XLSX, 구버전) |
