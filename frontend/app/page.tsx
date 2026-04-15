"use client";

import { useQuery } from "@tanstack/react-query";
import { expensesApi, projectsApi } from "@/lib/api";
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  FolderOpen,
  ReceiptText,
  CheckCircle2,
  AlertTriangle,
  Clock,
  XCircle,
} from "lucide-react";
import Link from "next/link";

function StatCard({
  title,
  value,
  icon: Icon,
  color,
  loading,
}: {
  title: string;
  value: number | undefined;
  icon: React.ElementType;
  color: string;
  loading: boolean;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className={`p-3 rounded-lg ${color}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          {loading ? (
            <Skeleton className="h-7 w-12 mt-1" />
          ) : (
            <p className="text-2xl font-bold text-gray-900">{value ?? 0}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { data: projects, isLoading: projLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });

  const { data: expenses, isLoading: expLoading } = useQuery({
    queryKey: ["expenses"],
    queryFn: () => expensesApi.list(),
  });

  const activeProjects = projects?.filter((p) => p.status === "active").length ?? 0;
  const totalExpenses = expenses?.length ?? 0;
  const pendingValidation =
    expenses?.filter((e) => e.status === "pending_validation").length ?? 0;
  const validated =
    expenses?.filter((e) => e.status === "validated").length ?? 0;
  const rejected =
    expenses?.filter((e) => e.status === "rejected").length ?? 0;

  const recentExpenses = expenses?.slice(0, 8) ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-900">대시보드</h2>
        <p className="text-sm text-gray-500 mt-0.5">
          R&D 과제 비용 집행 현황을 한눈에 확인하세요
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          title="진행 중 과제"
          value={activeProjects}
          icon={FolderOpen}
          color="bg-blue-50 text-blue-600"
          loading={projLoading}
        />
        <StatCard
          title="전체 비용 항목"
          value={totalExpenses}
          icon={ReceiptText}
          color="bg-purple-50 text-purple-600"
          loading={expLoading}
        />
        <StatCard
          title="검증 대기"
          value={pendingValidation}
          icon={Clock}
          color="bg-yellow-50 text-yellow-600"
          loading={expLoading}
        />
        <StatCard
          title="검증 완료"
          value={validated}
          icon={CheckCircle2}
          color="bg-green-50 text-green-600"
          loading={expLoading}
        />
        <StatCard
          title="반려"
          value={rejected}
          icon={XCircle}
          color="bg-red-50 text-red-600"
          loading={expLoading}
        />
      </div>

      {/* Recent Expenses */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">최근 비용 집행 항목</CardTitle>
        </CardHeader>
        <CardContent>
          {expLoading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : recentExpenses.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-8">
              등록된 비용 항목이 없습니다
            </p>
          ) : (
            <div className="divide-y divide-gray-100">
              {recentExpenses.map((expense) => (
                <Link
                  key={expense.id}
                  href={`/expenses/${expense.id}`}
                  className="flex items-center justify-between py-3 hover:bg-gray-50 -mx-2 px-2 rounded transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-medium px-2 py-0.5 bg-gray-100 text-gray-600 rounded">
                      {CATEGORY_LABELS[expense.category_type]}
                    </span>
                    <span className="text-sm font-medium text-gray-800">
                      {expense.title}
                    </span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-sm text-gray-600">
                      {expense.amount.toLocaleString()}원
                    </span>
                    <Badge
                      className={`text-xs ${EXPENSE_STATUS_COLORS[expense.status]}`}
                    >
                      {EXPENSE_STATUS_LABELS[expense.status]}
                    </Badge>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Projects summary */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">과제 목록</CardTitle>
        </CardHeader>
        <CardContent>
          {projLoading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : (projects ?? []).length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-8">
              등록된 과제가 없습니다
            </p>
          ) : (
            <div className="divide-y divide-gray-100">
              {(projects ?? []).slice(0, 5).map((project) => (
                <Link
                  key={project.id}
                  href={`/projects/${project.id}`}
                  className="flex items-center justify-between py-3 hover:bg-gray-50 -mx-2 px-2 rounded transition-colors"
                >
                  <div>
                    <p className="text-sm font-medium text-gray-800">
                      {project.name}
                    </p>
                    <p className="text-xs text-gray-400">
                      {project.code} · {project.institution}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-gray-700">
                      {project.total_budget.toLocaleString()}원
                    </p>
                    <p className="text-xs text-gray-400">
                      {project.period_start} ~ {project.period_end}
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
