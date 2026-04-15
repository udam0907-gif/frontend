import axios, { AxiosError } from "axios";
import type {
  Project,
  ProjectCreate,
  Template,
  ExpenseItem,
  ExpenseCreate,
  ValidationResult,
  RcmsManual,
  RcmsQaResponse,
  RcmsQaSession,
  DashboardStats,
  PaginatedResponse,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.response.use(
  (res) => res,
  (err: AxiosError) => {
    const msg =
      (err.response?.data as { message?: string })?.message ?? err.message;
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

  uploadFile: (id: string, type: "agreement" | "plan", file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient
      .post<Project>(`/projects/${id}/${type}`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },
};

// ─── Templates ───────────────────────────────────────────────────────────────

export const templatesApi = {
  list: (categoryType?: string) =>
    apiClient
      .get<Template[]>("/templates", { params: { category_type: categoryType } })
      .then((r) => r.data),

  upload: (
    categoryType: string,
    documentType: string,
    displayName: string,
    file: File
  ) => {
    const form = new FormData();
    form.append("file", file);
    form.append("category_type", categoryType);
    form.append("document_type", documentType);
    form.append("display_name", displayName);
    return apiClient
      .post<Template>("/templates", form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },

  deactivate: (id: string) =>
    apiClient.delete(`/templates/${id}`).then((r) => r.data),
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

  ask: (question: string, manualIds?: string[]) =>
    apiClient
      .post<RcmsQaResponse>("/rcms/qa", { question, manual_ids: manualIds })
      .then((r) => r.data),

  listSessions: () =>
    apiClient.get<RcmsQaSession[]>("/rcms/qa/history").then((r) => r.data),

  deleteManual: (id: string) =>
    apiClient.delete(`/rcms/manuals/${id}`).then((r) => r.data),
};

// ─── Projects stats (aggregated on frontend from list) ───────────────────────
// Dashboard uses projectsApi.list() + expensesApi.list() directly
