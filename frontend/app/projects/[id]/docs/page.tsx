"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueries, useQueryClient } from "@tanstack/react-query";
import { expensesApi, documentSetsApi, vendorsApi } from "@/lib/api";
import { CATEGORY_LABELS, DOCUMENT_SETS } from "@/lib/constants";
import type { DocumentSetResponse } from "@/lib/types";
import {
  Card,
  CardContent,
  CardHeader,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  FileText,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  FolderOpen,
  Copy,
  TableIcon,
  ImageIcon,
  Download,
} from "lucide-react";

const COMPARATIVE_CATEGORIES = ["materials", "outsourcing"];

const DOC_TYPE_LABELS: Record<string, string> = {
  quote: "견적서",
  comparative_quote: "비교견적서 (원금액 × 1.1)",
  expense_resolution: "지출결의서",
  service_contract: "용역계약서",
  work_order: "과업지시서",
  transaction_statement: "거래명세서",
  inspection_confirmation: "검수확인서",
  inspection_photos: "검수사진",
  vendor_business_registration: "업체 사업자등록증",
  vendor_bank_copy: "업체 통장사본",
  cash_expense_resolution: "지출결의서_현금",
  in_kind_expense_resolution: "지출결의서_현물",
  researcher_status_sheet: "참여연구원 현황표",
  receipt: "영수증",
  meeting_minutes: "회의내용",
};

const STATUS_CONFIG: Record<
  string,
  { label: string; color: string; icon: React.ElementType }
> = {
  // ── 현행 상태값 ──────────────────────────────────────────────────
  excel_rendered: {
    label: "생성 완료",
    color: "bg-green-100 text-green-700",
    icon: CheckCircle2,
  },
  vendor_attachment_included: {
    label: "업체 첨부파일 포함",
    color: "bg-blue-100 text-blue-700",
    icon: Copy,
  },
  mapping_needed: {
    label: "셀 매핑 필요",
    color: "bg-amber-100 text-amber-700",
    icon: TableIcon,
  },
  render_failed: {
    label: "생성 오류",
    color: "bg-red-100 text-red-700",
    icon: AlertTriangle,
  },
  template_missing: {
    label: "파일 미등록",
    color: "bg-yellow-100 text-yellow-700",
    icon: AlertTriangle,
  },
  vendor_file_missing: {
    label: "업체 파일 미등록",
    color: "bg-orange-100 text-orange-700",
    icon: AlertTriangle,
  },
  docx_rendered: {
    label: "생성 완료",
    color: "bg-green-100 text-green-700",
    icon: CheckCircle2,
  },
  passthrough_copy: {
    label: "첨부파일",
    color: "bg-blue-100 text-blue-700",
    icon: Copy,
  },
  error: {
    label: "오류",
    color: "bg-red-100 text-red-700",
    icon: AlertTriangle,
  },
};

export default function ProjectDocsPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [freshResults, setFreshResults] = useState<Record<string, DocumentSetResponse>>({});
  const [compareSelections, setCompareSelections] = useState<Record<string, string>>({});

  const { data: expenses, isLoading } = useQuery({
    queryKey: ["expenses", id],
    queryFn: () => expensesApi.list(id),
  });

  const { data: vendors } = useQuery({
    queryKey: ["vendors", id],
    queryFn: () => vendorsApi.list(id),
    enabled: !!id,
  });

  // 페이지 로드 시 각 expense의 기존 생성 결과 조회
  const latestSetQueries = useQueries({
    queries: (expenses ?? []).map((expense) => ({
      queryKey: ["latestSet", expense.id],
      queryFn: () => documentSetsApi.latestSet(expense.id),
      retry: false,
      staleTime: 60 * 1000,
    })),
  });

  // freshResults(이번 세션 생성) > DB 조회 결과 순으로 병합
  const results: Record<string, DocumentSetResponse> = {};
  (expenses ?? []).forEach((expense, i) => {
    const dbData = latestSetQueries[i]?.data;
    if (dbData && dbData.total > 0) results[expense.id] = dbData;
  });
  Object.assign(results, freshResults);

  const updateCompareMutation = useMutation({
    mutationFn: ({ expenseId, compareVendorId, existingMeta }: { expenseId: string; compareVendorId: string; existingMeta: Record<string, unknown> }) =>
      expensesApi.update(expenseId, { metadata: { ...existingMeta, compare_vendor_id: compareVendorId } }),
    onSuccess: (_data, { expenseId }) => {
      queryClient.invalidateQueries({ queryKey: ["expenses", id] });
      queryClient.invalidateQueries({ queryKey: ["latestSet", expenseId] });
      // 비교견적업체 변경 시 기존 문서세트 결과 초기화 (재생성 유도)
      setFreshResults(prev => { const next = { ...prev }; delete next[expenseId]; return next; });
    },
  });

  const generateMutation = useMutation({
    mutationFn: (expenseId: string) => documentSetsApi.generate(expenseId),
    onSuccess: (data, expenseId) => {
      setFreshResults((prev) => ({ ...prev, [expenseId]: data }));
      queryClient.invalidateQueries({ queryKey: ["latestSet", expenseId] });
    },
  });

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-lg font-bold text-gray-900">문서 출력</h3>
        <p className="text-sm text-gray-500 mt-0.5">
          비용집행 건을 선택하여 비목별 문서세트를 자동 생성합니다.
        </p>
      </div>

      <div className="p-3 rounded-lg bg-blue-50 border border-blue-100 text-xs text-blue-700 space-y-1">
        <p className="font-semibold text-sm">문서 자동화 원칙</p>
        <ul className="list-disc list-inside space-y-0.5">
          <li>
            업로드된 원본 양식에 비용집행 입력값을 정확히 매핑 (AI 생성 금지)
          </li>
          <li>비교견적서: 원금액 × 1.1 고정 규칙 자동 적용</li>
          <li>
            업체 사업자등록증·통장사본: 업체 등록 파일에서 직접 포함
          </li>
        </ul>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      ) : (expenses ?? []).length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-gray-400 text-sm">
            등록된 비용집행이 없습니다.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {(expenses ?? []).map((expense) => {
            const result = results[expense.id];
            const isGenerating =
              generateMutation.isPending &&
              generateMutation.variables === expense.id;
            const docSet = DOCUMENT_SETS[expense.category_type] ?? [];

            const needsComparative = COMPARATIVE_CATEGORIES.includes(expense.category_type);
            const savedCompareVendorId = expense.input_data?.compare_vendor_id as string | undefined;
            const selectedCompareVendorId = compareSelections[expense.id] ?? savedCompareVendorId ?? "";
            const compareVendorName = (vendors ?? []).find(v => v.id === selectedCompareVendorId)?.name;

            return (
              <Card key={expense.id}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge className="text-xs bg-gray-100 text-gray-700">
                          {CATEGORY_LABELS[expense.category_type]}
                        </Badge>
                        <span className="font-semibold text-gray-900 text-sm">
                          {expense.title}
                        </span>
                      </div>
                      <p className="text-xs text-gray-400 mt-0.5">
                        {expense.vendor_name ?? "업체 미지정"} ·{" "}
                        {Number(expense.amount).toLocaleString()}원
                        {expense.expense_date && ` · ${expense.expense_date}`}
                      </p>
                      {needsComparative && (() => {
                        const compareVendorObj = (vendors ?? []).find(v => v.id === selectedCompareVendorId);
                        const hasQuoteFile = !!compareVendorObj?.quote_template_path;
                        return (
                          <div className="mt-1.5 space-y-0.5">
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-gray-500">비교견적업체:</span>
                              {selectedCompareVendorId ? (
                                <>
                                  <span className="text-xs text-emerald-600 font-medium">{compareVendorName ?? selectedCompareVendorId}</span>
                                  {hasQuoteFile
                                    ? <span className="text-xs text-emerald-500">✓ 견적서 파일 있음</span>
                                    : <span className="text-xs text-red-500 font-semibold">⚠ 선택한 비교업체에 견적서 파일이 없습니다 (업체관리 → 견적서 업로드)</span>
                                  }
                                  <button
                                    className="text-xs text-gray-400 underline"
                                    onClick={() => setCompareSelections(prev => { const n = {...prev}; delete n[expense.id]; return n; })}
                                  >변경</button>
                                </>
                              ) : (
                                <select
                                  className="text-xs border border-orange-300 rounded px-2 py-0.5 bg-orange-50"
                                  value=""
                                  onChange={(e) => {
                                    const vendorId = e.target.value;
                                    if (!vendorId) return;
                                    setCompareSelections(prev => ({ ...prev, [expense.id]: vendorId }));
                                    updateCompareMutation.mutate({
                                      expenseId: expense.id,
                                      compareVendorId: vendorId,
                                      existingMeta: expense.input_data ?? {},
                                    });
                                  }}
                                >
                                  <option value="">— 비교견적업체 선택 필요 —</option>
                                  {(vendors ?? [])
                                    .filter(v => v.id !== (expense.input_data?.vendor_id as string))
                                    .map(v => (
                                      <option key={v.id} value={v.id}>
                                        {v.name}{v.quote_template_path ? " ✓" : " (견적서 파일 없음)"}
                                      </option>
                                    ))}
                                </select>
                              )}
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                    <Button
                      size="sm"
                      disabled={isGenerating}
                      onClick={() => generateMutation.mutate(expense.id)}
                      className="gap-1.5"
                    >
                      {isGenerating ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          생성 중...
                        </>
                      ) : (
                        <>
                          <FolderOpen className="w-3.5 h-3.5" />
                          문서세트 생성
                        </>
                      )}
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {result ? (
                    <div className="space-y-1.5">
                      <div className="flex gap-3 text-xs text-gray-400 pb-1.5 border-b mb-2">
                        <span>전체 {result.total}건</span>
                        <span className="text-green-600">
                          완료 {result.generated}건
                        </span>
                        {result.errors > 0 && (
                          <span className="text-orange-600">
                            미완료 {result.errors}건
                          </span>
                        )}
                      </div>
                      {result.items.map((item, idx) => {
                        const cfg =
                          STATUS_CONFIG[item.status] ?? STATUS_CONFIG.error;
                        const Icon = cfg.icon;
                        const canDownload = !!item.generated_document_id;
                        const docLabel =
                          DOC_TYPE_LABELS[item.document_type] ??
                          (item.output_path
                            ? item.output_path.split("/").pop() ?? item.document_type
                            : item.document_type);
                        return (
                          <div
                            key={item.generated_document_id ?? `${item.document_type}-${idx}`}
                            className="flex items-center justify-between py-1"
                          >
                            <div className="flex items-center gap-2">
                              <FileText className="w-3.5 h-3.5 text-gray-400" />
                              <span className="text-sm text-gray-700">
                                {docLabel}
                              </span>
                              {item.error_message && (
                                <span className="text-xs text-gray-400">
                                  ({item.error_message})
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              <Badge className={`text-xs gap-1 ${cfg.color}`}>
                                <Icon className="w-3 h-3" />
                                {cfg.label}
                              </Badge>
                              {canDownload && (
                                <a
                                  href={documentSetsApi.downloadUrl(item.generated_document_id!)}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-blue-600 text-white hover:bg-blue-700"
                                >
                                  <Download className="w-3 h-3" />
                                  다운로드
                                </a>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="space-y-1">
                      <p className="text-xs text-gray-400 mb-1.5">
                        예상 문서세트 ({docSet.length}건):
                      </p>
                      {docSet.map((doc) => (
                        <div
                          key={doc.key}
                          className="flex items-center gap-2 text-xs text-gray-500 py-0.5"
                        >
                          <FileText className="w-3 h-3 shrink-0" />
                          <span>{doc.label}</span>
                          {doc.note && (
                            <span className="text-blue-500">({doc.note})</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
