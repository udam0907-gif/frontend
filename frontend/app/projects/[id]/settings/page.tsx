"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { projectsApi, expensesApi } from "@/lib/api";
import { CATEGORY_LABELS, PROJECT_STATUS_LABELS } from "@/lib/constants";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Settings,
  CalendarRange,
  User,
  Building,
  DollarSign,
  Activity,
} from "lucide-react";
import { formatCurrency } from "@/lib/utils";

const STATUS_COLOR: Record<string, string> = {
  active: "bg-green-100 text-green-700",
  closed: "bg-gray-100 text-gray-600",
  suspended: "bg-yellow-100 text-yellow-700",
};

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start gap-4 py-3 border-b border-gray-50 last:border-0">
      <span className="text-sm text-gray-500 w-32 shrink-0">{label}</span>
      <span className="text-sm text-gray-800 font-medium flex-1">{value}</span>
    </div>
  );
}

export default function ProjectSettingsPage() {
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

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-900">과제 설정</h2>
        <p className="text-sm text-gray-500 mt-0.5">
          과제 기본 정보 및 예산 현황
        </p>
      </div>

      {/* 기본 정보 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Settings className="w-4 h-4" />
            기본 정보
          </CardTitle>
        </CardHeader>
        <CardContent>
          {projLoading ? (
            <div className="space-y-3">
              {[...Array(6)].map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : project ? (
            <div>
              <InfoRow label="과제명" value={project.name} />
              <InfoRow label="과제 코드" value={project.code} />
              <InfoRow
                label="주관기관"
                value={
                  <span className="flex items-center gap-1.5">
                    <Building className="w-3.5 h-3.5 text-gray-400" />
                    {project.institution}
                  </span>
                }
              />
              <InfoRow
                label="책임연구원"
                value={
                  <span className="flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5 text-gray-400" />
                    {project.principal_investigator}
                  </span>
                }
              />
              <InfoRow
                label="사업기간"
                value={
                  <span className="flex items-center gap-1.5">
                    <CalendarRange className="w-3.5 h-3.5 text-gray-400" />
                    {project.period_start} ~ {project.period_end}
                  </span>
                }
              />
              <InfoRow
                label="과제 상태"
                value={
                  <Badge
                    className={`text-xs ${STATUS_COLOR[project.status] ?? ""}`}
                  >
                    {PROJECT_STATUS_LABELS[project.status]}
                  </Badge>
                }
              />
              <InfoRow
                label="등록일"
                value={new Date(project.created_at).toLocaleDateString("ko-KR")}
              />
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* 예산 현황 카드 */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-5 flex items-center gap-4">
            <div className="p-3 bg-blue-50 rounded-lg">
              <DollarSign className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-xs text-gray-500">총 예산</p>
              {projLoading ? (
                <Skeleton className="h-6 w-28 mt-1" />
              ) : (
                <p className="text-lg font-bold text-gray-900">
                  {formatCurrency(project?.total_budget ?? 0)}
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5 flex items-center gap-4">
            <div className="p-3 bg-purple-50 rounded-lg">
              <Activity className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <p className="text-xs text-gray-500">집행액</p>
              {expLoading ? (
                <Skeleton className="h-6 w-28 mt-1" />
              ) : (
                <p className="text-lg font-bold text-gray-900">
                  {formatCurrency(totalSpent)}
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5 flex items-center gap-4">
            <div className="p-3 bg-green-50 rounded-lg">
              <Activity className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <p className="text-xs text-gray-500">잔여 예산</p>
              {expLoading || projLoading ? (
                <Skeleton className="h-6 w-28 mt-1" />
              ) : (
                <p className="text-lg font-bold text-gray-900">
                  {formatCurrency((project?.total_budget ?? 0) - totalSpent)}
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 집행률 */}
      {!projLoading && !expLoading && project && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">집행률</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between text-sm mb-2">
              <span className="text-gray-600">
                {formatCurrency(totalSpent)} / {formatCurrency(project.total_budget)}
              </span>
              <span className="font-bold text-gray-800">{executionRate}%</span>
            </div>
            <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  executionRate >= 90
                    ? "bg-red-500"
                    : executionRate >= 70
                    ? "bg-yellow-500"
                    : "bg-blue-500"
                }`}
                style={{ width: `${executionRate}%` }}
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* 비목별 예산 */}
      {(project?.budget_categories ?? []).length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">비목별 예산 배정</CardTitle>
          </CardHeader>
          <CardContent>
            {projLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : (
              <div className="space-y-3">
                {(project?.budget_categories ?? []).map((cat) => {
                  const rate =
                    cat.allocated_amount > 0
                      ? Math.min(
                          100,
                          Math.round(
                            (cat.spent_amount / cat.allocated_amount) * 100
                          )
                        )
                      : 0;
                  return (
                    <div key={cat.id} className="space-y-1">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-700 font-medium">
                          {CATEGORY_LABELS[cat.category_type] ??
                            cat.category_type}
                        </span>
                        <span className="text-gray-500 text-xs">
                          {formatCurrency(cat.spent_amount)} /{" "}
                          {formatCurrency(cat.allocated_amount)}
                        </span>
                      </div>
                      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-400 rounded-full"
                          style={{ width: `${rate}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* 수정 기능 안내 */}
      <Card className="border-dashed border-gray-200">
        <CardContent className="p-4 text-center">
          <p className="text-sm text-gray-400">
            과제 정보 수정 기능은 추후 지원 예정입니다.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
