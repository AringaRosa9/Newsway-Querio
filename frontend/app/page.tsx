"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  Sparkles,
  Globe,
  TrendingUp,
  Cpu,
  DollarSign,
  Earth,
  Users,
  Trophy,
  Clapperboard,
  HeartPulse,
  Landmark,
  ArrowRight,
} from "lucide-react";
import Navbar from "@/components/Navbar";

const CATEGORIES = [
  { label: "科技", value: "technology", icon: Cpu, color: "from-blue-400 to-cyan-400" },
  { label: "财经", value: "finance", icon: DollarSign, color: "from-emerald-400 to-teal-400" },
  { label: "国际", value: "international", icon: Earth, color: "from-violet-400 to-purple-400" },
  { label: "社会", value: "society", icon: Users, color: "from-orange-400 to-amber-400" },
  { label: "体育", value: "sports", icon: Trophy, color: "from-red-400 to-rose-400" },
  { label: "娱乐", value: "entertainment", icon: Clapperboard, color: "from-pink-400 to-fuchsia-400" },
  { label: "健康", value: "health", icon: HeartPulse, color: "from-lime-400 to-green-400" },
  { label: "政治", value: "politics", icon: Landmark, color: "from-slate-400 to-zinc-400" },
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

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch("/api/stats");
        if (res.ok) setStats(await res.json());
      } catch {
        // Stats are optional
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
    if (e.key === "Enter") handleSearch(query);
  };

  const handleCategoryClick = (category: string) => {
    router.push(`/search?q=&category=${encodeURIComponent(category)}`);
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Hero Section ──────────────────────────────────────── */}
      <section className="hero-gradient min-h-[85vh] flex flex-col relative">
        {/* Animated blobs */}
        <div className="hero-blob hero-blob-1" />
        <div className="hero-blob hero-blob-2" />
        <div className="hero-blob hero-blob-3" />

        {/* Navbar (transparent on hero) */}
        <Navbar variant="transparent" />

        {/* Hero Content */}
        <div className="flex-1 flex flex-col items-center justify-center px-4 pb-20 relative z-10">
          {/* Brand */}
          <div className="text-center mb-10 animate-fade-in">
            <div className="inline-flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-2xl bg-white/15 backdrop-blur-sm flex items-center justify-center border border-white/20 shadow-lg">
                <Sparkles className="w-6 h-6 text-white" />
              </div>
              <h1 className="text-4xl sm:text-5xl font-bold text-white tracking-tight">
                AI 新闻搜索
              </h1>
            </div>
            <p className="text-lg text-white/60 font-light">
              智能搜索 · AI 摘要 · 实时洞察
            </p>
          </div>

          {/* Search Box (glassmorphism) */}
          <div className="w-full max-w-2xl animate-fade-in-up animate-fade-in-delay-1">
            <div className="glass rounded-2xl p-1.5">
              <div className="relative flex items-center bg-white/10 rounded-xl">
                <Search className="absolute left-4 w-5 h-5 text-white/50 pointer-events-none" />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="搜索新闻... / Search news..."
                  className="flex-1 pl-12 pr-4 py-4 text-base bg-transparent border-none outline-none text-white placeholder-white/40"
                  autoFocus
                  autoComplete="off"
                  spellCheck={false}
                />
                <button
                  onClick={() => handleSearch(query)}
                  disabled={!query.trim()}
                  className="mr-2 px-6 py-2.5 bg-white text-gray-900 text-sm font-semibold rounded-xl hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-200 hover:shadow-lg"
                >
                  搜索
                </button>
              </div>
            </div>
            <p className="text-center text-white/30 text-xs mt-3">
              按 Enter 键搜索 · 支持中英文查询
            </p>
          </div>

          {/* Category Grid */}
          <div className="mt-10 grid grid-cols-4 sm:grid-cols-8 gap-3 max-w-2xl w-full animate-fade-in-up animate-fade-in-delay-2">
            {CATEGORIES.map((cat) => {
              const Icon = cat.icon;
              return (
                <button
                  key={cat.value}
                  onClick={() => handleCategoryClick(cat.value)}
                  className="glass-card flex flex-col items-center gap-2 py-3 px-2 rounded-xl cursor-pointer group"
                >
                  <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${cat.color} flex items-center justify-center shadow-sm group-hover:shadow-md transition-shadow`}>
                    <Icon className="w-4 h-4 text-white" />
                  </div>
                  <span className="text-xs text-white/70 group-hover:text-white transition-colors">
                    {cat.label}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── Stats & Features Section ─────────────────────────── */}
      <section className="bg-white py-16 px-4">
        <div className="max-w-4xl mx-auto">
          {/* Stats */}
          {stats && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-16 animate-fade-in">
              <StatCard
                icon={<Globe className="w-5 h-5" />}
                value={stats.total_articles.toLocaleString("zh-CN")}
                label="已索引文章"
                color="blue"
              />
              <StatCard
                icon={<TrendingUp className="w-5 h-5" />}
                value={stats.total_vectors?.toLocaleString("zh-CN") ?? "—"}
                label="向量索引"
                color="purple"
              />
              <StatCard
                icon={<Search className="w-5 h-5" />}
                value={stats.sources_count?.toLocaleString("zh-CN") ?? "—"}
                label="新闻来源"
                color="cyan"
              />
            </div>
          )}

          {/* Feature highlights */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <FeatureCard
              title="智能语义搜索"
              description="基于向量检索，理解查询意图而非简单关键词匹配"
              icon={<Search className="w-5 h-5" />}
            />
            <FeatureCard
              title="AI 摘要生成"
              description="自动汇总多篇报道，快速掌握事件全貌"
              icon={<Sparkles className="w-5 h-5" />}
            />
            <FeatureCard
              title="事件聚合追踪"
              description="智能聚类相关报道，追踪事件发展脉络"
              icon={<TrendingUp className="w-5 h-5" />}
            />
          </div>
        </div>
      </section>
    </div>
  );
}

function StatCard({
  icon,
  value,
  label,
  color,
}: {
  icon: React.ReactNode;
  value: string;
  label: string;
  color: "blue" | "purple" | "cyan";
}) {
  const colorMap = {
    blue: "from-blue-500 to-blue-600 text-blue-600 bg-blue-50",
    purple: "from-purple-500 to-purple-600 text-purple-600 bg-purple-50",
    cyan: "from-cyan-500 to-cyan-600 text-cyan-600 bg-cyan-50",
  };
  const c = colorMap[color];
  return (
    <div className="card-elevated rounded-2xl p-6 flex items-center gap-4">
      <div className={`w-12 h-12 rounded-xl ${c.split(" ").slice(2).join(" ")} flex items-center justify-center`}>
        {icon}
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-sm text-gray-500">{label}</p>
      </div>
    </div>
  );
}

function FeatureCard({
  title,
  description,
  icon,
}: {
  title: string;
  description: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="group text-center px-4">
      <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 flex items-center justify-center mx-auto mb-4 text-blue-600 group-hover:shadow-md transition-shadow">
        {icon}
      </div>
      <h3 className="text-base font-semibold text-gray-900 mb-2">{title}</h3>
      <p className="text-sm text-gray-500 leading-relaxed">{description}</p>
    </div>
  );
}
