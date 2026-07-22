"use client";

import { useEffect, useState } from "react";
import { Loader2, AlertCircle, Layers } from "lucide-react";
import Navbar from "@/components/Navbar";
import EventTimeline from "@/components/EventTimeline";

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
    <div className="min-h-screen bg-gray-50/50">
      <Navbar />

      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6">
        {/* Page header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center">
                <Layers className="w-4 h-4 text-white" />
              </div>
              事件追踪
            </h1>
            <p className="text-sm text-gray-400 mt-1">智能聚合相关报道，追踪事件发展</p>
          </div>

          {/* Time range selector */}
          <div className="flex items-center gap-1.5 bg-white rounded-xl border border-gray-200 p-1">
            {[
              { label: "24h", value: 24 },
              { label: "3天", value: 72 },
              { label: "7天", value: 168 },
            ].map((opt) => (
              <button
                key={opt.value}
                onClick={() => setHours(opt.value)}
                className={`px-3.5 py-1.5 text-xs font-medium rounded-lg transition-all duration-200 ${
                  hours === opt.value
                    ? "bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-sm"
                    : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Loading */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-24 animate-fade-in">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin mb-4" />
            <p className="text-sm text-gray-400">正在聚合事件...</p>
          </div>
        )}

        {/* Error */}
        {error && !loading && (
          <div className="flex flex-col items-center justify-center py-24 text-center animate-fade-in">
            <div className="w-16 h-16 rounded-2xl bg-red-50 flex items-center justify-center mb-4">
              <AlertCircle className="w-8 h-8 text-red-400" />
            </div>
            <p className="text-sm text-gray-500">{error}</p>
          </div>
        )}

        {/* Empty */}
        {!loading && !error && events.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-center animate-fade-in">
            <div className="w-16 h-16 rounded-2xl bg-gray-100 flex items-center justify-center mb-4">
              <Layers className="w-8 h-8 text-gray-300" />
            </div>
            <h2 className="text-lg font-semibold text-gray-700 mb-2">暂无事件</h2>
            <p className="text-sm text-gray-400">所选时间范围内未检测到事件聚合</p>
          </div>
        )}

        {/* Events */}
        {!loading && !error && events.length > 0 && (
          <div className="space-y-4 animate-fade-in">
            <p className="text-sm text-gray-400">
              检测到 <strong className="text-gray-700 font-semibold">{events.length}</strong> 个事件
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
