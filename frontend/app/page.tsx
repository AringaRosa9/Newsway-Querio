"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, Sparkles, Globe, TrendingUp, Layers, Bell } from "lucide-react";
import Link from "next/link";
import UserMenu from "@/components/UserMenu";

const CATEGORIES = [
  { label: "科技", value: "technology" },
  { label: "财经", value: "finance" },
  { label: "国际", value: "international" },
  { label: "社会", value: "society" },
  { label: "体育", value: "sports" },
  { label: "娱乐", value: "entertainment" },
  { label: "健康", value: "health" },
  { label: "政治", value: "politics" },
];

interface Stats {
  total_articles: number;
  total_vectors: number;
  sources_count: number;
}

export default function HomePage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [stats, setStats] = useState<Stats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch("/api/stats");
        if (res.ok) {
          const data = await res.json();
          setStats(data);
        }
      } catch {
        // Stats are optional; ignore errors
      } finally {
        setStatsLoading(false);
      }
    };
    fetchStats();
  }, []);

  const handleSearch = useCallback(
    (q: string) => {
      const trimmed = q.trim();
      if (!trimmed) return;
      router.push(`/search?q=${encodeURIComponent(trimmed)}`);
    },
    [router]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSearch(query);
    }
  };

  const handleCategoryClick = (category: string) => {
    router.push(`/search?q=&category=${encodeURIComponent(category)}`);
  };

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4 py-16 relative">
      {/* Top Navigation */}
      <nav className="absolute top-0 left-0 right-0 flex items-center justify-between px-6 py-4">
        <div className="flex items-center gap-4">
          <Link
            href="/events"
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-blue-600 transition-colors"
          >
            <Layers className="w-4 h-4" />
            事件追踪
          </Link>
          <Link
            href="/subscriptions"
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-blue-600 transition-colors"
          >
            <Bell className="w-4 h-4" />
            订阅
          </Link>
        </div>
        <UserMenu />
      </nav>

      {/* Logo / Brand */}
      <div className="mb-10 text-center">
        <div className="inline-flex items-center gap-2 mb-3">
          <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center shadow-lg">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900 tracking-tight">
            AI 新闻搜索
          </h1>
        </div>
        <p className="text-gray-500 text-base">
          智能搜索 · AI 摘要 · 实时洞察
        </p>
      </div>

      {/* Search Box */}
      <div className="w-full max-w-2xl">
        <div className="relative flex items-center bg-white border-2 border-gray-200 rounded-2xl shadow-md hover:border-blue-400 focus-within:border-blue-500 focus-within:shadow-lg transition-all duration-200">
          <Search className="absolute left-4 w-5 h-5 text-gray-400 pointer-events-none" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="搜索新闻... / Search news..."
            className="flex-1 pl-12 pr-4 py-4 text-base bg-transparent border-none outline-none text-gray-900 placeholder-gray-400"
            autoFocus
            autoComplete="off"
            spellCheck={false}
          />
          <button
            onClick={() => handleSearch(query)}
            disabled={!query.trim()}
            className="mr-2 px-5 py-2 bg-blue-600 text-white text-sm font-medium rounded-xl hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors duration-150"
          >
            搜索
          </button>
        </div>

        {/* Quick Category Chips */}
        <div className="mt-4 flex flex-wrap gap-2 justify-center">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.value}
              onClick={() => handleCategoryClick(cat.value)}
              className="px-3 py-1.5 text-sm text-gray-600 bg-white border border-gray-200 rounded-full hover:border-blue-400 hover:text-blue-600 hover:bg-blue-50 transition-all duration-150 cursor-pointer"
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Stats Section */}
      <div className="mt-12 flex flex-wrap gap-6 justify-center text-center">
        {statsLoading ? (
          <div className="flex gap-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton h-12 w-32 rounded-lg" />
            ))}
          </div>
        ) : stats ? (
          <>
            <StatCard
              icon={<Globe className="w-4 h-4" />}
              value={stats.total_articles.toLocaleString("zh-CN")}
              label="已索引文章"
            />
            <StatCard
              icon={<TrendingUp className="w-4 h-4" />}
              value={stats.total_vectors?.toLocaleString("zh-CN") ?? "—"}
              label="向量索引"
            />
            <StatCard
              icon={<Search className="w-4 h-4" />}
              value={stats.sources_count?.toLocaleString("zh-CN") ?? "—"}
              label="新闻来源"
            />
          </>
        ) : null}
      </div>

      {/* Footer hint */}
      <p className="mt-16 text-xs text-gray-400">
        按 Enter 键搜索 · 支持中英文查询
      </p>
    </main>
  );
}

function StatCard({
  icon,
  value,
  label,
}: {
  icon: React.ReactNode;
  value: string;
  label: string;
}) {
  return (
    <div className="flex flex-col items-center gap-1 px-6 py-3 bg-white rounded-xl border border-gray-100 shadow-sm">
      <div className="flex items-center gap-1.5 text-blue-600">
        {icon}
        <span className="text-xl font-bold text-gray-900">{value}</span>
      </div>
      <span className="text-xs text-gray-500">{label}</span>
    </div>
  );
}
