"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { expensesApi, exportApi } from "@/lib/api";
import { CATEGORY_LABELS, EXPENSE_STATUS_LABELS, EXPENSE_STATUS_COLORS } from "@/lib/constants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Download, Package } from "lucide-react";
import { formatCurrency } from "@/lib/utils";

export default function ExportPage() {
  const [exportingId, setExportingId] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  const { data: expenses, isLoading } = useQuery({
    queryKey: ["expenses", "", "validated"],
    queryFn: () => expensesApi.list(undefined, "validated"),
  });

  const exportMutation = useMutation({
    mutationFn: (id: string) => exportApi.generate(id),
    onSuccess: (data, id) => {
      setExportingId(null);
      if (data.download_url) {
        window.open(data.download_url, "_blank");
      }
      setMessage("내보내기 패키지가 생성되었습니다.");
    },
    onError: (err: Error) => {
      setExportingId(null);
      setMessage(`오류: ${err.message}`);
    },
  });

  const handleExport = (id: string) => {
    setExportingId(id);
    setMessage("");
    exportMutation.mutate(id);
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-bold text-gray-900">전체 출력문서</h2>
        <p className="text-sm text-gray-500 mt-0.5">
          검증 완료된 비용 항목을 ZIP 패키지로 내보냅니다
        </p>
      </div>

      {message && (
        <div className="p-3 bg-blue-50 rounded-lg text-sm text-blue-700">
          {message}
        </div>
      )}

      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Package className="w-4 h-4 text-blue-500" />
            <CardTitle className="text-base">내보내기 가능한 항목</CardTitle>
            <Badge className="bg-green-100 text-green-700 text-xs ml-auto">
              검증 완료 {expenses?.length ?? 0}건
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : (expenses ?? []).length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-8">
              검증 완료된 항목이 없습니다
            </p>
          ) : (
            <div className="divide-y divide-gray-100">
              {(expenses ?? []).map((expense) => (
                <div
                  key={expense.id}
                  className="py-3 flex items-center justify-between"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-medium px-2 py-0.5 bg-gray-100 text-gray-600 rounded">
                      {CATEGORY_LABELS[expense.category_type]}
                    </span>
                    <div>
                      <p className="text-sm font-medium text-gray-800">
                        {expense.title}
                      </p>
                      <p className="text-xs text-gray-400 mt-0.5">
                        {formatCurrency(expense.amount)}
                        {expense.vendor_name && ` · ${expense.vendor_name}`}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge className={`text-xs ${EXPENSE_STATUS_COLORS[expense.status]}`}>
                      {EXPENSE_STATUS_LABELS[expense.status]}
                    </Badge>
                    <Button
                      size="sm"
                      className="gap-1.5"
                      onClick={() => handleExport(expense.id)}
                      disabled={exportingId === expense.id}
                    >
                      <Download className="w-3.5 h-3.5" />
                      {exportingId === expense.id ? "생성 중..." : "ZIP 다운로드"}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <p className="text-sm font-semibold text-gray-700 mb-2">ZIP 패키지 구성</p>
          <ul className="text-sm text-gray-500 space-y-1 list-disc list-inside">
            <li>생성된 집행 서류 (DOCX)</li>
            <li>업로드된 첨부 서류</li>
            <li>유효성 검사 리포트</li>
            <li>manifest.json (생성 추적 정보)</li>
            <li>소스 참조 및 프롬프트 버전 로그</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
