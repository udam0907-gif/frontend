"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { projectsApi } from "@/lib/api";
import { PROJECT_STATUS_LABELS } from "@/lib/constants";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { ArrowLeft, CalendarRange, User, Activity } from "lucide-react";

const STATUS_COLOR: Record<string, string> = {
  active: "text-green-700 bg-green-100",
  closed: "text-gray-600 bg-gray-100",
  suspended: "text-yellow-700 bg-yellow-100",
};

export default function ProjectLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const { data: project, isLoading, isError } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => projectsApi.get(projectId),
    enabled: !!projectId,
  });

  return (
    <div className="space-y-4">
      {/* Project Context Bar */}
      <div className="rounded-lg bg-blue-50 border border-blue-200 px-4 py-3">
        {isLoading ? (
          <div className="flex items-center gap-4">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-4 w-24" />
          </div>
        ) : isError ? (
          <div className="flex items-center justify-between">
            <p className="text-sm text-red-600">과제 정보를 불러올 수 없습니다.</p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => router.push("/projects")}
            >
              <ArrowLeft className="w-3.5 h-3.5 mr-1" />
              과제 다시 선택
            </Button>
          </div>
        ) : project ? (
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-4 flex-wrap">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-semibold text-blue-500 uppercase tracking-wide">
                  선택 과제
                </span>
                <span className="text-sm font-bold text-blue-900">
                  {project.name}
                </span>
              </div>
              <div className="flex items-center gap-1 text-xs text-blue-700">
                <CalendarRange className="w-3.5 h-3.5" />
                {project.period_start} ~ {project.period_end}
              </div>
              <div className="flex items-center gap-1 text-xs text-blue-700">
                <User className="w-3.5 h-3.5" />
                {project.principal_investigator}
              </div>
              <div className="flex items-center gap-1 text-xs text-blue-700">
                <Activity className="w-3.5 h-3.5" />
                <span
                  className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                    STATUS_COLOR[project.status] ?? "text-gray-600"
                  }`}
                >
                  {PROJECT_STATUS_LABELS[project.status]}
                </span>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="text-blue-700 border-blue-300 hover:bg-blue-100 shrink-0"
              onClick={() => router.push("/projects")}
            >
              <ArrowLeft className="w-3.5 h-3.5 mr-1" />
              과제 다시 선택
            </Button>
          </div>
        ) : null}
      </div>

      {children}
    </div>
  );
}
