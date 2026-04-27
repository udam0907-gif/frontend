"use client";

import { useState, useMemo, useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { projectsApi } from "@/lib/api";
import { CATEGORY_LABELS } from "@/lib/constants";
import type { Project, ExpenseItem } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Lightbulb,
  Plus,
  StickyNote,
  ReceiptText,
  X,
} from "lucide-react";
import { formatCurrency } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ManualSchedule {
  id: string;
  date: string;       // "YYYY-MM-DD"
  title: string;
  note: string;
  color: "blue" | "green" | "orange" | "red" | "purple";
}

interface AutoRecommendation {
  date: string;
  title: string;
  type: "start" | "end" | "midpoint" | "quarter" | "final_prep" | "monthly_labor";
}

interface CalendarEvent {
  date: string;
  kind: "auto" | "manual" | "expense";
  title: string;
  subtitle?: string;
  color: string;
  raw?: ManualSchedule | AutoRecommendation | ExpenseItem;
}

// ---------------------------------------------------------------------------
// Color palette
// ---------------------------------------------------------------------------

const SCHEDULE_COLOR_OPTIONS: { value: ManualSchedule["color"]; label: string; cls: string }[] = [
  { value: "blue",   label: "파랑",  cls: "bg-blue-500"   },
  { value: "green",  label: "초록",  cls: "bg-green-500"  },
  { value: "orange", label: "주황",  cls: "bg-orange-500" },
  { value: "red",    label: "빨강",  cls: "bg-red-500"    },
  { value: "purple", label: "보라",  cls: "bg-purple-500" },
];

const DOT_COLOR: Record<string, string> = {
  blue:    "bg-blue-400",
  green:   "bg-green-400",
  orange:  "bg-orange-400",
  red:     "bg-red-400",
  purple:  "bg-purple-400",
  auto:    "bg-indigo-400",
  expense: "bg-emerald-400",
};

// ---------------------------------------------------------------------------
// Date utils
// ---------------------------------------------------------------------------

function toYMD(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function parseYMD(s: string): Date {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function addMonths(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth() + n, 1);
}

function lastDayOfMonth(y: number, m: number): number {
  return new Date(y, m + 1, 0).getDate();
}

// ---------------------------------------------------------------------------
// Auto-recommendations generator
// ---------------------------------------------------------------------------

function generateRecommendations(project: Project): AutoRecommendation[] {
  const recs: AutoRecommendation[] = [];
  if (!project.period_start || !project.period_end) return recs;

  const start = parseYMD(project.period_start);
  const end   = parseYMD(project.period_end);

  // 사업 시작
  recs.push({ date: toYMD(start), title: "🚀 사업 시작", type: "start" });

  // 사업 종료
  recs.push({ date: toYMD(end), title: "🏁 사업 종료", type: "end" });

  // 중간 점검
  const midMs = (start.getTime() + end.getTime()) / 2;
  recs.push({ date: toYMD(new Date(midMs)), title: "🔍 중간 점검", type: "midpoint" });

  // 최종 정산 준비 (종료 1개월 전)
  const finalPrep = new Date(end.getFullYear(), end.getMonth() - 1, end.getDate());
  if (finalPrep > start) {
    recs.push({ date: toYMD(finalPrep), title: "📋 최종 정산 준비", type: "final_prep" });
  }

  // 분기 집행 마감 (매 3개월 말일)
  let cur = new Date(start.getFullYear(), start.getMonth(), 1);
  let quarterCount = 0;
  while (cur <= end) {
    const monthsFromStart = (cur.getFullYear() - start.getFullYear()) * 12 + cur.getMonth() - start.getMonth();
    if (monthsFromStart > 0 && monthsFromStart % 3 === 0) {
      const qEnd = new Date(cur.getFullYear(), cur.getMonth(), 0); // last day of prev month
      if (qEnd > start && qEnd < end) {
        quarterCount++;
        recs.push({ date: toYMD(qEnd), title: `📊 ${quarterCount}분기 집행 마감`, type: "quarter" });
      }
    }
    cur = new Date(cur.getFullYear(), cur.getMonth() + 1, 1);
  }

  // 매월 인건비 마감일 (각 월 말일)
  const laborBudget = project.budget_categories?.find((c) => c.category_type === "labor");
  if (laborBudget && laborBudget.allocated_amount > 0) {
    let lCur = new Date(start.getFullYear(), start.getMonth(), 1);
    while (lCur <= end) {
      const lastDay = lastDayOfMonth(lCur.getFullYear(), lCur.getMonth());
      const ld = new Date(lCur.getFullYear(), lCur.getMonth(), lastDay);
      if (ld > start && ld <= end) {
        recs.push({ date: toYMD(ld), title: "💰 인건비 집행 마감", type: "monthly_labor" });
      }
      lCur = new Date(lCur.getFullYear(), lCur.getMonth() + 1, 1);
    }
  }

  return recs;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface ProjectCalendarProps {
  project: Project;
  expenses: ExpenseItem[];
}

export function ProjectCalendar({ project, expenses }: ProjectCalendarProps) {
  const queryClient = useQueryClient();

  // 현재 월
  const today = new Date();
  const [viewYear,  setViewYear]  = useState(today.getFullYear());
  const [viewMonth, setViewMonth] = useState(today.getMonth()); // 0-based

  // 선택된 날짜
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  // 수동 일정 추가 폼
  const [showAddForm, setShowAddForm] = useState(false);
  const [newTitle, setNewTitle]   = useState("");
  const [newNote,  setNewNote]    = useState("");
  const [newColor, setNewColor]   = useState<ManualSchedule["color"]>("blue");

  // metadata에서 수동 일정 읽기
  const schedules: ManualSchedule[] = useMemo(() => {
    const meta = (project as unknown as { metadata_?: Record<string, unknown> }).metadata_ ?? {};
    return (meta.schedules as ManualSchedule[]) ?? [];
  }, [project]);

  // 자동 추천 생성
  const recommendations = useMemo(() => generateRecommendations(project), [project]);

  // 전체 이벤트 맵 (date → events[])
  const eventMap = useMemo(() => {
    const map: Record<string, CalendarEvent[]> = {};

    const push = (date: string, ev: CalendarEvent) => {
      if (!map[date]) map[date] = [];
      map[date].push(ev);
    };

    // 자동 추천
    for (const r of recommendations) {
      push(r.date, {
        date: r.date, kind: "auto",
        title: r.title,
        color: "auto",
        raw: r,
      });
    }

    // 수동 일정
    for (const s of schedules) {
      push(s.date, {
        date: s.date, kind: "manual",
        title: s.title,
        subtitle: s.note,
        color: s.color,
        raw: s,
      });
    }

    // 비용집행
    for (const e of expenses) {
      if (e.expense_date) {
        push(e.expense_date, {
          date: e.expense_date, kind: "expense",
          title: `${CATEGORY_LABELS[e.category_type]} · ${e.title}`,
          subtitle: formatCurrency(e.amount),
          color: "expense",
          raw: e,
        });
      }
    }

    return map;
  }, [recommendations, schedules, expenses]);

  // ---------------------------------------------------------------------------
  // 수동 일정 저장 (project.metadata_.schedules PATCH)
  // ---------------------------------------------------------------------------

  const saveMutation = useMutation({
    mutationFn: async (newSchedules: ManualSchedule[]) => {
      const meta = (project as unknown as { metadata_?: Record<string, unknown> }).metadata_ ?? {};
      return projectsApi.update(project.id, {
        metadata: { ...meta, schedules: newSchedules },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", project.id] });
    },
  });

  const handleAddSchedule = useCallback(() => {
    if (!selectedDate || !newTitle.trim()) return;
    const newSchedule: ManualSchedule = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      date: selectedDate,
      title: newTitle.trim(),
      note: newNote.trim(),
      color: newColor,
    };
    saveMutation.mutate([...schedules, newSchedule]);
    setNewTitle("");
    setNewNote("");
    setNewColor("blue");
    setShowAddForm(false);
  }, [selectedDate, newTitle, newNote, newColor, schedules, saveMutation]);

  const handleDeleteSchedule = useCallback((id: string) => {
    saveMutation.mutate(schedules.filter((s) => s.id !== id));
  }, [schedules, saveMutation]);

  // ---------------------------------------------------------------------------
  // 달력 그리드 계산
  // ---------------------------------------------------------------------------

  const calendarDays = useMemo(() => {
    const firstDay = new Date(viewYear, viewMonth, 1).getDay(); // 0=Sun
    const daysInMonth = lastDayOfMonth(viewYear, viewMonth);
    const cells: (number | null)[] = Array(firstDay).fill(null);
    for (let d = 1; d <= daysInMonth; d++) cells.push(d);
    // 6행 맞추기
    while (cells.length % 7 !== 0) cells.push(null);
    return cells;
  }, [viewYear, viewMonth]);

  const monthLabel = new Date(viewYear, viewMonth, 1).toLocaleDateString("ko-KR", {
    year: "numeric", month: "long",
  });

  const prevMonth = () => {
    const d = new Date(viewYear, viewMonth - 1, 1);
    setViewYear(d.getFullYear()); setViewMonth(d.getMonth());
    setSelectedDate(null); setShowAddForm(false);
  };
  const nextMonth = () => {
    const d = new Date(viewYear, viewMonth + 1, 1);
    setViewYear(d.getFullYear()); setViewMonth(d.getMonth());
    setSelectedDate(null); setShowAddForm(false);
  };

  const todayStr = toYMD(today);

  const selectedEvents = selectedDate ? (eventMap[selectedDate] ?? []) : [];

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <CalendarDays className="w-4 h-4 text-blue-500" />
          일정 캘린더
          <div className="flex items-center gap-1 ml-1 text-xs font-normal text-gray-400">
            <span className="w-2 h-2 rounded-full bg-indigo-400 inline-block" /> 자동 추천
            <span className="w-2 h-2 rounded-full bg-blue-400 inline-block ml-2" /> 수동 일정
            <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block ml-2" /> 비용집행
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-4">
          {/* ── 달력 ── */}
          <div className="flex-1 min-w-0">
            {/* 월 이동 헤더 */}
            <div className="flex items-center justify-between mb-3">
              <Button variant="ghost" size="icon" className="w-7 h-7" onClick={prevMonth}>
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <span className="text-sm font-semibold text-gray-800">{monthLabel}</span>
              <Button variant="ghost" size="icon" className="w-7 h-7" onClick={nextMonth}>
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>

            {/* 요일 헤더 */}
            <div className="grid grid-cols-7 text-center text-xs text-gray-400 font-medium mb-1">
              {["일", "월", "화", "수", "목", "금", "토"].map((d) => (
                <div key={d} className="py-1">{d}</div>
              ))}
            </div>

            {/* 날짜 셀 */}
            <div className="grid grid-cols-7 gap-0.5">
              {calendarDays.map((day, idx) => {
                if (!day) return <div key={idx} />;
                const dateStr = `${viewYear}-${String(viewMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
                const events = eventMap[dateStr] ?? [];
                const isToday = dateStr === todayStr;
                const isSelected = dateStr === selectedDate;
                const isInProject =
                  project.period_start && project.period_end
                    ? dateStr >= project.period_start && dateStr <= project.period_end
                    : true;

                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setSelectedDate(dateStr === selectedDate ? null : dateStr);
                      setShowAddForm(false);
                    }}
                    className={[
                      "relative flex flex-col items-center p-1 rounded-md text-xs transition-colors min-h-[44px]",
                      isSelected ? "bg-blue-100 ring-1 ring-blue-400" : "hover:bg-gray-50",
                      isToday ? "font-bold text-blue-600" : "",
                      !isInProject ? "opacity-30" : "",
                      idx % 7 === 0 ? "text-red-500" : "",
                      idx % 7 === 6 ? "text-blue-500" : "",
                    ].join(" ")}
                  >
                    <span className={isToday ? "w-5 h-5 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs" : ""}>
                      {day}
                    </span>
                    {/* 이벤트 점 */}
                    {events.length > 0 && (
                      <div className="flex gap-0.5 flex-wrap justify-center mt-0.5">
                        {events.slice(0, 3).map((ev, i) => (
                          <span
                            key={i}
                            className={`w-1.5 h-1.5 rounded-full ${DOT_COLOR[ev.color] ?? "bg-gray-400"}`}
                          />
                        ))}
                        {events.length > 3 && (
                          <span className="text-[9px] text-gray-400">+{events.length - 3}</span>
                        )}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* ── 사이드 패널 ── */}
          <div className="w-56 shrink-0 border-l border-gray-100 pl-4 space-y-3">
            {selectedDate ? (
              <>
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-gray-800">
                    {parseYMD(selectedDate).toLocaleDateString("ko-KR", {
                      month: "long", day: "numeric",
                    })}
                  </p>
                  <button
                    type="button"
                    onClick={() => { setSelectedDate(null); setShowAddForm(false); }}
                    className="text-gray-300 hover:text-gray-500"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* 이벤트 목록 */}
                {selectedEvents.length === 0 ? (
                  <p className="text-xs text-gray-400">일정 없음</p>
                ) : (
                  <div className="space-y-2">
                    {selectedEvents.map((ev, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-2 text-xs group"
                      >
                        <span className={`mt-1 w-2 h-2 rounded-full shrink-0 ${DOT_COLOR[ev.color] ?? "bg-gray-400"}`} />
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-gray-800 truncate">{ev.title}</p>
                          {ev.subtitle && (
                            <p className="text-gray-400 truncate">{ev.subtitle}</p>
                          )}
                          {ev.kind === "auto" && (
                            <span className="inline-flex items-center gap-0.5 mt-0.5 text-indigo-500">
                              <Lightbulb className="w-2.5 h-2.5" /> 자동 추천
                            </span>
                          )}
                          {ev.kind === "expense" && (
                            <span className="inline-flex items-center gap-0.5 mt-0.5 text-emerald-500">
                              <ReceiptText className="w-2.5 h-2.5" /> 비용집행
                            </span>
                          )}
                          {ev.kind === "manual" && (
                            <button
                              type="button"
                              onClick={() => handleDeleteSchedule((ev.raw as ManualSchedule).id)}
                              className="text-red-300 hover:text-red-500 text-[10px] mt-0.5 hidden group-hover:block"
                            >
                              삭제
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* 일정 추가 버튼 */}
                {!showAddForm ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="w-full gap-1 text-xs mt-1"
                    onClick={() => setShowAddForm(true)}
                  >
                    <Plus className="w-3 h-3" />
                    일정 추가
                  </Button>
                ) : (
                  <div className="space-y-2 border border-blue-100 rounded-md p-2 bg-blue-50/40">
                    <div className="space-y-1">
                      <Label className="text-xs">제목 *</Label>
                      <Input
                        className="h-7 text-xs"
                        value={newTitle}
                        onChange={(e) => setNewTitle(e.target.value)}
                        placeholder="일정 제목"
                        autoFocus
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">메모</Label>
                      <Input
                        className="h-7 text-xs"
                        value={newNote}
                        onChange={(e) => setNewNote(e.target.value)}
                        placeholder="메모 (선택)"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">색상</Label>
                      <div className="flex gap-1.5">
                        {SCHEDULE_COLOR_OPTIONS.map((opt) => (
                          <button
                            key={opt.value}
                            type="button"
                            onClick={() => setNewColor(opt.value)}
                            className={[
                              "w-5 h-5 rounded-full transition-transform",
                              opt.cls,
                              newColor === opt.value ? "ring-2 ring-offset-1 ring-gray-500 scale-110" : "",
                            ].join(" ")}
                          />
                        ))}
                      </div>
                    </div>
                    <div className="flex gap-1.5">
                      <Button
                        type="button"
                        size="sm"
                        className="flex-1 h-7 text-xs"
                        disabled={!newTitle.trim() || saveMutation.isPending}
                        onClick={handleAddSchedule}
                      >
                        저장
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => { setShowAddForm(false); setNewTitle(""); setNewNote(""); }}
                      >
                        취소
                      </Button>
                    </div>
                  </div>
                )}
              </>
            ) : (
              /* 날짜 미선택 → 이달 이벤트 요약 */
              <div className="space-y-2">
                <p className="text-xs font-semibold text-gray-500">이달의 일정</p>
                {(() => {
                  const prefix = `${viewYear}-${String(viewMonth + 1).padStart(2, "0")}-`;
                  const thisMonthEvents = Object.entries(eventMap)
                    .filter(([d]) => d.startsWith(prefix))
                    .sort(([a], [b]) => a.localeCompare(b))
                    .flatMap(([, evs]) => evs);

                  if (thisMonthEvents.length === 0) {
                    return <p className="text-xs text-gray-400">이달 일정 없음</p>;
                  }
                  return thisMonthEvents.slice(0, 8).map((ev, i) => (
                    <div key={i} className="flex items-start gap-1.5 text-xs">
                      <span className={`mt-1 w-1.5 h-1.5 rounded-full shrink-0 ${DOT_COLOR[ev.color] ?? "bg-gray-400"}`} />
                      <div className="min-w-0">
                        <p className="text-gray-400 text-[10px]">{ev.date.slice(5)}</p>
                        <p className="text-gray-700 truncate">{ev.title}</p>
                      </div>
                    </div>
                  ));
                })()}
              </div>
            )}
          </div>
        </div>

        {/* 자동 추천 범례 */}
        <div className="border-t border-gray-100 pt-3">
          <p className="text-xs text-gray-400 flex items-center gap-1 mb-2">
            <Lightbulb className="w-3 h-3 text-indigo-400" />
            자동 추천 일정 (사업 기간·비목 기반)
          </p>
          <div className="flex flex-wrap gap-2">
            {recommendations.slice(0, 6).map((r, i) => (
              <button
                key={i}
                type="button"
                onClick={() => {
                  const d = parseYMD(r.date);
                  setViewYear(d.getFullYear());
                  setViewMonth(d.getMonth());
                  setSelectedDate(r.date);
                  setShowAddForm(false);
                }}
                className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition-colors"
              >
                <StickyNote className="w-3 h-3" />
                {r.title} <span className="text-indigo-400">{r.date.slice(5)}</span>
              </button>
            ))}
            {recommendations.length > 6 && (
              <span className="text-xs text-gray-400 self-center">
                외 {recommendations.length - 6}개…
              </span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
