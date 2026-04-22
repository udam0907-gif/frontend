"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { expensesApi, projectsApi } from "@/lib/api";
import { CATEGORY_LABELS } from "@/lib/constants";
import type { CategoryType } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function NewExpensePage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });

  const [form, setForm] = useState({
    project_id: "",
    category_type: "outsourcing" as CategoryType,
    title: "",
    description: "",
    amount: "",
    vendor_name: "",
    expense_date: "",
    usage_purpose: "",
    purchase_purpose: "",
    delivery_date: "",
    spec: "",
    quantity: "1",
    unit_price: "",
  });
  const [error, setError] = useState("");

  const mutation = useMutation({
    mutationFn: expensesApi.create,
    onSuccess: (expense) => {
      queryClient.invalidateQueries({ queryKey: ["expenses"] });
      router.push(`/expenses/${expense.id}`);
    },
    onError: (err: Error) => setError(err.message),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    const quantity = Number(form.quantity || 0);
    const unitPrice = Number(form.unit_price || 0);
    const lineAmount =
      quantity > 0 && unitPrice >= 0 ? quantity * unitPrice : undefined;

    mutation.mutate({
      project_id: form.project_id,
      category_type: form.category_type,
      title: form.title,
      description: form.description || undefined,
      amount: Number(form.amount),
      vendor_name: form.vendor_name || undefined,
      expense_date: form.expense_date || undefined,
      metadata: {
        usage_purpose: form.usage_purpose || undefined,
        purchase_purpose: form.purchase_purpose || undefined,
        delivery_date: form.delivery_date || undefined,
        spec: form.spec || undefined,
        quantity: quantity || undefined,
        unit_price: unitPrice || undefined,
        amount: lineAmount,
        line_items: [
          {
            item_name: form.title || undefined,
            spec: form.spec || undefined,
            quantity: quantity || undefined,
            unit_price: unitPrice || undefined,
            amount: lineAmount,
          },
        ],
      },
    });
  };

  return (
    <div className="max-w-2xl space-y-5">
      <div className="flex items-center gap-3">
        <Link href="/expenses">
          <Button variant="ghost" size="icon" className="w-8 h-8">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <h2 className="text-xl font-bold text-gray-900">비용 항목 추가</h2>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">항목 정보</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="project">과제 *</Label>
              <select
                id="project"
                required
                className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm"
                value={form.project_id}
                onChange={(e) =>
                  setForm({ ...form, project_id: e.target.value })
                }
              >
                <option value="">과제를 선택하세요</option>
                {(projects ?? []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.code})
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="category">비목 *</Label>
                <select
                  id="category"
                  required
                  className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm"
                  value={form.category_type}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      category_type: e.target.value as CategoryType,
                    })
                  }
                >
                  {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="amount">금액 *</Label>
                <Input
                  id="amount"
                  type="number"
                  required
                  min={1}
                  value={form.amount}
                  onChange={(e) => setForm({ ...form, amount: e.target.value })}
                  placeholder="0"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="title">항목명 *</Label>
              <Input
                id="title"
                required
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="예: 시약 구매, 분석 용역"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="vendor">업체명</Label>
                <Input
                  id="vendor"
                  value={form.vendor_name}
                  onChange={(e) =>
                    setForm({ ...form, vendor_name: e.target.value })
                  }
                  placeholder="거래 업체명"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="date">집행일</Label>
                <Input
                  id="date"
                  type="date"
                  value={form.expense_date}
                  onChange={(e) =>
                    setForm({ ...form, expense_date: e.target.value })
                  }
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="desc">설명</Label>
              <Textarea
                id="desc"
                rows={3}
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
                placeholder="집행 내용 요약"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="usage_purpose">사용 목적</Label>
                <Textarea
                  id="usage_purpose"
                  rows={2}
                  value={form.usage_purpose}
                  onChange={(e) =>
                    setForm({ ...form, usage_purpose: e.target.value })
                  }
                  placeholder="해당 품목의 사용 목적"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="purchase_purpose">구매 목적</Label>
                <Textarea
                  id="purchase_purpose"
                  rows={2}
                  value={form.purchase_purpose}
                  onChange={(e) =>
                    setForm({ ...form, purchase_purpose: e.target.value })
                  }
                  placeholder="구매 필요성과 집행 목적"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="delivery_date">납품일</Label>
              <Input
                id="delivery_date"
                type="date"
                value={form.delivery_date}
                onChange={(e) =>
                  setForm({ ...form, delivery_date: e.target.value })
                }
              />
            </div>

            <div className="space-y-3 rounded-lg border border-gray-200 p-4">
              <div>
                <p className="text-sm font-medium text-gray-900">품목 상세</p>
                <p className="text-xs text-gray-500 mt-1">
                  DOCX line item 및 품의서 context에 사용됩니다.
                </p>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="spec">규격</Label>
                <Input
                  id="spec"
                  value={form.spec}
                  onChange={(e) => setForm({ ...form, spec: e.target.value })}
                  placeholder="예: A4, 80g, 500매"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="quantity">수량</Label>
                  <Input
                    id="quantity"
                    type="number"
                    min={1}
                    value={form.quantity}
                    onChange={(e) =>
                      setForm({ ...form, quantity: e.target.value })
                    }
                    placeholder="1"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="unit_price">단가</Label>
                  <Input
                    id="unit_price"
                    type="number"
                    min={0}
                    value={form.unit_price}
                    onChange={(e) =>
                      setForm({ ...form, unit_price: e.target.value })
                    }
                    placeholder="0"
                  />
                </div>
              </div>
            </div>
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
            {mutation.isPending ? "등록 중..." : "비용 항목 등록"}
          </Button>
          <Link href="/expenses">
            <Button type="button" variant="outline">
              취소
            </Button>
          </Link>
        </div>
      </form>
    </div>
  );
}
