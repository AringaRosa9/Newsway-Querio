"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}

export default function Pagination({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
}: PaginationProps) {
  if (totalPages <= 1) return null;

  const startItem = (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalItems);

  const getPageNumbers = (): (number | "...")[] => {
    const delta = 2;
    const pages: (number | "...")[] = [];
    const left = Math.max(2, currentPage - delta);
    const right = Math.min(totalPages - 1, currentPage + delta);

    pages.push(1);
    if (left > 2) pages.push("...");
    for (let i = left; i <= right; i++) pages.push(i);
    if (right < totalPages - 1) pages.push("...");
    if (totalPages > 1) pages.push(totalPages);

    return pages;
  };

  return (
    <nav
      className="flex flex-col sm:flex-row items-center justify-between gap-3 py-4"
      aria-label="分页导航"
    >
      <p className="text-sm text-gray-400 order-2 sm:order-1">
        第 {startItem}–{endItem} 条，共 {totalItems.toLocaleString("zh-CN")} 条
      </p>

      <div className="flex items-center gap-1 order-1 sm:order-2">
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
          aria-label="上一页"
          className="flex items-center gap-1 px-3 py-1.5 text-sm border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 hover:border-blue-300 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        >
          <ChevronLeft className="w-4 h-4" />
          上一页
        </button>

        <div className="flex items-center gap-1">
          {getPageNumbers().map((page, i) =>
            page === "..." ? (
              <span key={`ellipsis-${i}`} className="px-2 text-gray-400 text-sm">
                ...
              </span>
            ) : (
              <button
                key={page}
                onClick={() => onPageChange(page as number)}
                aria-label={`第 ${page} 页`}
                aria-current={page === currentPage ? "page" : undefined}
                className={`w-9 h-9 text-sm rounded-lg border transition-all ${
                  page === currentPage
                    ? "bg-gradient-to-r from-blue-600 to-indigo-600 text-white border-transparent font-semibold shadow-sm"
                    : "text-gray-600 border-gray-200 hover:bg-gray-50 hover:border-blue-300"
                }`}
              >
                {page}
              </button>
            )
          )}
        </div>

        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
          aria-label="下一页"
          className="flex items-center gap-1 px-3 py-1.5 text-sm border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 hover:border-blue-300 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        >
          下一页
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </nav>
  );
}
