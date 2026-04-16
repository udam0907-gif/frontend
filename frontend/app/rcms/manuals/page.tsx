"use client";

import { useCallback, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { rcmsApi } from "@/lib/api";
import { PARSE_STATUS_LABELS } from "@/lib/constants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowLeft,
  Upload,
  BookOpen,
  Loader2,
  FileSpreadsheet,
  Image,
  X,
  Trash2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import Link from "next/link";

// ─── 허용 확장자 ───────────────────────────────────────────────────────────────
const ACCEPTED_TYPES = ".pdf,.docx,.doc,.xlsx,.xls,.jpg,.jpeg,.png";
const ACCEPTED_EXTENSIONS = new Set([
  "pdf", "docx", "doc", "xlsx", "xls", "jpg", "jpeg", "png",
]);

// ─── 업로드 큐 아이템 ─────────────────────────────────────────────────────────
interface UploadItem {
  uid: string;
  file: File;
  displayName: string;
  status: "uploading" | "done" | "error";
  error?: string;
}

// ─── 헬퍼 ────────────────────────────────────────────────────────────────────
const STATUS_COLORS: Record<string, string> = {
  pending:    "bg-gray-100 text-gray-600",
  processing: "bg-yellow-100 text-yellow-700",
  completed:  "bg-green-100 text-green-700",
  failed:     "bg-red-100 text-red-700",
};

const EXT_COLORS: Record<string, string> = {
  PDF:  "bg-red-50 text-red-600",
  DOCX: "bg-blue-50 text-blue-600",
  DOC:  "bg-blue-50 text-blue-600",
  XLSX: "bg-green-50 text-green-600",
  XLS:  "bg-green-50 text-green-600",
  JPG:  "bg-pink-50 text-pink-600",
  JPEG: "bg-pink-50 text-pink-600",
  PNG:  "bg-purple-50 text-purple-600",
};

function fileExt(name: string) {
  return name.split(".").pop()?.toLowerCase() ?? "";
}

function FileIcon({ name, cls }: { name: string; cls?: string }) {
  const ext = fileExt(name);
  if (["jpg", "jpeg", "png"].includes(ext))
    return <Image className={cls ?? "w-5 h-5 text-pink-400 shrink-0"} />;
  if (["xlsx", "xls"].includes(ext))
    return <FileSpreadsheet className={cls ?? "w-5 h-5 text-green-500 shrink-0"} />;
  return <BookOpen className={cls ?? "w-5 h-5 text-blue-400 shrink-0"} />;
}

function ExtBadge({ name }: { name: string }) {
  const ext = name.split(".").pop()?.toUpperCase() ?? "";
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${EXT_COLORS[ext] ?? "bg-gray-100 text-gray-500"}`}>
      {ext}
    </span>
  );
}

// ─── 메인 컴포넌트 ────────────────────────────────────────────────────────────
export default function RcmsManualsPage() {
  const queryClient = useQueryClient();
  const [isDragging, setIsDragging]   = useState(false);
  const [queue, setQueue]             = useState<UploadItem[]>([]);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting]       = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // ─── 매뉴얼 목록 ────────────────────────────────────────────────────────────
  const { data: manuals, isLoading } = useQuery({
    queryKey: ["rcms-manuals"],
    queryFn: rcmsApi.listManuals,
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.some(
        (m) => m.parse_status === "processing" || m.parse_status === "pending"
      ) ? 2000 : false;
    },
  });

  // ─── 단일 파일 업로드 ────────────────────────────────────────────────────────
  const uploadFile = useCallback(async (item: UploadItem) => {
    try {
      await rcmsApi.uploadManual(item.displayName, "1.0", item.file);
      setQueue((q) =>
        q.map((x) => x.uid === item.uid ? { ...x, status: "done" } : x)
      );
      queryClient.invalidateQueries({ queryKey: ["rcms-manuals"] });
      // 완료 후 3초 뒤 큐에서 제거
      setTimeout(() => {
        setQueue((q) => q.filter((x) => x.uid !== item.uid));
      }, 3000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "업로드 실패";
      setQueue((q) =>
        q.map((x) => x.uid === item.uid ? { ...x, status: "error", error: msg } : x)
      );
    }
  }, [queryClient]);

  // ─── 파일 목록 처리 (유효성 검사 → 큐 추가 → 자동 업로드) ──────────────────
  const handleFiles = useCallback((files: FileList | File[]) => {
    const arr = Array.from(files);
    const valid: UploadItem[] = [];
    const rejected: string[] = [];

    for (const file of arr) {
      const ext = fileExt(file.name);
      if (!ACCEPTED_EXTENSIONS.has(ext)) {
        rejected.push(file.name);
        continue;
      }
      const item: UploadItem = {
        uid: `${Date.now()}-${Math.random()}`,
        file,
        displayName: file.name.replace(/\.[^.]+$/, ""),
        status: "uploading",
      };
      valid.push(item);
    }

    if (rejected.length) {
      alert(`지원하지 않는 형식:\n${rejected.join("\n")}\n\nPDF·DOCX·XLSX·JPG·PNG만 가능합니다.`);
    }

    if (valid.length === 0) return;

    setQueue((q) => [...q, ...valid]);
    // 각 파일 즉시 병렬 업로드
    valid.forEach(uploadFile);
  }, [uploadFile]);

  // ─── 드래그 & 드롭 ──────────────────────────────────────────────────────────
  const onDragOver  = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(true); };
  const onDragLeave = (e: React.DragEvent) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node)) setIsDragging(false);
  };
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  // ─── 삭제 ───────────────────────────────────────────────────────────────────
  const handleDelete = async (id: string) => {
    setDeleting(true);
    try {
      await rcmsApi.deleteManual(id);
      queryClient.invalidateQueries({ queryKey: ["rcms-manuals"] });
      setConfirmDeleteId(null);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="max-w-3xl space-y-5">
      {/* 헤더 */}
      <div className="flex items-center gap-3">
        <Link href="/rcms">
          <Button variant="ghost" size="icon" className="w-8 h-8">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <div>
          <h2 className="text-xl font-bold text-gray-900">RCMS 매뉴얼 관리</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            파일을 드래그하거나 클릭하면 즉시 업로드됩니다 · 여러 파일 동시 가능
          </p>
        </div>
      </div>

      {/* 드롭존 */}
      <div
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`relative cursor-pointer rounded-xl border-2 border-dashed transition-all duration-200 ${
          isDragging
            ? "border-blue-400 bg-blue-50 scale-[1.01]"
            : "border-gray-200 bg-gray-50 hover:border-blue-300 hover:bg-blue-50/40"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept={ACCEPTED_TYPES}
          multiple
          onChange={(e) => { if (e.target.files) handleFiles(e.target.files); e.target.value = ""; }}
        />
        <div className="flex flex-col items-center justify-center gap-3 py-10 px-6 text-center pointer-events-none">
          <div className={`p-4 rounded-full transition-colors ${isDragging ? "bg-blue-100" : "bg-gray-100"}`}>
            <Upload className={`w-7 h-7 ${isDragging ? "text-blue-500" : "text-gray-400"}`} />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-700">
              {isDragging ? "여기에 놓으세요! 즉시 업로드됩니다" : "파일을 드래그하거나 클릭해서 선택"}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              PDF · DOCX · XLSX · JPG · PNG · 최대 100MB · 여러 파일 동시 가능
            </p>
          </div>
          <div className="flex gap-1.5 flex-wrap justify-center">
            {["PDF", "DOCX", "XLSX", "JPG", "PNG"].map((ext) => (
              <span key={ext} className="text-xs px-2 py-0.5 bg-white border border-gray-200 rounded text-gray-500">
                {ext}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* 업로드 진행 큐 */}
      {queue.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-gray-600">업로드 진행 중</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {queue.map((item) => (
              <div key={item.uid} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-gray-50 border border-gray-100">
                <FileIcon name={item.file.name} cls="w-4 h-4 text-gray-400 shrink-0" />
                <span className="text-sm text-gray-700 flex-1 truncate">{item.displayName}</span>
                <span className="text-xs text-gray-400 shrink-0">
                  {(item.file.size / 1024 / 1024).toFixed(1)} MB
                </span>
                {item.status === "uploading" && (
                  <Loader2 className="w-4 h-4 text-blue-500 animate-spin shrink-0" />
                )}
                {item.status === "done" && (
                  <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />
                )}
                {item.status === "error" && (
                  <div className="flex items-center gap-1 shrink-0">
                    <AlertCircle className="w-4 h-4 text-red-500" />
                    <span className="text-xs text-red-500 max-w-[120px] truncate">{item.error}</span>
                    <button
                      onClick={() => setQueue((q) => q.filter((x) => x.uid !== item.uid))}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* 등록된 매뉴얼 목록 */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">등록된 매뉴얼</CardTitle>
            <span className="text-xs text-gray-400">{(manuals ?? []).length}개</span>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}
            </div>
          ) : (manuals ?? []).length === 0 ? (
            <div className="py-12 text-center">
              <BookOpen className="w-8 h-8 text-gray-200 mx-auto mb-2" />
              <p className="text-sm text-gray-400">등록된 매뉴얼이 없습니다</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {(manuals ?? []).map((manual) => (
                <div key={manual.id} className="py-3.5 flex items-center gap-3">
                  <FileIcon name={manual.filename} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <p className="text-sm font-medium text-gray-800 truncate">
                        {manual.display_name}
                      </p>
                      <ExtBadge name={manual.filename} />
                    </div>
                    <p className="text-xs text-gray-400">
                      {manual.version && `v${manual.version}`}
                      {manual.total_chunks != null && ` · ${manual.total_chunks}청크`}
                    </p>
                  </div>
                  <Badge className={`text-xs shrink-0 flex items-center gap-1 ${STATUS_COLORS[manual.parse_status]}`}>
                    {manual.parse_status === "processing" && <Loader2 className="w-3 h-3 animate-spin" />}
                    {PARSE_STATUS_LABELS[manual.parse_status]}
                  </Badge>
                  <span className="text-xs text-gray-400 shrink-0">
                    {new Date(manual.created_at).toLocaleDateString("ko-KR")}
                  </span>

                  {/* 삭제 */}
                  {confirmDeleteId === manual.id ? (
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => handleDelete(manual.id)}
                        disabled={deleting}
                        className="text-xs px-2 py-1 bg-red-500 text-white rounded hover:bg-red-600 disabled:opacity-50 transition-colors"
                      >
                        {deleting ? <Loader2 className="w-3 h-3 animate-spin" /> : "삭제"}
                      </button>
                      <button
                        onClick={() => setConfirmDeleteId(null)}
                        className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded hover:bg-gray-200 transition-colors"
                      >
                        취소
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setConfirmDeleteId(manual.id)}
                      className="shrink-0 p-1.5 text-gray-300 hover:text-red-400 hover:bg-red-50 rounded transition-colors"
                      title="삭제"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
