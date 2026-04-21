"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { projectsApi } from "@/lib/api";
import { CATEGORY_LABELS } from "@/lib/constants";
import type { CategoryType } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import Link from "next/link";

interface BudgetRow {
  category_type: CategoryType;
  allocated_amount: number;
}

const ALL_CATEGORIES = Object.entries(CATEGORY_LABELS) as [CategoryType, string][];

export default function NewProjectPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [form, setForm] = useState({
    name: "",
    code: "",
    institution: "",
    principal_investigator: "",
    period_start: "",
    period_end: "",
    total_budget: "",
  });
  const [budgets, setBudgets] = useState<BudgetRow[]>([]);
  const [error, setError] = useState("");

  const mutation = useMutation({
    mutationFn: projectsApi.create,
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      router.push(`/projects/${project.id}`);
    },
    onError: (err: Error) => setError(err.message),
  });

  const addBudget = () => {
    const used = new Set(budgets.map((b) => b.category_type));
    const next = ALL_CATEGORIES.find(([k]) => !used.has(k));
    if (next) {
      setBudgets((prev) => [
        ...prev,
        { category_type: next[0], allocated_amount: 0 },
      ]);
    }
  };

  const removeBudget = (idx: number) =>
    setBudgets((prev) => prev.filter((_, i) => i !== idx));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    mutation.mutate({
      ...form,
      total_budget: Number(form.total_budget),
      budget_categories: budgets.filter((b) => b.allocated_amount > 0),
    });
  };

  return (
    <div className="max-w-2xl space-y-5">
      <div className="flex items-center gap-3">
        <Link href="/projects">
          <Button variant="ghost" size="icon" className="w-8 h-8">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <h2 className="text-xl font-bold text-gray-900">과제 등록</h2>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
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
                  onChange={(e) =>
                    setForm({ ...form, institution: e.target.value })
                  }
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
                    setForm({
                      ...form,
                      principal_investigator: e.target.value,
                    })
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
                  onChange={(e) =>
                    setForm({ ...form, period_start: e.target.value })
                  }
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="end">종료일 *</Label>
                <Input
                  id="end"
                  type="date"
                  required
                  value={form.period_end}
                  onChange={(e) =>
                    setForm({ ...form, period_end: e.target.value })
                  }
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
                  onChange={(e) =>
                    setForm({ ...form, total_budget: e.target.value })
                  }
                  placeholder="0"
                />
              </div>
            </div>
          </CardContent>
        </Card>

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
                비목을 추가하세요
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
                    className="w-40"
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

        {error && (
          <p className="text-sm text-red-600 bg-red-50 px-4 py-2 rounded-md">
            {error}
          </p>
        )}

        <div className="flex gap-3">
          <Button
            type="submit"
            disabled={mutation.isPending}
            className="flex-1"
          >
            {mutation.isPending ? "등록 중..." : "과제 등록"}
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
