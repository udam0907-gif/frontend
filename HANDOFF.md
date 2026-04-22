# HANDOFF — R&D 비용 집행 관리 시스템

최종 갱신: 2026-04-22

---

## 오늘 완료한 것 (2026-04-22)

- [x] `company_settings` 테이블 migration 적용 완료 (Alembic 007 stamp)
- [x] Docker 정상 실행 확인: `rnd_postgres`, `rnd_backend`, `rnd_frontend`
- [x] company-settings API 검증 완료
  - `GET /api/v1/company-settings`
  - `PUT /api/v1/company-settings`
  - `POST /api/v1/company-settings/files`
- [x] 저장 확인 필드: `company_name`, `company_registration_number`, `representative_name`,
  `address`, `business_type`, `business_item`, `phone`, `fax`, `email`,
  `default_manager_name`, `seal_image_path`
- [x] 파일 업로드 저장 확인: `company_business_registration_path`,
  `company_bank_copy_path`, `company_quote_template_path`,
  `company_transaction_statement_template_path`
- [x] `company_settings` 값이 document context에 반영됨
  (`recipient_*`, `buyer_*`, `our_company_*` 및 회사 기본서류 경로)
- [x] quote 재생성 시 `recipient_name = OpenAI Korea` 반영 확인

---

## 아직 안 된 것

| 항목 | 비고 |
|------|------|
| 브라우저 E2E (저장 버튼 클릭) 미확인 | company-settings UI에서 직접 저장 흐름 미검증 |
| quote 템플릿 `recipient_*` / `buyer_*` 전체 변수 직접 사용 미보강 | 템플릿이 해당 변수를 아직 직접 쓰지 않음 |
| 지출결의서 / 검수확인서 / 거래명세서 우리 회사 정보 반영 검증 | 다른 출력물에서 추가 확인 필요 |
| `usage_purpose` / `purchase_purpose` / `delivery_date` 빈 값 | expense_items 컬럼 없음, 프론트 입력 폼 필요 |
| `line_items` 규격/수량/단가 미반영 | 복수 품목 입력 UI 필요 |
| `inspection_confirmation` / `transaction_statement` DOCX 미전환 | 다음 단계 |

---

## 다음 작업 (우선순위 순)

1. **금액 표시 형식 수정** — 천 단위 콤마, 원 단위 표기 정비
2. **출력물별 양식 값 반영 점검** — 지출결의서/검수확인서/거래명세서 우리 회사 정보 확인
3. **과제 등록에 정부지원사업 정보 추가** — 과제 등록 폼 확장
4. **과제 등록에 연구원 등록 구조 추가** — 연구원 목록 관리 UI

---

## 기본 브랜치 / Docker 실행

- 브랜치: `master`
- 다음 컴퓨터에서도 **repo-master 기준**으로 Docker 실행 후 이어갈 것

```bash
# Docker 실행
docker compose up -d

# 마이그레이션 확인
docker exec rnd_backend bash -c "alembic current"

# 마이그레이션 적용 (필요 시)
docker exec rnd_backend bash -c "alembic upgrade head"

# 템플릿 재생성 (필요 시)
docker exec rnd_backend bash -c "python /app/make_docx_templates.py"
```

---

## 주의사항

- `quote` 문서는 `Vendor.quote_template_path` 사용 (시스템 템플릿 테이블 무시)
- `_find_template`: project-specific > global 우선순위
- `{%tr for item in line_items %}` 행과 content 행은 반드시 분리
- `test_*.py`, `test_outputs/`, `test_templates/` — 커밋 제외 (테스트용)

---

## RCMS 관련 금지사항

- RCMS 매뉴얼 연동 코드 수정 금지
- `skills/07_rcms_rag_skill.md` 범위 외 작업 금지
- RCMS 관련 API endpoint 변경 금지

---

## 현재 git 상태

- 브랜치: `master`
- 최신 commit: `a0fbffe` — (원격 최신)
- remote: `https://github.com/udam0907-gif/frontend.git`
- 미커밋 파일: `test_*.py`, `test_outputs/`, `test_templates/` (커밋 불필요)

---

## DB 주요 템플릿 (등록 현황)

| ID | 이름 | document_type | project_id |
|----|------|---------------|------------|
| `8a79a6a9` | 지출결의서 (DOCX) | expense_resolution | global |
| `fba83039` | 지출결의서 (DOCX) | expense_resolution | de8129c2 |
| `7c71ddc7` | 견적서 (DOCX) | quote | global |
| `2b5f3664` | 지출결의서 (원본) | expense_resolution | b315bd6b |
| `ec146f1d` | 유담 지출결의서 | expense_resolution | de8129c2 (XLSX, 구버전) |
