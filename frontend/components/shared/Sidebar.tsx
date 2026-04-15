"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FolderOpen,
  FileText,
  ReceiptText,
  BookOpen,
  Download,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "대시보드", icon: LayoutDashboard },
  { href: "/projects", label: "프로젝트", icon: FolderOpen },
  { href: "/templates", label: "템플릿 관리", icon: FileText },
  { href: "/expenses", label: "비용 집행", icon: ReceiptText },
  { href: "/rcms", label: "RCMS Q&A", icon: BookOpen },
  { href: "/export", label: "내보내기", icon: Download },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 bg-white border-r border-gray-200 flex flex-col shrink-0">
      <div className="px-5 py-4 border-b border-gray-100">
        <h1 className="text-sm font-bold text-gray-900 leading-tight">
          R&D 비용<br />집행 관리
        </h1>
      </div>
      <nav className="flex-1 py-3">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
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
      </nav>
      <div className="px-5 py-3 border-t border-gray-100 text-xs text-gray-400">
        v1.0.0
      </div>
    </aside>
  );
}
