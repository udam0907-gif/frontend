"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { rcmsApi, legalApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  BookOpen,
  Send,
  AlertCircle,
  CheckCircle2,
  FileText,
  ChevronDown,
  ChevronUp,
  Clock,
  Scale,
  Gavel,
  ListChecks,
  RefreshCw,
  Info,
  ShieldAlert,
  Bug,
} from "lucide-react";
import Link from "next/link";
import type {
  AnswerStatusType,
  DebugInfo,
  EvidenceChunk,
  RcmsQaResponse,
  RcmsQaSession,
  QuestionType,
} from "@/lib/types";

// ─── Question type helpers ────────────────────────────────────────────────────

const Q_TYPE_LABELS: Record<QuestionType, string> = {
  rcms_procedure: "RCMS 절차",
  legal_policy: "법령·규정",
  mixed: "복합 질문",
  definition: "용어 정의",
};
const Q_TYPE_COLORS: Record<QuestionType, string> = {
  rcms_procedure: "bg-blue-50 text-blue-700 border-blue-200",
  legal_policy: "bg-purple-50 text-purple-700 border-purple-200",
  mixed: "bg-orange-50 text-orange-700 border-orange-200",
  definition: "bg-teal-50 text-teal-700 border-teal-200",
};

const ANSWER_STATUS_LABELS: Record<AnswerStatusType, string> = {
  answered_with_direct_evidence: "직접 근거 확인",
  answered_with_mixed_sources: "복합 근거 확인",
  related_context_only: "관련 맥락만 확인",
  insufficient_evidence: "근거 불충분",
  not_found_in_uploaded_materials: "자료 없음",
  routing_error: "라우팅 오류",
};
const ANSWER_STATUS_COLORS: Record<AnswerStatusType, string> = {
  answered_with_direct_evidence: "bg-green-50 text-green-700 border-green-200",
  answered_with_mixed_sources: "bg-blue-50 text-blue-700 border-blue-200",
  related_context_only: "bg-yellow-50 text-yellow-700 border-yellow-200",
  insufficient_evidence: "bg-orange-50 text-orange-700 border-orange-200",
  not_found_in_uploaded_materials: "bg-red-50 text-red-700 border-red-200",
  routing_error: "bg-gray-50 text-gray-700 border-gray-200",
};
const CONFIDENCE_COLORS: Record<string, string> = {
  high: "bg-green-50 text-green-700 border-green-200",
  medium: "bg-yellow-50 text-yellow-700 border-yellow-200",
  low: "bg-red-50 text-red-700 border-red-200",
};

// ─── Evidence card ────────────────────────────────────────────────────────────

const TIER_STYLE: Record<number, { border: string; bg: string; hover: string; icon: string; label: string }> = {
  1: { border: "border-purple-200", bg: "bg-purple-50", hover: "hover:bg-purple-100", icon: "text-purple-500", label: "법령 원문" },
  2: { border: "border-emerald-200", bg: "bg-emerald-50", hover: "hover:bg-emerald-100", icon: "text-emerald-600", label: "공식 FAQ" },
  3: { border: "border-gray-200", bg: "bg-gray-50", hover: "hover:bg-gray-100", icon: "text-blue-400", label: "참고 자료" },
};

function EvidenceCard({ ev, index }: { ev: EvidenceChunk; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const pct = Math.round(ev.confidence * 100);
  const isLegal = ev.source_type === "legal";
  const tier = ev.evidence_tier ?? (isLegal ? 1 : 3);
  const style = TIER_STYLE[tier] ?? TIER_STYLE[3];

  const title = isLegal
    ? `${ev.law_name ?? "법령"}${ev.article_number ? ` ${ev.article_number}` : ""}`
    : (ev.display_name ?? "매뉴얼");

  const subtitle = isLegal
    ? ev.article_title ?? ev.section_title
    : ev.section_title;

  return (
    <div className={`border rounded-lg overflow-hidden text-xs ${style.border}`}>
      <button
        type="button"
        className={`w-full flex items-center gap-2 px-3 py-2 transition-colors text-left ${style.bg} ${style.hover}`}
        onClick={() => setExpanded((v) => !v)}
      >
        {tier === 1 ? (
          <Scale className={`w-3.5 h-3.5 shrink-0 ${style.icon}`} />
        ) : tier === 2 ? (
          <Gavel className={`w-3.5 h-3.5 shrink-0 ${style.icon}`} />
        ) : (
          <FileText className={`w-3.5 h-3.5 shrink-0 ${style.icon}`} />
        )}
        <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold shrink-0 ${
          tier === 1 ? "bg-purple-100 text-purple-700"
          : tier === 2 ? "bg-emerald-100 text-emerald-700"
          : "bg-gray-100 text-gray-500"
        }`}>
          {ev.source_label ?? style.label}
        </span>
        <span className="font-medium truncate max-w-[180px] text-gray-800">
          {title}
        </span>
        {ev.page != null && !isLegal && (
          <span className="text-gray-400 shrink-0">{ev.page}p</span>
        )}
        {subtitle && (
          <span className="text-gray-500 truncate flex-1">{subtitle}</span>
        )}
        {ev.is_decisive && (
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
        )}
        <span
          className={`ml-auto shrink-0 font-medium ${
            pct >= 90 ? "text-green-600" : pct >= 70 ? "text-blue-600" : "text-yellow-600"
          }`}
        >
          {pct}%
        </span>
        {expanded ? (
          <ChevronUp className="w-3.5 h-3.5 text-gray-400 shrink-0" />
        ) : (
          <ChevronDown className="w-3.5 h-3.5 text-gray-400 shrink-0" />
        )}
      </button>
      {expanded && (
        <div className="px-3 py-2.5 bg-white border-t border-gray-100">
          <p className="text-gray-600 italic leading-relaxed">"{ev.excerpt}"</p>
        </div>
      )}
    </div>
  );
}

// ─── Evidence group (by source type) ─────────────────────────────────────────

function EvidenceGroup({ evidence }: { evidence: EvidenceChunk[] }) {
  const legal = evidence.filter((e) => e.source_type === "legal");
  const rcms  = evidence.filter((e) => e.source_type === "rcms");

  return (
    <div className="space-y-3">
      {legal.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-1.5">
            <Scale className="w-3.5 h-3.5 text-purple-500" />
            <p className="text-xs font-semibold text-purple-700 uppercase tracking-wide">
              법령/규정 근거 ({legal.length}건)
            </p>
          </div>
          <div className="space-y-1.5">
            {legal.map((ev, i) => <EvidenceCard key={i} ev={ev} index={i} />)}
          </div>
        </div>
      )}
      {rcms.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-1.5">
            <FileText className="w-3.5 h-3.5 text-blue-400" />
            <p className="text-xs font-semibold text-blue-700 uppercase tracking-wide">
              RCMS 매뉴얼 근거 ({rcms.length}건)
            </p>
          </div>
          <div className="space-y-1.5">
            {rcms.map((ev, i) => <EvidenceCard key={i} ev={ev} index={i} />)}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Debug panel ─────────────────────────────────────────────────────────────

function DebugPanel({ debug }: { debug: DebugInfo }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center gap-2 px-3 py-2 bg-gray-100 hover:bg-gray-200 text-xs text-gray-600 transition-colors text-left"
        onClick={() => setOpen((v) => !v)}
      >
        <Bug className="w-3.5 h-3.5 shrink-0" />
        <span className="font-medium">디버그 정보</span>
        <span className="ml-2 text-gray-400">
          {debug.routing_decision} · {debug.rcms_candidates.length}rcms
          {" · "}
          {debug.legal_candidates.length}legal
        </span>
        {open ? (
          <ChevronUp className="w-3.5 h-3.5 ml-auto shrink-0" />
        ) : (
          <ChevronDown className="w-3.5 h-3.5 ml-auto shrink-0" />
        )}
      </button>
      {open && (
        <div className="px-3 py-2.5 bg-white space-y-2 text-xs text-gray-600">
          <p>
            <span className="font-medium">분류:</span> {debug.question_type}
          </p>
          <p>
            <span className="font-medium">정규화:</span> {debug.normalized_query}
          </p>
          <p>
            <span className="font-medium">라우팅:</span> {debug.routing_decision}
          </p>
          <p>
            <span className="font-medium">확장 쿼리:</span>{" "}
            {debug.expanded_queries.slice(0, 3).join(" / ")}
          </p>
          {debug.answerability && (
            <p>
              <span className="font-medium">답변가능성:</span>{" "}
              {debug.answerability.status} — {debug.answerability.explanation}
            </p>
          )}
          {debug.rcms_candidates.length > 0 && (
            <div>
              <p className="font-medium mb-1">RCMS 후보 ({debug.rcms_candidates.length}건):</p>
              {debug.rcms_candidates.map((c, i) => (
                <div key={i} className="pl-2 border-l-2 border-blue-200 mb-1">
                  <span className="text-blue-600">{c.display_name}</span>
                  {c.page != null && <span className="text-gray-400"> p.{c.page}</span>}
                  <span className="text-green-600 ml-1">
                    {(c.similarity * 100).toFixed(1)}%
                  </span>
                  <p className="text-gray-500 truncate">{c.excerpt}</p>
                </div>
              ))}
            </div>
          )}
          {debug.legal_candidates.length > 0 && (
            <div>
              <p className="font-medium mb-1">법령 후보 ({debug.legal_candidates.length}건):</p>
              {debug.legal_candidates.map((c, i) => (
                <div key={i} className="pl-2 border-l-2 border-purple-200 mb-1">
                  <span className="text-purple-600">{c.law_name}</span>
                  {c.article && <span className="text-gray-400"> {c.article}</span>}
                  <span className="text-green-600 ml-1">
                    {(c.similarity * 100).toFixed(1)}%
                  </span>
                  <p className="text-gray-500 truncate">{c.excerpt}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Answer block ─────────────────────────────────────────────────────────────

function AnswerBlock({ question, answer }: { question: string; answer: RcmsQaResponse }) {
  const qType = (answer.question_type ?? "rcms_procedure") as QuestionType;
  const statusType = answer.answer_status_type as AnswerStatusType;

  return (
    <Card>
      <CardHeader className="pb-2">
        <p className="text-sm font-semibold text-gray-800 leading-snug">Q. {question}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        {!answer.found_in_manual ? (
          <div className="flex items-start gap-2.5 p-3.5 bg-yellow-50 border border-yellow-200 rounded-lg">
            <AlertCircle className="w-4 h-4 text-yellow-500 shrink-0 mt-0.5" />
            <div className="text-sm text-yellow-800">
              <p className="font-semibold mb-0.5">답변을 찾지 못했습니다</p>
              <p className="text-yellow-700">{answer.detailed_explanation}</p>
            </div>
          </div>
        ) : (
          <>
            {/* Question type badge + short answer */}
            <div className="p-3.5 bg-blue-50 border border-blue-100 rounded-lg">
              <div className="flex items-center gap-2 mb-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                <p className="text-xs font-semibold text-blue-700 uppercase tracking-wide">요약 답변</p>
                <Badge className={`text-xs ml-auto ${Q_TYPE_COLORS[qType]}`}>
                  {Q_TYPE_LABELS[qType]}
                </Badge>
                {answer.confidence && (
                  <Badge className={`text-xs ${CONFIDENCE_COLORS[answer.confidence] ?? ""}`}>
                    {answer.confidence === "high"
                      ? "신뢰도 높음"
                      : answer.confidence === "medium"
                      ? "신뢰도 중간"
                      : "신뢰도 낮음"}
                  </Badge>
                )}
              </div>
              <p className="text-sm text-blue-800 leading-relaxed">{answer.short_answer}</p>
            </div>

            {/* Legal conclusion (legal_policy / mixed) */}
            {answer.conclusion && (
              <div className="p-3.5 bg-purple-50 border border-purple-200 rounded-lg">
                <div className="flex items-center gap-1.5 mb-1.5">
                  <Gavel className="w-3.5 h-3.5 text-purple-600" />
                  <p className="text-xs font-semibold text-purple-700 uppercase tracking-wide">법적 결론</p>
                </div>
                <p className="text-sm text-purple-900 leading-relaxed">{answer.conclusion}</p>
                {answer.legal_basis && (
                  <p className="text-xs text-purple-600 mt-1.5 font-medium">
                    근거: {answer.legal_basis}
                  </p>
                )}
              </div>
            )}

            {/* Conditions or exceptions */}
            {answer.conditions_or_exceptions && (
              <div className="p-3.5 bg-yellow-50 border border-yellow-200 rounded-lg">
                <div className="flex items-center gap-1.5 mb-1.5">
                  <Info className="w-3.5 h-3.5 text-yellow-600" />
                  <p className="text-xs font-semibold text-yellow-700 uppercase tracking-wide">조건 및 예외사항</p>
                </div>
                <p className="text-sm text-yellow-900 leading-relaxed whitespace-pre-line">
                  {answer.conditions_or_exceptions}
                </p>
              </div>
            )}

            {/* RCMS steps (rcms_procedure / mixed) */}
            {answer.rcms_steps && (
              <div className="p-3.5 bg-green-50 border border-green-200 rounded-lg">
                <div className="flex items-center gap-1.5 mb-1.5">
                  <ListChecks className="w-3.5 h-3.5 text-green-600" />
                  <p className="text-xs font-semibold text-green-700 uppercase tracking-wide">RCMS 처리 절차</p>
                </div>
                <p className="text-sm text-green-900 whitespace-pre-line leading-relaxed">
                  {answer.rcms_steps}
                </p>
              </div>
            )}

            {/* Further confirmation needed */}
            {answer.further_confirmation_needed && (
              <div className="flex items-start gap-2 p-3 bg-orange-50 border border-orange-200 rounded-lg">
                <ShieldAlert className="w-4 h-4 text-orange-500 shrink-0 mt-0.5" />
                <p className="text-xs text-orange-800">
                  이 답변은 추가 확인이 권장됩니다. 담당 기관 또는 규정 원문을 직접 확인하세요.
                </p>
              </div>
            )}

            {/* Detailed explanation */}
            <div className="p-3.5 bg-gray-50 border border-gray-100 rounded-lg">
              <p className="text-xs font-semibold text-gray-600 mb-1.5 uppercase tracking-wide">상세 설명</p>
              <p className="text-sm text-gray-700 whitespace-pre-line leading-relaxed">
                {answer.detailed_explanation}
              </p>
            </div>

            {/* Evidence separated by source */}
            {answer.evidence.length > 0 && (
              <EvidenceGroup evidence={answer.evidence} />
            )}

            {/* Meta */}
            <div className="flex items-center gap-1.5 pt-1 flex-wrap">
              {statusType && ANSWER_STATUS_LABELS[statusType] && (
                <Badge
                  className={`text-xs ${ANSWER_STATUS_COLORS[statusType] ?? "bg-gray-50 text-gray-700 border-gray-200"}`}
                >
                  {ANSWER_STATUS_LABELS[statusType]}
                </Badge>
              )}
              <span className="text-xs text-gray-400">
                {answer.model_version} · v{answer.prompt_version}
              </span>
            </div>

            {/* Debug panel */}
            {answer.debug && <DebugPanel debug={answer.debug} />}
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ─── History answer block ─────────────────────────────────────────────────────

function SessionAnswerBlock({ session }: { session: RcmsQaSession }) {
  const ans = session.answer;
  const qType = (ans.question_type ?? "rcms_procedure") as QuestionType;

  return (
    <Card className="border-orange-100">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2 text-xs text-gray-400 mb-1">
          <Clock className="w-3 h-3" />
          {new Date(session.created_at).toLocaleString("ko-KR")}
        </div>
        <p className="text-sm font-semibold text-gray-800">Q. {session.question}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        {!ans.found_in_manual ? (
          <div className="flex items-start gap-2 p-3 bg-yellow-50 rounded-lg text-sm text-yellow-700">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            답변을 찾을 수 없습니다.
          </div>
        ) : (
          <>
            <div className="p-3 bg-blue-50 rounded-lg">
              <div className="flex items-center gap-2 mb-1">
                <p className="text-xs font-semibold text-blue-600">요약 답변</p>
                <Badge className={`text-xs ml-auto ${Q_TYPE_COLORS[qType]}`}>
                  {Q_TYPE_LABELS[qType]}
                </Badge>
              </div>
              <p className="text-sm text-blue-800">{ans.short_answer}</p>
            </div>
            {ans.conclusion && (
              <div className="p-3 bg-purple-50 rounded-lg">
                <p className="text-xs font-semibold text-purple-600 mb-1">법적 결론</p>
                <p className="text-sm text-purple-900">{ans.conclusion}</p>
                {ans.legal_basis && (
                  <p className="text-xs text-purple-600 mt-1">근거: {ans.legal_basis}</p>
                )}
              </div>
            )}
            {ans.rcms_steps && (
              <div className="p-3 bg-green-50 rounded-lg">
                <p className="text-xs font-semibold text-green-600 mb-1">RCMS 처리 절차</p>
                <p className="text-sm text-green-900 whitespace-pre-line">{ans.rcms_steps}</p>
              </div>
            )}
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-xs font-semibold text-gray-500 mb-1">상세 설명</p>
              <p className="text-sm text-gray-700 whitespace-pre-line">{ans.detailed_explanation}</p>
            </div>
            {ans.evidence && ans.evidence.length > 0 && (
              <EvidenceGroup evidence={ans.evidence} />
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function RcmsQaPage() {
  const queryClient = useQueryClient();
  const [question, setQuestion] = useState("");
  const [currentAnswer, setCurrentAnswer] = useState<{
    question: string;
    answer: RcmsQaResponse;
  } | null>(null);
  const [selectedSession, setSelectedSession] = useState<RcmsQaSession | null>(null);

  const { data: manuals } = useQuery({
    queryKey: ["rcms-manuals"],
    queryFn: rcmsApi.listManuals,
  });

  const { data: legalDocs } = useQuery({
    queryKey: ["legal-docs"],
    queryFn: legalApi.list,
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.some(
        (d) => d.sync_status === "processing" || d.sync_status === "pending"
      ) ? 3000 : false;
    },
  });

  const { data: sessions, isLoading: sessionsLoading } = useQuery({
    queryKey: ["rcms-sessions"],
    queryFn: rcmsApi.listSessions,
  });

  const [debugMode, setDebugMode] = useState(false);

  const askMutation = useMutation({
    mutationFn: (q: string) => rcmsApi.ask(q, undefined, debugMode),
    onSuccess: (answer, q) => {
      setCurrentAnswer({ question: q, answer });
      setSelectedSession(null);
      queryClient.invalidateQueries({ queryKey: ["rcms-sessions"] });
    },
  });

  const completedManuals = manuals?.filter((m) => m.parse_status === "completed") ?? [];
  const processingManuals = manuals?.filter(
    (m) => m.parse_status === "pending" || m.parse_status === "processing"
  ) ?? [];
  const completedLegal = legalDocs?.filter((d) => d.sync_status === "completed") ?? [];

  const canAsk = completedManuals.length > 0 || completedLegal.length > 0;

  const handleAsk = () => {
    const q = question.trim();
    if (!q) return;
    setSelectedSession(null);
    askMutation.mutate(q);
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900">RCMS Q&A</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            RCMS 매뉴얼 · 국가연구개발 법령을 함께 검색하여 답변합니다
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/rcms/laws">
            <Button variant="outline" size="sm" className="gap-1.5">
              <Scale className="w-4 h-4" />
              법령 관리
            </Button>
          </Link>
          <Link href="/rcms/manuals">
            <Button variant="outline" size="sm" className="gap-1.5">
              <BookOpen className="w-4 h-4" />
              매뉴얼 관리
            </Button>
          </Link>
        </div>
      </div>

      {/* Warnings */}
      {completedManuals.length === 0 && processingManuals.length === 0 && completedLegal.length === 0 && (
        <div className="flex items-center gap-2 p-3.5 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-800">
          <AlertCircle className="w-4 h-4 shrink-0" />
          RCMS 매뉴얼과 법령이 없습니다.{" "}
          <Link href="/rcms/manuals" className="underline font-medium">매뉴얼</Link>
          {" "}또는{" "}
          <Link href="/rcms/laws" className="underline font-medium">법령</Link>
          을 먼저 등록해주세요.
        </div>
      )}
      {processingManuals.length > 0 && completedManuals.length === 0 && completedLegal.length === 0 && (
        <div className="flex items-center gap-2 p-3.5 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
          <AlertCircle className="w-4 h-4 shrink-0" />
          매뉴얼 {processingManuals.length}개가 인덱싱 중입니다. 잠시 후 질문하세요.
        </div>
      )}

      <div className="grid grid-cols-3 gap-5">
        {/* Left: Q&A */}
        <div className="col-span-2 space-y-4">
          <Card>
            <CardContent className="p-4 space-y-3">
              <Textarea
                rows={4}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleAsk();
                }}
                placeholder={
                  "RCMS 사용 절차 또는 법령·규정 관련 질문을 입력하세요\n예: 편성된 연구비를 다른 항목으로 한도전용이 가능한가요?"
                }
                disabled={!canAsk}
              />
              <div className="flex items-center gap-2">
                <Button
                  className="flex-1 gap-2 h-10"
                  onClick={handleAsk}
                  disabled={!question.trim() || askMutation.isPending || !canAsk}
                >
                  {askMutation.isPending ? (
                    <>
                      <span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
                      검색 중...
                    </>
                  ) : (
                    <>
                      <Send className="w-4 h-4" />
                      질문하기 (Ctrl+Enter)
                    </>
                  )}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className={`gap-1.5 h-10 text-xs ${
                    debugMode
                      ? "bg-gray-800 text-white border-gray-800 hover:bg-gray-700"
                      : ""
                  }`}
                  onClick={() => setDebugMode((v) => !v)}
                  title="디버그 모드 토글"
                >
                  <Bug className="w-3.5 h-3.5" />
                  {debugMode ? "Debug ON" : "Debug"}
                </Button>
              </div>
            </CardContent>
          </Card>

          {askMutation.isPending && (
            <Card>
              <CardContent className="p-4 space-y-3">
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-10 w-full" />
              </CardContent>
            </Card>
          )}

          {currentAnswer && !askMutation.isPending && !selectedSession && (
            <AnswerBlock question={currentAnswer.question} answer={currentAnswer.answer} />
          )}
          {selectedSession && !askMutation.isPending && (
            <SessionAnswerBlock session={selectedSession} />
          )}
          {askMutation.isError && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              <AlertCircle className="w-4 h-4 shrink-0" />
              오류: {askMutation.error?.message}
            </div>
          )}
        </div>

        {/* Right: Sidebar */}
        <div className="space-y-4">
          {/* Legal docs */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <Scale className="w-3.5 h-3.5 text-purple-500" />
                  법령/규정
                </span>
                <Link href="/rcms/laws">
                  <span className="text-xs font-normal text-purple-500 hover:underline">
                    {completedLegal.length}개 ›
                  </span>
                </Link>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1.5">
              {completedLegal.length === 0 ? (
                <div className="space-y-1.5">
                  <p className="text-xs text-gray-400">등록된 법령 없음</p>
                  <Link href="/rcms/laws">
                    <Button variant="outline" size="sm" className="w-full text-xs h-7 gap-1">
                      <RefreshCw className="w-3 h-3" />
                      법령 동기화
                    </Button>
                  </Link>
                </div>
              ) : (
                completedLegal.map((d) => (
                  <div key={d.id} className="flex items-center gap-2 text-xs">
                    <Scale className="w-3 h-3 text-purple-400 shrink-0" />
                    <span className="text-gray-700 truncate flex-1">{d.law_name}</span>
                    {d.total_chunks != null && (
                      <span className="text-gray-400 shrink-0">{d.total_chunks}청크</span>
                    )}
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          {/* RCMS Manuals */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <BookOpen className="w-3.5 h-3.5 text-blue-400" />
                  RCMS 매뉴얼
                </span>
                <span className="text-xs font-normal text-gray-400">{completedManuals.length}개</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {completedManuals.length === 0 ? (
                <p className="text-xs text-gray-400">인덱싱 완료된 매뉴얼 없음</p>
              ) : (
                completedManuals.map((m) => (
                  <div key={m.id} className="flex items-center gap-2 text-xs">
                    <BookOpen className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                    <span className="text-gray-700 truncate flex-1">{m.display_name}</span>
                    {m.total_chunks != null && (
                      <span className="text-gray-400 shrink-0">{m.total_chunks}청크</span>
                    )}
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          {/* Q&A history */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">최근 질문 이력</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1.5">
              {sessionsLoading ? (
                <>
                  <Skeleton className="h-7 w-full" />
                  <Skeleton className="h-7 w-full" />
                </>
              ) : (sessions ?? []).length === 0 ? (
                <p className="text-xs text-gray-400">질문 이력이 없습니다</p>
              ) : (
                (sessions ?? []).slice(0, 10).map((s) => {
                  const qType = (s.answer?.question_type ?? "rcms_procedure") as QuestionType;
                  return (
                    <button
                      key={s.id}
                      className={`w-full text-left text-xs px-2 py-1.5 rounded transition-colors truncate block ${
                        selectedSession?.id === s.id
                          ? "bg-blue-50 text-blue-700 font-medium"
                          : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                      }`}
                      onClick={() => { setSelectedSession(s); setCurrentAnswer(null); }}
                      title={s.question}
                    >
                      <span
                        className={`inline-block w-1.5 h-1.5 rounded-full mr-1.5 shrink-0 align-middle ${
                          qType === "legal_policy"
                            ? "bg-purple-400"
                            : qType === "mixed"
                            ? "bg-orange-400"
                            : qType === "definition"
                            ? "bg-teal-400"
                            : s.answer?.found_in_manual
                            ? "bg-green-400"
                            : "bg-yellow-400"
                        }`}
                      />
                      {s.question}
                    </button>
                  );
                })
              )}
            </CardContent>
          </Card>

          {/* Policy notice */}
          <div className="p-3 bg-gray-50 rounded-lg text-xs text-gray-500 space-y-1 leading-relaxed">
            <p className="font-medium text-gray-700">답변 정책</p>
            <div className="flex items-start gap-1">
              <Scale className="w-3 h-3 text-purple-400 mt-0.5 shrink-0" />
              <p>법령 질문: 국가연구개발혁신법 등 법령 우선 검색</p>
            </div>
            <div className="flex items-start gap-1">
              <BookOpen className="w-3 h-3 text-blue-400 mt-0.5 shrink-0" />
              <p>절차 질문: 업로드된 RCMS 매뉴얼 검색</p>
            </div>
            <p>소스에 없는 내용은 추측하지 않습니다.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
