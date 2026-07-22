"use client";

import { useEffect, useState } from "react";
import { Loader2, AlertCircle, Layers } from "lucide-react";
import Link from "next/link";
import EventTimeline from "@/components/EventTimeline";
import UserMenu from "@/components/UserMenu";

interface TimelineEntry {
  article_id: string;
  title: string;
  source: string;
  published_at: string;
  summary: string;
}

interface EventData {
  id: string;
  title: string;
  summary: string;
  category: string;
  article_count: number;
  entities: string[];
  sentiment_distribution: { positive: number; neutral: number; negative: number };
  first_seen: string;
  last_updated: string;
  timeline: TimelineEntry[];
}

export default function EventsPage() {
  const [events, setEvents] = useState<EventData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hours, setHours] = useState(72);

  useEffect(() => {
    const fetchEvents = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/events?hours=${hours}`);
        if (!res.ok) throw new Error(`服务器错误 ${res.status}`);
        const data = await res.json();
        setEvents(data.events ?? []);
      } catch (e) {
        setError(e instanceof Error ? e.message : "加载失败");
      } finally {
        setLoading(false);
      }
    };
    fetchEvents();
  }, [hours]);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-white border-b border-gray-100 shadow-sm">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="text-lg font-bold text-blue-600 tracking-tight"
            >
              AI 新闻
            </Link>
            <span className="text-sm text-gray-500 flex items-center gap-1">
              <Layers className="w-4 h-4" />
              事件追踪
            </span>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/search?q=" className="text-sm text-gray-500 hover:text-blue-600">
              搜索
            </Link>
            <UserMenu />
          </div>
        </div>
      </header>

      {/* Time range selector */}
      <div className="max-w-5xl mx-auto px-4 py-4">
        <div className="flex items-center gap-2 mb-6">
          <span className="text-sm text-gray-500">时间范围：</span>
          {[
            { label: "24小时", value: 24 },
            { label: "3天", value: 72 },
            { label: "7天", value: 168 },
          ].map((opt) => (
            <button
              key={opt.value}
              onClick={() => setHours(opt.value)}
              className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                hours === opt.value
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white text-gray-600 border-gray-200 hover:border-blue-300"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* Loading */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-20">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin mb-4" />
            <p className="text-sm text-gray-500">正在聚合事件...</p>
          </div>
        )}

        {/* Error */}
        {error && !loading && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <AlertCircle className="w-12 h-12 text-red-400 mb-4" />
            <p className="text-sm text-gray-500">{error}</p>
          </div>
        )}

        {/* Empty */}
        {!loading && !error && events.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <Layers className="w-12 h-12 text-gray-300 mb-4" />
            <h2 className="text-lg font-semibold text-gray-700 mb-2">
              暂无事件
            </h2>
            <p className="text-sm text-gray-400">
              所选时间范围内未检测到事件聚合
            </p>
          </div>
        )}

        {/* Events */}
        {!loading && !error && events.length > 0 && (
          <div className="space-y-4">
            <p className="text-sm text-gray-500 mb-4">
              检测到 <strong className="text-gray-800">{events.length}</strong>{" "}
              个事件
            </p>
            {events.map((event) => (
              <EventTimeline key={event.id} event={event} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
