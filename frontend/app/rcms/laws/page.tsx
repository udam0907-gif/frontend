"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { legalApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowLeft,
  RefreshCw,
  Scale,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Trash2,
  Download,
} from "lucide-react";
import Link from "next/link";
import type { LegalDoc } from "@/lib/types";

// ─── Status styling ───────────────────────────────────────────────────────────
const STATUS_COLORS: Record<string, string> = {
  pending:    "bg-gray-100 text-gray-600",
  processing: "bg-yellow-100 text-yellow-700",
  completed:  "bg-green-100 text-green-700",
  failed:     "bg-red-100 text-red-700",
};
const STATUS_LABELS: Record<string, string> = {
  pending:    "대기",
  processing: "동기화 중",
  completed:  "완료",
  failed:     "실패",
};

// ─── Default laws that can be synced ─────────────────────────────────────────
const DEFAULT_LAWS = [
  "국가연구개발혁신법",
  "국가연구개발혁신법 시행령",
  "국가연구개발사업 연구개발비 사용 기준",
] as const;

// ─── Single law card ──────────────────────────────────────────────────────────

function LegalDocCard({
  doc,
  onDelete,
  deleting,
}: {
  doc: LegalDoc;
  onDelete: (id: string) => void;
  deleting: boolean;
}) {
  const [confirmDelete, setConfirmDelete] = useState(false);

  return (
    <div className="py-3.5 flex items-start gap-3 border-b border-gray-100 last:border-0">
      <Scale className="w-5 h-5 text-purple-400 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <p className="text-sm font-medium text-gray-800 truncate">{doc.law_name}</p>
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-gray-400">
          {doc.promulgation_date && <span>공포: {doc.promulgation_date}</span>}
          {doc.effective_date && <span>시행: {doc.effective_date}</span>}
          {doc.total_articles != null && <span>{doc.total_articles}개 조문</span>}
          {doc.total_chunks != null && <span>{doc.total_chunks}청크</span>}
        </div>
        {doc.sync_error && (
          <p className="text-xs text-red-500 mt-0.5 truncate">{doc.sync_error}</p>
        )}
      </div>

      <Badge className={`text-xs shrink-0 flex items-center gap-1 ${STATUS_COLORS[doc.sync_status]}`}>
        {doc.sync_status === "processing" && <Loader2 className="w-3 h-3 animate-spin" />}
        {doc.sync_status === "completed" && <CheckCircle2 className="w-3 h-3" />}
        {STATUS_LABELS[doc.sync_status]}
      </Badge>

      <span className="text-xs text-gray-400 shrink-0">
        {new Date(doc.created_at).toLocaleDateString("ko-KR")}
      </span>

      {confirmDelete ? (
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => { onDelete(doc.id); setConfirmDelete(false); }}
            disabled={deleting}
            className="text-xs px-2 py-1 bg-red-500 text-white rounded hover:bg-red-600 disabled:opacity-50 transition-colors"
          >
            {deleting ? <Loader2 className="w-3 h-3 animate-spin" /> : "삭제"}
          </button>
          <button
            onClick={() => setConfirmDelete(false)}
            className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded hover:bg-gray-200 transition-colors"
          >
            취소
          </button>
        </div>
      ) : (
        <button
          onClick={() => setConfirmDelete(true)}
          className="shrink-0 p-1.5 text-gray-300 hover:text-red-400 hover:bg-red-50 rounded transition-colors"
          title="삭제"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function LegalDocsPage() {
  const queryClient = useQueryClient();
  const [customLawName, setCustomLawName] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const { data: docs, isLoading } = useQuery({
    queryKey: ["legal-docs"],
    queryFn: legalApi.list,
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.some(
        (d) => d.sync_status === "processing" || d.sync_status === "pending"
      ) ? 3000 : false;
    },
  });

  const syncMutation = useMutation({
    mutationFn: (lawName: string) => legalApi.syncLaw(lawName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["legal-docs"] });
      setCustomLawName("");
    },
  });

  const syncDefaultsMutation = useMutation({
    mutationFn: () => legalApi.syncDefaults(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["legal-docs"] });
    },
  });

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try {
      await legalApi.delete(id);
      queryClient.invalidateQueries({ queryKey: ["legal-docs"] });
    } finally {
      setDeletingId(null);
    }
  };

  const existingNames = new Set((docs ?? []).map((d) => d.law_name));
  const missingDefaults = DEFAULT_LAWS.filter((n) => !existingNames.has(n));

  return (
    <div className="max-w-3xl space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link href="/rcms">
          <Button variant="ghost" size="icon" className="w-8 h-8">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <div>
          <h2 className="text-xl font-bold text-gray-900">법령/규정 관리</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            국가법령정보 Open API에서 법령을 동기화합니다
          </p>
        </div>
      </div>

      {/* API key notice */}
      <div className="flex items-start gap-2.5 p-3.5 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
        <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold mb-0.5">Korea Law Open API 설정 필요</p>
          <p className="text-blue-700 text-xs">
            법령 동기화를 사용하려면{" "}
            <strong>law.go.kr</strong>에서 무료 회원가입 후 발급된 이메일을{" "}
            <code className="bg-blue-100 px-1 rounded">.env</code>의{" "}
            <code className="bg-blue-100 px-1 rounded">LAW_API_OC=이메일</code>에 설정하세요.
          </p>
        </div>
      </div>

      {/* Default laws sync */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Download className="w-4 h-4 text-purple-500" />
              기본 법령 동기화
            </CardTitle>
            <Button
              size="sm"
              className="gap-1.5 bg-purple-600 hover:bg-purple-700"
              onClick={() => syncDefaultsMutation.mutate()}
              disabled={syncDefaultsMutation.isPending}
            >
              {syncDefaultsMutation.isPending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <RefreshCw className="w-3.5 h-3.5" />
              )}
              전체 동기화
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {DEFAULT_LAWS.map((name) => {
            const existing = (docs ?? []).find((d) => d.law_name === name);
            return (
              <div key={name} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-gray-50 border border-gray-100">
                <Scale className="w-4 h-4 text-purple-400 shrink-0" />
                <span className="text-sm text-gray-700 flex-1">{name}</span>
                {existing ? (
                  <Badge className={`text-xs ${STATUS_COLORS[existing.sync_status]}`}>
                    {existing.sync_status === "processing" && <Loader2 className="w-3 h-3 animate-spin mr-1" />}
                    {STATUS_LABELS[existing.sync_status]}
                  </Badge>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-6 text-xs px-2"
                    onClick={() => syncMutation.mutate(name)}
                    disabled={syncMutation.isPending}
                  >
                    동기화
                  </Button>
                )}
              </div>
            );
          })}
          {syncDefaultsMutation.isSuccess && (
            <p className="text-xs text-green-600 flex items-center gap-1 mt-1">
              <CheckCircle2 className="w-3 h-3" />
              {syncDefaultsMutation.data?.message}
            </p>
          )}
          {syncDefaultsMutation.isError && (
            <p className="text-xs text-red-500 mt-1">
              오류: {syncDefaultsMutation.error?.message}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Custom law sync */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">기타 법령 추가</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <input
              type="text"
              value={customLawName}
              onChange={(e) => setCustomLawName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && customLawName.trim()) {
                  syncMutation.mutate(customLawName.trim());
                }
              }}
              placeholder="법령명 입력 (예: 연구개발특구 육성에 관한 특별법)"
              className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-300"
            />
            <Button
              className="gap-1.5 bg-purple-600 hover:bg-purple-700"
              onClick={() => {
                if (customLawName.trim()) syncMutation.mutate(customLawName.trim());
              }}
              disabled={!customLawName.trim() || syncMutation.isPending}
            >
              {syncMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              동기화
            </Button>
          </div>
          {syncMutation.isError && (
            <p className="text-xs text-red-500 mt-2">오류: {syncMutation.error?.message}</p>
          )}
          {syncMutation.isSuccess && (
            <p className="text-xs text-green-600 mt-2 flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" />
              {syncMutation.data?.message}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Registered legal docs */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">등록된 법령</CardTitle>
            <span className="text-xs text-gray-400">{(docs ?? []).length}개</span>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}
            </div>
          ) : (docs ?? []).length === 0 ? (
            <div className="py-12 text-center">
              <Scale className="w-8 h-8 text-gray-200 mx-auto mb-2" />
              <p className="text-sm text-gray-400">등록된 법령이 없습니다</p>
              <p className="text-xs text-gray-400 mt-1">위에서 동기화를 시작하세요</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {(docs ?? []).map((doc) => (
                <LegalDocCard
                  key={doc.id}
                  doc={doc}
                  onDelete={handleDelete}
                  deleting={deletingId === doc.id}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
