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
}

// ─── Template ────────────────────────────────────────────────────────────────

export interface Template {
  id: string;
  category_type: CategoryType;
  document_type: string;
  display_name: string;
  filename: string;
  version: number;
  field_map: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
}

// ─── Expense ─────────────────────────────────────────────────────────────────

export interface ExpenseDocument {
  id: string;
  document_type: string;
  original_filename: string;
  upload_status: string;
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
  input_data: Record<string, unknown>;
  documents: ExpenseDocument[];
  created_at: string;
}

export interface ExpenseCreate {
  project_id: string;
  category_type: CategoryType;
  title: string;
  description?: string;
  amount: number;
  vendor_name?: string;
  expense_date?: string;
  input_data?: Record<string, unknown>;
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

export type QuestionType = "rcms_procedure" | "legal_policy" | "mixed";

export type AnswerStatus =
  | "answered_with_evidence"
  | "not_found_in_uploaded_manuals";

/** Evidence from either a legal document or an RCMS manual. */
export interface EvidenceChunk {
  source_type: "legal" | "rcms";

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
}

export interface RcmsQaResponse {
  question_type: QuestionType;
  short_answer: string;
  conclusion: string | null;
  legal_basis: string | null;
  rcms_steps: string | null;
  detailed_explanation: string;
  evidence: EvidenceChunk[];
  found_in_manual: boolean;
  answer_status: AnswerStatus;
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
    legal_basis?: string | null;
    rcms_steps?: string | null;
    detailed_explanation: string;
    evidence: EvidenceChunk[];
    found_in_manual: boolean;
    answer_status: AnswerStatus;
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
