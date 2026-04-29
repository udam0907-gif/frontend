"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { companySettingsApi } from "@/lib/api";
import { TemplatesPanel } from "@/components/company/TemplatesPanel";
import type {
  CompanySettingsExtractedFields,
  CompanySettingsUpdate,
  CompanySettingsUploadType,
} from "@/lib/types";

type TabId = "info" | "templates";

const TABS: { id: TabId; label: string }[] = [
  { id: "info", label: "회사 정보" },
  { id: "templates", label: "템플릿 관리" },
];

const DEFAULT_COMPANY_ID = "default";

const emptyForm: CompanySettingsUpdate = {
  company_id: DEFAULT_COMPANY_ID,
  company_name: "",
  company_registration_number: "",
  representative_name: "",
  address: "",
  business_type: "",
  business_item: "",
  phone: "",
  fax: "",
  email: "",
  seal_image_path: "",
};

const fileLabels: Record<CompanySettingsUploadType, string> = {
  business_registration: "사업자등록증",
  bank_copy: "통장사본",
  quote_template: "견적서 양식",
  transaction_statement_template: "거래명세서 양식",
  seal_image: "직인 이미지",
};

const autoExtractFieldLabels: Record<keyof CompanySettingsExtractedFields, string> = {
  company_name: "회사명",
  company_registration_number: "사업자등록번호",
  representative_name: "대표자명",
  address: "주소",
  business_type: "업태",
  business_item: "업종",
  phone: "전화번호",
  fax: "팩스",
  email: "이메일",
};

const autoExtractFields = Object.keys(autoExtractFieldLabels) as Array<keyof CompanySettingsExtractedFields>;
const extractableFileTypes: CompanySettingsUploadType[] = [
  "business_registration",
  "quote_template",
  "transaction_statement_template",
];
const businessRegistrationFields: Array<keyof CompanySettingsExtractedFields> = [
  "company_name",
  "company_registration_number",
  "representative_name",
  "address",
  "business_type",
  "business_item",
];
const contactFields: Array<keyof CompanySettingsExtractedFields> = ["phone", "fax", "email"];
const uploadExtractFields: Partial<
  Record<CompanySettingsUploadType, Array<keyof CompanySettingsExtractedFields>>
> = {
  business_registration: businessRegistrationFields,
  quote_template: contactFields,
  transaction_statement_template: contactFields,
};

type UploadStage =
  | "idle"
  | "saved"
  | "selected"
  | "uploading"
  | "uploaded"
  | "extracting"
  | "autofilled"
  | "no_extractable_data"
  | "error";

type FileUploadUiState = {
  fileName: string | null;
  stage: UploadStage;
  message: string;
  error: string | null;
};

const initialFileUiState = (): Record<CompanySettingsUploadType, FileUploadUiState> => ({
  business_registration: {
    fileName: null,
    stage: "idle",
    message: "파일을 선택하거나 드래그해서 놓으면 즉시 업로드됩니다.",
    error: null,
  },
  bank_copy: {
    fileName: null,
    stage: "idle",
    message: "파일을 선택하거나 드래그해서 놓으면 즉시 업로드됩니다.",
    error: null,
  },
  quote_template: {
    fileName: null,
    stage: "idle",
    message: "파일을 선택하거나 드래그해서 놓으면 즉시 업로드됩니다.",
    error: null,
  },
  transaction_statement_template: {
    fileName: null,
    stage: "idle",
    message: "파일을 선택하거나 드래그해서 놓으면 즉시 업로드됩니다.",
    error: null,
  },
  seal_image: {
    fileName: null,
    stage: "idle",
    message: "파일을 선택하거나 드래그해서 놓으면 즉시 업로드됩니다.",
    error: null,
  },
});

const stageLabelMap: Record<UploadStage, string> = {
  idle: "대기 중",
  saved: "서버 저장됨",
  selected: "파일 선택됨",
  uploading: "업로드 중",
  uploaded: "업로드 완료",
  extracting: "추출 중",
  autofilled: "기본정보 반영 완료",
  no_extractable_data: "자동 입력 정보 없음",
  error: "실패",
};

function formatDateTime(value: string | null | undefined) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function looksBrokenText(value: string | null | undefined) {
  if (!value) return false;
  return /Ã|Â|�/.test(value);
}

function clearExtractFields(
  base: CompanySettingsUpdate,
  fields: Array<keyof CompanySettingsExtractedFields> = autoExtractFields
): CompanySettingsUpdate {
  const next = { ...base };
  for (const field of fields) {
    next[field] = "";
  }
  return next;
}

function clearAutoExtractFields(base: CompanySettingsUpdate): CompanySettingsUpdate {
  return clearExtractFields(base);
}

function applyExtractedFields(
  base: CompanySettingsUpdate,
  extracted: CompanySettingsExtractedFields,
  fields: Array<keyof CompanySettingsExtractedFields> = autoExtractFields
): { nextForm: CompanySettingsUpdate; filledLabels: string[] } {
  const nextForm = clearExtractFields(base, fields);
  const filledLabels: string[] = [];

  for (const field of fields) {
    const candidate = extracted[field];
    if (candidate && typeof candidate === "string") {
      nextForm[field] = candidate;
      filledLabels.push(autoExtractFieldLabels[field]);
    }
  }

  return { nextForm, filledLabels };
}

export default function CompanySettingsPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabId>("info");
  const [form, setForm] = useState<CompanySettingsUpdate>(emptyForm);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [autoFilledFields, setAutoFilledFields] = useState<string[]>([]);
  const [draggingFileType, setDraggingFileType] = useState<CompanySettingsUploadType | null>(null);
  const [fileUiState, setFileUiState] = useState<Record<CompanySettingsUploadType, FileUploadUiState>>(
    initialFileUiState
  );
  const [hasInitializedFromFiles, setHasInitializedFromFiles] = useState(true);
  const fileInputRefs = useRef<Partial<Record<CompanySettingsUploadType, HTMLInputElement | null>>>({});

  const { data, isLoading } = useQuery({
    queryKey: ["company-settings", DEFAULT_COMPANY_ID],
    queryFn: () => companySettingsApi.get(DEFAULT_COMPANY_ID),
  });

  useEffect(() => {
    if (!data) return;
    setForm((prev) => ({
      ...prev,
      company_id: data.company_id || DEFAULT_COMPANY_ID,
      company_name: data.company_name ?? "",
      company_registration_number: data.company_registration_number ?? "",
      representative_name: data.representative_name ?? "",
      address: data.address ?? "",
      business_type: data.business_type ?? "",
      business_item: data.business_item ?? "",
      phone: data.phone ?? "",
      fax: data.fax ?? "",
      email: data.email ?? "",
      seal_image_path: data.seal_image_path ?? "",
      company_business_registration_path: data.company_business_registration_path ?? "",
      company_bank_copy_path: data.company_bank_copy_path ?? "",
      company_quote_template_path: data.company_quote_template_path ?? "",
      company_transaction_statement_template_path: data.company_transaction_statement_template_path ?? "",
    }));

    setFileUiState((prev) => {
      const next = { ...prev };
      (Object.keys(fileLabels) as CompanySettingsUploadType[]).forEach((fileType) => {
        const status = data.file_statuses?.[fileType];
        if (
          prev[fileType].stage === "idle" ||
          prev[fileType].stage === "saved" ||
          prev[fileType].stage === "uploaded" ||
          prev[fileType].stage === "autofilled" ||
          prev[fileType].stage === "no_extractable_data"
        ) {
          next[fileType] = {
            ...prev[fileType],
            fileName: status?.file_name ?? null,
            stage: status?.exists ? "saved" : "idle",
            message: status?.exists
              ? "서버에 저장된 파일이 있습니다."
              : "파일을 선택하거나 드래그해서 놓으면 즉시 업로드됩니다.",
            error: prev[fileType].stage === "error" ? prev[fileType].error : null,
          };
        }
      });
      return next;
    });
  }, [data]);

  useEffect(() => {
    if (!data || true) return;

    const hasUploadedFiles = extractableFileTypes.some(
      (fileType) => !!data.file_statuses?.[fileType]?.exists
    );

    if (!hasUploadedFiles) {
      setForm((prev) => clearAutoExtractFields(prev));
      setAutoFilledFields([]);
      setHasInitializedFromFiles(true);
      return;
    }

    let cancelled = false;

    const initializeFromFiles = async () => {
      try {
        const extraction = await companySettingsApi.extract(DEFAULT_COMPANY_ID);
        if (cancelled) return;

        setForm((prev) => {
          const { nextForm } = applyExtractedFields(prev, extraction.extracted);
          return nextForm;
        });
        setAutoFilledFields(
          autoExtractFields
            .filter((field) => {
              const value = extraction.extracted[field];
              return typeof value === "string" && value.trim();
            })
            .map((field) => autoExtractFieldLabels[field])
        );
      } catch (err) {
        if (cancelled) return;
        const errorMessage = err instanceof Error ? err.message : "회사 기본서류 자동 추출에 실패했습니다.";
        setMessage({ type: "error", text: errorMessage });
      } finally {
        if (!cancelled) {
          setHasInitializedFromFiles(true);
        }
      }
    };

    initializeFromFiles();

    return () => {
      cancelled = true;
    };
  }, [data, hasInitializedFromFiles]);

  const saveMutation = useMutation({
    mutationFn: (payload: CompanySettingsUpdate) => companySettingsApi.update(payload),
    onSuccess: () => {
      setMessage({ type: "success", text: "회사 설정이 저장되었습니다." });
      queryClient.invalidateQueries({ queryKey: ["company-settings", DEFAULT_COMPANY_ID] });
    },
    onError: (err: Error) => setMessage({ type: "error", text: err.message }),
  });

  const uploadMutation = useMutation({
    mutationFn: ({ fileType, file }: { fileType: CompanySettingsUploadType; file: File }) =>
      companySettingsApi.uploadFile(DEFAULT_COMPANY_ID, fileType, file),
    onSuccess: async (uploadedSettings, variables) => {
      const { fileType, file } = variables;
      queryClient.setQueryData(["company-settings", DEFAULT_COMPANY_ID], uploadedSettings);
      setFileUiState((prev) => ({
        ...prev,
        [fileType]: {
          fileName: file.name,
          stage: "uploaded",
          message: "업로드 완료. 회사 기본정보 추출을 시작합니다.",
          error: null,
        },
      }));
      setForm((prev) => ({
        ...prev,
        company_id: uploadedSettings.company_id || DEFAULT_COMPANY_ID,
        seal_image_path: uploadedSettings.seal_image_path ?? prev.seal_image_path,
        company_business_registration_path:
          uploadedSettings.company_business_registration_path ?? prev.company_business_registration_path,
        company_bank_copy_path: uploadedSettings.company_bank_copy_path ?? prev.company_bank_copy_path,
        company_quote_template_path:
          uploadedSettings.company_quote_template_path ?? prev.company_quote_template_path,
        company_transaction_statement_template_path:
          uploadedSettings.company_transaction_statement_template_path ?? prev.company_transaction_statement_template_path,
      }));

      try {
        if (!extractableFileTypes.includes(fileType)) {
          setFileUiState((prev) => ({
            ...prev,
            [fileType]: {
              fileName: file.name,
              stage: "uploaded",
              message: "?낅줈???꾨즺. ???뚯씪??湲곕낯?뺣낫 ?먮룞 異붿텧 ??곸씠 ?꾨땲?묐땲??",
              error: null,
            },
          }));
          setMessage({ type: "success", text: `${fileLabels[fileType]} ?낅줈?쒓? ?꾨즺?섏뿀?듬땲??` });
          return;
        }

        const targetFields = uploadExtractFields[fileType] ?? autoExtractFields;
        setForm((prev) => clearExtractFields(prev, targetFields));
        setAutoFilledFields([]);
        setFileUiState((prev) => ({
          ...prev,
          [fileType]: {
            fileName: file.name,
            stage: "extracting",
            message: "업로드 완료. 회사 기본정보를 추출하는 중입니다.",
            error: null,
          },
        }));
        const extraction = await companySettingsApi.extract(DEFAULT_COMPANY_ID);
        const { filledLabels } = applyExtractedFields(form, extraction.extracted, targetFields);

        setForm((prev) => {
          const { nextForm } = applyExtractedFields(prev, extraction.extracted, targetFields);
          return nextForm;
        });
        setAutoFilledFields(filledLabels);
        if (filledLabels.length > 0) {
          setFileUiState((prev) => ({
            ...prev,
            [fileType]: {
              fileName: file.name,
              stage: "autofilled",
              message: `${filledLabels.join(", ")} 항목이 회사 기본 정보에 자동 반영되었습니다.`,
              error: null,
            },
          }));
          setMessage({
            type: "success",
            text: `회사 기본정보가 자동 반영되었습니다. (${filledLabels.join(", ")})`,
          });
        } else {
          setFileUiState((prev) => ({
            ...prev,
            [fileType]: {
              fileName: file.name,
              stage: "no_extractable_data",
              message: "업로드 완료, 자동 입력할 정보 없음",
              error: null,
            },
          }));
          setMessage({ type: "success", text: "업로드 완료, 자동 입력할 정보 없음" });
        }
      } catch (err) {
        setAutoFilledFields([]);
        const errorMessage = err instanceof Error ? err.message : "자동 추출 중 오류가 발생했습니다.";
        setFileUiState((prev) => ({
          ...prev,
          [fileType]: {
            fileName: file.name,
            stage: "error",
            message: "업로드는 완료되었지만 자동 추출에 실패했습니다.",
            error: errorMessage,
          },
        }));
        setMessage({ type: "error", text: `업로드 후 자동 추출 실패: ${errorMessage}` });
      }
    },
    onError: (err: Error, variables) => {
      const { fileType, file } = variables;
      setFileUiState((prev) => ({
        ...prev,
        [fileType]: {
          fileName: file.name,
          stage: "error",
          message: "업로드에 실패했습니다.",
          error: err.message,
        },
      }));
      setMessage({ type: "error", text: err.message });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (fileType: CompanySettingsUploadType) =>
      companySettingsApi.deleteFile(DEFAULT_COMPANY_ID, fileType),
    onSuccess: async (updatedSettings, fileType) => {
      queryClient.setQueryData(["company-settings", DEFAULT_COMPANY_ID], updatedSettings);
      setFileUiState((prev) => ({
        ...prev,
        [fileType]: {
          fileName: null,
          stage: "idle",
          message: "파일이 삭제되었습니다. 새 파일을 선택하거나 드래그해서 놓으면 즉시 업로드됩니다.",
          error: null,
        },
      }));

      try {
        const extraction = await companySettingsApi.extract(DEFAULT_COMPANY_ID);
        setForm((prev) => {
          const { nextForm } = applyExtractedFields(prev, extraction.extracted);
          return nextForm;
        });

        const filledLabels = autoExtractFields
          .filter((field) => {
            const value = extraction.extracted[field];
            return typeof value === "string" && value.trim();
          })
          .map((field) => autoExtractFieldLabels[field]);

        setAutoFilledFields(filledLabels);
        setMessage({
          type: "success",
          text:
            filledLabels.length > 0
              ? `${fileLabels[fileType]} 파일이 삭제되었고, 남아 있는 서류 기준으로 회사 기본정보를 다시 계산했습니다.`
              : `${fileLabels[fileType]} 파일이 삭제되었습니다. 현재 자동 입력할 정보가 없습니다.`,
        });
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "삭제 후 회사 기본정보 재계산에 실패했습니다.";
        setMessage({ type: "error", text: errorMessage });
      }
    },
    onError: (err: Error) => {
      setMessage({ type: "error", text: err.message });
    },
  });

  const handleSave = () => {
    saveMutation.mutate({ ...form });
  };

  const handleUpload = (fileType: CompanySettingsUploadType, file: File) => {
    setAutoFilledFields([]);
    setFileUiState((prev) => ({
      ...prev,
      [fileType]: {
        fileName: file.name,
        stage: "uploading",
        message: "파일 선택됨. 업로드를 시작합니다.",
        error: null,
      },
    }));
    uploadMutation.mutate({ fileType, file });
  };

  const handleFileSelected = (fileType: CompanySettingsUploadType, file: File | null) => {
    if (!file) {
      setMessage({ type: "error", text: `${fileLabels[fileType]} 파일을 선택해주세요.` });
      return;
    }
    setFileUiState((prev) => ({
      ...prev,
      [fileType]: {
        fileName: file.name,
        stage: "selected",
        message: "파일 선택됨. 잠시 후 업로드가 시작됩니다.",
        error: null,
      },
    }));
    handleUpload(fileType, file);
  };

  const handleDelete = (fileType: CompanySettingsUploadType) => {
    deleteMutation.mutate(fileType);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-900">회사 설정</h2>
        <p className="text-sm text-gray-500 mt-0.5">
          문서 출력에 사용할 회사 기본 정보, 기본 서류, 템플릿을 관리합니다.
        </p>
      </div>

      {/* 탭 네비게이션 */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex gap-6">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-blue-600 text-blue-700"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* 템플릿 관리 탭 */}
      {activeTab === "templates" && <TemplatesPanel />}

      {/* 회사 정보 탭 */}
      {activeTab === "info" && (
      <div className="space-y-6">

      {message && (
        <div
          className={`rounded-lg px-4 py-3 text-sm ${
            message.type === "success" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
          }`}
        >
          {message.text}
        </div>
      )}

      {autoFilledFields.length > 0 && (
        <div className="rounded-lg px-4 py-3 text-sm bg-blue-50 text-blue-700">
          회사 기본정보가 자동 반영되었습니다: {autoFilledFields.join(", ")}
        </div>
      )}

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">회사 기본 정보</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <Label htmlFor="company_name">회사명</Label>
              {autoFilledFields.includes("회사명") && (
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-medium text-blue-700">
                  자동 입력됨
                </span>
              )}
            </div>
            <Input id="company_name" value={form.company_name ?? ""} onChange={(e) => setForm((prev) => ({ ...prev, company_name: e.target.value }))} placeholder="예: 주식회사 씨엠" />
            <p className="text-xs text-gray-400">견적서·거래명세서의 귀중/귀하 란에 표시됩니다.</p>
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <Label htmlFor="company_registration_number">사업자등록번호</Label>
              {autoFilledFields.includes("사업자등록번호") && (
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-medium text-blue-700">
                  자동 입력됨
                </span>
              )}
            </div>
            <Input id="company_registration_number" value={form.company_registration_number ?? ""} onChange={(e) => setForm((prev) => ({ ...prev, company_registration_number: e.target.value }))} />
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <Label htmlFor="representative_name">대표자명</Label>
              {autoFilledFields.includes("대표자명") && (
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-medium text-blue-700">
                  자동 입력됨
                </span>
              )}
            </div>
            <Input id="representative_name" value={form.representative_name ?? ""} onChange={(e) => setForm((prev) => ({ ...prev, representative_name: e.target.value }))} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="address">주소</Label>
              {autoFilledFields.includes("주소") && (
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-medium text-blue-700">
                  자동 입력됨
                </span>
              )}
            </div>
            <Input id="address" value={form.address ?? ""} onChange={(e) => setForm((prev) => ({ ...prev, address: e.target.value }))} />
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <Label htmlFor="business_type">업태</Label>
              {autoFilledFields.includes("업태") && (
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-medium text-blue-700">
                  자동 입력됨
                </span>
              )}
            </div>
            <Input id="business_type" value={form.business_type ?? ""} onChange={(e) => setForm((prev) => ({ ...prev, business_type: e.target.value }))} />
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <Label htmlFor="business_item">업종</Label>
              {autoFilledFields.includes("업종") && (
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-medium text-blue-700">
                  자동 입력됨
                </span>
              )}
            </div>
            <Input id="business_item" value={form.business_item ?? ""} onChange={(e) => setForm((prev) => ({ ...prev, business_item: e.target.value }))} />
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <Label htmlFor="phone">전화번호</Label>
              {autoFilledFields.includes("전화번호") && (
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-medium text-blue-700">
                  자동 입력됨
                </span>
              )}
            </div>
            <Input id="phone" value={form.phone ?? ""} onChange={(e) => setForm((prev) => ({ ...prev, phone: e.target.value }))} />
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <Label htmlFor="fax">팩스</Label>
              {autoFilledFields.includes("팩스") && (
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-medium text-blue-700">
                  자동 입력됨
                </span>
              )}
            </div>
            <Input id="fax" value={form.fax ?? ""} onChange={(e) => setForm((prev) => ({ ...prev, fax: e.target.value }))} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="email">이메일</Label>
              {autoFilledFields.includes("이메일") && (
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-medium text-blue-700">
                  자동 입력됨
                </span>
              )}
            </div>
            <Input id="email" value={form.email ?? ""} onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))} />
          </div>
          <div className="sm:col-span-2 flex justify-end">
            <Button onClick={handleSave} disabled={saveMutation.isPending || isLoading}>
              {saveMutation.isPending ? "저장 중..." : "저장"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">회사 기본 서류</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          {(Object.keys(fileLabels) as CompanySettingsUploadType[]).map((fileType) => (
            <div key={fileType} className="space-y-1.5">
              {(() => {
                const savedStatus = data?.file_statuses?.[fileType];
                const savedUpdatedAt = formatDateTime(savedStatus?.updated_at);
                return (
                  <>
              <div>
                <Label htmlFor={fileType}>{fileLabels[fileType]}</Label>
              </div>
              <div
                className={`rounded-lg border-2 border-dashed px-4 py-4 transition-colors ${
                  draggingFileType === fileType
                    ? "border-blue-500 bg-blue-50"
                    : "border-gray-200 bg-gray-50"
                }`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDraggingFileType(fileType);
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  setDraggingFileType((prev) => (prev === fileType ? null : prev));
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  setDraggingFileType(null);
                  handleFileSelected(fileType, e.dataTransfer.files?.[0] ?? null);
                }}
              >
                <input
                  ref={(el) => {
                    fileInputRefs.current[fileType] = el;
                  }}
                  id={fileType}
                  type="file"
                  accept={fileType === "quote_template" || fileType === "transaction_statement_template" ? ".docx,.xlsx,.xls,.pdf" : ".pdf,.jpg,.jpeg,.png"}
                  className="hidden"
                  onChange={(e) => {
                    handleFileSelected(fileType, e.target.files?.[0] ?? null);
                    e.currentTarget.value = "";
                  }}
                />
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-gray-800">
                      파일을 드래그해서 놓거나 파일 선택으로 업로드하세요.
                    </p>
                    <p className="text-xs text-gray-500">
                      {fileType === "quote_template" || fileType === "transaction_statement_template"
                        ? "DOCX, XLSX, XLS, PDF 파일 업로드 가능"
                        : "PDF, JPG, JPEG, PNG 파일 업로드 가능"}
                    </p>
                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                          fileUiState[fileType].stage === "error"
                            ? "bg-red-100 text-red-700"
                            : fileUiState[fileType].stage === "autofilled"
                              ? "bg-blue-100 text-blue-700"
                            : fileUiState[fileType].stage === "no_extractable_data"
                              ? "bg-amber-100 text-amber-700"
                              : fileUiState[fileType].stage === "saved"
                                ? "bg-emerald-100 text-emerald-700"
                                : fileUiState[fileType].stage === "uploading" || fileUiState[fileType].stage === "extracting"
                                  ? "bg-sky-100 text-sky-700"
                                  : fileUiState[fileType].stage === "uploaded"
                                    ? "bg-green-100 text-green-700"
                                    : "bg-gray-200 text-gray-700"
                        }`}
                      >
                        {stageLabelMap[fileUiState[fileType].stage]}
                      </span>
                      <span className="text-xs text-gray-600">{fileUiState[fileType].message}</span>
                    </div>
                    {fileUiState[fileType].fileName && (
                      <p className="text-sm text-gray-700">
                        현재 선택/처리 파일: <span className="font-semibold">{fileUiState[fileType].fileName}</span>
                      </p>
                    )}
                    <p className="text-xs text-gray-500">
                      {savedStatus?.exists && savedStatus.file_name
                        ? `현재 등록 파일: ${savedStatus.file_name}${savedUpdatedAt ? ` / 마지막 변경 ${savedUpdatedAt}` : ""}`
                        : "현재 등록된 파일이 없습니다."}
                    </p>
                    {fileUiState[fileType].error && (
                      <p className="text-xs text-red-600">{fileUiState[fileType].error}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      className="hidden"
                      onClick={() => {
                        setFileUiState((prev) => ({
                          ...prev,
                          [fileType]: {
                            ...prev[fileType],
                            stage: "selected",
                            message: "파일 선택 창이 열렸습니다. 파일을 고르면 즉시 업로드됩니다.",
                            error: null,
                          },
                        }));
                        fileInputRefs.current[fileType]?.click();
                      }}
                      disabled={uploadMutation.isPending || deleteMutation.isPending}
                    >
                      수정
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => handleDelete(fileType)}
                      disabled={uploadMutation.isPending || deleteMutation.isPending}
                    >
                      삭제
                    </Button>
                  </div>
                </div>
              </div>
                  </>
                );
              })()}
            </div>
          ))}
        </CardContent>
      </Card>
      </div>
      )}
    </div>
  );
}
