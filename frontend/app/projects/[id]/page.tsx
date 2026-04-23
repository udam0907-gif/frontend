"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { projectsApi, expensesApi } from "@/lib/api";
import {
  CATEGORY_LABELS,
  EXPENSE_STATUS_COLORS,
  EXPENSE_STATUS_LABELS,
} from "@/lib/constants";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ReceiptText,
  FileText,
  Building2,
  Printer,
  TrendingUp,
  CalendarClock,
} from "lucide-react";
import Link from "next/link";
import { formatCurrency } from "@/lib/utils";

export default function ProjectDashboardPage() {
  const params = useParams();
  const projectId = params.id as string;

  const { data: project, isLoading: projLoading } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => projectsApi.get(projectId),
    enabled: !!projectId,
  });

  const { data: expenses, isLoading: expLoading } = useQuery({
    queryKey: ["expenses", projectId],
    queryFn: () => expensesApi.list(projectId),
    enabled: !!projectId,
  });

  const totalSpent =
    expenses?.reduce((sum, e) => sum + e.amount, 0) ?? 0;
  const executionRate =
    project && project.total_budget > 0
      ? Math.min(100, Math.round((totalSpent / project.total_budget) * 100))
      : 0;

  const recentExpenses = (expenses ?? []).slice(0, 6);

  const quickActions = [
    {
      label: "비용집행 등록",
      href: `/projects/${projectId}/expenses`,
      icon: ReceiptText,
      color: "bg-blue-50 text-blue-600 hover:bg-blue-100",
    },
    {
      label: "템플릿 관리",
      href: `/projects/${projectId}/templates`,
      icon: FileText,
      color: "bg-purple-50 text-purple-600 hover:bg-purple-100",
    },
    {
      label: "업체 관리",
      href: `/projects/${projectId}/vendors`,
      icon: Building2,
      color: "bg-green-50 text-green-600 hover:bg-green-100",
    },
    {
      label: "문서 출력",
      href: `/projects/${projectId}/docs`,
      icon: Printer,
      color: "bg-orange-50 text-orange-600 hover:bg-orange-100",
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        {projLoading ? (
          <Skeleton className="h-7 w-64" />
        ) : (
          <>
            <h2 className="text-xl font-bold text-gray-900">
              {project?.name ?? "과제 대시보드"}
            </h2>
            <p className="text-sm text-gray-500 mt-0.5">
              {project?.code} · {project?.institution}
            </p>
          </>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-5">
            <p className="text-xs text-gray-500 mb-1">총 예산</p>
            {projLoading ? (
              <Skeleton className="h-6 w-28" />
            ) : (
              <p className="text-lg font-bold text-gray-900">
                {formatCurrency(project?.total_budget ?? 0)}
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <p className="text-xs text-gray-500 mb-1">집행액</p>
            {expLoading ? (
              <Skeleton className="h-6 w-28" />
            ) : (
              <p className="text-lg font-bold text-gray-900">
                {formatCurrency(totalSpent)}
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <p className="text-xs text-gray-500 mb-1">집행률</p>
            {expLoading || projLoading ? (
              <Skeleton className="h-6 w-16" />
            ) : (
              <div className="flex items-center gap-2">
                <p className="text-lg font-bold text-gray-900">
                  {executionRate}%
                </p>
                <TrendingUp className="w-4 h-4 text-blue-500" />
              </div>
            )}
            {!expLoading && !projLoading && (
              <div className="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full transition-all"
                  style={{ width: `${executionRate}%` }}
                />
              </div>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <p className="text-xs text-gray-500 mb-1">집행 건수</p>
            {expLoading ? (
              <Skeleton className="h-6 w-12" />
            ) : (
              <div className="flex items-center gap-2">
                <p className="text-lg font-bold text-gray-900">
                  {expenses?.length ?? 0}건
                </p>
                <CalendarClock className="w-4 h-4 text-purple-500" />
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">빠른 실행</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {quickActions.map(({ label, href, icon: Icon, color }) => (
              <Link key={href} href={href}>
                <button
                  className={`w-full flex flex-col items-center gap-2 p-4 rounded-lg transition-colors ${color}`}
                >
                  <Icon className="w-6 h-6" />
                  <span className="text-sm font-medium">{label}</span>
                </button>
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Recent Expenses */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">최근 비용집행</CardTitle>
            <Link href={`/projects/${projectId}/expenses`}>
              <Button variant="ghost" size="sm" className="text-xs text-blue-600">
                전체 보기
              </Button>
            </Link>
          </div>
        </CardHeader>
        <CardContent>
          {expLoading ? (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : recentExpenses.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-sm text-gray-400">등록된 비용집행이 없습니다</p>
              <Link href={`/projects/${projectId}/expenses`}>
                <Button variant="outline" size="sm" className="mt-3">
                  비용집행 등록
                </Button>
              </Link>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {recentExpenses.map((expense) => (
                <div
                  key={expense.id}
                  className="flex items-center justify-between py-3"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-medium px-2 py-0.5 bg-gray-100 text-gray-600 rounded">
                      {CATEGORY_LABELS[expense.category_type]}
                    </span>
                    <span className="text-sm font-medium text-gray-800">
                      {expense.title}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-gray-600">
                      {formatCurrency(expense.amount)}
                    </span>
                    <Badge
                      className={`text-xs ${EXPENSE_STATUS_COLORS[expense.status]}`}
                    >
                      {EXPENSE_STATUS_LABELS[expense.status]}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Budget breakdown */}
      {(project?.budget_categories ?? []).length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">비목별 예산 현황</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {(project?.budget_categories ?? []).map((cat) => {
                const rate =
                  cat.allocated_amount > 0
                    ? Math.min(
                        100,
                        Math.round((cat.spent_amount / cat.allocated_amount) * 100)
                      )
                    : 0;
                return (
                  <div key={cat.id} className="space-y-1">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-700">
                        {CATEGORY_LABELS[cat.category_type] ?? cat.category_type}
                      </span>
                      <span className="text-gray-500 text-xs">
                        {formatCurrency(cat.spent_amount)} /{" "}
                        {formatCurrency(cat.allocated_amount)} ({rate}%)
                      </span>
                    </div>
                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-400 rounded-full"
                        style={{ width: `${rate}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
