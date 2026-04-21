"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { expensesApi, projectsApi } from "@/lib/api";
import {
  CATEGORY_LABELS,
  EXPENSE_STATUS_COLORS,
  EXPENSE_STATUS_LABELS,
} from "@/lib/constants";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Info } from "lucide-react";
import Link from "next/link";

export default function AllExpensesPage() {
  const [projectFilter, setProjectFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });

  const { data: expenses, isLoading } = useQuery({
    queryKey: ["expenses", projectFilter, statusFilter],
    queryFn: () =>
      expensesApi.list(projectFilter || undefined, statusFilter || undefined),
  });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900">전체 집행현황</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            모든 과제의 비용집행 항목을 조회합니다
          </p>
        </div>
      </div>

      {/* 등록 안내 */}
      <div className="flex items-center gap-2 p-3 rounded-lg bg-blue-50 border border-blue-100">
        <Info className="w-4 h-4 text-blue-500 shrink-0" />
        <p className="text-sm text-blue-700">
          비용집행 등록은 각 과제 페이지에서 진행합니다.{" "}
          <Link href="/projects" className="underline font-medium">
            과제 목록에서 선택하세요.
          </Link>
        </p>
      </div>

      {/* 필터 */}
      <div className="flex gap-3 flex-wrap">
        <select
          className="border border-gray-200 rounded-md px-3 py-2 text-sm"
          value={projectFilter}
          onChange={(e) => setProjectFilter(e.target.value)}
        >
          <option value="">전체 과제</option>
          {(projects ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <select
          className="border border-gray-200 rounded-md px-3 py-2 text-sm"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">전체 상태</option>
          {Object.entries(EXPENSE_STATUS_LABELS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-20 w-full rounded-lg" />
          ))}
        </div>
      ) : (expenses ?? []).length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <p className="text-gray-400 text-sm">비용 항목이 없습니다</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {(expenses ?? []).map((expense) => (
            <Card
              key={expense.id}
              className="hover:shadow-sm transition-shadow"
            >
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-medium px-2 py-0.5 bg-gray-100 text-gray-600 rounded">
                      {CATEGORY_LABELS[expense.category_type]}
                    </span>
                    <div>
                      <p className="text-sm font-semibold text-gray-800">
                        {expense.title}
                      </p>
                      {expense.vendor_name && (
                        <p className="text-xs text-gray-400 mt-0.5">
                          {expense.vendor_name}
                          {expense.expense_date &&
                            ` · ${expense.expense_date}`}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-sm font-bold text-gray-700">
                      {expense.amount.toLocaleString()}원
                    </span>
                    <Badge
                      className={`text-xs ${
                        EXPENSE_STATUS_COLORS[expense.status]
                      }`}
                    >
                      {EXPENSE_STATUS_LABELS[expense.status]}
                    </Badge>
                    <span className="text-xs text-gray-400">
                      서류 {expense.documents?.length ?? 0}건
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
