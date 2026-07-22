"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, AlertCircle, SearchX, Clock } from "lucide-react";
import Navbar from "@/components/Navbar";
import SearchBox from "@/components/SearchBox";
import SummaryCard from "@/components/SummaryCard";
import ResultCard from "@/components/ResultCard";
import FilterPanel, { Filters } from "@/components/FilterPanel";
import Pagination from "@/components/Pagination";
import { trackSearch } from "@/lib/analytics";

const PAGE_SIZE = 20;

interface Citation {
  index: number;
  title: string;
  source: string;
  url: string;
}

interface Summary {
  summary_text: string;
  citations: Citation[];
}

interface Article {
  id: string;
  title: string;
  content: string;
  source: string;
  url: string;
  published_at: string;
  category?: string;
  sentiment?: string;
  entities?: string[];
  score?: number;
}

interface SearchResponse {
  query: string;
  parsed_query?: object;
  summary?: Summary;
  results: Article[];
  total: number;
  page: number;
  page_size: number;
  took_ms: number;
}

function buildSearchUrl(q: string, filters: Filters, page: number): string {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (filters.time_from) params.set("time_from", filters.time_from);
  if (filters.time_to) params.set("time_to", filters.time_to);
  if (filters.category) params.set("category", filters.category);
  if (filters.sentiment) params.set("sentiment", filters.sentiment);
  if (filters.source) params.set("source", filters.source);
  if (filters.language) params.set("language", filters.language);
  params.set("page", String(page));
  params.set("page_size", String(PAGE_SIZE));
  return `/api/search?${params.toString()}`;
}

function ResultSkeleton() {
  return (
    <div className="card rounded-2xl p-5 space-y-3">
      <div className="skeleton h-5 w-4/5 rounded" />
      <div className="flex gap-2">
        <div className="skeleton h-4 w-20 rounded-full" />
        <div className="skeleton h-4 w-16 rounded-full" />
        <div className="skeleton h-4 w-24 rounded-full" />
      </div>
      <div className="space-y-2">
        <div className="skeleton h-3 w-full rounded" />
        <div className="skeleton h-3 w-5/6 rounded" />
        <div className="skeleton h-3 w-3/4 rounded" />
      </div>
    </div>
  );
}

function SearchPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const queryParam = searchParams.get("q") ?? "";
  const pageParam = parseInt(searchParams.get("page") ?? "1", 10);
  const filtersFromUrl: Filters = {
    time_from: searchParams.get("time_from") ?? undefined,
    time_to: searchParams.get("time_to") ?? undefined,
    category: searchParams.get("category") ?? undefined,
    sentiment: searchParams.get("sentiment") ?? undefined,
    source: searchParams.get("source") ?? undefined,
    language: searchParams.get("language") ?? undefined,
  };

  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchResults = useCallback(
    async (q: string, filters: Filters, page: number) => {
      setLoading(true);
      setError(null);
      setData(null);
      try {
        const url = buildSearchUrl(q, filters, page);
        const res = await fetch(url);
        if (!res.ok) {
          const text = await res.text();
          throw new Error(`服务器错误 ${res.status}: ${text.slice(0, 100)}`);
        }
        const json: SearchResponse = await res.json();
        setData(json);
        trackSearch(q, json.total, json.took_ms);
      } catch (e) {
        setError(e instanceof Error ? e.message : "未知错误，请稍后重试");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    fetchResults(queryParam, filtersFromUrl, pageParam);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams.toString()]);

  const pushParams = useCallback(
    (q: string, filters: Filters, page: number) => {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (filters.time_from) params.set("time_from", filters.time_from);
      if (filters.time_to) params.set("time_to", filters.time_to);
      if (filters.category) params.set("category", filters.category);
      if (filters.sentiment) params.set("sentiment", filters.sentiment);
      if (filters.source) params.set("source", filters.source);
      if (filters.language) params.set("language", filters.language);
      if (page > 1) params.set("page", String(page));
      router.push(`/search?${params.toString()}`);
    },
    [router]
  );

  const handleSearch = (q: string) => pushParams(q, filtersFromUrl, 1);
  const handleFilterChange = (filters: Filters) => pushParams(queryParam, filters, 1);
  const handlePageChange = (page: number) => {
    pushParams(queryParam, filtersFromUrl, page);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <div className="min-h-screen bg-gray-50/50">
      {/* Navbar with embedded search */}
      <Navbar>
        <SearchBox defaultValue={queryParam} size="sm" onSearch={handleSearch} placeholder="搜索新闻..." />
      </Navbar>

      {/* Main Layout */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Sidebar Filters */}
          <aside className="w-full lg:w-64 flex-shrink-0">
            <FilterPanel filters={filtersFromUrl} onFilterChange={handleFilterChange} />
          </aside>

          {/* Results */}
          <main className="flex-1 min-w-0">
            {/* Results Meta */}
            {data && !loading && (
              <div className="flex items-center justify-between mb-5 animate-fade-in">
                <span className="text-sm text-gray-500">
                  共{" "}
                  <strong className="text-gray-800 font-semibold">
                    {data.total.toLocaleString("zh-CN")}
                  </strong>{" "}
                  条结果
                  {queryParam && (
                    <span className="text-gray-400">
                      {" — "}
                      <span className="text-gray-600">&ldquo;{queryParam}&rdquo;</span>
                    </span>
                  )}
                </span>
                <span className="flex items-center gap-1 text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-full">
                  <Clock className="w-3 h-3" />
                  {data.took_ms} ms
                </span>
              </div>
            )}

            {/* Loading */}
            {loading && (
              <div className="space-y-4 animate-fade-in">
                <SummaryCard summary="" citations={[]} articleCount={0} loading />
                {Array.from({ length: 5 }).map((_, i) => (
                  <ResultSkeleton key={i} />
                ))}
                <div className="flex justify-center py-4">
                  <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
                </div>
              </div>
            )}

            {/* Error */}
            {error && !loading && (
              <div className="flex flex-col items-center justify-center py-20 text-center animate-fade-in">
                <div className="w-16 h-16 rounded-2xl bg-red-50 flex items-center justify-center mb-4">
                  <AlertCircle className="w-8 h-8 text-red-400" />
                </div>
                <h2 className="text-lg font-semibold text-gray-800 mb-2">搜索出错</h2>
                <p className="text-sm text-gray-500 max-w-md mb-6">{error}</p>
                <button
                  onClick={() => fetchResults(queryParam, filtersFromUrl, pageParam)}
                  className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-sm font-medium rounded-xl hover:shadow-lg hover:shadow-blue-500/25 transition-all"
                >
                  重试
                </button>
              </div>
            )}

            {/* Empty */}
            {data && !loading && data.results.length === 0 && (
              <div className="flex flex-col items-center justify-center py-20 text-center animate-fade-in">
                <div className="w-16 h-16 rounded-2xl bg-gray-100 flex items-center justify-center mb-4">
                  <SearchX className="w-8 h-8 text-gray-300" />
                </div>
                <h2 className="text-lg font-semibold text-gray-700 mb-2">未找到相关结果</h2>
                <p className="text-sm text-gray-400 max-w-md">
                  尝试使用不同的关键词，或调整筛选条件
                </p>
              </div>
            )}

            {/* Results */}
            {data && !loading && data.results.length > 0 && (
              <div className="space-y-4">
                {data.summary && data.summary.summary_text && (
                  <SummaryCard
                    summary={data.summary.summary_text}
                    citations={data.summary.citations ?? []}
                    articleCount={data.results.length}
                  />
                )}

                {data.results.map((article, idx) => (
                  <ResultCard
                    key={article.id}
                    article={article}
                    position={idx + 1 + (data.page - 1) * PAGE_SIZE}
                    query={queryParam}
                  />
                ))}

                <div className="mt-6">
                  <Pagination
                    currentPage={data.page}
                    totalPages={totalPages}
                    totalItems={data.total}
                    pageSize={PAGE_SIZE}
                    onPageChange={handlePageChange}
                  />
                </div>
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
        </div>
      }
    >
      <SearchPageInner />
    </Suspense>
  );
}
