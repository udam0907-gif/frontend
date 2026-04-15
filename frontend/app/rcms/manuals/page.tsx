"use client";

import { useCallback, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { rcmsApi } from "@/lib/api";
import { PARSE_STATUS_LABELS } from "@/lib/constants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowLeft,
  Upload,
  BookOpen,
  Loader2,
  FileText,
  FileSpreadsheet,
  Image,
  X,
} from "lucide-react";
import Link from "next/link";

// ─── 허용 파일 형식 ────────────────────────────────────────────────────────────
const ACCEPTED_TYPES = ".pdf,.docx,.doc,.xlsx,.xls,.jpg,.jpeg,.png";
const ACCEPTED_MIME = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.ms-excel",
  "image/jpeg",
  "image/png",
];

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-gray-100 text-gray-600",
  processing: "bg-yellow-100 text-yellow-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

function fileIcon(filename: string) {
  const ext = filename.split(".").pop()?.toLowerCase();
  if (["jpg", "jpeg", "png"].includes(ext ?? ""))
    return <Image className="w-5 h-5 text-pink-400 shrink-0" />;
  if (["xlsx", "xls"].includes(ext ?? ""))
    return <FileSpreadsheet className="w-5 h-5 text-green-500 shrink-0" />;
  return <BookOpen className="w-5 h-5 text-blue-400 shrink-0" />;
}

function fileTypeBadge(filename: string) {
  const ext = filename.split(".").pop()?.toUpperCase();
  const colors: Record<string, string> = {
    PDF: "bg-red-50 text-red-600",
    DOCX: "bg-blue-50 text-blue-600",
    DOC: "bg-blue-50 text-blue-600",
    XLSX: "bg-green-50 text-green-600",
    XLS: "bg-green-50 text-green-600",
    JPG: "bg-pink-50 text-pink-600",
    JPEG: "bg-pink-50 text-pink-600",
    PNG: "bg-purple-50 text-purple-600",
  };
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${colors[ext ?? ""] ?? "bg-gray-100 text-gray-500"}`}>
      {ext}
    </span>
  );
}

export default function RcmsManualsPage() {
  const queryClient = useQueryClient();
  const [displayName, setDisplayName] = useState("");
  const [version, setVersion] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState("");

  const { data: manuals, isLoading } = useQuery({
    queryKey: ["rcms-manuals"],
    queryFn: rcmsApi.listManuals,
    refetchInterval: (query) => {
      const data = query.state.data;
      const hasProcessing = data?.some(
        (m) => m.parse_status === "processing" || m.parse_status === "pending"
      );
      return hasProcessing ? 3000 : false;
    },
  });

  const uploadMutation = useMutation({
    mutationFn: () => rcmsApi.uploadManual(displayName, version, file!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rcms-manuals"] });
      setDisplayName("");
      setVersion("");
      setFile(null);
      setError("");
    },
    onError: (err: Error) => setError(err.message),
  });

  // ─── 파일 선택 핸들러 ──────────────────────────────────────────────────────
  const handleFileSelect = useCallback((selected: File | null) => {
    if (!selected) return;
    if (!ACCEPTED_MIME.includes(selected.type) && selected.type !== "") {
      setError("지원하지 않는 파일 형식입니다. PDF, DOCX, XLSX, JPG, PNG만 가능합니다.");
      return;
    }
    setError("");
    setFile(selected);
    // 이름 자동 채우기 (비어 있을 때만)
    if (!displayName) {
      setDisplayName(selected.name.replace(/\.[^.]+$/, ""));
    }
  }, [displayName]);

  // ─── 드래그 & 드롭 ────────────────────────────────────────────────────────
  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };
  const onDragLeave = () => setIsDragging(false);
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFileSelect(dropped);
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
            PDF · DOCX · XLSX · JPG · PNG 파일을 드래그하거나 클릭해서 업로드하세요
          </p>
        </div>
      </div>

      {/* 업로드 폼 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">매뉴얼 업로드</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">

          {/* 드래그 앤 드롭 존 */}
          <label
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            className={`block cursor-pointer rounded-xl border-2 border-dashed transition-all duration-200 ${
              isDragging
                ? "border-blue-400 bg-blue-50 scale-[1.01]"
                : file
                ? "border-green-400 bg-green-50"
                : "border-gray-200 bg-gray-50 hover:border-blue-300 hover:bg-blue-50/40"
            }`}
          >
            <input
              type="file"
              className="hidden"
              accept={ACCEPTED_TYPES}
              onChange={(e) => handleFileSelect(e.target.files?.[0] ?? null)}
            />
            <div className="flex flex-col items-center justify-center gap-3 py-10 px-6 text-center">
              {file ? (
                <>
                  <div className="flex items-center gap-2 bg-white border border-green-200 rounded-lg px-4 py-2.5 shadow-sm">
                    {fileIcon(file.name)}
                    <span className="text-sm font-medium text-gray-800 max-w-xs truncate">
                      {file.name}
                    </span>
                    <span className="text-xs text-gray-400">
                      ({(file.size / 1024 / 1024).toFixed(1)} MB)
                    </span>
                    <button
                      type="button"
                      onClick={(e) => { e.preventDefault(); setFile(null); }}
                      className="ml-1 text-gray-400 hover:text-red-500 transition-colors"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                  <p className="text-xs text-green-600">파일이 선택되었습니다. 다른 파일로 교체하려면 클릭하세요.</p>
                </>
              ) : (
                <>
                  <div className={`p-4 rounded-full transition-colors ${isDragging ? "bg-blue-100" : "bg-gray-100"}`}>
                    <Upload className={`w-7 h-7 ${isDragging ? "text-blue-500" : "text-gray-400"}`} />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-700">
                      {isDragging ? "여기에 놓으세요!" : "파일을 드래그하거나 클릭해서 선택"}
                    </p>
                    <p className="text-xs text-gray-400 mt-1">
                      PDF · DOCX · XLSX · JPG · PNG · 최대 100MB
                    </p>
                  </div>
                  {/* 형식 뱃지 */}
                  <div className="flex gap-1.5 flex-wrap justify-center">
                    {["PDF", "DOCX", "XLSX", "JPG", "PNG"].map((ext) => (
                      <span key={ext} className="text-xs px-2 py-0.5 bg-white border border-gray-200 rounded text-gray-500">
                        {ext}
                      </span>
                    ))}
                  </div>
                </>
              )}
            </div>
          </label>

          {/* 이름 / 버전 */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="dname">매뉴얼 이름 *</Label>
              <Input
                id="dname"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="예: RCMS 사용자 매뉴얼 2024"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ver">버전</Label>
              <Input
                id="ver"
                value={version}
                onChange={(e) => setVersion(e.target.value)}
                placeholder="예: v3.2"
              />
            </div>
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">
              {error}
            </p>
          )}

          <Button
            className="w-full gap-2 h-11 text-sm font-medium"
            onClick={() => uploadMutation.mutate()}
            disabled={!displayName.trim() || !file || uploadMutation.isPending}
          >
            {uploadMutation.isPending ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> 업로드 중...</>
            ) : (
              <><Upload className="w-4 h-4" /> 업로드 및 RAG 인덱싱 시작</>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* 매뉴얼 목록 */}
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
              {[...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
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
                  {fileIcon(manual.filename)}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <p className="text-sm font-medium text-gray-800 truncate">
                        {manual.display_name}
                      </p>
                      {fileTypeBadge(manual.filename)}
                    </div>
                    <p className="text-xs text-gray-400">
                      {manual.filename}
                      {manual.version && ` · ${manual.version}`}
                      {manual.total_chunks != null && ` · ${manual.total_chunks}개 청크`}
                    </p>
                  </div>
                  <Badge
                    className={`text-xs shrink-0 flex items-center gap-1 ${STATUS_COLORS[manual.parse_status]}`}
                  >
                    {manual.parse_status === "processing" && (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    )}
                    {PARSE_STATUS_LABELS[manual.parse_status]}
                  </Badge>
                  <span className="text-xs text-gray-400 shrink-0">
                    {new Date(manual.created_at).toLocaleDateString("ko-KR")}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
