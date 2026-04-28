"use client";

import { useQuery } from "@tanstack/react-query";
import { expensesApi, projectsApi } from "@/lib/api";
import {
  EXPENSE_STATUS_COLORS,
  EXPENSE_STATUS_LABELS,
  PROJECT_STATUS_LABELS,
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
  FolderOpen,
  FolderCheck,
  FolderClock,
  FolderX,
  ReceiptText,
  CheckCircle2,
  AlertCircle,
  ChevronRight,
  Plus,
} from "lucide-react";
import Link from "next/link";
import { fmt } from "@/lib/utils";

const STATUS_COLOR: Record<string, string> = {
  active: "bg-green-100 text-green-700",
  closed: "bg-gray-100 text-gray-600",
  suspended: "bg-yellow-100 text-yellow-700",
};

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
            <p className="text-2xl font-bold text-gray-900">{fmt(value ?? 0)}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function AllDashboardPage() {
  const { data: projects, isLoading: projLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });

  const { data: expenses, isLoading: expLoading } = useQuery({
    queryKey: ["expenses"],
    queryFn: () => expensesApi.list(),
  });

  const totalProjects = projects?.length ?? 0;
  const activeProjects = projects?.filter((p) => p.status === "active").length ?? 0;
  const closedProjects = projects?.filter((p) => p.status === "closed").length ?? 0;
  const suspendedProjects = projects?.filter((p) => p.status === "suspended").length ?? 0;

  const totalExpenses = expenses?.length ?? 0;
  const exportedExpenses = expenses?.filter((e) => e.status === "exported").length ?? 0;

  // 이번 달 집행건 (expense_date 기준)
  const now = new Date();
  const thisMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const thisMonthExpenses =
    expenses?.filter(
      (e) => e.expense_date && e.expense_date.startsWith(thisMonth)
    ).length ?? 0;

  // 최근 작업 과제 (최대 5개)
  const recentProjects = (projects ?? []).slice(0, 5);

  // 마감 임박 과제 (종료일이 90일 이내인 진행 중 과제)
  const urgentProjects = (projects ?? []).filter((p) => {
    if (p.status !== "active") return false;
    const endDate = new Date(p.period_end);
    const diffDays = Math.ceil(
      (endDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)
    );
    return diffDays >= 0 && diffDays <= 90;
  });

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-bold text-gray-900">전체 과제 대시보드</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            모든 R&D 과제의 집행 현황을 한눈에 확인합니다
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/projects">
            <Button variant="outline" size="sm" className="gap-1.5">
              <FolderOpen className="w-4 h-4" />
              과제 목록 보기
            </Button>
          </Link>
          <Link href="/projects/new">
            <Button size="sm" className="gap-1.5">
              <Plus className="w-4 h-4" />
              새 과제 생성
            </Button>
          </Link>
        </div>
      </div>

      {/* 과제 개요 Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="전체 과제"
          value={totalProjects}
          icon={FolderOpen}
          color="bg-blue-50 text-blue-600"
          loading={projLoading}
        />
        <StatCard
          title="진행 중"
          value={activeProjects}
          icon={FolderCheck}
          color="bg-green-50 text-green-600"
          loading={projLoading}
        />
        <StatCard
          title="종료 예정"
          value={urgentProjects.length}
          icon={FolderClock}
          color="bg-yellow-50 text-yellow-600"
          loading={projLoading}
        />
        <StatCard
          title="종료"
          value={closedProjects + suspendedProjects}
          icon={FolderX}
          color="bg-gray-100 text-gray-600"
          loading={projLoading}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 최근 작업 과제 목록 */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">최근 과제 목록</CardTitle>
                <Link href="/projects">
                  <Button variant="ghost" size="sm" className="text-xs text-blue-600">
                    전체 보기
                  </Button>
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              {projLoading ? (
                <div className="space-y-3">
                  {[...Array(4)].map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : recentProjects.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-8">
                  등록된 과제가 없습니다
                </p>
              ) : (
                <div className="divide-y divide-gray-100">
                  {recentProjects.map((project) => (
                    <div
                      key={project.id}
                      className="flex items-center justify-between py-3"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <p className="text-sm font-semibold text-gray-800 truncate">
                            {project.name}
                          </p>
                          <Badge
                            className={`text-xs shrink-0 ${STATUS_COLOR[project.status]}`}
                          >
                            {PROJECT_STATUS_LABELS[project.status]}
                          </Badge>
                        </div>
                        <p className="text-xs text-gray-400">
                          {project.code} · {project.institution} ·{" "}
                          {project.period_start} ~ {project.period_end}
                        </p>
                      </div>
                      <Link href={`/projects/${project.id}`} className="ml-3 shrink-0">
                        <Button size="sm" variant="outline" className="gap-1 text-xs">
                          과제 들어가기
                          <ChevronRight className="w-3.5 h-3.5" />
                        </Button>
                      </Link>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* 우측 요약 카드 */}
        <div className="space-y-4">
          {/* 요약 Stats */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-gray-600">집행 요약</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <FolderCheck className="w-4 h-4 text-green-500" />
                  진행 중 과제
                </div>
                {projLoading ? (
                  <Skeleton className="h-5 w-8" />
                ) : (
                  <span className="font-bold text-gray-900">{fmt(activeProjects)}건</span>
                )}
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <ReceiptText className="w-4 h-4 text-blue-500" />
                  이번달 집행건
                </div>
                {expLoading ? (
                  <Skeleton className="h-5 w-8" />
                ) : (
                  <span className="font-bold text-gray-900">{fmt(thisMonthExpenses)}건</span>
                )}
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <CheckCircle2 className="w-4 h-4 text-purple-500" />
                  출력완료
                </div>
                {expLoading ? (
                  <Skeleton className="h-5 w-8" />
                ) : (
                  <span className="font-bold text-gray-900">{fmt(exportedExpenses)}건</span>
                )}
              </div>
            </CardContent>
          </Card>

          {/* 마감 임박 */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-gray-600 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-yellow-500" />
                마감 임박 과제
              </CardTitle>
            </CardHeader>
            <CardContent>
              {projLoading ? (
                <Skeleton className="h-16 w-full" />
              ) : urgentProjects.length === 0 ? (
                <p className="text-xs text-gray-400 text-center py-4">
                  90일 이내 마감 과제 없음
                </p>
              ) : (
                <div className="space-y-2">
                  {urgentProjects.slice(0, 3).map((p) => {
                    const endDate = new Date(p.period_end);
                    const diffDays = Math.ceil(
                      (endDate.getTime() - now.getTime()) /
                        (1000 * 60 * 60 * 24)
                    );
                    return (
                      <Link
                        key={p.id}
                        href={`/projects/${p.id}`}
                        className="block p-2.5 rounded-md bg-yellow-50 hover:bg-yellow-100 transition-colors"
                      >
                        <p className="text-xs font-semibold text-gray-800 truncate">
                          {p.name}
                        </p>
                        <p className="text-xs text-yellow-700 mt-0.5">
                          D-{diffDays} ({p.period_end})
                        </p>
                      </Link>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {/* 구조 원칙 안내 */}
          <Card className="bg-gray-50 border-gray-200">
            <CardContent className="p-4">
              <p className="text-xs font-semibold text-gray-600 mb-2">운영 원칙</p>
              <ul className="text-xs text-gray-500 space-y-1">
                <li>서식 구조는 절대 변경 불가</li>
                <li>검증 실패 상태로 내보내기 불가</li>
                <li>모든 집행에 근거와 로그 필수</li>
                <li>회사 데이터는 과제별로 격리</li>
              </ul>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* 전체 집행 현황 요약 */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          title="전체 집행 건수"
          value={totalExpenses}
          icon={ReceiptText}
          color="bg-blue-50 text-blue-600"
          loading={expLoading}
        />
        <StatCard
          title="이번달 집행"
          value={thisMonthExpenses}
          icon={FolderClock}
          color="bg-purple-50 text-purple-600"
          loading={expLoading}
        />
        <StatCard
          title="출력 완료"
          value={exportedExpenses}
          icon={CheckCircle2}
          color="bg-green-50 text-green-600"
          loading={expLoading}
        />
      </div>
    </div>
  );
}
