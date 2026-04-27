"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { expensesApi } from "@/lib/api";
import {
  CATEGORY_LABELS,
  EXPENSE_STATUS_COLORS,
  EXPENSE_STATUS_LABELS,
} from "@/lib/constants";
import type { CategoryType, ExpenseItem } from "@/lib/types";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ClipboardList } from "lucide-react";
import { formatCurrency } from "@/lib/utils";

// 비목별 상세 필드 정의
const DETAIL_FIELDS: Record<CategoryType, { key: string; label: string }[]> = {
  meeting: [
    { key: "attendee_count", label: "참석자 수" },
    { key: "purpose", label: "사용목적" },
  ],
  materials: [
    { key: "product_name", label: "상품명" },
    { key: "quantity", label: "수량" },
    { key: "unit_price", label: "단가 (원)" },
  ],
  outsourcing: [
    { key: "product_name", label: "상품명" },
    { key: "work_content", label: "작업내용" },
    { key: "specification", label: "산출내역/규격" },
  ],
  test_report: [
    { key: "test_institution", label: "시험기관명" },
    { key: "test_items", label: "시험항목" },
  ],
  labor: [
    { key: "researcher_name", label: "연구원명" },
    { key: "payment_type", label: "지급구분" },
    { key: "participation_months", label: "참여기간 (개월)" },
    { key: "participation_rate", label: "참여율 (%)" },
  ],
  other: [],
};

function formatValue(key: string, value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (key === "payment_type") {
    return value === "cash" ? "현금" : value === "in_kind" ? "현물" : String(value);
  }
  if (typeof value === "number") {
    if (key === "unit_price" || key === "amount") return formatCurrency(value);
    return value.toLocaleString("ko-KR");
  }
  return String(value);
}

function ExpenseDetailCard({ expense }: { expense: ExpenseItem }) {
  const fields = DETAIL_FIELDS[expense.category_type] ?? [];
  const inputData = expense.input_data ?? {};

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium px-2 py-0.5 bg-gray-100 text-gray-600 rounded">
              {CATEGORY_LABELS[expense.category_type]}
            </span>
            <span className="text-sm font-semibold text-gray-800">
              {expense.title}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm font-bold text-gray-700">
              {formatCurrency(expense.amount)}
            </span>
            <Badge
              className={`text-xs ${EXPENSE_STATUS_COLORS[expense.status]}`}
            >
              {EXPENSE_STATUS_LABELS[expense.status]}
            </Badge>
          </div>
        </div>
        {(expense.vendor_name || expense.expense_date) && (
          <p className="text-xs text-gray-400 mt-1">
            {expense.vendor_name && `업체: ${expense.vendor_name}`}
            {expense.vendor_name && expense.expense_date && " · "}
            {expense.expense_date && `집행일: ${expense.expense_date}`}
          </p>
        )}
      </CardHeader>
      <CardContent>
        {fields.length === 0 ? (
          <p className="text-xs text-gray-400">상세 필드 없음</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-2 px-2 text-xs font-semibold text-gray-500 w-36">
                    항목
                  </th>
                  <th className="text-left py-2 px-2 text-xs font-semibold text-gray-500">
                    값
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {fields.map((field) => (
                  <tr key={field.key}>
                    <td className="py-2 px-2 text-gray-500 font-medium">
                      {field.label}
                    </td>
                    <td className="py-2 px-2 text-gray-800">
                      {formatValue(field.key, inputData[field.key])}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* 첨부 문서 */}
        {(expense.documents ?? []).length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            <p className="text-xs font-semibold text-gray-400 mb-2">첨부 서류</p>
            <div className="flex flex-wrap gap-2">
              {expense.documents.map((doc) => (
                <span
                  key={doc.id}
                  className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded"
                >
                  {doc.original_filename}
                </span>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function ProjectDetailsPage() {
  const params = useParams();
  const projectId = params.id as string;

  const { data: expenses, isLoading } = useQuery({
    queryKey: ["expenses", projectId],
    queryFn: () => expensesApi.list(projectId),
    enabled: !!projectId,
  });

  // 비목별 그룹핑
  const grouped = (expenses ?? []).reduce<Record<string, ExpenseItem[]>>(
    (acc, expense) => {
      const key = expense.category_type;
      if (!acc[key]) acc[key] = [];
      acc[key].push(expense);
      return acc;
    },
    {}
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-900">집행상세</h2>
        <p className="text-sm text-gray-500 mt-0.5">
          비용집행별 상세 필드 내용을 확인합니다
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-40 w-full rounded-lg" />
          ))}
        </div>
      ) : (expenses ?? []).length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <ClipboardList className="w-8 h-8 text-gray-300 mx-auto mb-3" />
            <p className="text-sm text-gray-400">등록된 비용집행이 없습니다</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {(Object.entries(grouped) as [CategoryType, ExpenseItem[]][]).map(
            ([category, items]) => (
              <div key={category} className="space-y-3">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-semibold text-gray-700">
                    {CATEGORY_LABELS[category]}
                  </h3>
                  <span className="text-xs text-gray-400">{items.length}건</span>
                </div>
                {items.map((expense) => (
                  <ExpenseDetailCard key={expense.id} expense={expense} />
                ))}
              </div>
            )
          )}
        </div>
      )}
    </div>
  );
}
