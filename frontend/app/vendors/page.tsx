"use client";

import { useCallback, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { projectsApi, vendorsApi } from "@/lib/api";
import type { Vendor, VendorCategory, VendorCreate } from "@/lib/types";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Building2,
  Upload,
  Trash2,
  CheckCircle2,
  X,
  FileText,
  AlertCircle,
  Loader2,
  Sparkles,
} from "lucide-react";

const ACCEPTED = ".docx,.xlsx,.pdf,.jpg,.jpeg,.png";

type VendorFileType =
  | "business_registration"
  | "bank_copy"
  | "quote_template"
  | "transaction_statement";

const FORM_FILE_FIELDS: {
  key: VendorFileType;
  label: string;
  pathField: keyof Vendor;
  priority: number;
}[] = [
  { key: "business_registration", label: "사업자등록증", pathField: "business_registration_path", priority: 1 },
  { key: "quote_template", label: "견적서 원본 양식", pathField: "quote_template_path", priority: 2 },
  { key: "transaction_statement", label: "거래명세서 원본 양식", pathField: "transaction_statement_path", priority: 2 },
  { key: "bank_copy", label: "통장사본", pathField: "bank_copy_path", priority: 3 },
];

function DropZone({
  label, file, onFile, onClear, uploading, extracting, badge,
}: {
  label: string;
  file: File | null;
  onFile: (f: File) => void;
  onClear: () => void;
  uploading?: boolean;
  extracting?: boolean;
  badge?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const f = e.dataTransfer.files[0];
      if (f) onFile(f);
    },
    [onFile]
  );

  const busy = uploading || extracting;

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => !file && !busy && inputRef.current?.click()}
      className={`relative flex flex-col items-center justify-center gap-1.5 rounded-lg border-2 border-dashed p-3 text-center transition-colors select-none min-h-[96px] ${
        busy ? "border-gray-200 bg-gray-50 cursor-wait"
        : dragging ? "border-blue-400 bg-blue-50 cursor-copy"
        : file ? "border-green-300 bg-green-50 cursor-default"
        : "border-gray-300 hover:border-blue-300 hover:bg-gray-50 cursor-pointer"
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        className="hidden"
        disabled={!!busy}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";
        }}
      />
      {badge && !file && (
        <span className="absolute top-1 left-1 text-[9px] bg-blue-100 text-blue-600 font-semibold px-1.5 py-0.5 rounded">
          {badge}
        </span>
      )}
      {extracting ? (
        <>
          <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
          <p className="text-[11px] text-blue-600 font-medium">정보 추출 중...</p>
        </>
      ) : uploading ? (
        <p className="text-xs text-blue-600 font-medium">업로드 중...</p>
      ) : file ? (
        <>
          <FileText className="w-4 h-4 text-green-600 shrink-0" />
          <p className="text-[11px] font-medium text-green-700 break-all max-w-full px-1 leading-tight">{file.name}</p>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onClear(); }}
            className="absolute top-1 right-1 rounded-full p-0.5 text-gray-400 hover:text-red-500"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </>
      ) : (
        <>
          <Upload className="w-4 h-4 text-gray-400 shrink-0" />
          <p className="text-[11px] text-gray-600 font-medium leading-tight">{label}</p>
          <p className="text-[10px] text-gray-400">DOCX · XLSX · PDF · JPG · PNG</p>
          <p className="text-[10px] text-gray-400">클릭 또는 드래그</p>
        </>
      )}
    </div>
  );
}

function FileBadge({ path, label }: { path: string | null; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium whitespace-nowrap ${
      path ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-400"
    }`}>
      {path ? <CheckCircle2 className="w-3 h-3 shrink-0" /> : <AlertCircle className="w-3 h-3 shrink-0" />}
      {label}
    </span>
  );
}

interface FormState {
  name: string;
  vendor_category: VendorCategory;
  business_number: string;
  contact: string;
}

const initialForm: FormState = {
  name: "",
  vendor_category: "매입처",
  business_number: "",
  contact: "",
};

const PRIORITY_BADGE: Record<number, string> = { 1: "1순위(추출)", 2: "2순위(추출)", 3: "3순위(보조)" };

export default function VendorsPage() {
  const qc = useQueryClient();
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [form, setForm] = useState<FormState>(initialForm);
  const [formFiles, setFormFiles] = useState<Record<VendorFileType, File | null>>({
    business_registration: null,
    quote_template: null,
    transaction_statement: null,
    bank_copy: null,
  });
  const [extractingKey, setExtractingKey] = useState<VendorFileType | null>(null);
  const [extractNotice, setExtractNotice] = useState<string | null>(null);
  const [fileUploading, setFileUploading] = useState<string | null>(null);

  const { data: projects, isLoading: projectsLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });

  const { data: vendors, isLoading: vendorsLoading } = useQuery({
    queryKey: ["vendors", selectedProjectId],
    queryFn: () => vendorsApi.list(selectedProjectId),
    enabled: !!selectedProjectId,
  });

  const handleFormFile = async (key: VendorFileType, file: File) => {
    setFormFiles((prev) => ({ ...prev, [key]: file }));
    setExtractingKey(key);
    setExtractNotice(null);
    try {
      const result = await vendorsApi.extractInfo(file);
      let filled = false;
      setForm((prev) => {
        const next = { ...prev };
        if (result.vendor_name && !next.name) { next.name = result.vendor_name; filled = true; }
        if (result.business_number && !next.business_number) { next.business_number = result.business_number; filled = true; }
        if (result.contact && !next.contact) { next.contact = result.contact; filled = true; }
        return next;
      });
      if (filled) setExtractNotice("📋 파일에서 업체 정보를 자동으로 채웠습니다. 내용을 확인하고 필요하면 수정하세요.");
    } catch {
      // 추출 실패는 조용히 처리
    } finally {
      setExtractingKey(null);
    }
  };

  const clearFormFile = (key: VendorFileType) => {
    setFormFiles((prev) => ({ ...prev, [key]: null }));
    setExtractNotice(null);
  };

  const createMutation = useMutation({
    mutationFn: async (data: VendorCreate) => {
      const vendor = await vendorsApi.create(data);
      for (const ft of Object.keys(formFiles) as VendorFileType[]) {
        const file = formFiles[ft];
        if (file) {
          setFileUploading(`form_${ft}`);
          await vendorsApi.uploadFile(vendor.id, ft, file);
        }
      }
      return vendor;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["vendors", selectedProjectId] });
      setForm(initialForm);
      setFormFiles({ business_registration: null, quote_template: null, transaction_statement: null, bank_copy: null });
      setExtractNotice(null);
      setFileUploading(null);
    },
    onError: () => setFileUploading(null),
  });

  const deleteMutation = useMutation({
    mutationFn: (vendorId: string) => vendorsApi.delete(vendorId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["vendors", selectedProjectId] }),
  });

  const handleListFileUpload = async (vendor: Vendor, fileType: VendorFileType, file: File) => {
    setFileUploading(`${vendor.id}_${fileType}`);
    try {
      await vendorsApi.uploadFile(vendor.id, fileType, file);
      qc.invalidateQueries({ queryKey: ["vendors", selectedProjectId] });
    } finally {
      setFileUploading(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-900">업체 관리</h2>
        <p className="text-sm text-gray-500 mt-0.5">과제별 거래 업체를 등록하고 관리합니다.</p>
      </div>

      {/* 과제 선택 */}
      <Card>
        <CardContent className="pt-4 pb-4">
          <div className="flex items-center gap-4">
            <Label className="text-sm font-medium text-gray-700 shrink-0">과제 선택</Label>
            {projectsLoading ? (
              <Skeleton className="h-9 w-64" />
            ) : (
              <select
                className="border border-gray-200 rounded-md px-3 py-2 text-sm flex-1 max-w-xs"
                value={selectedProjectId}
                onChange={(e) => {
                  setSelectedProjectId(e.target.value);
                  setForm(initialForm);
                  setFormFiles({ business_registration: null, quote_template: null, transaction_statement: null, bank_copy: null });
                  setExtractNotice(null);
                }}
              >
                <option value="">— 과제를 선택하세요 —</option>
                {(projects ?? []).map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            )}
          </div>
        </CardContent>
      </Card>

      {!selectedProjectId ? (
        <div className="rounded-lg border border-dashed border-gray-200 py-16 text-center">
          <Building2 className="w-8 h-8 text-gray-300 mx-auto mb-3" />
          <p className="text-sm text-gray-400">과제를 선택하면 업체 목록과 등록 폼이 표시됩니다.</p>
        </div>
      ) : (
        <>
          {/* Registration form */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Building2 className="w-4 h-4" />
                업체 등록
              </CardTitle>
              <p className="text-xs text-gray-500">
                파일을 업로드하면 업체명·사업자번호·연락처가 자동으로 채워집니다.
                내용을 확인 후 업체 구분을 선택하고 저장하세요.
              </p>
            </CardHeader>
            <CardContent className="space-y-5">
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Sparkles className="w-3.5 h-3.5 text-blue-500" />
                  <p className="text-xs font-semibold text-gray-600">파일 업로드 → 업체 정보 자동 추출</p>
                </div>
                {extractNotice && (
                  <div className="mb-3 p-2.5 rounded-lg bg-blue-50 border border-blue-200 text-xs text-blue-700">
                    {extractNotice}
                  </div>
                )}
                <div className="grid grid-cols-2 gap-3">
                  {FORM_FILE_FIELDS.map((ft) => (
                    <div key={ft.key} className="space-y-1">
                      <Label className="text-xs text-gray-600">{ft.label}</Label>
                      <DropZone
                        label={ft.label}
                        file={formFiles[ft.key]}
                        onFile={(f) => handleFormFile(ft.key, f)}
                        onClear={() => clearFormFile(ft.key)}
                        uploading={fileUploading === `form_${ft.key}`}
                        extracting={extractingKey === ft.key}
                        badge={PRIORITY_BADGE[ft.priority]}
                      />
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
                  기본 정보 (자동 추출 후 수정 가능)
                </p>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label>업체명 *</Label>
                    <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="예: 문구스토어" />
                  </div>
                  <div className="space-y-1.5">
                    <Label>업체 구분 *</Label>
                    <select
                      className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm"
                      value={form.vendor_category}
                      onChange={(e) => setForm((f) => ({ ...f, vendor_category: e.target.value as VendorCategory }))}
                    >
                      <option value="매입처">매입처</option>
                      <option value="매출처">매출처</option>
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <Label>사업자번호 *</Label>
                    <Input value={form.business_number} onChange={(e) => setForm((f) => ({ ...f, business_number: e.target.value }))} placeholder="123-45-67890" />
                  </div>
                  <div className="space-y-1.5">
                    <Label>연락처</Label>
                    <Input value={form.contact} onChange={(e) => setForm((f) => ({ ...f, contact: e.target.value }))} placeholder="010-0000-0000" />
                  </div>
                </div>
              </div>

              <div className="flex gap-2">
                <Button
                  size="sm"
                  disabled={createMutation.isPending || !form.name || !form.business_number || !!extractingKey}
                  onClick={() => createMutation.mutate({ ...form, project_id: selectedProjectId })}
                >
                  {createMutation.isPending ? "저장 중..." : "업체 저장"}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setForm(initialForm);
                    setFormFiles({ business_registration: null, quote_template: null, transaction_statement: null, bank_copy: null });
                    setExtractNotice(null);
                  }}
                >
                  초기화
                </Button>
              </div>
              {createMutation.isError && (
                <p className="text-xs text-red-500">{(createMutation.error as Error).message}</p>
              )}
            </CardContent>
          </Card>

          {/* Vendor list */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">업체 목록</CardTitle>
            </CardHeader>
            <CardContent>
              {vendorsLoading ? (
                <div className="space-y-2">
                  {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}
                </div>
              ) : (vendors ?? []).length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-8">등록된 업체가 없습니다</p>
              ) : (
                <div className="space-y-4">
                  {(vendors ?? []).map((vendor) => (
                    <div key={vendor.id} className="border border-gray-200 rounded-lg p-4 space-y-3">
                      <div className="flex items-start justify-between">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <p className="font-semibold text-gray-900">{vendor.name}</p>
                            <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-700">
                              {vendor.vendor_category}
                            </span>
                          </div>
                          <p className="text-xs text-gray-400">
                            {vendor.business_number}{vendor.contact && ` · ${vendor.contact}`}
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-500 hover:text-red-700 shrink-0"
                          onClick={() => deleteMutation.mutate(vendor.id)}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        <FileBadge path={vendor.quote_template_path} label="견적서" />
                        <FileBadge path={vendor.transaction_statement_path} label="거래명세서" />
                        <FileBadge path={vendor.business_registration_path} label="사업자등록증" />
                        <FileBadge path={vendor.bank_copy_path} label="통장사본" />
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        {FORM_FILE_FIELDS.map((ft) => {
                          const hasFile = Boolean(vendor[ft.pathField]);
                          const uploading = fileUploading === `${vendor.id}_${ft.key}`;
                          return (
                            <label
                              key={ft.key}
                              className={`flex items-center gap-2 p-2 rounded border cursor-pointer text-xs transition-colors ${
                                hasFile ? "border-green-200 bg-green-50 text-green-700" : "border-dashed border-gray-300 text-gray-500 hover:border-blue-400"
                              }`}
                            >
                              <input
                                type="file"
                                accept={ACCEPTED}
                                className="hidden"
                                disabled={uploading}
                                onChange={(e) => {
                                  const f = e.target.files?.[0];
                                  if (f) handleListFileUpload(vendor, ft.key, f);
                                  e.target.value = "";
                                }}
                              />
                              {hasFile ? <CheckCircle2 className="w-3.5 h-3.5 shrink-0" /> : <Upload className="w-3.5 h-3.5 shrink-0" />}
                              {uploading ? "업로드 중..." : ft.label}
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
