"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { templatesApi } from "@/lib/api";
import { CATEGORY_LABELS } from "@/lib/constants";
import type { CategoryType } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Upload, FileText, AlertCircle } from "lucide-react";

const ALL_CATEGORIES = Object.entries(CATEGORY_LABELS) as [CategoryType, string][];

export default function TemplatesPage() {
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
      templatesApi.upload(
        form.category_type,
        form.document_type,
        form.display_name,
        file!
      ),
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
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["templates"] }),
  });

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-bold text-gray-900">템플릿 관리</h2>
        <p className="text-sm text-gray-500 mt-0.5">
          비목별 DOCX 서식 파일을 업로드하세요. 서식은 문서 생성의 최우선 기준입니다.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-5">
        {/* Upload Form */}
        <Card className="col-span-1">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">템플릿 업로드</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="p-2 bg-amber-50 rounded text-xs text-amber-700 flex items-start gap-1.5">
              <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              업로드된 서식의 구조는 절대 수정되지 않습니다
            </div>
            <div className="space-y-1.5">
              <Label>비목 *</Label>
              <select
                className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm"
                value={form.category_type}
                onChange={(e) =>
                  setForm({ ...form, category_type: e.target.value as CategoryType })
                }
              >
                {ALL_CATEGORIES.map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>서류 유형 *</Label>
              <Input
                value={form.document_type}
                onChange={(e) => setForm({ ...form, document_type: e.target.value })}
                placeholder="예: quote, service_contract"
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
              <Label>DOCX 파일 *</Label>
              <label className="block">
                <input
                  type="file"
                  className="hidden"
                  accept=".docx"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
                <div className="border-2 border-dashed border-gray-200 rounded-lg p-3 text-center cursor-pointer hover:border-blue-300 transition-colors">
                  <p className="text-xs text-gray-400">
                    {file ? file.name : "DOCX 파일 선택"}
                  </p>
                </div>
              </label>
            </div>
            {error && (
              <p className="text-xs text-red-600 bg-red-50 px-2 py-1.5 rounded">
                {error}
              </p>
            )}
            <Button
              className="w-full gap-2"
              size="sm"
              onClick={() => uploadMutation.mutate()}
              disabled={
                !form.document_type ||
                !form.display_name ||
                !file ||
                uploadMutation.isPending
              }
            >
              <Upload className="w-3.5 h-3.5" />
              {uploadMutation.isPending ? "업로드 중..." : "업로드"}
            </Button>
          </CardContent>
        </Card>

        {/* Templates List */}
        <div className="col-span-2 space-y-4">
          <div className="flex items-center gap-3">
            <select
              className="border border-gray-200 rounded-md px-3 py-2 text-sm"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
            >
              <option value="">전체 비목</option>
              {ALL_CATEGORIES.map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <span className="text-sm text-gray-400">
              {templates?.length ?? 0}개 템플릿
            </span>
          </div>

          {isLoading ? (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-16 w-full rounded-lg" />
              ))}
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
                <Card key={tmpl.id} className={tmpl.is_active ? "" : "opacity-50"}>
                  <CardContent className="p-4 flex items-center gap-3">
                    <FileText className="w-5 h-5 text-blue-400 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-gray-800">
                          {tmpl.display_name}
                        </p>
                        <Badge className="text-xs bg-gray-100 text-gray-600">
                          {CATEGORY_LABELS[tmpl.category_type]}
                        </Badge>
                        <Badge className="text-xs bg-blue-50 text-blue-600">
                          v{tmpl.version}
                        </Badge>
                        {!tmpl.is_active && (
                          <Badge className="text-xs bg-red-50 text-red-500">
                            비활성
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-gray-400 mt-0.5">
                        {tmpl.document_type} · {tmpl.filename}
                      </p>
                    </div>
                    {tmpl.is_active && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-400 hover:text-red-600 shrink-0"
                        onClick={() => deactivateMutation.mutate(tmpl.id)}
                        disabled={deactivateMutation.isPending}
                      >
                        비활성화
                      </Button>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
