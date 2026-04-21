"use client";

import { useState, useRef } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { templatesApi } from "@/lib/api";
import { CATEGORY_LABELS } from "@/lib/constants";
import type { CategoryType } from "@/lib/types";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Upload, Trash2, FileText } from "lucide-react";

const CATEGORY_OPTIONS: { value: CategoryType; label: string }[] = [
  { value: "materials", label: "재료비" },
  { value: "meeting", label: "회의비" },
  { value: "outsourcing", label: "외주가공비" },
  { value: "test_report", label: "시험성적비" },
  { value: "labor", label: "인건비" },
];

const DOC_TYPES_BY_CATEGORY: Record<string, { value: string; label: string }[]> = {
  materials: [
    { value: "quote", label: "견적서" },
    { value: "comparative_quote", label: "비교견적서" },
    { value: "expense_resolution", label: "지출결의서" },
    { value: "inspection_confirmation", label: "검수확인서" },
  ],
  outsourcing: [
    { value: "quote", label: "견적서" },
    { value: "comparative_quote", label: "비교견적서" },
    { value: "service_contract", label: "용역계약서" },
    { value: "work_order", label: "과업지시서" },
    { value: "transaction_statement", label: "거래명세서" },
    { value: "inspection_photos", label: "검수사진" },
  ],
  labor: [
    { value: "cash_expense_resolution", label: "지출결의서_현금" },
    { value: "in_kind_expense_resolution", label: "지출결의서_현물" },
    { value: "researcher_status_sheet", label: "참여연구원 현황표" },
  ],
  test_report: [
    { value: "quote", label: "견적서" },
    { value: "expense_resolution", label: "지출결의서" },
    { value: "transaction_statement", label: "거래명세서" },
  ],
  meeting: [
    { value: "receipt", label: "영수증" },
    { value: "meeting_minutes", label: "회의내용" },
  ],
  other: [{ value: "other", label: "기타" }],
};

interface FormState {
  displayName: string;
  categoryType: CategoryType;
  documentType: string;
  file: File | null;
}

const initialForm: FormState = {
  displayName: "",
  categoryType: "materials",
  documentType: "quote",
  file: null,
};

export default function ProjectTemplatesPage() {
  const params = useParams();
  const projectId = params.id as string;
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [form, setForm] = useState<FormState>(initialForm);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const { data: templates, isLoading } = useQuery({
    queryKey: ["templates", projectId],
    queryFn: () => templatesApi.list(undefined, projectId),
  });

  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!form.file) throw new Error("파일을 선택하세요.");
      return templatesApi.upload(
        form.categoryType,
        form.documentType,
        form.displayName || form.file.name,
        form.file,
        projectId
      );
    },
    onSuccess: () => {
      setMessage({ type: "success", text: "템플릿이 등록되었습니다." });
      setForm(initialForm);
      if (fileInputRef.current) fileInputRef.current.value = "";
      queryClient.invalidateQueries({ queryKey: ["templates", projectId] });
    },
    onError: (err: Error) => {
      setMessage({ type: "error", text: err.message });
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => templatesApi.deactivate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["templates", projectId] });
    },
  });

  // 비목 변경 시 문서 종류 초기값 업데이트
  const handleCategoryChange = (cat: CategoryType) => {
    const firstDocType = DOC_TYPES_BY_CATEGORY[cat]?.[0]?.value ?? "other";
    setForm((f) => ({ ...f, categoryType: cat, documentType: firstDocType }));
  };

  const handleReset = () => {
    setForm(initialForm);
    setMessage(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-900">템플릿 관리</h2>
        <p className="text-sm text-gray-500 mt-0.5">
          비목별 서식 템플릿을 등록하고 관리합니다
        </p>
      </div>

      {/* 등록 폼 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Upload className="w-4 h-4" />
            템플릿 등록
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {message && (
            <div
              className={`p-3 rounded-lg text-sm ${
                message.type === "success"
                  ? "bg-green-50 text-green-700"
                  : "bg-red-50 text-red-700"
              }`}
            >
              {message.text}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="displayName">템플릿명</Label>
              <Input
                id="displayName"
                placeholder="예: 재료비 견적서 양식"
                value={form.displayName}
                onChange={(e) =>
                  setForm((f) => ({ ...f, displayName: e.target.value }))
                }
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="categoryType">유형 (비목)</Label>
              <select
                id="categoryType"
                className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm"
                value={form.categoryType}
                onChange={(e) =>
                  handleCategoryChange(e.target.value as CategoryType)
                }
              >
                {CATEGORY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="documentType">문서 종류</Label>
              <select
                id="documentType"
                className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm"
                value={form.documentType}
                onChange={(e) =>
                  setForm((f) => ({ ...f, documentType: e.target.value }))
                }
              >
                {(DOC_TYPES_BY_CATEGORY[form.categoryType] ?? []).map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="file">파일 업로드 (DOCX / XLSX / PDF / JPG / PNG)</Label>
              <input
                ref={fileInputRef}
                id="file"
                type="file"
                accept=".docx,.xlsx,.pdf,.jpg,.jpeg,.png"
                className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm file:mr-3 file:border-0 file:bg-blue-50 file:text-blue-700 file:text-xs file:font-medium file:px-2 file:py-1 file:rounded"
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    file: e.target.files?.[0] ?? null,
                  }))
                }
              />
            </div>
          </div>

          <div className="flex gap-2">
            <Button
              onClick={() => uploadMutation.mutate()}
              disabled={uploadMutation.isPending || !form.file}
            >
              {uploadMutation.isPending ? "저장 중..." : "저장"}
            </Button>
            <Button variant="outline" onClick={handleReset}>
              초기화
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 템플릿 목록 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <FileText className="w-4 h-4" />
            등록된 템플릿
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : (templates ?? []).length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-8">
              등록된 템플릿이 없습니다
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100">
                    <th className="text-left py-2.5 px-2 text-xs font-semibold text-gray-500">
                      템플릿명
                    </th>
                    <th className="text-left py-2.5 px-2 text-xs font-semibold text-gray-500">
                      유형
                    </th>
                    <th className="text-left py-2.5 px-2 text-xs font-semibold text-gray-500">
                      파일명
                    </th>
                    <th className="text-left py-2.5 px-2 text-xs font-semibold text-gray-500">
                      상태
                    </th>
                    <th className="py-2.5 px-2" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {(templates ?? []).map((tpl) => (
                    <tr key={tpl.id} className="hover:bg-gray-50">
                      <td className="py-3 px-2 font-medium text-gray-800">
                        {tpl.name}
                      </td>
                      <td className="py-3 px-2 text-gray-600">
                        {CATEGORY_LABELS[tpl.category_type] ?? tpl.category_type}
                      </td>
                      <td className="py-3 px-2 text-gray-500 text-xs">
                        {tpl.filename}
                      </td>
                      <td className="py-3 px-2">
                        <Badge
                          className={
                            tpl.is_active
                              ? "bg-green-100 text-green-700 text-xs"
                              : "bg-gray-100 text-gray-500 text-xs"
                          }
                        >
                          {tpl.is_active ? "활성" : "비활성"}
                        </Badge>
                      </td>
                      <td className="py-3 px-2">
                        {tpl.is_active && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-500 hover:text-red-700 hover:bg-red-50 h-7 px-2"
                            onClick={() => deactivateMutation.mutate(tpl.id)}
                            disabled={deactivateMutation.isPending}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
