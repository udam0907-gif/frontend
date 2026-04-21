"use client";

import { useQuery } from "@tanstack/react-query";
import { projectsApi } from "@/lib/api";
import { CATEGORY_LABELS, PROJECT_STATUS_LABELS } from "@/lib/constants";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Plus, ChevronRight } from "lucide-react";
import Link from "next/link";

const STATUS_COLOR: Record<string, string> = {
  active: "bg-green-100 text-green-700",
  closed: "bg-gray-100 text-gray-600",
  suspended: "bg-yellow-100 text-yellow-700",
};

export default function ProjectsPage() {
  const { data: projects, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900">과제 목록</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            R&D 과제 목록 · 과제를 선택하여 상세 관리로 이동합니다
          </p>
        </div>
        <Link href="/projects/new">
          <Button size="sm" className="gap-1.5">
            <Plus className="w-4 h-4" />
            과제 등록
          </Button>
        </Link>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-28 w-full rounded-lg" />
          ))}
        </div>
      ) : (projects ?? []).length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <p className="text-gray-400 text-sm">등록된 과제가 없습니다</p>
            <Link href="/projects/new">
              <Button variant="outline" className="mt-4" size="sm">
                과제 등록하기
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {(projects ?? []).map((project) => (
            <Card
              key={project.id}
              className="hover:shadow-sm transition-shadow"
            >
              <CardContent className="p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0 space-y-1">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-gray-900 truncate">
                        {project.name}
                      </h3>
                      <Badge
                        className={`text-xs shrink-0 ${STATUS_COLOR[project.status]}`}
                      >
                        {PROJECT_STATUS_LABELS[project.status]}
                      </Badge>
                    </div>
                    <p className="text-sm text-gray-500">
                      {project.code} · {project.institution} ·{" "}
                      {project.principal_investigator}
                    </p>
                    <p className="text-xs text-gray-400">
                      {project.period_start} ~ {project.period_end}
                    </p>
                    {(project.budget_categories ?? []).length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {(project.budget_categories ?? []).map((cat) => (
                          <span
                            key={cat.id}
                            className="text-xs px-2 py-0.5 bg-blue-50 text-blue-600 rounded"
                          >
                            {CATEGORY_LABELS[cat.category_type] ??
                              cat.category_type}
                            : {cat.allocated_amount.toLocaleString()}원
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="flex flex-col items-end gap-3 shrink-0">
                    <div className="text-right">
                      <p className="text-lg font-bold text-gray-800">
                        {project.total_budget.toLocaleString()}원
                      </p>
                      <p className="text-xs text-gray-400 mt-0.5">총 예산</p>
                    </div>
                    <Link href={`/projects/${project.id}`}>
                      <Button size="sm" className="gap-1.5">
                        선택
                        <ChevronRight className="w-3.5 h-3.5" />
                      </Button>
                    </Link>
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
