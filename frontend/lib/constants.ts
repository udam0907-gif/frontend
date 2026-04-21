import type { CategoryType } from "./types";

export const CATEGORY_LABELS: Record<CategoryType, string> = {
  outsourcing: "외주비",
  labor: "인건비",
  test_report: "시험·검사비",
  materials: "재료비",
  meeting: "회의비",
  other: "기타",
};

export const REQUIRED_DOCS: Record<CategoryType, { key: string; label: string }[]> = {
  outsourcing: [
    { key: "quote", label: "견적서" },
    { key: "comparative_quote", label: "비교견적서" },
    { key: "service_contract", label: "용역계약서" },
    { key: "work_order", label: "작업지시서" },
    { key: "transaction_statement", label: "거래명세서" },
    { key: "inspection_photos", label: "검수 사진" },
    { key: "vendor_business_registration", label: "사업자등록증" },
    { key: "vendor_bank_copy", label: "통장사본" },
  ],
  labor: [
    { key: "cash_expense_resolution", label: "현금인건비 집행결의서" },
    { key: "in_kind_expense_resolution", label: "현물인건비 집행결의서" },
    { key: "researcher_status_sheet", label: "연구원 현황표" },
  ],
  test_report: [
    { key: "quote", label: "견적서" },
    { key: "expense_resolution", label: "집행결의서" },
    { key: "transaction_statement", label: "거래명세서" },
  ],
  materials: [
    { key: "quote", label: "견적서" },
    { key: "comparative_quote", label: "비교견적서" },
    { key: "expense_resolution", label: "집행결의서" },
    { key: "inspection_confirmation", label: "검수확인서" },
    { key: "vendor_business_registration", label: "사업자등록증" },
    { key: "vendor_bank_copy", label: "통장사본" },
  ],
  meeting: [
    { key: "receipt", label: "영수증" },
    { key: "meeting_minutes", label: "회의록" },
  ],
  other: [],
};

export const EXPENSE_STATUS_LABELS: Record<string, string> = {
  draft: "작성 중",
  pending_validation: "검증 대기",
  validated: "검증 완료",
  rejected: "반려",
  exported: "내보내기 완료",
};

export const EXPENSE_STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  pending_validation: "bg-yellow-100 text-yellow-700",
  validated: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
  exported: "bg-blue-100 text-blue-700",
};

export const PROJECT_STATUS_LABELS: Record<string, string> = {
  active: "진행 중",
  closed: "종료",
  suspended: "중단",
};

export const PARSE_STATUS_LABELS: Record<string, string> = {
  pending: "대기 중",
  processing: "처리 중",
  completed: "완료",
  failed: "실패",
};

// ─── 비목별 필수 문서세트 ─────────────────────────────────────────────────────

export interface DocumentSetItem {
  key: string;
  label: string;
  note?: string;
}

export const DOCUMENT_SETS: Record<CategoryType, DocumentSetItem[]> = {
  materials: [
    { key: "quote", label: "견적서" },
    { key: "comparative_quote", label: "비교견적서", note: "원금액 × 1.1 자동계산" },
    { key: "expense_resolution", label: "지출결의서" },
    { key: "inspection_confirmation", label: "검수확인서" },
    { key: "vendor_business_registration", label: "업체 사업자등록증" },
    { key: "vendor_bank_copy", label: "업체 통장사본" },
  ],
  outsourcing: [
    { key: "quote", label: "견적서" },
    { key: "comparative_quote", label: "비교견적서", note: "원금액 × 1.1 자동계산" },
    { key: "service_contract", label: "용역계약서" },
    { key: "work_order", label: "과업지시서" },
    { key: "transaction_statement", label: "거래명세서" },
    { key: "inspection_photos", label: "검수사진" },
    { key: "vendor_business_registration", label: "업체 사업자등록증" },
    { key: "vendor_bank_copy", label: "업체 통장사본" },
  ],
  labor: [
    { key: "cash_expense_resolution", label: "지출결의서_현금" },
    { key: "in_kind_expense_resolution", label: "지출결의서_현물" },
    { key: "researcher_status_sheet", label: "참여연구원 현황표" },
  ],
  test_report: [
    { key: "quote", label: "견적서" },
    { key: "expense_resolution", label: "지출결의서" },
    { key: "transaction_statement", label: "거래명세서" },
  ],
  meeting: [
    { key: "receipt", label: "영수증" },
    { key: "meeting_minutes", label: "회의내용" },
  ],
  other: [],
};
