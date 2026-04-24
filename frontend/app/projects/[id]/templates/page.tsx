"use client";

import React, { useState, useRef } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { templatesApi } from "@/lib/api";
import { CATEGORY_LABELS } from "@/lib/constants";
import type { CategoryType } from "@/lib/types";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Upload, Trash2, FileText, Settings, ChevronDown, ChevronUp } from "lucide-react";

const CATEGORY_OPTIONS: { value: CategoryType; label: string }[] = [
  { value: "materials", label: "재료비" },
  { value: "meeting", label: "회의비" },
  { value: "outsourcing", label: "외주가공비" },
  { value: "test_report", label: "시험성적비" },
  { value: "labor", label: "인건비" },
];

const DOC_TYPES_BY_CATEGORY: Record<string, { value: string; label: string }[]> = {
  materials: [
    { value: "quote", label: "견적서" },
    { value: "comparative_quote", label: "비교견적서" },
    { value: "expense_resolution", label: "지출결의서" },
    { value: "inspection_confirmation", label: "검수확인서" },
  ],
  outsourcing: [
    { value: "quote", label: "견적서" },
    { value: "comparative_quote", label: "비교견적서" },
    { value: "service_contract", label: "용역계약서" },
    { value: "work_order", label: "과업지시서" },
    { value: "transaction_statement", label: "거래명세서" },
    { value: "inspection_photos", label: "검수사진" },
  ],
  labor: [
    { value: "cash_expense_resolution", label: "지출결의서_현금" },
    { value: "in_kind_expense_resolution", label: "지출결의서_현물" },
    { value: "researcher_status_sheet", label: "참여연구원 현황표" },
  ],
  test_report: [
    { value: "quote", label: "견적서" },
    { value: "expense_resolution", label: "지출결의서" },
    { value: "transaction_statement", label: "거래명세서" },
  ],
  meeting: [
    { value: "receipt", label: "영수증" },
    { value: "meeting_minutes", label: "회의내용" },
  ],
  other: [{ value: "other", label: "기타" }],
};

interface FormState {
  displayName: string;
  categoryType: CategoryType;
  documentType: string;
  file: File | null;
}

type UploadStage = "idle" | "selected" | "uploading" | "saved" | "error";

const RENDER_STRATEGIES = [
  { value: "marker_table", label: "마커 테이블 (기본값 — 텍스트 마커로 테이블 탐색)" },
  { value: "standard_table", label: "고정 테이블 (수신:/발행일자: 구조 양식)" },
  { value: "paragraph_fill", label: "문단 채움 (표 없는 텍스트 구조 양식)" },
  { value: "docxtpl", label: "docxtpl ({{variable}} 플레이스홀더 양식)" },
];

const STRATEGY_DEFAULT_CONFIG: Record<string, Record<string, unknown>> = {
  marker_table: {
    date_marker: "작성일자",
    amount_marker: "합계금액",
    line_items_marker: "품목",
    subtotal_row_offset: 28,
    vat_row_offset: 29,
    total_row_offset: 30,
    total_col: 5,
  },
  standard_table: {
    header_table_idx: 0,
    body_table_idx: 1,
    recipient_pos: { row: 0, col: 1 },
    date_pos: { row: 0, col: 4 },
    sender_manager_pos: { row: 1, col: 1 },
    sender_name_pos: { row: 2, col: 1 },
    line_items_start_row: 3,
    line_items_end_row: 7,
    line_items_columns: { seq: 0, item_name: 1, spec: 3, unit_price: 4, amount: 5 },
  },
  paragraph_fill: {
    paragraph_map: {
      issue_date: 7,
      recipient_name: 12,
      supplier_name: 13,
    },
    line_items_para_start: 30,
  },
  docxtpl: {},
};

const initialForm: FormState = {
  displayName: "",
  categoryType: "materials",
  documentType: "quote",
  file: null,
};

export default function ProjectTemplatesPage() {
  const params = useParams();
  const projectId = params.id as string;
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [form, setForm] = useState<FormState>(initialForm);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploadStage, setUploadStage] = useState<UploadStage>("idle");
  const [uploadStatusText, setUploadStatusText] = useState("파일을 드래그해서 놓거나 파일 선택으로 업로드할 템플릿을 고르세요.");

  // 렌더 프로파일 편집 상태
  const [profileEditingId, setProfileEditingId] = useState<string | null>(null);
  const [profileStrategy, setProfileStrategy] = useState("marker_table");
  const [profileTextboxReplacement, setProfileTextboxReplacement] = useState(true);
  const [profileConfigJson, setProfileConfigJson] = useState("");
  const [profileMessage, setProfileMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const { data: templates, isLoading } = useQuery({
    queryKey: ["templates", projectId],
    queryFn: () => templatesApi.list(undefined, projectId),
  });

  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!form.file) throw new Error("파일을 선택하세요.");
      setUploadStage("uploading");
      setUploadStatusText("업로드/저장 중입니다.");
      return templatesApi.upload(
        form.categoryType,
        form.documentType,
        form.displayName || form.file.name,
        form.file,
        projectId
      );
    },
    onSuccess: () => {
      setMessage({ type: "success", text: "템플릿이 등록되었습니다." });
      setUploadStage("saved");
      setUploadStatusText("저장 완료");
      setForm(initialForm);
      if (fileInputRef.current) fileInputRef.current.value = "";
      queryClient.invalidateQueries({ queryKey: ["templates", projectId] });
    },
    onError: (err: Error) => {
      setUploadStage("error");
      setUploadStatusText("저장에 실패했습니다.");
      setMessage({ type: "error", text: err.message });
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => templatesApi.deactivate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["templates", projectId] });
    },
  });

  const renderProfileMutation = useMutation({
    mutationFn: ({ id, profile }: { id: string; profile: Record<string, unknown> }) =>
      templatesApi.setRenderProfile(id, profile),
    onSuccess: () => {
      setProfileMessage({ type: "success", text: "렌더 프로파일이 저장되었습니다." });
      queryClient.invalidateQueries({ queryKey: ["templates", projectId] });
    },
    onError: (err: Error) => {
      setProfileMessage({ type: "error", text: `저장 실패: ${err.message}` });
    },
  });

  const clearProfileMutation = useMutation({
    mutationFn: (id: string) => templatesApi.clearRenderProfile(id),
    onSuccess: () => {
      setProfileMessage({ type: "success", text: "프로파일이 초기화되었습니다. (자동감지 방식으로 복원)" });
      queryClient.invalidateQueries({ queryKey: ["templates", projectId] });
    },
  });

  const openProfileEditor = (tpl: { id: string; document_type?: string }) => {
    setProfileEditingId(tpl.id);
    setProfileStrategy("marker_table");
    setProfileTextboxReplacement(true);
    setProfileConfigJson(JSON.stringify(STRATEGY_DEFAULT_CONFIG["marker_table"], null, 2));
    setProfileMessage(null);
  };

  const handleStrategyChange = (strategy: string) => {
    setProfileStrategy(strategy);
    const defaultCfg = STRATEGY_DEFAULT_CONFIG[strategy] || {};
    setProfileConfigJson(JSON.stringify(defaultCfg, null, 2));
  };

  const handleSaveProfile = () => {
    if (!profileEditingId) return;
    let strategyConfig: Record<string, unknown> = {};
    try {
      strategyConfig = JSON.parse(profileConfigJson);
    } catch {
      setProfileMessage({ type: "error", text: "전략 설정 JSON 형식 오류입니다." });
      return;
    }
    const configKey =
      profileStrategy === "paragraph_fill" ? "paragraph_config" :
      profileStrategy === "standard_table" ? "standard_table_config" :
      profileStrategy === "marker_table" ? "marker_table_config" : null;

    const profile: Record<string, unknown> = {
      doc_type: "quote",
      render_strategy: profileStrategy,
      textbox_replacement: profileTextboxReplacement,
      ...(configKey ? { [configKey]: strategyConfig } : {}),
    };
    renderProfileMutation.mutate({ id: profileEditingId, profile });
  };

  // 비목 변경 시 문서 종류 초기값 업데이트
  const handleCategoryChange = (cat: CategoryType) => {
    const firstDocType = DOC_TYPES_BY_CATEGORY[cat]?.[0]?.value ?? "other";
    setForm((f) => ({ ...f, categoryType: cat, documentType: firstDocType }));
  };

  const handleReset = () => {
    setForm(initialForm);
    setMessage(null);
    setUploadStage("idle");
    setUploadStatusText("파일을 드래그해서 놓거나 파일 선택으로 업로드할 템플릿을 고르세요.");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleFileSelected = (file: File | null) => {
    if (!file) {
      setUploadStage("error");
      setUploadStatusText("파일을 선택하세요.");
      return;
    }

    setForm((prev) => ({
      ...prev,
      displayName: prev.displayName || file.name,
      file,
    }));
    setMessage(null);
    setUploadStage("selected");
    setUploadStatusText("파일 선택됨");
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-900">템플릿 관리</h2>
        <p className="text-sm text-gray-500 mt-0.5">
          비목별 서식 템플릿을 등록하고 관리합니다
        </p>
      </div>

      {/* 등록 폼 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Upload className="w-4 h-4" />
            템플릿 등록
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {message && (
            <div
              className={`p-3 rounded-lg text-sm ${
                message.type === "success"
                  ? "bg-green-50 text-green-700"
                  : "bg-red-50 text-red-700"
              }`}
            >
              {message.text}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="displayName">템플릿명</Label>
              <Input
                id="displayName"
                placeholder="예: 재료비 견적서 양식"
                value={form.displayName}
                onChange={(e) =>
                  setForm((f) => ({ ...f, displayName: e.target.value }))
                }
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="categoryType">유형 (비목)</Label>
              <select
                id="categoryType"
                className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm"
                value={form.categoryType}
                onChange={(e) =>
                  handleCategoryChange(e.target.value as CategoryType)
                }
              >
                {CATEGORY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="documentType">문서 종류</Label>
              <select
                id="documentType"
                className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm"
                value={form.documentType}
                onChange={(e) =>
                  setForm((f) => ({ ...f, documentType: e.target.value }))
                }
              >
                {(DOC_TYPES_BY_CATEGORY[form.categoryType] ?? []).map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="file">파일 업로드 (DOCX / XLSX / PDF / JPG / PNG)</Label>
              <div
                className={`rounded-lg border-2 border-dashed px-4 py-4 transition-colors ${
                  dragActive ? "border-blue-500 bg-blue-50" : "border-gray-200 bg-gray-50"
                }`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragActive(true);
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  setDragActive(false);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragActive(false);
                  handleFileSelected(e.dataTransfer.files?.[0] ?? null);
                }}
              >
                <input
                  ref={fileInputRef}
                  id="file"
                  type="file"
                  accept=".docx,.xlsx,.pdf,.jpg,.jpeg,.png"
                  className="hidden"
                  onChange={(e) => {
                    handleFileSelected(e.target.files?.[0] ?? null);
                    e.currentTarget.value = "";
                  }}
                />
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-gray-800">
                      파일을 드래그해서 놓거나 파일 선택으로 업로드하세요.
                    </p>
                    <p className="text-xs text-gray-500">DOCX / XLSX / PDF / JPG / PNG 업로드 가능</p>
                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                          uploadStage === "error"
                            ? "bg-red-100 text-red-700"
                            : uploadStage === "saved"
                              ? "bg-green-100 text-green-700"
                              : uploadStage === "uploading"
                                ? "bg-sky-100 text-sky-700"
                                : uploadStage === "selected"
                                  ? "bg-blue-100 text-blue-700"
                                  : "bg-gray-200 text-gray-700"
                        }`}
                      >
                        {uploadStage === "idle"
                          ? "대기 중"
                          : uploadStage === "selected"
                            ? "파일 선택됨"
                            : uploadStage === "uploading"
                              ? "업로드/저장 중"
                              : uploadStage === "saved"
                                ? "저장 완료"
                                : "실패"}
                      </span>
                      <span className="text-xs text-gray-600">{uploadStatusText}</span>
                    </div>
                    {form.file && (
                      <p className="text-sm text-gray-700">
                        현재 선택 파일: <span className="font-semibold">{form.file.name}</span>
                      </p>
                    )}
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploadMutation.isPending}
                  >
                    파일 선택
                  </Button>
                </div>
              </div>
            </div>
          </div>

          <div className="flex gap-2">
            <Button
              onClick={() => uploadMutation.mutate()}
              disabled={uploadMutation.isPending || !form.file}
            >
              {uploadMutation.isPending ? "저장 중..." : "저장"}
            </Button>
            <Button variant="outline" onClick={handleReset}>
              초기화
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 템플릿 목록 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <FileText className="w-4 h-4" />
            등록된 템플릿
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : (templates ?? []).length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-8">
              등록된 템플릿이 없습니다
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100">
                    <th className="text-left py-2.5 px-2 text-xs font-semibold text-gray-500">
                      템플릿명
                    </th>
                    <th className="text-left py-2.5 px-2 text-xs font-semibold text-gray-500">
                      유형
                    </th>
                    <th className="text-left py-2.5 px-2 text-xs font-semibold text-gray-500">
                      파일명
                    </th>
                    <th className="text-left py-2.5 px-2 text-xs font-semibold text-gray-500">
                      상태
                    </th>
                    <th className="py-2.5 px-2" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {(templates ?? []).map((tpl) => (
                    <React.Fragment key={tpl.id}>
                      <tr className="hover:bg-gray-50">
                        <td className="py-3 px-2 font-medium text-gray-800">
                          {tpl.name}
                        </td>
                        <td className="py-3 px-2 text-gray-600">
                          {CATEGORY_LABELS[tpl.category_type] ?? tpl.category_type}
                        </td>
                        <td className="py-3 px-2 text-gray-500 text-xs">
                          {tpl.filename}
                        </td>
                        <td className="py-3 px-2">
                          <Badge
                            className={
                              tpl.is_active
                                ? "bg-green-100 text-green-700 text-xs"
                                : "bg-gray-100 text-gray-500 text-xs"
                            }
                          >
                            {tpl.is_active ? "활성" : "비활성"}
                          </Badge>
                        </td>
                        <td className="py-3 px-2">
                          <div className="flex items-center gap-1">
                            {tpl.is_active && ["quote", "comparative_quote"].includes(tpl.document_type) && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="text-blue-600 hover:text-blue-800 hover:bg-blue-50 h-7 px-2 text-xs"
                                onClick={() =>
                                  profileEditingId === tpl.id
                                    ? setProfileEditingId(null)
                                    : openProfileEditor(tpl)
                                }
                              >
                                <Settings className="w-3.5 h-3.5 mr-1" />
                                프로파일
                                {profileEditingId === tpl.id
                                  ? <ChevronUp className="w-3 h-3 ml-1" />
                                  : <ChevronDown className="w-3 h-3 ml-1" />}
                              </Button>
                            )}
                            {tpl.is_active && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="text-red-500 hover:text-red-700 hover:bg-red-50 h-7 px-2"
                                onClick={() => deactivateMutation.mutate(tpl.id)}
                                disabled={deactivateMutation.isPending}
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>

                      {profileEditingId === tpl.id && (
                        <tr key={`${tpl.id}-profile`}>
                          <td colSpan={5} className="bg-blue-50 px-4 py-4 border-b border-blue-100">
                            <div className="space-y-3">
                              <p className="text-xs font-semibold text-blue-700 flex items-center gap-1">
                                <Settings className="w-3.5 h-3.5" />
                                렌더 프로파일 설정 —{" "}
                                <span className="font-normal">{tpl.name}</span>
                              </p>

                              {profileMessage && (
                                <div
                                  className={`text-xs px-3 py-2 rounded ${
                                    profileMessage.type === "success"
                                      ? "bg-green-100 text-green-700"
                                      : "bg-red-100 text-red-700"
                                  }`}
                                >
                                  {profileMessage.text}
                                </div>
                              )}

                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                <div className="space-y-1">
                                  <label className="text-xs font-medium text-gray-700">렌더 전략</label>
                                  <select
                                    className="w-full border border-gray-200 rounded px-2 py-1.5 text-xs bg-white"
                                    value={profileStrategy}
                                    onChange={(e) => handleStrategyChange(e.target.value)}
                                  >
                                    {RENDER_STRATEGIES.map((s) => (
                                      <option key={s.value} value={s.value}>
                                        {s.label}
                                      </option>
                                    ))}
                                  </select>
                                </div>

                                <div className="flex items-center gap-2 pt-5">
                                  <input
                                    type="checkbox"
                                    id="textbox-replacement"
                                    checked={profileTextboxReplacement}
                                    onChange={(e) => setProfileTextboxReplacement(e.target.checked)}
                                    className="w-4 h-4"
                                  />
                                  <label htmlFor="textbox-replacement" className="text-xs text-gray-700">
                                    텍스트박스 XML 치환 (귀하 / 작성일자 / 공급자블록)
                                  </label>
                                </div>
                              </div>

                              {profileStrategy !== "docxtpl" && (
                                <div className="space-y-1">
                                  <label className="text-xs font-medium text-gray-700">
                                    전략 설정 (JSON)
                                    <span className="ml-2 font-normal text-gray-400">
                                      — 전략 변경 시 기본값으로 초기화
                                    </span>
                                  </label>
                                  <textarea
                                    className="w-full border border-gray-200 rounded px-3 py-2 text-xs font-mono bg-white resize-y"
                                    rows={10}
                                    value={profileConfigJson}
                                    onChange={(e) => setProfileConfigJson(e.target.value)}
                                    spellCheck={false}
                                  />
                                </div>
                              )}

                              <div className="flex gap-2 pt-1">
                                <Button
                                  size="sm"
                                  onClick={handleSaveProfile}
                                  disabled={renderProfileMutation.isPending}
                                  className="text-xs h-7"
                                >
                                  {renderProfileMutation.isPending ? "저장 중..." : "프로파일 저장"}
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => clearProfileMutation.mutate(tpl.id)}
                                  disabled={clearProfileMutation.isPending}
                                  className="text-xs h-7 text-gray-600"
                                >
                                  초기화 (자동감지)
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => setProfileEditingId(null)}
                                  className="text-xs h-7"
                                >
                                  닫기
                                </Button>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
