"use client";

import { useCallback, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { projectsApi } from "@/lib/api";
import { CATEGORY_LABELS } from "@/lib/constants";
import type { CategoryType, ResearcherCreate, ExtractedProjectData } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  ArrowLeft,
  FileUp,
  Loader2,
  Plus,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BudgetRow {
  category_type: CategoryType;
  allocated_amount: number;
}

interface UploadedFile {
  file: File;
  label: string;
}

const ALL_CATEGORIES = Object.entries(CATEGORY_LABELS) as [CategoryType, string][];

// ---------------------------------------------------------------------------
// Researcher row editor
// ---------------------------------------------------------------------------

function ResearcherRowEditor({
  row,
  idx,
  onChange,
  onRemove,
}: {
  row: ResearcherCreate;
  idx: number;
  onChange: (idx: number, field: keyof ResearcherCreate, value: unknown) => void;
  onRemove: (idx: number) => void;
}) {
  return (
    <div className="grid grid-cols-12 gap-2 items-center py-2 border-b border-gray-100 last:border-0 text-sm">
      {/* 인력구분 */}
      <div className="col-span-1">
        <select
          className="w-full border border-gray-200 rounded px-1.5 py-1 text-xs"
          value={row.personnel_type}
          onChange={(e) => onChange(idx, "personnel_type", e.target.value as "기존" | "신규")}
        >
          <option value="기존">기존</option>
          <option value="신규">신규</option>
        </select>
      </div>
      {/* 성명 */}
      <div className="col-span-2">
        <Input
          className="h-7 text-xs"
          value={row.name}
          placeholder="성명"
          onChange={(e) => onChange(idx, "name", e.target.value)}
        />
      </div>
      {/* 직위 */}
      <div className="col-span-2">
        <Input
          className="h-7 text-xs"
          value={row.position ?? ""}
          placeholder="직위"
          onChange={(e) => onChange(idx, "position", e.target.value || null)}
        />
      </div>
      {/* 연봉 */}
      <div className="col-span-1">
        <Input
          type="number"
          className="h-7 text-xs"
          value={row.annual_salary ?? ""}
          placeholder="연봉"
          onChange={(e) => onChange(idx, "annual_salary", e.target.value ? Number(e.target.value) : null)}
        />
      </div>
      {/* 월급여 */}
      <div className="col-span-1">
        <Input
          type="number"
          className="h-7 text-xs"
          value={row.monthly_salary ?? ""}
          placeholder="월급여"
          onChange={(e) => onChange(idx, "monthly_salary", e.target.value ? Number(e.target.value) : null)}
        />
      </div>
      {/* 참여기간 */}
      <div className="col-span-1">
        <Input
          type="number"
          className="h-7 text-xs"
          value={row.participation_months ?? ""}
          placeholder="개월"
          onChange={(e) => onChange(idx, "participation_months", e.target.value ? Number(e.target.value) : null)}
        />
      </div>
      {/* 참여율 */}
      <div className="col-span-1">
        <Input
          type="number"
          className="h-7 text-xs"
          value={row.participation_rate ?? ""}
          placeholder="%"
          onChange={(e) => onChange(idx, "participation_rate", e.target.value ? Number(e.target.value) : null)}
        />
      </div>
      {/* 현금 */}
      <div className="col-span-1">
        <Input
          type="number"
          className="h-7 text-xs"
          value={row.cash_amount ?? ""}
          placeholder="현금"
          onChange={(e) => onChange(idx, "cash_amount", e.target.value ? Number(e.target.value) : null)}
        />
      </div>
      {/* 현물 */}
      <div className="col-span-1">
        <Input
          type="number"
          className="h-7 text-xs"
          value={row.in_kind_amount ?? ""}
          placeholder="현물"
          onChange={(e) => onChange(idx, "in_kind_amount", e.target.value ? Number(e.target.value) : null)}
        />
      </div>
      {/* 삭제 */}
      <div className="col-span-1 flex justify-center">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="w-6 h-6 text-red-400 hover:text-red-600"
          onClick={() => onRemove(idx)}
        >
          <Trash2 className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function NewProjectPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  // 기본 정보 폼
  const [form, setForm] = useState({
    name: "",
    code: "",
    institution: "",
    principal_investigator: "",
    period_start: "",
    period_end: "",
    total_budget: "",
  });

  // 비목별 예산
  const [budgets, setBudgets] = useState<BudgetRow[]>([]);

  // 참여연구원
  const [researchers, setResearchers] = useState<ResearcherCreate[]>([]);

  // PDF 업로드 관련
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState("");
  const [extractedResult, setExtractedResult] = useState<ExtractedProjectData | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [error, setError] = useState("");

  // ---------------------------------------------------------------------------
  // 과제 등록 mutation
  // ---------------------------------------------------------------------------

  const createMutation = useMutation({
    mutationFn: projectsApi.create,
    onSuccess: async (project) => {
      if (researchers.length > 0) {
        try { await projectsApi.upsertResearchers(project.id, researchers); } catch {}
      }
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      router.push(`/projects/${project.id}`);
    },
    onError: (err: Error) => setError(err.message),
  });

  // ---------------------------------------------------------------------------
  // PDF 파일 선택 처리
  // ---------------------------------------------------------------------------

  const handleFileAdd = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    const newFiles: UploadedFile[] = files.map((f) => ({ file: f, label: f.name }));
    setUploadedFiles((prev) => [...prev, ...newFiles]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const removeFile = (idx: number) =>
    setUploadedFiles((prev) => prev.filter((_, i) => i !== idx));

  // ---------------------------------------------------------------------------
  // 자동 추출
  // ---------------------------------------------------------------------------

  const handleExtract = useCallback(async () => {
    if (!uploadedFiles.length) return;
    setExtracting(true);
    setExtractError("");
    setExtractedResult(null);

    try {
      // 각 파일을 순서대로 추출하여 결과를 머지
      let merged: Partial<ExtractedProjectData> = {};
      let allResearchers: ResearcherCreate[] = [];
      let allBudgets: ExtractedProjectData["budget_categories"] = [];

      for (const uf of uploadedFiles) {
        const result = await projectsApi.extractPdf("auto", uf.file);

        // 기본 정보: 먼저 추출된 값 우선 (null이면 덮어씀)
        if (!merged.name && result.name) merged.name = result.name;
        if (!merged.code && result.code) merged.code = result.code;
        if (!merged.institution && result.institution) merged.institution = result.institution;
        if (!merged.principal_investigator && result.principal_investigator)
          merged.principal_investigator = result.principal_investigator;
        if (!merged.period_start && result.period_start) merged.period_start = result.period_start;
        if (!merged.period_end && result.period_end) merged.period_end = result.period_end;
        if (!merged.total_budget && result.total_budget) merged.total_budget = result.total_budget;

        // 비목: 새로 추출된 것 추가 (중복 category_type 제거)
        for (const b of result.budget_categories) {
          if (!allBudgets.find((x) => x.category_type === b.category_type)) {
            allBudgets.push(b);
          }
        }

        // 연구원: 모두 추가
        if (result.researchers.length > 0) {
          allResearchers = result.researchers;
        }

        merged.doc_type = result.doc_type;
        merged.confidence = result.confidence;
      }

      const finalResult = merged as ExtractedProjectData;
      finalResult.budget_categories = allBudgets;
      finalResult.researchers = allResearchers;
      setExtractedResult(finalResult);

      // 폼에 자동 채우기
      setForm((prev) => ({
        name: finalResult.name ?? prev.name,
        code: finalResult.code ?? prev.code,
        institution: finalResult.institution ?? prev.institution,
        principal_investigator: finalResult.principal_investigator ?? prev.principal_investigator,
        period_start: finalResult.period_start ?? prev.period_start,
        period_end: finalResult.period_end ?? prev.period_end,
        total_budget: finalResult.total_budget ? String(finalResult.total_budget) : prev.total_budget,
      }));

      if (allBudgets.length > 0) {
        setBudgets(
          allBudgets.map((b) => ({
            category_type: b.category_type as CategoryType,
            allocated_amount: Number(b.allocated_amount),
          }))
        );
      }

      if (allResearchers.length > 0) {
        setResearchers(
          allResearchers.map((r, i) => ({
            ...r,
            sort_order: i,
          }))
        );
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "추출 중 오류가 발생했습니다.";
      setExtractError(msg);
    } finally {
      setExtracting(false);
    }
  }, [uploadedFiles]);

  // ---------------------------------------------------------------------------
  // 비목 편집
  // ---------------------------------------------------------------------------

  const addBudget = () => {
    const used = new Set(budgets.map((b) => b.category_type));
    const next = ALL_CATEGORIES.find(([k]) => !used.has(k));
    if (next) {
      setBudgets((prev) => [...prev, { category_type: next[0], allocated_amount: 0 }]);
    }
  };

  const removeBudget = (idx: number) =>
    setBudgets((prev) => prev.filter((_, i) => i !== idx));

  // ---------------------------------------------------------------------------
  // 연구원 편집
  // ---------------------------------------------------------------------------

  const addResearcher = () => {
    setResearchers((prev) => [
      ...prev,
      {
        personnel_type: "기존",
        name: "",
        position: null,
        annual_salary: null,
        monthly_salary: null,
        participation_months: null,
        participation_rate: null,
        cash_amount: null,
        in_kind_amount: null,
        sort_order: prev.length,
      },
    ]);
  };

  const updateResearcher = (idx: number, field: keyof ResearcherCreate, value: unknown) => {
    setResearchers((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], [field]: value };
      return next;
    });
  };

  const removeResearcher = (idx: number) =>
    setResearchers((prev) => prev.filter((_, i) => i !== idx));

  // ---------------------------------------------------------------------------
  // Submit
  // ---------------------------------------------------------------------------

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    const meta: Record<string, unknown> = {};
    if (extractedResult?.overview)     meta.overview     = extractedResult.overview;
    if (extractedResult?.deliverables) meta.deliverables = extractedResult.deliverables;
    if (extractedResult?.schedule)     meta.schedule     = extractedResult.schedule;
    createMutation.mutate({
      ...form,
      total_budget: Number(form.total_budget),
      budget_categories: budgets.filter((b) => b.allocated_amount > 0),
      metadata: meta,
    });
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="max-w-3xl space-y-5">
      <div className="flex items-center gap-3">
        <Link href="/projects">
          <Button variant="ghost" size="icon" className="w-8 h-8">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <h2 className="text-xl font-bold text-gray-900">과제 등록</h2>
      </div>

      {/* ── PDF 자동 추출 카드 ── */}
      <Card className="border-blue-100 bg-blue-50/30">
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2 text-blue-700">
            <Sparkles className="w-4 h-4" />
            PDF 자동 추출
            <span className="text-xs font-normal text-blue-500 ml-1">
              사업계획서 · 협약체결확약서 · 참여연구원현황표 업로드 시 자동 입력
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {/* 파일 목록 */}
          {uploadedFiles.length > 0 && (
            <div className="space-y-2">
              {uploadedFiles.map((uf, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 bg-white border border-blue-100 rounded-md px-3 py-2"
                >
                  <FileUp className="w-4 h-4 text-blue-400 shrink-0" />
                  <span className="flex-1 text-sm text-gray-700 truncate">{uf.label}</span>
                  <span className="text-xs text-blue-400 shrink-0">자동 감지</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="w-6 h-6 text-gray-400 hover:text-red-500 shrink-0"
                    onClick={() => removeFile(idx)}
                  >
                    <X className="w-3.5 h-3.5" />
                  </Button>
                </div>
              ))}
            </div>
          )}

          {/* 업로드 버튼 영역 */}
          <div className="flex items-center gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              multiple
              className="hidden"
              onChange={handleFileAdd}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-1.5 border-blue-200 text-blue-700 hover:bg-blue-50"
              onClick={() => fileInputRef.current?.click()}
            >
              <Plus className="w-3.5 h-3.5" />
              PDF 추가
            </Button>

            {uploadedFiles.length > 0 && (
              <Button
                type="button"
                size="sm"
                className="gap-1.5 bg-blue-600 hover:bg-blue-700 text-white"
                disabled={extracting}
                onClick={handleExtract}
              >
                {extracting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    추출 중...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5" />
                    자동 추출
                  </>
                )}
              </Button>
            )}

            {extractedResult && (
              <Badge variant="outline" className="text-green-600 border-green-300 bg-green-50 text-xs">
                추출 완료 (신뢰도 {Math.round(extractedResult.confidence * 100)}%)
              </Badge>
            )}
          </div>

          {extractError && (
            <p className="text-xs text-red-600 bg-red-50 px-3 py-1.5 rounded">
              {extractError}
            </p>
          )}
        </CardContent>
      </Card>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* ── 기본 정보 ── */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">기본 정보</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="name">과제명 *</Label>
                <Input
                  id="name"
                  required
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="과제명을 입력하세요"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="code">과제 번호 *</Label>
                <Input
                  id="code"
                  required
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                  placeholder="예: 2024-ABC-0001"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="institution">주관기관 *</Label>
                <Input
                  id="institution"
                  required
                  value={form.institution}
                  onChange={(e) => setForm({ ...form, institution: e.target.value })}
                  placeholder="기관명"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="pi">연구책임자 *</Label>
                <Input
                  id="pi"
                  required
                  value={form.principal_investigator}
                  onChange={(e) =>
                    setForm({ ...form, principal_investigator: e.target.value })
                  }
                  placeholder="성명"
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="start">시작일 *</Label>
                <Input
                  id="start"
                  type="date"
                  required
                  value={form.period_start}
                  onChange={(e) => setForm({ ...form, period_start: e.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="end">종료일 *</Label>
                <Input
                  id="end"
                  type="date"
                  required
                  value={form.period_end}
                  onChange={(e) => setForm({ ...form, period_end: e.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="budget">총 예산 (원) *</Label>
                <Input
                  id="budget"
                  type="number"
                  required
                  min={1}
                  value={form.total_budget}
                  onChange={(e) => setForm({ ...form, total_budget: e.target.value })}
                  placeholder="0"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ── 비목별 예산 ── */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">비목별 예산</CardTitle>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={addBudget}
                className="gap-1.5"
                disabled={budgets.length >= ALL_CATEGORIES.length}
              >
                <Plus className="w-3.5 h-3.5" />
                비목 추가
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {budgets.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-4">
                비목을 추가하거나 PDF에서 자동 추출하세요
              </p>
            ) : (
              budgets.map((row, idx) => (
                <div key={idx} className="flex items-center gap-3">
                  <select
                    className="flex-1 border border-gray-200 rounded-md px-3 py-2 text-sm"
                    value={row.category_type}
                    onChange={(e) => {
                      const updated = [...budgets];
                      updated[idx].category_type = e.target.value as CategoryType;
                      setBudgets(updated);
                    }}
                  >
                    {ALL_CATEGORIES.map(([k, label]) => (
                      <option key={k} value={k}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <Input
                    type="number"
                    min={0}
                    className="w-44"
                    value={row.allocated_amount || ""}
                    onChange={(e) => {
                      const updated = [...budgets];
                      updated[idx].allocated_amount = Number(e.target.value);
                      setBudgets(updated);
                    }}
                    placeholder="금액 (원)"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="w-8 h-8 text-red-400 hover:text-red-600"
                    onClick={() => removeBudget(idx)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* ── 사업계획서 주요 내용 (추출됐을 때만 표시) ── */}
        {extractedResult && (extractedResult.overview || extractedResult.deliverables || extractedResult.schedule) && (
          <Card className="border-indigo-100 bg-indigo-50/20">
            <CardHeader className="pb-3">
              <CardTitle className="text-base text-indigo-700 flex items-center gap-2">
                <Sparkles className="w-4 h-4" />
                사업계획서 주요 내용
                <span className="text-xs font-normal text-indigo-400">AI 추출 결과 · 과제 등록 시 함께 저장됩니다</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              {extractedResult.overview && (
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-indigo-600">📋 개요</p>
                  <p className="text-gray-700 bg-white border border-indigo-100 rounded-md px-3 py-2 leading-relaxed whitespace-pre-wrap">
                    {extractedResult.overview}
                  </p>
                </div>
              )}
              {extractedResult.deliverables && (
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-indigo-600">🎯 결과물 및 주요 성능지표</p>
                  <p className="text-gray-700 bg-white border border-indigo-100 rounded-md px-3 py-2 leading-relaxed whitespace-pre-wrap">
                    {extractedResult.deliverables}
                  </p>
                </div>
              )}
              {extractedResult.schedule && (
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-indigo-600">📅 사업추진 일정</p>
                  <p className="text-gray-700 bg-white border border-indigo-100 rounded-md px-3 py-2 leading-relaxed whitespace-pre-wrap">
                    {extractedResult.schedule}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* ── 참여연구원 현황표 ── */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">참여연구원 현황</CardTitle>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={addResearcher}
                className="gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                연구원 추가
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {researchers.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-4">
                연구원을 추가하거나 PDF에서 자동 추출하세요
              </p>
            ) : (
              <>
                {/* 헤더 */}
                <div className="grid grid-cols-12 gap-2 text-xs text-gray-500 font-medium pb-2 border-b border-gray-200 mb-1">
                  <div className="col-span-1">구분</div>
                  <div className="col-span-2">성명</div>
                  <div className="col-span-2">직위</div>
                  <div className="col-span-1">연봉(천)</div>
                  <div className="col-span-1">월급(천)</div>
                  <div className="col-span-1">기간(월)</div>
                  <div className="col-span-1">참여율%</div>
                  <div className="col-span-1">현금(천)</div>
                  <div className="col-span-1">현물(천)</div>
                  <div className="col-span-1"></div>
                </div>
                {researchers.map((row, idx) => (
                  <ResearcherRowEditor
                    key={idx}
                    row={row}
                    idx={idx}
                    onChange={updateResearcher}
                    onRemove={removeResearcher}
                  />
                ))}
              </>
            )}
          </CardContent>
        </Card>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 px-4 py-2 rounded-md">
            {error}
          </p>
        )}

        <div className="flex gap-3">
          <Button
            type="submit"
            disabled={createMutation.isPending}
            className="flex-1"
          >
            {createMutation.isPending ? "등록 중..." : "과제 등록"}
          </Button>
          <Link href="/projects">
            <Button type="button" variant="outline">
              취소
            </Button>
          </Link>
        </div>
      </form>
    </div>
  );
}
