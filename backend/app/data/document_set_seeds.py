"""비목별 문서세트 시드 데이터 — 작업지시서 §2-2~§2-7 매트릭스 기준."""

DOCUMENT_SET_SEEDS = [
    # ───────── 외주가공 ─────────
    {"category": "outsourcing", "doc_kind": "quotation",             "source": "AUTO",       "is_required": True,  "sort_order": 1},
    {"category": "outsourcing", "doc_kind": "comparative_quotation", "source": "AUTO",       "is_required": True,  "sort_order": 2},
    {"category": "outsourcing", "doc_kind": "service_contract",      "source": "AUTO",       "is_required": True,  "sort_order": 3,
     "template_path": "templates/외주가공/용역계약서.docx"},
    {"category": "outsourcing", "doc_kind": "task_order",            "source": "AUTO",       "is_required": True,  "sort_order": 4,
     "template_path": "templates/외주가공/과업지시서.docx"},
    {"category": "outsourcing", "doc_kind": "delivery_note",         "source": "AUTO",       "is_required": True,  "sort_order": 5},
    {"category": "outsourcing", "doc_kind": "expense_resolution",    "source": "AUTO",       "is_required": True,  "sort_order": 6},
    {"category": "outsourcing", "doc_kind": "inspection_photo",      "source": "INPUT_FILL", "is_required": True,  "sort_order": 7,
     "upload_hint": "검수 현장 사진(JPG/PNG)을 1장 이상 업로드해주세요."},
    {"category": "outsourcing", "doc_kind": "tax_invoice",           "source": "UPLOAD",     "is_required": True,  "sort_order": 8,
     "upload_hint": "홈택스(hometax.go.kr) → 조회/발급 → 전자세금계산서 → PDF 다운로드 후 업로드해주세요."},
    {"category": "outsourcing", "doc_kind": "transfer_receipt",      "source": "UPLOAD",     "is_required": True,  "sort_order": 9,
     "upload_hint": "거래은행 인터넷뱅킹 → 이체결과 조회 → 이체확인증 PDF 발급 후 업로드해주세요."},

    # ───────── 시험분석비 (test_report enum 그대로 사용) ─────────
    {"category": "test_report", "doc_kind": "quotation",                    "source": "UPLOAD", "is_required": True,  "sort_order": 1,
     "upload_hint": "시험기관에서 발급한 견적서 PDF/JPG를 업로드해주세요."},
    {"category": "test_report", "doc_kind": "external_application",         "source": "AUTO",   "is_required": True,  "sort_order": 2,
     "template_path": "templates/시험분석/외부신청서_동의서.docx"},
    {"category": "test_report", "doc_kind": "delivery_note",                "source": "UPLOAD", "is_required": False, "sort_order": 3,
     "upload_hint": "시험기관 발급 거래명세서 (있는 경우)"},
    {"category": "test_report", "doc_kind": "test_certificate",             "source": "UPLOAD", "is_required": True,  "sort_order": 4,
     "upload_hint": "공인기관 발급 시험성적서 PDF (필수 증빙 — 누락 시 검증 차단)"},
    {"category": "test_report", "doc_kind": "expense_resolution",           "source": "AUTO",   "is_required": True,  "sort_order": 5},
    {"category": "test_report", "doc_kind": "tax_invoice",                  "source": "UPLOAD", "is_required": True,  "sort_order": 6,
     "upload_hint": "홈택스 발행 세금계산서 PDF"},
    {"category": "test_report", "doc_kind": "transfer_receipt",             "source": "UPLOAD", "is_required": True,  "sort_order": 7,
     "upload_hint": "은행 발급 입금확인증 PDF"},
    {"category": "test_report", "doc_kind": "vendor_business_registration", "source": "UPLOAD", "is_required": False, "sort_order": 8},
    {"category": "test_report", "doc_kind": "vendor_bank_copy",             "source": "UPLOAD", "is_required": False, "sort_order": 9},

    # ───────── 인건비 ─────────
    {"category": "labor", "doc_kind": "researcher_status",       "source": "AUTO",   "is_required": True,  "sort_order": 1,
     "template_path": "templates/인건비/참여연구원현황표.docx"},
    {"category": "labor", "doc_kind": "payslip",                 "source": "AUTO",   "is_required": True,  "sort_order": 2,
     "template_path": "templates/인건비/급여명세서.docx"},
    {"category": "labor", "doc_kind": "expense_resolution_cash", "source": "AUTO",   "is_required": True,  "sort_order": 3,
     "template_path": "templates/인건비/지출결의서_현금.docx"},
    {"category": "labor", "doc_kind": "expense_resolution_inkind","source": "AUTO",   "is_required": False, "sort_order": 4,
     "template_path": "templates/인건비/지출결의서_현물.docx"},
    {"category": "labor", "doc_kind": "transfer_receipt",        "source": "UPLOAD", "is_required": True,  "sort_order": 5,
     "upload_hint": "급여 이체확인증 PDF (매월)"},
    {"category": "labor", "doc_kind": "health_insurance",        "source": "UPLOAD", "is_required": False, "sort_order": 6,
     "upload_hint": "신규채용자 1회 — 건강보험공단(nhis.or.kr) 자격득실확인서"},

    # ───────── 연구활동비 (신규) ─────────
    {"category": "research_activity", "doc_kind": "quotation",                    "source": "UPLOAD", "is_required": False, "sort_order": 1,
     "upload_hint": "운영기관 발급 견적서 (있는 경우)"},
    {"category": "research_activity", "doc_kind": "billing_letter",              "source": "UPLOAD", "is_required": True,  "sort_order": 2,
     "upload_hint": "운영기관 청구 공문 PDF"},
    {"category": "research_activity", "doc_kind": "expense_resolution",          "source": "AUTO",   "is_required": True,  "sort_order": 3,
     "template_path": "templates/연구활동비/지출결의서.docx"},
    {"category": "research_activity", "doc_kind": "tax_invoice",                 "source": "UPLOAD", "is_required": True,  "sort_order": 4},
    {"category": "research_activity", "doc_kind": "transfer_receipt",            "source": "UPLOAD", "is_required": True,  "sort_order": 5},
    {"category": "research_activity", "doc_kind": "vendor_business_registration","source": "UPLOAD", "is_required": False, "sort_order": 6},
    {"category": "research_activity", "doc_kind": "vendor_bank_copy",            "source": "UPLOAD", "is_required": False, "sort_order": 7},

    # ───────── 간접비(신용평가) (신규) ─────────
    {"category": "indirect_credit", "doc_kind": "credit_report",      "source": "UPLOAD", "is_required": True,  "sort_order": 1,
     "upload_hint": "기업신용평가기관 발급 평가서 PDF"},
    {"category": "indirect_credit", "doc_kind": "expense_resolution", "source": "AUTO",   "is_required": True,  "sort_order": 2,
     "template_path": "templates/간접비/지출결의서.docx"},
    {"category": "indirect_credit", "doc_kind": "tax_invoice",        "source": "UPLOAD", "is_required": True,  "sort_order": 3},
    {"category": "indirect_credit", "doc_kind": "transfer_receipt",   "source": "UPLOAD", "is_required": True,  "sort_order": 4},

    # ───────── 위탁정산비 (신규) ─────────
    {"category": "entrusted_audit", "doc_kind": "expense_resolution",          "source": "AUTO",   "is_required": True,  "sort_order": 1,
     "template_path": "templates/위탁정산비/지출결의서.docx"},
    {"category": "entrusted_audit", "doc_kind": "tax_invoice",                 "source": "UPLOAD", "is_required": True,  "sort_order": 2},
    {"category": "entrusted_audit", "doc_kind": "transfer_receipt",            "source": "UPLOAD", "is_required": True,  "sort_order": 3,
     "upload_hint": "부가세 입금확인증 PDF"},
    {"category": "entrusted_audit", "doc_kind": "vendor_business_registration","source": "UPLOAD", "is_required": False, "sort_order": 4},
    {"category": "entrusted_audit", "doc_kind": "vendor_bank_copy",            "source": "UPLOAD", "is_required": False, "sort_order": 5},

    # 재료비는 시드 미포함 (기존 DOCUMENT_SETS 코드 상수가 그대로 작동)
]
