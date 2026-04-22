"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { companySettingsApi } from "@/lib/api";
import type {
  CompanySettingsUpdate,
  CompanySettingsUploadType,
} from "@/lib/types";

const DEFAULT_COMPANY_ID = "default";

const emptyForm: CompanySettingsUpdate = {
  company_id: DEFAULT_COMPANY_ID,
  company_name: "",
  company_registration_number: "",
  representative_name: "",
  address: "",
  business_type: "",
  business_item: "",
  phone: "",
  fax: "",
  email: "",
  default_manager_name: "",
  seal_image_path: "",
};

const fileLabels: Record<CompanySettingsUploadType, string> = {
  business_registration: "Business Registration",
  bank_copy: "Bank Copy",
  quote_template: "Quote Template",
  transaction_statement_template: "Transaction Statement Template",
  seal_image: "Seal Image",
};

export default function CompanySettingsPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<CompanySettingsUpdate>(emptyForm);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [files, setFiles] = useState<Partial<Record<CompanySettingsUploadType, File | null>>>({});

  const { data, isLoading } = useQuery({
    queryKey: ["company-settings", DEFAULT_COMPANY_ID],
    queryFn: () => companySettingsApi.get(DEFAULT_COMPANY_ID),
  });

  useEffect(() => {
    if (!data) return;
    setForm({
      company_id: data.company_id || DEFAULT_COMPANY_ID,
      company_name: data.company_name ?? "",
      company_registration_number: data.company_registration_number ?? "",
      representative_name: data.representative_name ?? "",
      address: data.address ?? "",
      business_type: data.business_type ?? "",
      business_item: data.business_item ?? "",
      phone: data.phone ?? "",
      fax: data.fax ?? "",
      email: data.email ?? "",
      default_manager_name: data.default_manager_name ?? "",
      seal_image_path: data.seal_image_path ?? "",
      company_business_registration_path: data.company_business_registration_path ?? "",
      company_bank_copy_path: data.company_bank_copy_path ?? "",
      company_quote_template_path: data.company_quote_template_path ?? "",
      company_transaction_statement_template_path: data.company_transaction_statement_template_path ?? "",
    });
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: (payload: CompanySettingsUpdate) => companySettingsApi.update(payload),
    onSuccess: () => {
      setMessage({ type: "success", text: "Company settings saved." });
      queryClient.invalidateQueries({ queryKey: ["company-settings", DEFAULT_COMPANY_ID] });
    },
    onError: (err: Error) => setMessage({ type: "error", text: err.message }),
  });

  const uploadMutation = useMutation({
    mutationFn: ({ fileType, file }: { fileType: CompanySettingsUploadType; file: File }) =>
      companySettingsApi.uploadFile(DEFAULT_COMPANY_ID, fileType, file),
    onSuccess: () => {
      setMessage({ type: "success", text: "Default company file uploaded." });
      setFiles({});
      queryClient.invalidateQueries({ queryKey: ["company-settings", DEFAULT_COMPANY_ID] });
    },
    onError: (err: Error) => setMessage({ type: "error", text: err.message }),
  });

  const registrationState = useMemo(
    () => [
      { label: "Business Registration", registered: !!data?.company_business_registration_path },
      { label: "Bank Copy", registered: !!data?.company_bank_copy_path },
      { label: "Quote Template", registered: !!data?.company_quote_template_path },
      { label: "Transaction Statement Template", registered: !!data?.company_transaction_statement_template_path },
      { label: "Seal Image", registered: !!data?.seal_image_path },
    ],
    [data]
  );

  const handleSave = () => {
    saveMutation.mutate(form);
  };

  const handleUpload = (fileType: CompanySettingsUploadType) => {
    const file = files[fileType];
    if (!file) {
      setMessage({ type: "error", text: `Select a file for ${fileLabels[fileType]}.` });
      return;
    }
    uploadMutation.mutate({ fileType, file });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-900">Company Settings</h2>
        <p className="text-sm text-gray-500 mt-0.5">
          Manage the top-level company profile and default files used for document output.
        </p>
      </div>

      {message && (
        <div
          className={`rounded-lg px-4 py-3 text-sm ${
            message.type === "success" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
          }`}
        >
          {message.text}
        </div>
      )}

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Company Profile</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="company_name">Company Name</Label>
            <Input id="company_name" value={form.company_name ?? ""} onChange={(e) => setForm((prev) => ({ ...prev, company_name: e.target.value }))} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="company_registration_number">Registration Number</Label>
            <Input id="company_registration_number" value={form.company_registration_number ?? ""} onChange={(e) => setForm((prev) => ({ ...prev, company_registration_number: e.target.value }))} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="representative_name">Representative</Label>
            <Input id="representative_name" value={form.representative_name ?? ""} onChange={(e) => setForm((prev) => ({ ...prev, representative_name: e.target.value }))} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="default_manager_name">Default Manager</Label>
            <Input id="default_manager_name" value={form.default_manager_name ?? ""} onChange={(e) => setForm((prev) => ({ ...prev, default_manager_name: e.target.value }))} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="address">Address</Label>
            <Input id="address" value={form.address ?? ""} onChange={(e) => setForm((prev) => ({ ...prev, address: e.target.value }))} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="business_type">Business Type</Label>
            <Input id="business_type" value={form.business_type ?? ""} onChange={(e) => setForm((prev) => ({ ...prev, business_type: e.target.value }))} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="business_item">Business Item</Label>
            <Input id="business_item" value={form.business_item ?? ""} onChange={(e) => setForm((prev) => ({ ...prev, business_item: e.target.value }))} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="phone">Phone</Label>
            <Input id="phone" value={form.phone ?? ""} onChange={(e) => setForm((prev) => ({ ...prev, phone: e.target.value }))} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="fax">Fax</Label>
            <Input id="fax" value={form.fax ?? ""} onChange={(e) => setForm((prev) => ({ ...prev, fax: e.target.value }))} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" value={form.email ?? ""} onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))} />
          </div>
          <div className="sm:col-span-2 flex justify-end">
            <Button onClick={handleSave} disabled={saveMutation.isPending || isLoading}>
              {saveMutation.isPending ? "Saving..." : "Save"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Default Company Files</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {registrationState.map((item) => (
              <div key={item.label} className="rounded-lg border border-gray-200 px-4 py-3 flex items-center justify-between">
                <span className="text-sm text-gray-700">{item.label}</span>
                <span className={`text-xs font-medium ${item.registered ? "text-green-600" : "text-gray-400"}`}>
                  {item.registered ? "Registered" : "Not registered"}
                </span>
              </div>
            ))}
          </div>

          {(Object.keys(fileLabels) as CompanySettingsUploadType[]).map((fileType) => (
            <div key={fileType} className="grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-3 items-end">
              <div className="space-y-1.5">
                <Label htmlFor={fileType}>{fileLabels[fileType]}</Label>
                <input
                  id={fileType}
                  type="file"
                  accept={fileType === "quote_template" || fileType === "transaction_statement_template" ? ".docx" : ".pdf,.jpg,.jpeg,.png"}
                  className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm file:mr-3 file:border-0 file:bg-blue-50 file:text-blue-700 file:text-xs file:font-medium file:px-2 file:py-1 file:rounded"
                  onChange={(e) => setFiles((prev) => ({ ...prev, [fileType]: e.target.files?.[0] ?? null }))}
                />
              </div>
              <Button variant="outline" onClick={() => handleUpload(fileType)} disabled={uploadMutation.isPending}>
                Upload
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
