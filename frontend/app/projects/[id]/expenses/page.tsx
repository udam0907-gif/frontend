"use client";

import { useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { expensesApi, projectsApi, vendorsApi } from "@/lib/api";
import {
  CATEGORY_LABELS,
  EXPENSE_STATUS_COLORS,
  EXPENSE_STATUS_LABELS,
} from "@/lib/constants";
import type { CategoryType, ExpenseCreate } from "@/lib/types";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ReceiptText, Plus, Pencil, Trash2, X } from "lucide-react";
import { formatCurrency } from "@/lib/utils";

interface EditForm {
  title: string;
  amount: string;
  quantity: string;
  unitPrice: string;
  vendorId: string;
  vendorName: string;
  compareVendorId: string;
  expenseDate: string;
  note: string;
}

// 비교견적이 필요한 비목
const COMPARATIVE_CATEGORIES: CategoryType[] = ["materials", "outsourcing"];

const CATEGORY_OPTIONS: { value: CategoryType; label: string }[] = [
  { value: "materials", label: "재료비" },
  { value: "meeting", label: "회의비" },
  { value: "outsourcing", label: "외주가공비" },
  { value: "test_report", label: "시험성적비" },
  { value: "labor", label: "인건비" },
];

interface BaseForm {
  categoryType: CategoryType;
  expenseDate: string;
  vendorId: string;   // 주업체 ID
  vendorName: string; // 주업체명 (표시용)
  compareVendorId: string;   // 비교견적업체 ID
  compareVendorName: string; // 비교견적업체명 (표시용)
  amount: string;
  budgetItem: string;
  note: string;
  usagePurpose: string;
  purchasePurpose: string;
  deliveryDate: string;
  spec: string;
  quantity: string;
  unitPrice: string;
}

interface MeetingFields {
  attendeeCount: string;
  purpose: string;
  receiptFile: File | null;
}

interface MaterialsFields {
  productName: string;
}

interface OutsourcingFields {
  productName: string;
  workContent: string;
  specification: string;
}

interface TestReportFields {
  testInstitution: string;
  testItems: string;
  reportFile: File | null;
}

interface LaborFields {
  researcherName: string;
  paymentType: "cash" | "in_kind";
  participationMonths: string;
  participationRate: string;
}

const initialBase: BaseForm = {
  categoryType: "materials",
  expenseDate: "",
  vendorId: "",
  vendorName: "",
  compareVendorId: "",
  compareVendorName: "",
  amount: "",
  budgetItem: "",
  note: "",
  usagePurpose: "",
  purchasePurpose: "",
  deliveryDate: "",
  spec: "",
  quantity: "",
  unitPrice: "",
};

const initialMeeting: MeetingFields = { attendeeCount: "", purpose: "", receiptFile: null };
const initialMaterials: MaterialsFields = { productName: "" };
const initialOutsourcing: OutsourcingFields = { productName: "", workContent: "", specification: "" };
const initialTestReport: TestReportFields = { testInstitution: "", testItems: "", reportFile: null };
const initialLabor: LaborFields = { researcherName: "", paymentType: "cash", participationMonths: "", participationRate: "" };

export default function ProjectExpensesPage() {
  const params = useParams();
  const projectId = params.id as string;
  const queryClient = useQueryClient();

  const receiptRef = useRef<HTMLInputElement>(null);
  const reportRef = useRef<HTMLInputElement>(null);

  const [base, setBase] = useState<BaseForm>(initialBase);
  const [meeting, setMeeting] = useState<MeetingFields>(initialMeeting);
  const [materials, setMaterials] = useState<MaterialsFields>(initialMaterials);
  const [outsourcing, setOutsourcing] = useState<OutsourcingFields>(initialOutsourcing);
  const [testReport, setTestReport] = useState<TestReportFields>(initialTestReport);
  const [labor, setLabor] = useState<LaborFields>(initialLabor);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // 수정/삭제 상태
  const [editingExpense, setEditingExpense] = useState<import("@/lib/types").ExpenseItem | null>(null);
  const [editForm, setEditForm] = useState<EditForm>({
    title: "", amount: "", quantity: "", unitPrice: "",
    vendorId: "", vendorName: "", compareVendorId: "", expenseDate: "", note: "",
  });

  const { data: project } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => projectsApi.get(projectId),
    enabled: !!projectId,
  });

  const { data: vendors } = useQuery({
    queryKey: ["vendors", projectId],
    queryFn: () => vendorsApi.list(projectId),
    enabled: !!projectId,
  });

  const { data: expenses, isLoading: expLoading } = useQuery({
    queryKey: ["expenses", projectId],
    queryFn: () => expensesApi.list(projectId),
    enabled: !!projectId,
  });

  const needsComparative = COMPARATIVE_CATEGORIES.includes(base.categoryType);

  // 재료비: 수량 × 단가 자동계산
  const materialsAutoAmount =
    base.categoryType === "materials" && base.quantity && base.unitPrice
      ? Number(base.quantity) * Number(base.unitPrice)
      : null;

  // 비교견적 금액 = 원금액 × 1.1
  const compareAmount =
    needsComparative && base.compareVendorId
      ? (() => {
          const base_ =
            base.categoryType === "materials" && materialsAutoAmount !== null
              ? materialsAutoAmount
              : Number(base.amount);
          return base_ > 0 ? Math.ceil(base_ * 1.1) : null;
        })()
      : null;

  const buildInputData = (): Record<string, unknown> => {
    const base_: Record<string, unknown> = {};
    const quantity = Number(base.quantity) || 0;
    const unitPrice = Number(base.unitPrice) || 0;
    const lineAmount = quantity > 0 ? quantity * unitPrice : 0;
    const itemName =
      base.categoryType === "materials"
        ? materials.productName || base.budgetItem
        : base.categoryType === "outsourcing"
        ? outsourcing.productName || base.budgetItem
        : base.budgetItem;
    if (base.vendorId) base_["vendor_id"] = base.vendorId;
    if (base.compareVendorId) {
      base_["compare_vendor_id"] = base.compareVendorId;
      if (compareAmount) base_["compare_amount"] = compareAmount;
    }
    if (base.usagePurpose) base_["usage_purpose"] = base.usagePurpose;
    if (base.purchasePurpose) base_["purchase_purpose"] = base.purchasePurpose;
    if (base.deliveryDate) base_["delivery_date"] = base.deliveryDate;
    if (base.spec) base_["spec"] = base.spec;
    if (quantity > 0) base_["quantity"] = quantity;
    if (unitPrice > 0) base_["unit_price"] = unitPrice;
    if (lineAmount > 0) base_["amount"] = lineAmount;
    if (itemName || base.spec || quantity > 0 || unitPrice > 0) {
      base_["line_items"] = [
        {
          item_name: itemName || undefined,
          spec: base.spec || undefined,
          quantity: quantity || undefined,
          unit_price: unitPrice || undefined,
          amount: lineAmount || undefined,
        },
      ];
    }

    switch (base.categoryType) {
      case "meeting":
        return { ...base_, attendee_count: Number(meeting.attendeeCount) || 0, purpose: meeting.purpose };
      case "materials":
        return { ...base_, product_name: materials.productName };
      case "outsourcing":
        return { ...base_, product_name: outsourcing.productName, work_content: outsourcing.workContent, specification: outsourcing.specification };
      case "test_report":
        return { ...base_, test_institution: testReport.testInstitution, test_items: testReport.testItems };
      case "labor":
        return { ...base_, researcher_name: labor.researcherName, payment_type: labor.paymentType, participation_months: Number(labor.participationMonths) || 0, participation_rate: Number(labor.participationRate) || 0 };
      default:
        return base_;
    }
  };

  const createMutation = useMutation({
    mutationFn: (data: ExpenseCreate) => expensesApi.create(data),
    onSuccess: () => {
      setMessage({ type: "success", text: "비용집행이 등록되었습니다." });
      handleReset();
      queryClient.invalidateQueries({ queryKey: ["expenses", projectId] });
    },
    onError: (err: Error) => {
      setMessage({ type: "error", text: err.message });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<ExpenseCreate> }) =>
      expensesApi.update(id, data),
    onSuccess: () => {
      setMessage({ type: "success", text: "수정되었습니다." });
      setEditingExpense(null);
      queryClient.invalidateQueries({ queryKey: ["expenses", projectId] });
    },
    onError: (err: Error) => {
      setMessage({ type: "error", text: err.message });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => expensesApi.delete(id),
    onSuccess: () => {
      setMessage({ type: "success", text: "삭제되었습니다." });
      queryClient.invalidateQueries({ queryKey: ["expenses", projectId] });
    },
    onError: (err: Error) => {
      setMessage({ type: "error", text: err.message });
    },
  });

  const handleStartEdit = (expense: import("@/lib/types").ExpenseItem) => {
    const meta = expense.input_data ?? {};
    const isMaterials = expense.category_type === "materials";
    setEditingExpense(expense);
    setEditForm({
      title: expense.title,
      amount: isMaterials ? "" : String(expense.amount),
      quantity: isMaterials ? String(meta.quantity ?? "") : "",
      unitPrice: isMaterials ? String(meta.unit_price ?? "") : "",
      vendorId: (meta.vendor_id as string) ?? "",
      vendorName: expense.vendor_name ?? "",
      compareVendorId: (meta.compare_vendor_id as string) ?? "",
      expenseDate: expense.expense_date ?? "",
      note: expense.description ?? "",
    });
  };

  const handleSaveEdit = () => {
    if (!editingExpense) return;
    const isMaterials = editingExpense.category_type === "materials";
    const computedAmount = isMaterials
      ? Number(editForm.quantity) * Number(editForm.unitPrice)
      : Number(editForm.amount);
    if (!computedAmount || computedAmount <= 0) {
      setMessage({ type: "error", text: "금액을 입력하세요." });
      return;
    }
    const compareAmount = editForm.compareVendorId
      ? Math.ceil(computedAmount * 1.1)
      : undefined;
    const existingMeta = editingExpense.input_data ?? {};
    const newMeta: Record<string, unknown> = {
      ...existingMeta,
      ...(editForm.vendorId ? { vendor_id: editForm.vendorId } : {}),
      ...(editForm.compareVendorId
        ? { compare_vendor_id: editForm.compareVendorId, compare_amount: compareAmount }
        : { compare_vendor_id: undefined, compare_amount: undefined }),
      ...(isMaterials
        ? { quantity: Number(editForm.quantity), unit_price: Number(editForm.unitPrice) }
        : {}),
    };
    // undefined 키 제거
    Object.keys(newMeta).forEach(k => newMeta[k] === undefined && delete newMeta[k]);

    updateMutation.mutate({
      id: editingExpense.id,
      data: {
        title: editForm.title,
        amount: computedAmount,
        vendor_name: editForm.vendorName || undefined,
        expense_date: editForm.expenseDate || undefined,
        description: editForm.note || undefined,
        metadata: newMeta,
      },
    });
  };

  const handleDelete = (expense: import("@/lib/types").ExpenseItem) => {
    if (!window.confirm(`"${expense.title}" 비용집행 항목을 삭제하시겠습니까?\n생성된 문서도 함께 삭제됩니다.`)) return;
    deleteMutation.mutate(expense.id);
  };

  const handleSubmit = () => {
    if (!base.budgetItem.trim()) {
      setMessage({ type: "error", text: "예산항목을 입력하세요." });
      return;
    }
    const amount =
      base.categoryType === "materials" && materialsAutoAmount !== null
        ? materialsAutoAmount
        : Number(base.amount);
    if (!amount || amount <= 0) {
      setMessage({ type: "error", text: "금액을 입력하세요." });
      return;
    }

    const payload: ExpenseCreate = {
      project_id: projectId,
      category_type: base.categoryType,
      title: base.budgetItem,
      description: base.note || undefined,
      amount,
      vendor_name: base.vendorName || undefined,
      expense_date: base.expenseDate || undefined,
      metadata: buildInputData(),
    };

    createMutation.mutate(payload);
  };

  const handleReset = () => {
    setBase(initialBase);
    setMeeting(initialMeeting);
    setMaterials(initialMaterials);
    setOutsourcing(initialOutsourcing);
    setTestReport(initialTestReport);
    setLabor(initialLabor);
    if (receiptRef.current) receiptRef.current.value = "";
    if (reportRef.current) reportRef.current.value = "";
  };

  const handleVendorSelect = (vendorId: string) => {
    const v = (vendors ?? []).find((x) => x.id === vendorId);
    setBase((f) => ({
      ...f,
      vendorId: vendorId,
      vendorName: v?.name ?? "",
      // 비교견적업체가 주업체와 같으면 초기화
      compareVendorId: f.compareVendorId === vendorId ? "" : f.compareVendorId,
      compareVendorName: f.compareVendorId === vendorId ? "" : f.compareVendorName,
    }));
  };

  const handleCompareVendorSelect = (vendorId: string) => {
    const v = (vendors ?? []).find((x) => x.id === vendorId);
    setBase((f) => ({ ...f, compareVendorId: vendorId, compareVendorName: v?.name ?? "" }));
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-900">비용집행 등록</h2>
        <p className="text-sm text-gray-500 mt-0.5">
          {project?.name ?? "과제"} · 비용 항목을 등록합니다
        </p>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Plus className="w-4 h-4" />
            비용 항목 입력
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          {message && (
            <div
              className={`p-3 rounded-lg text-sm ${
                message.type === "success" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
              }`}
            >
              {message.text}
            </div>
          )}

          {/* 공통 입력 */}
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">공통 정보</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>과제명</Label>
                <Input value={project?.name ?? "로딩 중..."} readOnly className="bg-gray-50" />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="categoryType">집행유형 *</Label>
                <select
                  id="categoryType"
                  className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm"
                  value={base.categoryType}
                  onChange={(e) =>
                    setBase((f) => ({
                      ...f,
                      categoryType: e.target.value as CategoryType,
                      compareVendorId: "",
                      compareVendorName: "",
                    }))
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
                <Label htmlFor="expenseDate">집행일자</Label>
                <Input
                  id="expenseDate"
                  type="date"
                  value={base.expenseDate}
                  onChange={(e) => setBase((f) => ({ ...f, expenseDate: e.target.value }))}
                />
              </div>

              {/* 주업체 선택 */}
              <div className="space-y-1.5">
                <Label htmlFor="vendorId">업체명</Label>
                {(vendors ?? []).length > 0 ? (
                  <select
                    id="vendorId"
                    className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm"
                    value={base.vendorId}
                    onChange={(e) => handleVendorSelect(e.target.value)}
                  >
                    <option value="">-- 업체 선택 --</option>
                    {(vendors ?? []).map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.name} ({v.vendor_category})
                      </option>
                    ))}
                  </select>
                ) : (
                  <Input
                    id="vendorName"
                    placeholder="업체명 입력 (업체 탭에서 먼저 등록하세요)"
                    value={base.vendorName}
                    onChange={(e) => setBase((f) => ({ ...f, vendorName: e.target.value }))}
                  />
                )}
              </div>

              {/* 비교견적업체 선택 — 비목이 해당될 때만 표시 */}
              {needsComparative && (
                <div className="space-y-1.5 sm:col-span-2">
                  <Label htmlFor="compareVendorId">
                    비교견적업체{" "}
                    <span className="text-xs font-normal text-gray-400">(견적금액 자동 +10%)</span>
                  </Label>
                  {(vendors ?? []).length > 0 ? (
                    <select
                      id="compareVendorId"
                      className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm"
                      value={base.compareVendorId}
                      onChange={(e) => handleCompareVendorSelect(e.target.value)}
                    >
                      <option value="">-- 비교견적업체 선택 (선택사항) --</option>
                      {(vendors ?? [])
                        .filter((v) => v.id !== base.vendorId)
                        .map((v) => (
                          <option key={v.id} value={v.id}>
                            {v.name} ({v.vendor_category})
                          </option>
                        ))}
                    </select>
                  ) : (
                    <p className="text-xs text-gray-400 py-2">
                      업체 탭에서 비교견적업체를 먼저 등록하세요.
                    </p>
                  )}
                  {compareAmount !== null && (
                    <p className="text-xs text-blue-600 font-medium">
                      비교견적 자동 금액: {formatCurrency(compareAmount)} (원금액 × 1.1)
                    </p>
                  )}
                </div>
              )}

              <div className="space-y-1.5">
                <Label htmlFor="budgetItem">예산항목 *</Label>
                <Input
                  id="budgetItem"
                  placeholder="예: AI 칩 구매"
                  value={base.budgetItem}
                  onChange={(e) => setBase((f) => ({ ...f, budgetItem: e.target.value }))}
                />
              </div>

              {base.categoryType !== "materials" && (
                <div className="space-y-1.5">
                  <Label htmlFor="amount">금액 (원) *</Label>
                  <Input
                    id="amount"
                    type="number"
                    placeholder="0"
                    value={base.amount}
                    onChange={(e) => setBase((f) => ({ ...f, amount: e.target.value }))}
                  />
                </div>
              )}

              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor="note">비고</Label>
                <Textarea
                  id="note"
                  placeholder="비고 사항 입력"
                  rows={2}
                  value={base.note}
                  onChange={(e) => setBase((f) => ({ ...f, note: e.target.value }))}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="usagePurpose">사용 목적</Label>
                <Textarea
                  id="usagePurpose"
                  rows={2}
                  value={base.usagePurpose}
                  onChange={(e) => setBase((f) => ({ ...f, usagePurpose: e.target.value }))}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="purchasePurpose">구매 목적</Label>
                <Textarea
                  id="purchasePurpose"
                  rows={2}
                  value={base.purchasePurpose}
                  onChange={(e) => setBase((f) => ({ ...f, purchasePurpose: e.target.value }))}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="deliveryDate">납품일</Label>
                <Input
                  id="deliveryDate"
                  type="date"
                  value={base.deliveryDate}
                  onChange={(e) => setBase((f) => ({ ...f, deliveryDate: e.target.value }))}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="spec">규격</Label>
                <Input
                  id="spec"
                  value={base.spec}
                  onChange={(e) => setBase((f) => ({ ...f, spec: e.target.value }))}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="quantity">수량</Label>
                <Input
                  id="quantity"
                  type="number"
                  min={0}
                  value={base.quantity}
                  onChange={(e) => setBase((f) => ({ ...f, quantity: e.target.value }))}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="unitPrice">단가</Label>
                <Input
                  id="unitPrice"
                  type="number"
                  min={0}
                  value={base.unitPrice}
                  onChange={(e) => setBase((f) => ({ ...f, unitPrice: e.target.value }))}
                />
              </div>
            </div>
          </div>

          {/* 비목별 추가 입력 */}
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
              {CATEGORY_LABELS[base.categoryType]} 추가 정보
            </p>

            {base.categoryType === "meeting" && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label>참석자 수</Label>
                  <Input
                    type="number"
                    placeholder="0"
                    value={meeting.attendeeCount}
                    onChange={(e) => setMeeting((f) => ({ ...f, attendeeCount: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>사용목적</Label>
                  <Input
                    placeholder="예: 월례 연구 회의"
                    value={meeting.purpose}
                    onChange={(e) => setMeeting((f) => ({ ...f, purpose: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5 sm:col-span-2">
                  <Label>영수증 업로드</Label>
                  <input
                    ref={receiptRef}
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png"
                    className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm file:mr-3 file:border-0 file:bg-blue-50 file:text-blue-700 file:text-xs file:font-medium file:px-2 file:py-1 file:rounded"
                    onChange={(e) => setMeeting((f) => ({ ...f, receiptFile: e.target.files?.[0] ?? null }))}
                  />
                </div>
              </div>
            )}

            {base.categoryType === "materials" && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="space-y-1.5 sm:col-span-3">
                  <Label>상품명</Label>
                  <Input
                    placeholder="예: NVIDIA A100 GPU"
                    value={materials.productName}
                    onChange={(e) => setMaterials((f) => ({ ...f, productName: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>수량</Label>
                  <Input
                    type="number"
                    placeholder="0"
                    value={base.quantity}
                    onChange={(e) => setBase((f) => ({ ...f, quantity: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>단가 (원)</Label>
                  <Input
                    type="number"
                    placeholder="0"
                    value={base.unitPrice}
                    onChange={(e) => setBase((f) => ({ ...f, unitPrice: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>금액 (자동계산)</Label>
                  <Input
                    readOnly
                    className="bg-gray-50 font-semibold"
                    value={materialsAutoAmount !== null ? formatCurrency(materialsAutoAmount) : ""}
                  />
                </div>
              </div>
            )}

            {base.categoryType === "outsourcing" && (
              <div className="grid grid-cols-1 gap-4">
                <div className="space-y-1.5">
                  <Label>상품명</Label>
                  <Input
                    placeholder="예: PCB 기판 제작"
                    value={outsourcing.productName}
                    onChange={(e) => setOutsourcing((f) => ({ ...f, productName: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>작업내용</Label>
                  <Input
                    placeholder="예: 시제품 PCB 설계 및 제작"
                    value={outsourcing.workContent}
                    onChange={(e) => setOutsourcing((f) => ({ ...f, workContent: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>산출내역 / 규격</Label>
                  <Input
                    placeholder="예: 100mm × 80mm, 4층, 수량 10매"
                    value={outsourcing.specification}
                    onChange={(e) => setOutsourcing((f) => ({ ...f, specification: e.target.value }))}
                  />
                </div>
              </div>
            )}

            {base.categoryType === "test_report" && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label>시험기관명</Label>
                  <Input
                    placeholder="예: 한국산업기술시험원"
                    value={testReport.testInstitution}
                    onChange={(e) => setTestReport((f) => ({ ...f, testInstitution: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>시험항목</Label>
                  <Input
                    placeholder="예: EMC, 안전성 시험"
                    value={testReport.testItems}
                    onChange={(e) => setTestReport((f) => ({ ...f, testItems: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5 sm:col-span-2">
                  <Label>성적서 업로드</Label>
                  <input
                    ref={reportRef}
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png"
                    className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm file:mr-3 file:border-0 file:bg-blue-50 file:text-blue-700 file:text-xs file:font-medium file:px-2 file:py-1 file:rounded"
                    onChange={(e) => setTestReport((f) => ({ ...f, reportFile: e.target.files?.[0] ?? null }))}
                  />
                </div>
              </div>
            )}

            {base.categoryType === "labor" && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label>연구원명</Label>
                  <Input
                    placeholder="예: 홍길동"
                    value={labor.researcherName}
                    onChange={(e) => setLabor((f) => ({ ...f, researcherName: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>지급구분</Label>
                  <select
                    className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm"
                    value={labor.paymentType}
                    onChange={(e) =>
                      setLabor((f) => ({ ...f, paymentType: e.target.value as "cash" | "in_kind" }))
                    }
                  >
                    <option value="cash">현금</option>
                    <option value="in_kind">현물</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <Label>참여기간 (개월)</Label>
                  <Input
                    type="number"
                    placeholder="0"
                    value={labor.participationMonths}
                    onChange={(e) => setLabor((f) => ({ ...f, participationMonths: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>참여율 (%)</Label>
                  <Input
                    type="number"
                    placeholder="0"
                    min={0}
                    max={100}
                    value={labor.participationRate}
                    onChange={(e) => setLabor((f) => ({ ...f, participationRate: e.target.value }))}
                  />
                </div>
              </div>
            )}
          </div>

          <div className="flex gap-2 pt-2">
            <Button onClick={handleSubmit} disabled={createMutation.isPending}>
              {createMutation.isPending ? "저장 중..." : "저장"}
            </Button>
            <Button variant="outline" onClick={handleReset}>
              초기화
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 비용집행 목록 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <ReceiptText className="w-4 h-4" />
            이 과제 비용집행 목록
          </CardTitle>
        </CardHeader>
        <CardContent>
          {expLoading ? (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : (expenses ?? []).length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-8">등록된 비용집행이 없습니다</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100">
                    <th className="text-left py-2.5 px-2 text-xs font-semibold text-gray-500">유형</th>
                    <th className="text-left py-2.5 px-2 text-xs font-semibold text-gray-500">항목명</th>
                    <th className="text-left py-2.5 px-2 text-xs font-semibold text-gray-500">업체</th>
                    <th className="text-right py-2.5 px-2 text-xs font-semibold text-gray-500">금액</th>
                    <th className="text-left py-2.5 px-2 text-xs font-semibold text-gray-500">상태</th>
                    <th className="py-2.5 px-2 text-xs font-semibold text-gray-500">액션</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {(expenses ?? []).map((expense) => (
                    <tr key={expense.id} className={`hover:bg-gray-50 ${editingExpense?.id === expense.id ? "bg-blue-50" : ""}`}>
                      <td className="py-3 px-2">
                        <span className="text-xs font-medium px-2 py-0.5 bg-gray-100 text-gray-600 rounded">
                          {CATEGORY_LABELS[expense.category_type]}
                        </span>
                      </td>
                      <td className="py-3 px-2 font-medium text-gray-800">{expense.title}</td>
                      <td className="py-3 px-2 text-gray-500 text-xs">{expense.vendor_name ?? "-"}</td>
                      <td className="py-3 px-2 text-right text-gray-700 font-semibold">
                        {formatCurrency(expense.amount)}
                      </td>
                      <td className="py-3 px-2">
                        <Badge className={`text-xs ${EXPENSE_STATUS_COLORS[expense.status]}`}>
                          {EXPENSE_STATUS_LABELS[expense.status]}
                        </Badge>
                      </td>
                      <td className="py-3 px-2">
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => editingExpense?.id === expense.id ? setEditingExpense(null) : handleStartEdit(expense)}
                            className="p-1 rounded hover:bg-blue-100 text-blue-600"
                            title="수정"
                          >
                            {editingExpense?.id === expense.id ? <X className="w-3.5 h-3.5" /> : <Pencil className="w-3.5 h-3.5" />}
                          </button>
                          <button
                            onClick={() => handleDelete(expense)}
                            disabled={deleteMutation.isPending}
                            className="p-1 rounded hover:bg-red-100 text-red-500"
                            title="삭제"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* 인라인 수정 패널 */}
              {editingExpense && (
                <div className="mt-4 p-4 border border-blue-200 rounded-lg bg-blue-50 space-y-4">
                  <p className="text-sm font-semibold text-blue-800">수정: {editingExpense.title}</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="space-y-1 sm:col-span-2">
                      <Label className="text-xs">예산항목명</Label>
                      <Input value={editForm.title} onChange={e => setEditForm(f => ({ ...f, title: e.target.value }))} />
                    </div>

                    {editingExpense.category_type === "materials" ? (
                      <>
                        <div className="space-y-1">
                          <Label className="text-xs">수량</Label>
                          <Input type="number" value={editForm.quantity} onChange={e => setEditForm(f => ({ ...f, quantity: e.target.value }))} />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">단가 (원)</Label>
                          <Input type="number" value={editForm.unitPrice} onChange={e => setEditForm(f => ({ ...f, unitPrice: e.target.value }))} />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">금액 (자동계산)</Label>
                          <Input readOnly className="bg-white" value={
                            editForm.quantity && editForm.unitPrice
                              ? formatCurrency(Number(editForm.quantity) * Number(editForm.unitPrice))
                              : ""
                          } />
                        </div>
                      </>
                    ) : (
                      <div className="space-y-1">
                        <Label className="text-xs">금액 (원)</Label>
                        <Input type="number" value={editForm.amount} onChange={e => setEditForm(f => ({ ...f, amount: e.target.value }))} />
                      </div>
                    )}

                    <div className="space-y-1">
                      <Label className="text-xs">집행일자</Label>
                      <Input type="date" value={editForm.expenseDate} onChange={e => setEditForm(f => ({ ...f, expenseDate: e.target.value }))} />
                    </div>

                    <div className="space-y-1">
                      <Label className="text-xs">주업체</Label>
                      <select
                        className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm"
                        value={editForm.vendorId}
                        onChange={e => {
                          const v = (vendors ?? []).find(x => x.id === e.target.value);
                          setEditForm(f => ({ ...f, vendorId: e.target.value, vendorName: v?.name ?? "" }));
                        }}
                      >
                        <option value="">-- 업체 선택 --</option>
                        {(vendors ?? []).map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
                      </select>
                    </div>

                    {COMPARATIVE_CATEGORIES.includes(editingExpense.category_type) && (
                      <div className="space-y-1 sm:col-span-2">
                        <Label className="text-xs">
                          비교견적업체{" "}
                          <span className="font-normal text-gray-400">(선택 시 금액 × 1.1 자동계산)</span>
                        </Label>
                        <select
                          className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm"
                          value={editForm.compareVendorId}
                          onChange={e => setEditForm(f => ({ ...f, compareVendorId: e.target.value }))}
                        >
                          <option value="">-- 비교견적업체 선택 --</option>
                          {(vendors ?? []).filter(v => v.id !== editForm.vendorId).map(v => (
                            <option key={v.id} value={v.id}>{v.name}</option>
                          ))}
                        </select>
                        {editForm.compareVendorId && (() => {
                          const baseAmt = editingExpense.category_type === "materials"
                            ? Number(editForm.quantity) * Number(editForm.unitPrice)
                            : Number(editForm.amount);
                          return baseAmt > 0 ? (
                            <p className="text-xs text-blue-600">비교견적 금액: {formatCurrency(Math.ceil(baseAmt * 1.1))}</p>
                          ) : null;
                        })()}
                      </div>
                    )}

                    <div className="space-y-1 sm:col-span-2">
                      <Label className="text-xs">비고</Label>
                      <Input value={editForm.note} onChange={e => setEditForm(f => ({ ...f, note: e.target.value }))} />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={handleSaveEdit} disabled={updateMutation.isPending}>
                      {updateMutation.isPending ? "저장 중..." : "저장"}
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setEditingExpense(null)}>취소</Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
