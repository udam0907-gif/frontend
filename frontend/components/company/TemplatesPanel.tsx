"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { templatesApi } from "@/lib/api";
import { CATEGORY_LABELS } from "@/lib/constants";
import type { CategoryType, FieldRegistryItem, FieldMapEntry } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Upload, FileText, AlertCircle, Settings2, ChevronDown, ChevronUp } from "lucide-react";

const ALL_CATEGORIES = Object.entries(CATEGORY_LABELS) as [CategoryType, string][];
const CELL_RE = /^[A-Za-z]{1,3}[1-9][0-9]*$/;

function validateCell(val: string): boolean {
  return val === "" || CELL_RE.test(val.trim());
}

function CellMappingPanel({
  templateId, fieldMap, onSaved,
}: {
  templateId: string;
  fieldMap: Record<string, unknown>;
  onSaved: () => void;
}) {
  const { data: registry, isLoading: regLoading } = useQuery({
    queryKey: ["field-registry"],
    queryFn: templatesApi.getFieldRegistry,
    staleTime: Infinity,
  });

  const initialCells = (): Record<string, string> => {
    const result: Record<string, string> = {};
    for (const [key, val] of Object.entries(fieldMap)) {
      const entry = val as FieldMapEntry;
      if (entry?.cell) result[key] = entry.cell;
    }
    return result;
  };

  const [cells, setCells] = useState<Record<string, string>>(initialCells);
  const [errors, setErrors] = useState<Record<string, boolean>>({});
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">("idle");

  const saveMutation = useMutation({
    mutationFn: (mapping: Record<string, string>) =>
      templatesApi.setCellMapping(templateId, mapping),
    onSuccess: () => {
      setSaveStatus("success");
      onSaved();
      setTimeout(() => setSaveStatus("idle"), 3000);
    },
    onError: () => {
      setSaveStatus("error");
      setTimeout(() => setSaveStatus("idle"), 3000);
    },
  });

  const handleChange = (key: string, val: string) => {
    setCells((prev) => ({ ...prev, [key]: val.toUpperCase() }));
    setErrors((prev) => ({ ...prev, [key]: !validateCell(val) }));
  };

  const handleSave = () => {
    const newErrors: Record<string, boolean> = {};
    let hasError = false;
    for (const [key, val] of Object.entries(cells)) {
      if (!validateCell(val)) { newErrors[key] = true; hasError = true; }
    }
    setErrors(newErrors);
    if (hasError) return;

    const mapping: Record<string, string> = {};
    for (const [key, val] of Object.entries(cells)) {
      if (val.trim()) mapping[key] = val.trim().toUpperCase();
    }
    saveMutation.mutate(mapping);
  };

  if (regLoading) {
    return (
      <div className="p-4 space-y-2">
        {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
      </div>
    );
  }

  return (
    <div className="border-t border-gray-100 bg-gray-50 px-4 py-4">
      <p className="text-xs text-gray-500 mb-3">
        각 필드가 XLSX의 어느 셀에 해당하는지 입력하세요. 예: <code className="bg-gray-200 px-1 rounded">B3</code>
      </p>
      <div className="mb-3 p-2 bg-blue-50 border border-blue-100 rounded text-xs text-blue-700 space-y-0.5">
        <p className="font-medium">병합셀 주의사항</p>
        <p>· 병합셀은 <strong>좌상단 셀 주소</strong>를 입력하세요 (예: A3:G3 병합이면 A3)</p>
        <p>· 같은 병합 범위에 두 필드를 매핑하면 첫 번째 필드만 입력됩니다</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500 border-b border-gray-200">
              <th className="text-left py-1.5 pr-3 font-medium w-36">필드</th>
              <th className="text-left py-1.5 pr-3 font-medium w-28">라벨</th>
              <th className="text-left py-1.5 pr-3 font-medium w-16">타입</th>
              <th className="text-left py-1.5 pr-3 font-medium w-12">필수</th>
              <th className="text-left py-1.5 font-medium w-28">셀 주소</th>
            </tr>
          </thead>
          <tbody>
            {(registry ?? []).map((field: FieldRegistryItem) => (
              <tr key={field.key} className="border-b border-gray-100 last:border-0">
                <td className="py-1.5 pr-3 font-mono text-gray-600">{field.key}</td>
                <td className="py-1.5 pr-3 text-gray-700">{field.label}</td>
                <td className="py-1.5 pr-3">
                  <Badge variant="outline" className="text-xs py-0 h-5">{field.type}</Badge>
                </td>
                <td className="py-1.5 pr-3 text-center">
                  {field.required ? <span className="text-red-500 font-bold">*</span> : <span className="text-gray-300">-</span>}
                </td>
                <td className="py-1.5">
                  <Input
                    value={cells[field.key] ?? ""}
                    onChange={(e) => handleChange(field.key, e.target.value)}
                    placeholder="예: B3"
                    className={`h-7 text-xs w-24 font-mono uppercase ${errors[field.key] ? "border-red-400 focus-visible:ring-red-400" : ""}`}
                    maxLength={6}
                  />
                  {errors[field.key] && <p className="text-red-500 text-xs mt-0.5">잘못된 형식</p>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center gap-3 mt-4">
        <Button
          size="sm"
          onClick={handleSave}
          disabled={saveMutation.isPending || Object.values(errors).some(Boolean)}
          className="gap-1.5"
        >
          {saveMutation.isPending ? "저장 중..." : "셀 매핑 저장"}
        </Button>
        {saveStatus === "success" && <span className="text-xs text-green-600 font-medium">저장되었습니다</span>}
        {saveStatus === "error" && <span className="text-xs text-red-500 font-medium">저장 실패</span>}
        <span className="text-xs text-gray-400 ml-auto">
          {Object.values(cells).filter(Boolean).length} / {(registry ?? []).length} 필드 매핑됨
        </span>
      </div>
    </div>
  );
}

function TemplateCard({
  tmpl, onDeactivate, isDeactivating, onMappingSaved,
}: {
  tmpl: {
    id: string;
    display_name: string;
    category_type: CategoryType;
    version: number;
    document_type: string;
    filename: string;
    is_active: boolean;
    field_map: Record<string, unknown>;
  };
  onDeactivate: (id: string) => void;
  isDeactivating: boolean;
  onMappingSaved: () => void;
}) {
  const [showMapping, setShowMapping] = useState(false);

  const mappedCount = Object.values(tmpl.field_map).filter(
    (v) => (v as FieldMapEntry)?.cell
  ).length;

  const isPassthrough = /\.(pdf|jpg|jpeg|png)$/i.test(tmpl.filename);

  return (
    <Card className={tmpl.is_active ? "" : "opacity-50"}>
      <CardContent className="p-0">
        <div className="p-4 flex items-center gap-3">
          <FileText className="w-5 h-5 text-blue-400 shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="text-sm font-medium text-gray-800">{tmpl.display_name}</p>
              <Badge className="text-xs bg-gray-100 text-gray-600">{CATEGORY_LABELS[tmpl.category_type]}</Badge>
              <Badge className="text-xs bg-blue-50 text-blue-600">v{tmpl.version}</Badge>
              {isPassthrough ? (
                <Badge className="text-xs bg-purple-50 text-purple-600">첨부 파일</Badge>
              ) : mappedCount > 0 ? (
                <Badge className="text-xs bg-green-50 text-green-600">셀매핑 {mappedCount}개</Badge>
              ) : (
                <Badge className="text-xs bg-amber-50 text-amber-600">매핑 미설정</Badge>
              )}
              {!tmpl.is_active && <Badge className="text-xs bg-red-50 text-red-500">비활성</Badge>}
            </div>
            <p className="text-xs text-gray-400 mt-0.5">{tmpl.document_type} · {tmpl.filename}</p>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {tmpl.is_active && (
              <>
                {!isPassthrough && (
                  <Button
                    variant="ghost" size="sm"
                    className="text-gray-500 hover:text-blue-600 gap-1 text-xs h-7 px-2"
                    onClick={() => setShowMapping((v) => !v)}
                  >
                    <Settings2 className="w-3.5 h-3.5" />
                    셀 매핑
                    {showMapping ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  </Button>
                )}
                <Button
                  variant="ghost" size="sm"
                  className="text-red-400 hover:text-red-600 text-xs h-7 px-2"
                  onClick={() => onDeactivate(tmpl.id)}
                  disabled={isDeactivating}
                >
                  비활성화
                </Button>
              </>
            )}
          </div>
        </div>
        {showMapping && (
          <CellMappingPanel templateId={tmpl.id} fieldMap={tmpl.field_map} onSaved={onMappingSaved} />
        )}
      </CardContent>
    </Card>
  );
}

export function TemplatesPanel() {
  const queryClient = useQueryClient();
  const [categoryFilter, setCategoryFilter] = useState("");
  const [form, setForm] = useState({
    category_type: "outsourcing" as CategoryType,
    document_type: "",
    display_name: "",
  });
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");

  const { data: templates, isLoading } = useQuery({
    queryKey: ["templates", categoryFilter],
    queryFn: () => templatesApi.list(categoryFilter || undefined),
  });

  const uploadMutation = useMutation({
    mutationFn: () =>
      templatesApi.upload(form.category_type, form.document_type, form.display_name, file!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      setForm({ category_type: "outsourcing", document_type: "", display_name: "" });
      setFile(null);
      setError("");
    },
    onError: (err: Error) => setError(err.message),
  });

  const deactivateMutation = useMutation({
    mutationFn: templatesApi.deactivate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["templates"] }),
  });

  return (
    <div className="space-y-5">
      <p className="text-sm text-gray-500">서식 파일을 업로드하세요. XLSX/XLS는 셀 매핑, DOCX는 플레이스홀더, PDF/JPG/PNG는 첨부 파일로 처리됩니다.</p>

      <div className="grid grid-cols-3 gap-5">
        <Card className="col-span-1">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">템플릿 업로드</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="p-2 bg-amber-50 rounded text-xs text-amber-700 flex items-start gap-1.5">
              <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              업로드 후 셀 매핑을 설정해야 값이 입력됩니다
            </div>
            <div className="space-y-1.5">
              <Label>비목 *</Label>
              <select
                className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm"
                value={form.category_type}
                onChange={(e) => setForm({ ...form, category_type: e.target.value as CategoryType })}
              >
                {ALL_CATEGORIES.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>서류 유형 *</Label>
              <Input
                value={form.document_type}
                onChange={(e) => setForm({ ...form, document_type: e.target.value })}
                placeholder="예: quote, expense_resolution"
              />
            </div>
            <div className="space-y-1.5">
              <Label>표시 이름 *</Label>
              <Input
                value={form.display_name}
                onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                placeholder="예: 견적서 서식"
              />
            </div>
            <div className="space-y-1.5">
              <Label>서식 파일 *</Label>
              <label className="block">
                <input
                  type="file"
                  className="hidden"
                  accept=".xlsx,.xls,.docx,.pdf,.jpg,.jpeg,.png"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
                <div className="border-2 border-dashed border-gray-200 rounded-lg p-3 text-center cursor-pointer hover:border-blue-300 transition-colors">
                  <p className="text-xs text-gray-400">{file ? file.name : "파일 선택"}</p>
                  <p className="text-xs text-gray-300 mt-0.5">XLSX · XLS · DOCX · PDF · JPG · PNG</p>
                </div>
              </label>
            </div>
            {error && <p className="text-xs text-red-600 bg-red-50 px-2 py-1.5 rounded">{error}</p>}
            <Button
              className="w-full gap-2"
              size="sm"
              onClick={() => uploadMutation.mutate()}
              disabled={!form.document_type || !form.display_name || !file || uploadMutation.isPending}
            >
              <Upload className="w-3.5 h-3.5" />
              {uploadMutation.isPending ? "업로드 중..." : "업로드"}
            </Button>
          </CardContent>
        </Card>

        <div className="col-span-2 space-y-4">
          <div className="flex items-center gap-3">
            <select
              className="border border-gray-200 rounded-md px-3 py-2 text-sm"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
            >
              <option value="">전체 비목</option>
              {ALL_CATEGORIES.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <span className="text-sm text-gray-400">{templates?.length ?? 0}개 템플릿</span>
          </div>

          {isLoading ? (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-16 w-full rounded-lg" />)}
            </div>
          ) : (templates ?? []).length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <p className="text-gray-400 text-sm">등록된 템플릿이 없습니다</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {(templates ?? []).map((tmpl) => (
                <TemplateCard
                  key={tmpl.id}
                  tmpl={tmpl as Parameters<typeof TemplateCard>[0]["tmpl"]}
                  onDeactivate={(id) => deactivateMutation.mutate(id)}
                  isDeactivating={deactivateMutation.isPending}
                  onMappingSaved={() => queryClient.invalidateQueries({ queryKey: ["templates"] })}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
