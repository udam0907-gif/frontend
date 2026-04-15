"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { rcmsApi } from "@/lib/api";
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
} from "lucide-react";
import Link from "next/link";
import type { EvidenceChunk, RcmsQaResponse, RcmsQaSession } from "@/lib/types";

// ─── Evidence card ────────────────────────────────────────────────────────────

function EvidenceCard({ ev, index }: { ev: EvidenceChunk; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const pct = Math.round(ev.confidence * 100);

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden text-xs">
      <button
        type="button"
        className="w-full flex items-center gap-2 px-3 py-2 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
        onClick={() => setExpanded((v) => !v)}
      >
        <FileText className="w-3.5 h-3.5 text-blue-400 shrink-0" />
        <span className="font-medium text-blue-700 truncate max-w-[180px]">
          {ev.display_name}
        </span>
        {ev.page != null && (
          <span className="text-gray-400 shrink-0">{ev.page}p</span>
        )}
        {ev.section_title && (
          <span className="text-gray-600 truncate flex-1">{ev.section_title}</span>
        )}
        <span
          className={`ml-auto shrink-0 font-medium ${
            pct >= 90
              ? "text-green-600"
              : pct >= 75
              ? "text-blue-600"
              : "text-yellow-600"
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

// ─── Answer block ─────────────────────────────────────────────────────────────

function AnswerBlock({
  question,
  answer,
}: {
  question: string;
  answer: RcmsQaResponse;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <p className="text-sm font-semibold text-gray-800 leading-snug">
          Q. {question}
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {!answer.found_in_manual ? (
          <div className="flex items-start gap-2.5 p-3.5 bg-yellow-50 border border-yellow-200 rounded-lg">
            <AlertCircle className="w-4 h-4 text-yellow-500 shrink-0 mt-0.5" />
            <div className="text-sm text-yellow-800">
              <p className="font-semibold mb-0.5">매뉴얼에서 답변을 찾지 못했습니다</p>
              <p className="text-yellow-700">{answer.detailed_explanation}</p>
            </div>
          </div>
        ) : (
          <>
            {/* Short answer */}
            <div className="p-3.5 bg-blue-50 border border-blue-100 rounded-lg">
              <div className="flex items-center gap-1.5 mb-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                <p className="text-xs font-semibold text-blue-700 uppercase tracking-wide">
                  요약 답변
                </p>
              </div>
              <p className="text-sm text-blue-800 leading-relaxed">
                {answer.short_answer}
              </p>
            </div>

            {/* Detailed explanation */}
            <div className="p-3.5 bg-gray-50 border border-gray-100 rounded-lg">
              <p className="text-xs font-semibold text-gray-600 mb-1.5 uppercase tracking-wide">
                상세 설명
              </p>
              <p className="text-sm text-gray-700 whitespace-pre-line leading-relaxed">
                {answer.detailed_explanation}
              </p>
            </div>

            {/* Evidence */}
            {answer.evidence.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  근거 자료 ({answer.evidence.length}건)
                </p>
                <div className="space-y-1.5">
                  {answer.evidence.map((ev, i) => (
                    <EvidenceCard key={i} ev={ev} index={i} />
                  ))}
                </div>
              </div>
            )}

            {/* Status badge */}
            <div className="flex items-center gap-1.5 pt-1">
              <Badge className="text-xs bg-green-50 text-green-700 border-green-200">
                answered_with_evidence
              </Badge>
              <span className="text-xs text-gray-400">
                {answer.model_version} · v{answer.prompt_version}
              </span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ─── History answer block (from session) ─────────────────────────────────────

function SessionAnswerBlock({ session }: { session: RcmsQaSession }) {
  const ans = session.answer;
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
            업로드된 RCMS 매뉴얼에서 해당 내용을 찾을 수 없습니다.
          </div>
        ) : (
          <>
            <div className="p-3 bg-blue-50 rounded-lg">
              <p className="text-xs font-semibold text-blue-600 mb-1">요약 답변</p>
              <p className="text-sm text-blue-800">{ans.short_answer}</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-xs font-semibold text-gray-500 mb-1">상세 설명</p>
              <p className="text-sm text-gray-700 whitespace-pre-line">
                {ans.detailed_explanation}
              </p>
            </div>
            {ans.evidence.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-500 mb-2">
                  근거 자료 ({ans.evidence.length}건)
                </p>
                <div className="space-y-1.5">
                  {ans.evidence.map((ev, i) => (
                    <EvidenceCard key={i} ev={ev} index={i} />
                  ))}
                </div>
              </div>
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
  const [selectedSession, setSelectedSession] = useState<RcmsQaSession | null>(
    null
  );

  const { data: manuals } = useQuery({
    queryKey: ["rcms-manuals"],
    queryFn: rcmsApi.listManuals,
  });

  const { data: sessions, isLoading: sessionsLoading } = useQuery({
    queryKey: ["rcms-sessions"],
    queryFn: rcmsApi.listSessions,
  });

  const askMutation = useMutation({
    mutationFn: (q: string) => rcmsApi.ask(q),
    onSuccess: (answer, q) => {
      setCurrentAnswer({ question: q, answer });
      setSelectedSession(null);
      queryClient.invalidateQueries({ queryKey: ["rcms-sessions"] });
    },
  });

  const completedManuals =
    manuals?.filter((m) => m.parse_status === "completed") ?? [];
  const processingManuals =
    manuals?.filter(
      (m) => m.parse_status === "pending" || m.parse_status === "processing"
    ) ?? [];

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
            업로드된 RCMS 매뉴얼 내용만을 근거로 답변합니다
          </p>
        </div>
        <Link href="/rcms/manuals">
          <Button variant="outline" size="sm" className="gap-1.5">
            <BookOpen className="w-4 h-4" />
            매뉴얼 관리
          </Button>
        </Link>
      </div>

      {/* No manuals warning */}
      {completedManuals.length === 0 && processingManuals.length === 0 && (
        <div className="flex items-center gap-2 p-3.5 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-800">
          <AlertCircle className="w-4 h-4 shrink-0" />
          RCMS 매뉴얼이 없습니다.{" "}
          <Link href="/rcms/manuals" className="underline font-medium">
            매뉴얼을 먼저 업로드
          </Link>
          해주세요.
        </div>
      )}
      {processingManuals.length > 0 && completedManuals.length === 0 && (
        <div className="flex items-center gap-2 p-3.5 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
          <AlertCircle className="w-4 h-4 shrink-0" />
          매뉴얼 {processingManuals.length}개가 RAG 인덱싱 중입니다. 잠시 후
          질문하세요.
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
                  "RCMS 관련 질문을 입력하세요\n예: 외주비 집행 시 비교견적서는 어떤 경우에 필요한가요?"
                }
                disabled={completedManuals.length === 0}
              />
              <Button
                className="w-full gap-2 h-10"
                onClick={handleAsk}
                disabled={
                  !question.trim() ||
                  askMutation.isPending ||
                  completedManuals.length === 0
                }
              >
                {askMutation.isPending ? (
                  <>
                    <span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
                    매뉴얼 검색 중...
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    질문하기 (Ctrl+Enter)
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Loading skeleton */}
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

          {/* Current answer */}
          {currentAnswer && !askMutation.isPending && !selectedSession && (
            <AnswerBlock
              question={currentAnswer.question}
              answer={currentAnswer.answer}
            />
          )}

          {/* Session from history */}
          {selectedSession && !askMutation.isPending && (
            <SessionAnswerBlock session={selectedSession} />
          )}

          {/* Error */}
          {askMutation.isError && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              <AlertCircle className="w-4 h-4 shrink-0" />
              오류가 발생했습니다: {askMutation.error?.message}
            </div>
          )}
        </div>

        {/* Right: Sidebar */}
        <div className="space-y-4">
          {/* Manual list */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center justify-between">
                <span>검색 대상 매뉴얼</span>
                <span className="text-xs font-normal text-gray-400">
                  {completedManuals.length}개
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {completedManuals.length === 0 ? (
                <p className="text-xs text-gray-400">인덱싱 완료된 매뉴얼 없음</p>
              ) : (
                completedManuals.map((m) => (
                  <div key={m.id} className="flex items-center gap-2 text-xs">
                    <BookOpen className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                    <span className="text-gray-700 truncate flex-1">
                      {m.display_name}
                    </span>
                    {m.total_chunks != null && (
                      <span className="text-gray-400 shrink-0">
                        {m.total_chunks}청크
                      </span>
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
                (sessions ?? []).slice(0, 10).map((s) => (
                  <button
                    key={s.id}
                    className={`w-full text-left text-xs px-2 py-1.5 rounded transition-colors truncate block ${
                      selectedSession?.id === s.id
                        ? "bg-blue-50 text-blue-700 font-medium"
                        : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                    }`}
                    onClick={() => {
                      setSelectedSession(s);
                      setCurrentAnswer(null);
                    }}
                    title={s.question}
                  >
                    <span
                      className={`inline-block w-1.5 h-1.5 rounded-full mr-1.5 shrink-0 align-middle ${
                        s.answer?.found_in_manual
                          ? "bg-green-400"
                          : "bg-yellow-400"
                      }`}
                    />
                    {s.question}
                  </button>
                ))
              )}
            </CardContent>
          </Card>

          {/* Policy notice */}
          <div className="p-3 bg-gray-50 rounded-lg text-xs text-gray-500 space-y-1 leading-relaxed">
            <p className="font-medium text-gray-700">답변 정책</p>
            <p>업로드된 RCMS 매뉴얼 내용만을 근거로 답변합니다.</p>
            <p>외부 지식 및 추측은 사용하지 않습니다.</p>
            <p>
              근거가 없을 경우{" "}
              <span className="font-mono bg-yellow-50 text-yellow-700 px-1 rounded">
                not_found
              </span>{" "}
              로 표시됩니다.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
