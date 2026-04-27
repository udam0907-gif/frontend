// ─── Enums ───────────────────────────────────────────────────────────────────

export type ProjectStatus = "active" | "closed" | "suspended";

export type CategoryType =
  | "outsourcing"
  | "labor"
  | "test_report"
  | "materials"
  | "meeting"
  | "other";

export type ExpenseStatus =
  | "draft"
  | "pending_validation"
  | "validated"
  | "rejected"
  | "exported";

export type ParseStatus = "pending" | "processing" | "completed" | "failed";

// ─── Project ─────────────────────────────────────────────────────────────────

export interface BudgetCategory {
  id: string;
  category_type: CategoryType;
  allocated_amount: number;
  spent_amount: number;
}

export interface Project {
  id: string;
  name: string;
  code: string;
  institution: string;
  principal_investigator: string;
  period_start: string;
  period_end: string;
  total_budget: number;
  status: ProjectStatus;
  agreement_file_path: string | null;
  plan_file_path: string | null;
  metadata_: Record<string, unknown>;
  budget_categories: BudgetCategory[];
  created_at: string;
}

export interface ProjectCreate {
  name: string;
  code: string;
  institution: string;
  principal_investigator: string;
  period_start: string;
  period_end: string;
  total_budget: number;
  budget_categories?: { category_type: CategoryType; allocated_amount: number }[];
  metadata?: Record<string, unknown>;
}

// ─── Template ────────────────────────────────────────────────────────────────

export interface Template {
  id: string;
  category_type: CategoryType;
  document_type: string;
  name: string;
  display_name: string; // 호환성 유지 — 백엔드 name 필드 별칭
  filename: string;
  version: number;
  field_map: Record<string, unknown>;
  is_active: boolean;
  project_id: string | null;
  created_at: string;
}

// ─── Expense ─────────────────────────────────────────────────────────────────

export interface ExpenseDocument {
  id: string;
  document_type: string;
  filename: string;
  file_path: string;
  file_size?: number | null;
  mime_type?: string | null;
  upload_status: string;
  created_at?: string;
  updated_at?: string;
}

export interface ExpenseItem {
  id: string;
  project_id: string;
  category_type: CategoryType;
  title: string;
  description: string | null;
  amount: number;
  vendor_name: string | null;
  expense_date: string | null;
  status: ExpenseStatus;
  input_data: ExpenseMetadata;
  documents: ExpenseDocument[];
  created_at: string;
}

export interface ExpenseLineItem {
  item_name?: string;
  spec?: string;
  quantity?: number;
  unit_price?: number;
  amount?: number;
  remark?: string;
}

export interface ExpenseMetadata {
  usage_purpose?: string;
  purchase_purpose?: string;
  delivery_date?: string;
  spec?: string;
  quantity?: number;
  unit_price?: number;
  amount?: number;
  line_items?: ExpenseLineItem[];
  [key: string]: unknown;
}

export interface ExpenseCreate {
  project_id: string;
  category_type: CategoryType;
  title: string;
  description?: string;
  amount: number;
  vendor_name?: string;
  expense_date?: string;
  metadata?: ExpenseMetadata;
}

// ─── Validation ──────────────────────────────────────────────────────────────

export interface ValidationCheck {
  code: string;
  message: string;
  field?: string;
}

export interface ValidationResult {
  id: string;
  expense_item_id: string;
  is_valid: boolean;
  blocking_errors: ValidationCheck[];
  warnings: ValidationCheck[];
  passed_checks: ValidationCheck[];
  validated_at: string;
}

// ─── RCMS ────────────────────────────────────────────────────────────────────

export interface RcmsManual {
  id: string;
  filename: string;
  original_filename: string;
  display_name: string;
  version: string;
  parse_status: ParseStatus;
  total_chunks: number | null;
  created_at: string;
}

export type QuestionType = "rcms_procedure" | "legal_policy" | "mixed" | "definition";

export type AnswerStatus =
  | "answered_with_evidence"
  | "not_found_in_uploaded_manuals";

export type AnswerStatusType =
  | "answered_with_direct_evidence"
  | "answered_with_mixed_sources"
  | "related_context_only"
  | "insufficient_evidence"
  | "not_found_in_uploaded_materials"
  | "routing_error";

/** Evidence from either a legal document or an RCMS manual. */
export interface EvidenceChunk {
  source_type: "legal" | "rcms";
  evidence_tier?: 1 | 2 | 3;
  source_label?: string; // "법령 원문 근거" | "공식 FAQ/운영안내 근거" | "일반 참고 문맥"

  // RCMS manual fields
  manual_id?: string;
  display_name?: string;

  // Legal document fields
  law_name?: string;
  article_number?: string;
  article_title?: string;

  // Common
  page?: number | null;
  section_title?: string | null;
  excerpt: string;
  confidence: number;
  chunk_id?: string;
  is_decisive?: boolean;
}

export interface DebugInfo {
  question_type: string;
  normalized_query: string;
  expanded_queries: string[];
  routing_decision: string;
  rcms_candidates: Array<{
    chunk_id: string;
    display_name: string;
    page: number | null;
    section: string;
    similarity: number;
    excerpt: string;
  }>;
  legal_candidates: Array<{
    chunk_id: string;
    law_name: string;
    article: string;
    similarity: number;
    excerpt: string;
  }>;
  rule_cards: unknown[];
  answerability: {
    status: string;
    has_direct_evidence: boolean;
    explanation: string;
  };
}

export interface RcmsQaResponse {
  question_type: QuestionType;
  short_answer: string;
  conclusion: string | null;
  conditions_or_exceptions: string | null;
  legal_basis: string | null;
  rcms_steps: string | null;
  detailed_explanation: string;
  further_confirmation_needed: boolean;
  confidence: "high" | "medium" | "low";
  evidence: EvidenceChunk[];
  found_in_manual: boolean;
  answer_status: string;
  answer_status_type: AnswerStatusType;
  question_understanding?: {
    question_type: QuestionType;
    normalized_query: string;
    expanded_queries: string[];
    routing_decision: string;
  };
  debug?: DebugInfo | null;
  model_version: string;
  prompt_version: string;
}

export interface RcmsQaSession {
  id: string;
  question: string;
  answer: {
    question_type?: QuestionType;
    short_answer: string;
    conclusion?: string | null;
    conditions_or_exceptions?: string | null;
    legal_basis?: string | null;
    rcms_steps?: string | null;
    detailed_explanation: string;
    evidence: EvidenceChunk[];
    found_in_manual: boolean;
    answer_status: string;
  };
  model_version: string;
  prompt_version: string;
  created_at: string;
}

// ─── Legal documents ──────────────────────────────────────────────────────────

export interface LegalDoc {
  id: string;
  law_name: string;
  law_mst: string;
  source_type: string;   // "api" | "upload"
  promulgation_date: string | null;
  effective_date: string | null;
  total_articles: number | null;
  total_chunks: number | null;
  sync_status: ParseStatus;
  sync_error: string | null;
  created_at: string;
}

// ─── Dashboard ───────────────────────────────────────────────────────────────

export interface DashboardStats {
  total_projects: number;
  active_projects: number;
  total_expenses: number;
  pending_validation: number;
  validated: number;
  rejected: number;
}

// ─── Vendor ──────────────────────────────────────────────────────────────────

export type VendorCategory = "매입처" | "매출처";

export interface Vendor {
  id: string;
  project_id: string;
  name: string;
  vendor_category: VendorCategory;
  business_number: string;
  contact: string | null;
  business_registration_path: string | null;
  bank_copy_path: string | null;
  quote_template_path: string | null;
  transaction_statement_path: string | null;
  created_at: string;
  updated_at: string;
}

export interface VendorCreate {
  project_id: string;
  name: string;
  vendor_category: VendorCategory;
  business_number: string;
  contact?: string;
}

// ─── Document Set ─────────────────────────────────────────────────────────────

export type DocSetItemStatus =
  | "excel_rendered"              // XLSX 셀 매핑으로 값 입력 완료 (업체 양식 포함)
  | "vendor_attachment_included"  // 업체 파일 바이너리 첨부 (사업자등록증/통장사본 등)
  | "mapping_needed"              // XLSX이지만 셀 매핑 미설정 (원본 복사)
  | "render_failed"               // 렌더링 예외
  | "template_missing"            // 어느 소스에서도 파일 없음
  | "vendor_file_missing";        // 업체/비교견적업체 파일 슬롯 비어 있음

// ─── Cell Mapping ────────────────────────────────────────────────────────────

export interface FieldRegistryItem {
  key: string;
  label: string;
  type: "text" | "number" | "date";
  required: boolean;
}

export interface FieldMapEntry {
  label: string;
  type: string;
  required: boolean;
  cell?: string;
  _meta?: { source?: string };
}

export interface DocSetItem {
  document_type: string;
  status: DocSetItemStatus;
  output_path: string | null;
  generated_document_id: string | null;
  error_message: string | null;
  is_vendor_doc: boolean;
}

export interface DocumentSetResponse {
  expense_item_id: string;
  category_type: string;
  total: number;
  generated: number;
  errors: number;
  all_generated: boolean;
  items: DocSetItem[];
}

// ─── Project Researcher ──────────────────────────────────────────────────────

export interface ProjectResearcher {
  id: string;
  project_id: string;
  personnel_type: "기존" | "신규";
  name: string;
  position: string | null;
  annual_salary: number | null;
  monthly_salary: number | null;
  participation_months: number | null;
  participation_rate: number | null;
  cash_amount: number | null;
  in_kind_amount: number | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface ResearcherCreate {
  personnel_type: "기존" | "신규";
  name: string;
  position?: string | null;
  annual_salary?: number | null;
  monthly_salary?: number | null;
  participation_months?: number | null;
  participation_rate?: number | null;
  cash_amount?: number | null;
  in_kind_amount?: number | null;
  sort_order?: number;
}

export interface ExtractedBudgetCategory {
  category_type: CategoryType;
  allocated_amount: number;
}

export interface ExtractedProjectData {
  name: string | null;
  code: string | null;
  institution: string | null;
  principal_investigator: string | null;
  period_start: string | null;
  period_end: string | null;
  total_budget: number | null;
  budget_categories: ExtractedBudgetCategory[];
  researchers: ResearcherCreate[];
  overview: string | null;
  deliverables: string | null;
  schedule: string | null;
  doc_type: string;
  confidence: number;
}

// ─── API ─────────────────────────────────────────────────────────────────────

export interface ApiError {
  error: string;
  message: string;
  details?: unknown;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export type CompanySettingsUploadType =
  | "business_registration"
  | "bank_copy"
  | "quote_template"
  | "transaction_statement_template"
  | "seal_image";

export interface CompanySettingsFileStatus {
  path: string | null;
  exists: boolean;
  file_name: string | null;
  updated_at: string | null;
}

export interface CompanySettings {
  id: string | null;
  company_id: string;
  company_name: string | null;
  company_registration_number: string | null;
  representative_name: string | null;
  address: string | null;
  business_type: string | null;
  business_item: string | null;
  phone: string | null;
  fax: string | null;
  email: string | null;
  seal_image_path: string | null;
  company_business_registration_path: string | null;
  company_bank_copy_path: string | null;
  company_quote_template_path: string | null;
  company_transaction_statement_template_path: string | null;
  file_statuses: Record<CompanySettingsUploadType, CompanySettingsFileStatus>;
  created_at: string | null;
  updated_at: string | null;
}

export interface CompanySettingsUpdate {
  company_id?: string;
  company_name?: string;
  company_registration_number?: string;
  representative_name?: string;
  address?: string;
  business_type?: string;
  business_item?: string;
  phone?: string;
  fax?: string;
  email?: string;
  seal_image_path?: string;
  company_business_registration_path?: string;
  company_bank_copy_path?: string;
  company_quote_template_path?: string;
  company_transaction_statement_template_path?: string;
}

export interface CompanySettingsExtractedFields {
  company_name?: string | null;
  company_registration_number?: string | null;
  representative_name?: string | null;
  address?: string | null;
  business_type?: string | null;
  business_item?: string | null;
  phone?: string | null;
  fax?: string | null;
  email?: string | null;
}

export interface CompanySettingsExtractResponse {
  company_id: string;
  extracted: CompanySettingsExtractedFields;
  source_by_field: Record<string, string>;
  used_files: string[];
}
