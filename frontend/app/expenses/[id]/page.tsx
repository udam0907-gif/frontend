"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { expensesApi, validationApi, exportApi } from "@/lib/api";
import { CATEGORY_LABELS, EXPENSE_STATUS_COLORS, EXPENSE_STATUS_LABELS, REQUIRED_DOCS } from "@/lib/constants";
import type { CategoryType } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, Upload, CheckCircle2, XCircle, AlertTriangle, Download, FileText } from "lucide-react";
import Link from "next/link";
import { use } from "react";

export default function ExpenseDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const queryClient = useQueryClient();
  const [uploadingDoc, setUploadingDoc] = useState<string | null>(null);

  const { data: expense, isLoading } = useQuery({
    queryKey: ["expense", id],
    queryFn: () => expensesApi.get(id),
  });

  const { data: validation } = useQuery({
    queryKey: ["validation", id],
    queryFn: () => validationApi.getResult(id),
    enabled: !!expense && expense.status !== "draft",
    retry: false,
  });

  const validateMutation = useMutation({
    mutationFn: () => validationApi.validate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["validation", id] });
      queryClient.invalidateQueries({ queryKey: ["expense", id] });
      queryClient.invalidateQueries({ queryKey: ["expenses"] });
    },
  });

  const exportMutation = useMutation({
    mutationFn: () => exportApi.generate(id),
    onSuccess: (data) => {
      if (data.download_url) window.open(data.download_url, "_blank");
    },
  });

  const handleDocUpload = async (docType: string, file: File) => {
    setUploadingDoc(docType);
    try {
      await expensesApi.uploadDocument(id, docType, file);
      queryClient.invalidateQueries({ queryKey: ["expense", id] });
    } finally {
      setUploadingDoc(null);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4 max-w-3xl">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!expense) return <p className="text-gray-500">항목을 찾을 수 없습니다.</p>;

  const requiredDocs = REQUIRED_DOCS[expense.category_type as CategoryType] ?? [];
  const uploadedDocTypes = new Set(
    expense.documents?.map((d) => d.document_type) ?? []
  );

  return (
    <div className="max-w-3xl space-y-5">
      <div className="flex items-center gap-3">
        <Link href="/expenses">
          <Button variant="ghost" size="icon" className="w-8 h-8">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-gray-900">{expense.title}</h2>
            <Badge className={`text-xs ${EXPENSE_STATUS_COLORS[expense.status]}`}>
              {EXPENSE_STATUS_LABELS[expense.status]}
            </Badge>
          </div>
          <p className="text-sm text-gray-500 mt-0.5">
            {CATEGORY_LABELS[expense.category_type]} · {expense.amount.toLocaleString()}원
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => validateMutation.mutate()}
            disabled={validateMutation.isPending}
          >
            {validateMutation.isPending ? "검증 중..." : "유효성 검사"}
          </Button>
          <Button
            size="sm"
            onClick={() => exportMutation.mutate()}
            disabled={exportMutation.isPending || expense.status !== "validated"}
          >
            <Download className="w-3.5 h-3.5 mr-1.5" />
            내보내기
          </Button>
        </div>
      </div>

      {/* Expense Details */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">집행 정보</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4 text-sm">
          <div><span className="text-gray-400">업체명:</span> <span className="font-medium">{expense.vendor_name ?? "-"}</span></div>
          <div><span className="text-gray-400">집행일:</span> <span className="font-medium">{expense.expense_date ?? "-"}</span></div>
          {expense.description && (
            <div className="col-span-2">
              <span className="text-gray-400">설명:</span>
              <span className="font-medium ml-1">{expense.description}</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Required Documents */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">필수 서류</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {requiredDocs.length === 0 ? (
            <p className="text-sm text-gray-400">이 비목은 서류 요건이 없습니다</p>
          ) : (
            requiredDocs.map(({ key, label }) => {
              const uploaded = uploadedDocTypes.has(key);
              return (
                <div
                  key={key}
                  className="flex items-center justify-between py-2 px-3 rounded-lg border border-gray-100 hover:bg-gray-50"
                >
                  <div className="flex items-center gap-2.5">
                    {uploaded ? (
                      <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />
                    ) : (
                      <div className="w-4 h-4 rounded-full border-2 border-gray-300 shrink-0" />
                    )}
                    <span className={`text-sm ${uploaded ? "text-gray-700" : "text-gray-500"}`}>
                      {label}
                    </span>
                    {uploaded && (
                      <span className="text-xs text-green-600 bg-green-50 px-1.5 py-0.5 rounded">
                        업로드 완료
                      </span>
                    )}
                  </div>
                  <label className="cursor-pointer">
                    <input
                      type="file"
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleDocUpload(key, file);
                      }}
                    />
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-md border border-gray-200 px-3 py-1.5 text-sm font-medium transition-colors ${
                        uploadingDoc === key
                          ? "opacity-50 cursor-not-allowed"
                          : "hover:bg-gray-50 cursor-pointer"
                      }`}
                    >
                      <Upload className="w-3.5 h-3.5" />
                      {uploadingDoc === key ? "업로드 중..." : uploaded ? "재업로드" : "업로드"}
                    </span>
                  </label>
                </div>
              );
            })
          )}
        </CardContent>
      </Card>

      {/* Validation Result */}
      {validation && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <CardTitle className="text-base">유효성 검사 결과</CardTitle>
              {validation.is_valid ? (
                <CheckCircle2 className="w-4 h-4 text-green-500" />
              ) : (
                <XCircle className="w-4 h-4 text-red-500" />
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {validation.blocking_errors.length > 0 && (
              <div>
                <p className="text-sm font-semibold text-red-600 mb-1.5">
                  차단 오류 ({validation.blocking_errors.length})
                </p>
                {validation.blocking_errors.map((e, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm text-red-700 bg-red-50 px-3 py-2 rounded mb-1">
                    <XCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                    {e.message}
                  </div>
                ))}
              </div>
            )}
            {validation.warnings.length > 0 && (
              <div>
                <p className="text-sm font-semibold text-yellow-600 mb-1.5">
                  경고 ({validation.warnings.length})
                </p>
                {validation.warnings.map((w, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm text-yellow-700 bg-yellow-50 px-3 py-2 rounded mb-1">
                    <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                    {w.message}
                  </div>
                ))}
              </div>
            )}
            {validation.passed_checks.length > 0 && (
              <div>
                <p className="text-sm font-semibold text-green-600 mb-1.5">
                  통과 ({validation.passed_checks.length})
                </p>
                {validation.passed_checks.map((p, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm text-green-700 bg-green-50 px-3 py-2 rounded mb-1">
                    <CheckCircle2 className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                    {p.message}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
