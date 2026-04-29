import axios, { AxiosError } from "axios";
import type {
  Project,
  ProjectCreate,
  ProjectResearcher,
  ResearcherCreate,
  ExtractedProjectData,
  Template,
  ExpenseItem,
  ExpenseCreate,
  ValidationResult,
  RcmsManual,
  RcmsQaResponse,
  RcmsQaSession,
  LegalDoc,
  DashboardStats,
  PaginatedResponse,
  Vendor,
  VendorCreate,
  DocumentSetResponse,
  FieldRegistryItem,
  CompanySettings,
  CompanySettingsExtractResponse,
  CompanySettingsUpdate,
  CompanySettingsUploadType,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.response.use(
  (res) => res,
  (err: AxiosError) => {
    const data = err.response?.data as { message?: string; detail?: string | { detail?: string } } | undefined;
    const detail =
      typeof data?.detail === "string"
        ? data.detail
        : typeof data?.detail === "object" && data.detail && "detail" in data.detail
          ? data.detail.detail
          : undefined;
    const msg = data?.message ?? detail ?? err.message;
    return Promise.reject(new Error(msg));
  }
);

// ─── Projects ────────────────────────────────────────────────────────────────

export const projectsApi = {
  list: () => apiClient.get<Project[]>("/projects").then((r) => r.data),

  get: (id: string) =>
    apiClient.get<Project>(`/projects/${id}`).then((r) => r.data),

  create: (data: ProjectCreate) =>
    apiClient.post<Project>("/projects", data).then((r) => r.data),

  update: (id: string, data: Partial<Pick<ProjectCreate, "name" | "institution" | "principal_investigator" | "period_start" | "period_end" | "total_budget" | "status"> & { metadata?: Record<string, unknown> }>) =>
    apiClient.patch<Project>(`/projects/${id}`, data).then((r) => r.data),

  updateMetadata: (id: string, metadata: Record<string, unknown>) =>
    apiClient.patch<{ status: string }>(`/projects/${id}/metadata`, metadata).then((r) => r.data),

  uploadFile: (id: string, type: "agreement" | "plan", file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient
      .post<Project>(`/projects/${id}/${type}`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },

  extractPdf: (docType: "auto" | "plan" | "agreement" | "researcher", file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient
      .post<ExtractedProjectData>(`/projects/extract-pdf?doc_type=${docType}`, form, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 120000,
      })
      .then((r) => r.data);
  },

  listResearchers: (projectId: string) =>
    apiClient
      .get<ProjectResearcher[]>(`/projects/${projectId}/researchers`)
      .then((r) => r.data),

  upsertResearchers: (projectId: string, researchers: ResearcherCreate[]) =>
    apiClient
      .post<ProjectResearcher[]>(`/projects/${projectId}/researchers`, researchers)
      .then((r) => r.data),
};

// ─── Templates ───────────────────────────────────────────────────────────────

export const templatesApi = {
  list: (categoryType?: string, projectId?: string) =>
    apiClient
      .get<Template[]>("/templates", {
        params: { category_type: categoryType, project_id: projectId },
      })
      .then((r) => r.data),

  upload: (
    categoryType: string,
    documentType: string,
    displayName: string,
    file: File,
    projectId?: string
  ) => {
    const form = new FormData();
    form.append("file", file);
    form.append("category_type", categoryType);
    form.append("document_type", documentType);
    form.append("name", displayName);
    if (projectId) form.append("project_id", projectId);
    return apiClient
      .post<Template>("/templates", form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },

  deactivate: (id: string) =>
    apiClient.delete(`/templates/${id}`).then((r) => r.data),

  getFieldRegistry: () =>
    apiClient
      .get<{ fields: FieldRegistryItem[] }>("/templates/fields/registry")
      .then((r) => r.data.fields),

  setCellMapping: (id: string, mapping: Record<string, string>) =>
    apiClient
      .put<Template>(`/templates/${id}/cell-mapping`, { mapping })
      .then((r) => r.data),

  getRenderProfile: (id: string) =>
    apiClient
      .get<{ template_id: string; document_type: string; render_profile: Record<string, unknown> | null; strategy_examples: Record<string, unknown> }>(`/templates/${id}/render-profile`)
      .then((r) => r.data),

  setRenderProfile: (id: string, profile: Record<string, unknown>) =>
    apiClient
      .put<Template>(`/templates/${id}/render-profile`, profile)
      .then((r) => r.data),

  clearRenderProfile: (id: string) =>
    apiClient
      .delete<Template>(`/templates/${id}/render-profile`)
      .then((r) => r.data),
};

// ─── Expenses ────────────────────────────────────────────────────────────────

export const expensesApi = {
  list: (projectId?: string, status?: string) =>
    apiClient
      .get<ExpenseItem[]>("/expenses", { params: { project_id: projectId, status } })
      .then((r) => r.data),

  get: (id: string) =>
    apiClient.get<ExpenseItem>(`/expenses/${id}`).then((r) => r.data),

  create: (data: ExpenseCreate) =>
    apiClient.post<ExpenseItem>("/expenses", data).then((r) => r.data),

  update: (id: string, data: Partial<ExpenseCreate>) =>
    apiClient.patch<ExpenseItem>(`/expenses/${id}`, data).then((r) => r.data),

  delete: (id: string) =>
    apiClient.delete(`/expenses/${id}`).then((r) => r.data),

  uploadDocument: (expenseId: string, documentType: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    form.append("document_type", documentType);
    return apiClient
      .post(`/expenses/${expenseId}/documents`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },

  deleteDocument: (expenseId: string, documentId: string) =>
    apiClient.delete(`/expenses/${expenseId}/documents/${documentId}`).then((r) => r.data),
};

// ─── Validation ──────────────────────────────────────────────────────────────

export const validationApi = {
  validate: (expenseId: string) =>
    apiClient
      .post<ValidationResult>(`/validation/${expenseId}`)
      .then((r) => r.data),

  getResult: (expenseId: string) =>
    apiClient
      .get<ValidationResult>(`/validation/${expenseId}`)
      .then((r) => r.data),
};

// ─── Export ──────────────────────────────────────────────────────────────────

export const exportApi = {
  generate: (expenseId: string) =>
    apiClient
      .post<{ download_url: string }>(`/export/${expenseId}`)
      .then((r) => r.data),
};

// ─── RCMS ────────────────────────────────────────────────────────────────────

export const rcmsApi = {
  listManuals: () =>
    apiClient.get<RcmsManual[]>("/rcms/manuals").then((r) => r.data),

  uploadManual: (displayName: string, version: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    form.append("display_name", displayName);
    form.append("version", version);
    return apiClient
      .post<RcmsManual>("/rcms/manuals", form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },

  ask: (question: string, manualIds?: string[], debug?: boolean) =>
    apiClient
      .post<RcmsQaResponse>("/rcms/qa", {
        question,
        manual_ids: manualIds,
        debug: debug ?? false,
      })
      .then((r) => r.data),

  listSessions: () =>
    apiClient.get<RcmsQaSession[]>("/rcms/qa/history").then((r) => r.data),

  deleteManual: (id: string) =>
    apiClient.delete(`/rcms/manuals/${id}`).then((r) => r.data),
};

// ─── Legal documents ──────────────────────────────────────────────────────────

export const legalApi = {
  list: () =>
    apiClient.get<LegalDoc[]>("/rcms/laws").then((r) => r.data),

  syncLaw: (lawName: string, lawMst?: string) =>
    apiClient
      .post<{ message: string; law_name: string }>("/rcms/laws/sync", {
        law_name: lawName,
        law_mst: lawMst ?? null,
      })
      .then((r) => r.data),

  syncDefaults: () =>
    apiClient
      .post<{ message: string; laws: string[] }>("/rcms/laws/sync-defaults")
      .then((r) => r.data),

  delete: (id: string) =>
    apiClient.delete(`/rcms/laws/${id}`).then((r) => r.data),
};

// ─── Vendors ─────────────────────────────────────────────────────────────────

export interface VendorExtractResult {
  vendor_name: string | null;
  business_number: string | null;
  contact: string | null;
  source: string;
  confidence: Record<string, number>;
}

export const vendorsApi = {
  list: (projectId: string) =>
    apiClient
      .get<Vendor[]>("/vendors", { params: { project_id: projectId } })
      .then((r) => r.data),

  create: (data: VendorCreate) =>
    apiClient.post<Vendor>("/vendors", data).then((r) => r.data),

  update: (id: string, data: Partial<VendorCreate>) =>
    apiClient.patch<Vendor>(`/vendors/${id}`, data).then((r) => r.data),

  delete: (id: string) =>
    apiClient.delete(`/vendors/${id}`).then((r) => r.data),

  extractInfo: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient
      .post<VendorExtractResult>("/vendors/extract", form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },

  uploadFile: (
    id: string,
    fileType:
      | "business_registration"
      | "bank_copy"
      | "quote_template"
      | "transaction_statement",
    file: File
  ) => {
    const form = new FormData();
    form.append("file", file);
    form.append("file_type", fileType);
    return apiClient
      .post<Vendor>(`/vendors/${id}/files`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },
};

// ─── Document Sets ────────────────────────────────────────────────────────────

export const documentSetsApi = {
  generate: (expenseId: string) =>
    apiClient
      .post<DocumentSetResponse>(`/documents/generate-set/${expenseId}`)
      .then((r) => r.data),

  latestSet: (expenseId: string) =>
    apiClient
      .get<DocumentSetResponse>(`/documents/latest-set/${expenseId}`)
      .then((r) => r.data),

  getStatus: (expenseId: string) =>
    apiClient
      .get<{
        expense_item_id: string;
        total_generated: number;
        documents: unknown[];
      }>(`/documents/set-status/${expenseId}`)
      .then((r) => r.data),

  downloadUrl: (documentId: string) =>
    `${BASE_URL}/api/v1/documents/${documentId}/download`,
};

// ─── Projects stats (aggregated on frontend from list) ───────────────────────
// Dashboard uses projectsApi.list() + expensesApi.list() directly

// ─── Backup ──────────────────────────────────────────────────────────────────

export interface BackupFile {
  name: string;
  size_bytes: number;
  size_label: string;
  type_label: string;
  suffix: string;
  created_at: string;
}

export const backupApi = {
  listFiles: () =>
    apiClient.get<BackupFile[]>("/backup/files").then((r) => r.data),

  getRestoreGuide: () =>
    apiClient.get<{ content: string }>("/backup/restore-guide").then((r) => r.data),

  downloadUrl: (filename: string) =>
    `${BASE_URL}/api/v1/backup/download/${encodeURIComponent(filename)}`,
};

// ─── Company Settings ─────────────────────────────────────────────────────────

export const companySettingsApi = {
  get: (companyId = "default") =>
    apiClient
      .get<CompanySettings>("/company-settings", { params: { company_id: companyId } })
      .then((r) => r.data),

  update: (data: CompanySettingsUpdate) =>
    apiClient.put<CompanySettings>("/company-settings", data).then((r) => r.data),

  uploadFile: (companyId: string, fileType: CompanySettingsUploadType, file: File) => {
    const form = new FormData();
    form.append("company_id", companyId);
    form.append("file_type", fileType);
    form.append("file", file);
    return apiClient
      .post<CompanySettings>("/company-settings/files", form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },

  deleteFile: (companyId: string, fileType: CompanySettingsUploadType) =>
    apiClient
      .delete<CompanySettings>("/company-settings/files", {
        params: { company_id: companyId, file_type: fileType },
      })
      .then((r) => r.data),

  extract: (companyId = "default", fileType?: CompanySettingsUploadType) =>
    apiClient
      .post<CompanySettingsExtractResponse>("/company-settings/extract", null, {
        params: { company_id: companyId, file_type: fileType },
      })
      .then((r) => r.data),
};
