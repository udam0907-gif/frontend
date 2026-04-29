"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FolderOpen,
  ReceiptText,
  BookOpen,
  Download,
  Building2,
  ClipboardList,
  Printer,
  Settings,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";

const globalNavItems = [
  { href: "/", label: "전체 과제 대시보드", icon: LayoutDashboard, exact: true },
  { href: "/projects", label: "과제 목록", icon: FolderOpen, exact: true },
  { href: "/expenses", label: "전체 집행 현황", icon: ReceiptText, exact: false },
  { href: "/vendors", label: "업체 관리", icon: Building2, exact: false },
  { href: "/company-settings", label: "회사 설정", icon: Settings, exact: false },
  { href: "/export", label: "전체 출력문서", icon: Download, exact: false },
];

const projectNavDefs = [
  { suffix: "", label: "과제 전용 대시보드", icon: LayoutDashboard, exact: true },
  { suffix: "/expenses", label: "비용집행", icon: ReceiptText, exact: false },
  { suffix: "/details", label: "집행상세", icon: ClipboardList, exact: false },
  { suffix: "/docs", label: "문서 출력", icon: Printer, exact: false },
  { suffix: "/settings", label: "과제 설정", icon: Settings, exact: false },
];

export function Sidebar() {
  const pathname = usePathname();

  const projectIdMatch = pathname.match(/\/projects\/([^/]+)/);
  const rawId = projectIdMatch?.[1];
  const currentProjectId = rawId && rawId !== "new" ? rawId : null;

  const projectNavItems = currentProjectId
    ? projectNavDefs.map((def) => ({
        href: `/projects/${currentProjectId}${def.suffix}`,
        label: def.label,
        icon: def.icon,
        exact: def.exact,
      }))
    : null;

  function isActive(href: string, exact: boolean) {
    if (exact) return pathname === href;
    return pathname.startsWith(href);
  }

  return (
    <aside className="w-60 bg-white border-r border-gray-200 flex flex-col shrink-0">
      <div className="px-5 py-4 border-b border-gray-100">
        <h1 className="text-sm font-bold text-gray-900 leading-tight">
          정부지원사업
          <br />
          운영 시스템
        </h1>
      </div>

      <nav className="flex-1 py-2 overflow-y-auto">
        {/* 전체 관리 */}
        <p className="px-5 pt-4 pb-1 text-xs font-semibold text-gray-400 uppercase tracking-wide">
          전체 관리
        </p>
        {globalNavItems.map(({ href, label, icon: Icon, exact }) => {
          const active = isActive(href, exact);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-5 py-2.5 text-sm transition-colors",
                active
                  ? "bg-blue-50 text-blue-700 font-medium border-r-2 border-blue-600"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
              )}
            >
              <Icon className="w-4 h-4 shrink-0" />
              {label}
            </Link>
          );
        })}

        {/* 선택 과제 */}
        <p className="px-5 pt-5 pb-1 text-xs font-semibold text-gray-400 uppercase tracking-wide">
          선택 과제
        </p>

        {projectNavItems ? (
          projectNavItems.map(({ href, label, icon: Icon, exact }) => {
            const active = isActive(href, exact);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 px-5 py-2.5 text-sm transition-colors",
                  active
                    ? "bg-blue-50 text-blue-700 font-medium border-r-2 border-blue-600"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                )}
              >
                <Icon className="w-4 h-4 shrink-0" />
                {label}
              </Link>
            );
          })
        ) : (
          <div className="mx-3 my-2 px-3 py-3 rounded-md bg-gray-50 border border-dashed border-gray-200">
            <div className="flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-gray-300 mt-0.5 shrink-0" />
              <p className="text-xs text-gray-400 leading-relaxed">
                과제를 먼저 선택하세요.
              </p>
            </div>
            {projectNavDefs.map((def) => (
              <div
                key={def.suffix}
                className="flex items-center gap-3 px-0 py-1.5 mt-0.5 text-sm text-gray-300 cursor-not-allowed"
              >
                <def.icon className="w-4 h-4 shrink-0" />
                {def.label}
              </div>
            ))}
          </div>
        )}

        {/* RCMS */}
        <p className="px-5 pt-5 pb-1 text-xs font-semibold text-gray-400 uppercase tracking-wide">
          RCMS
        </p>
        <Link
          href="/rcms"
          className={cn(
            "flex items-center gap-3 px-5 py-2.5 text-sm transition-colors",
            pathname.startsWith("/rcms")
              ? "bg-blue-50 text-blue-700 font-medium border-r-2 border-blue-600"
              : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
          )}
        >
          <BookOpen className="w-4 h-4 shrink-0" />
          RCMS 질의응답
        </Link>
      </nav>

      <div className="px-5 py-3 border-t border-gray-100 text-xs text-gray-400">
        v1.0.0
      </div>
    </aside>
  );
}
