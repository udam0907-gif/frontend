"use client";

import { useQuery } from "@tanstack/react-query";
import { backupApi, type BackupFile } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Database, Archive, FileText, Download, RefreshCw } from "lucide-react";

const TYPE_ICON: Record<string, React.ReactNode> = {
  ".sql": <Database className="w-5 h-5 text-blue-500" />,
  ".tar.gz": <Archive className="w-5 h-5 text-orange-500" />,
  ".gz": <Archive className="w-5 h-5 text-orange-500" />,
  ".md": <FileText className="w-5 h-5 text-gray-500" />,
};

const TYPE_COLOR: Record<string, string> = {
  "DB 백업": "bg-blue-100 text-blue-700",
  "파일 백업": "bg-orange-100 text-orange-700",
  "복원 가이드": "bg-gray-100 text-gray-600",
};

function FileRow({ file }: { file: BackupFile }) {
  const icon = TYPE_ICON[file.suffix] ?? <FileText className="w-5 h-5 text-gray-400" />;
  const badgeClass = TYPE_COLOR[file.type_label] ?? "bg-gray-100 text-gray-600";

  return (
    <div className="flex items-center justify-between py-3 px-4 border-b border-gray-100 last:border-0 hover:bg-gray-50 transition-colors">
      <div className="flex items-center gap-3 min-w-0">
        {icon}
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">{file.name}</p>
          <p className="text-xs text-gray-400">{file.created_at}</p>
        </div>
      </div>
      <div className="flex items-center gap-3 shrink-0 ml-4">
        <span className="text-xs text-gray-500">{file.size_label}</span>
        <Badge className={badgeClass}>{file.type_label}</Badge>
        <a href={backupApi.downloadUrl(file.name)} download>
          <Button variant="outline" size="sm" className="gap-1.5">
            <Download className="w-3.5 h-3.5" />
            다운로드
          </Button>
        </a>
      </div>
    </div>
  );
}

function RestoreGuide({ content }: { content: string }) {
  if (!content) return null;
  const lines = content.split("\n");
  return (
    <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono bg-gray-50 rounded-md p-4 leading-relaxed overflow-x-auto">
      {lines.join("\n")}
    </pre>
  );
}

export default function BackupPage() {
  const { data: files, isLoading: filesLoading, refetch } = useQuery({
    queryKey: ["backup-files"],
    queryFn: backupApi.listFiles,
  });

  const { data: guide, isLoading: guideLoading } = useQuery({
    queryKey: ["backup-restore-guide"],
    queryFn: backupApi.getRestoreGuide,
  });

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">백업 관리</h1>
          <p className="text-sm text-gray-500 mt-0.5">백업 파일 목록 및 복원 가이드</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()} className="gap-1.5">
          <RefreshCw className="w-3.5 h-3.5" />
          새로고침
        </Button>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">백업 파일 목록</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {filesLoading ? (
            <div className="space-y-3 p-4">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : !files || files.length === 0 ? (
            <div className="py-12 text-center text-sm text-gray-400">백업 파일이 없습니다.</div>
          ) : (
            <div>
              {files.map((f) => <FileRow key={f.name} file={f} />)}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">복원 가이드</CardTitle>
        </CardHeader>
        <CardContent>
          {guideLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : (
            <RestoreGuide content={guide?.content ?? ""} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
