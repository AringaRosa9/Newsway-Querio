"use client";

import { useState } from "react";
import { Filter, RotateCcw, Check } from "lucide-react";

export interface Filters {
  time_from?: string;
  time_to?: string;
  category?: string;
  sentiment?: string;
  source?: string;
}

interface FilterPanelProps {
  filters: Filters;
  onFilterChange: (filters: Filters) => void;
}

const CATEGORIES = [
  { label: "全部", value: "" },
  { label: "科技", value: "technology" },
  { label: "财经", value: "finance" },
  { label: "国际", value: "international" },
  { label: "社会", value: "society" },
  { label: "体育", value: "sports" },
  { label: "娱乐", value: "entertainment" },
  { label: "健康", value: "health" },
  { label: "政治", value: "politics" },
];

const SENTIMENTS = [
  { label: "全部", value: "" },
  { label: "正面", value: "positive" },
  { label: "中性", value: "neutral" },
  { label: "负面", value: "negative" },
];

const TIME_PRESETS = [
  { label: "全部", value: "" },
  { label: "今天", value: "today" },
  { label: "本周", value: "week" },
  { label: "本月", value: "month" },
];

function getPresetDates(preset: string): { time_from?: string; time_to?: string } {
  const now = new Date();
  const toISO = (d: Date) => d.toISOString().split("T")[0];

  switch (preset) {
    case "today":
      return { time_from: toISO(now), time_to: toISO(now) };
    case "week": {
      const start = new Date(now);
      start.setDate(now.getDate() - 7);
      return { time_from: toISO(start), time_to: toISO(now) };
    }
    case "month": {
      const start = new Date(now);
      start.setMonth(now.getMonth() - 1);
      return { time_from: toISO(start), time_to: toISO(now) };
    }
    default:
      return { time_from: undefined, time_to: undefined };
  }
}

export default function FilterPanel({ filters, onFilterChange }: FilterPanelProps) {
  const [local, setLocal] = useState<Filters>(filters);
  const [activePreset, setActivePreset] = useState<string>("");
  const [isExpanded, setIsExpanded] = useState(false);

  const update = (partial: Partial<Filters>) => {
    setLocal((prev) => ({ ...prev, ...partial }));
  };

  const handlePreset = (preset: string) => {
    setActivePreset(preset);
    const dates = getPresetDates(preset);
    update({ time_from: dates.time_from, time_to: dates.time_to });
  };

  const handleApply = () => {
    onFilterChange(local);
  };

  const handleReset = () => {
    const empty: Filters = {};
    setLocal(empty);
    setActivePreset("");
    onFilterChange(empty);
  };

  const hasActiveFilters =
    !!filters.category || !!filters.sentiment || !!filters.time_from || !!filters.source;

  return (
    <aside className="bg-white border border-gray-100 rounded-2xl shadow-sm overflow-hidden">
      {/* Header */}
      <button
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
        onClick={() => setIsExpanded((v) => !v)}
      >
        <span className="flex items-center gap-2">
          <Filter className="w-4 h-4" />
          筛选条件
          {hasActiveFilters && (
            <span className="w-2 h-2 rounded-full bg-blue-500" />
          )}
        </span>
        <span className="text-gray-400 text-xs">{isExpanded ? "收起" : "展开"}</span>
      </button>

      {/* Always-visible on desktop; collapsible on mobile */}
      <div className={`${isExpanded ? "block" : "hidden"} lg:block`}>
        <div className="px-4 pb-4 space-y-5 border-t border-gray-50 pt-3">
          {/* Time Range */}
          <section>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              时间范围
            </p>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {TIME_PRESETS.map((p) => (
                <button
                  key={p.value}
                  onClick={() => handlePreset(p.value)}
                  className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                    activePreset === p.value
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-gray-600 border-gray-200 hover:border-blue-300"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">开始日期</label>
                <input
                  type="date"
                  value={local.time_from ?? ""}
                  onChange={(e) => {
                    setActivePreset("custom");
                    update({ time_from: e.target.value || undefined });
                  }}
                  className="w-full text-xs border border-gray-200 rounded-lg px-2 py-1.5 text-gray-700 focus:outline-none focus:border-blue-400"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">结束日期</label>
                <input
                  type="date"
                  value={local.time_to ?? ""}
                  onChange={(e) => {
                    setActivePreset("custom");
                    update({ time_to: e.target.value || undefined });
                  }}
                  className="w-full text-xs border border-gray-200 rounded-lg px-2 py-1.5 text-gray-700 focus:outline-none focus:border-blue-400"
                />
              </div>
            </div>
          </section>

          {/* Category */}
          <section>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              新闻分类
            </p>
            <div className="flex flex-wrap gap-1.5">
              {CATEGORIES.map((c) => (
                <button
                  key={c.value}
                  onClick={() => update({ category: c.value || undefined })}
                  className={`px-3 py-1 text-xs rounded-full border transition-colors flex items-center gap-1 ${
                    (local.category ?? "") === c.value
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-gray-600 border-gray-200 hover:border-blue-300"
                  }`}
                >
                  {(local.category ?? "") === c.value && c.value && (
                    <Check className="w-3 h-3" />
                  )}
                  {c.label}
                </button>
              ))}
            </div>
          </section>

          {/* Sentiment */}
          <section>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              情感倾向
            </p>
            <div className="flex flex-wrap gap-1.5">
              {SENTIMENTS.map((s) => (
                <button
                  key={s.value}
                  onClick={() => update({ sentiment: s.value || undefined })}
                  className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                    (local.sentiment ?? "") === s.value
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-gray-600 border-gray-200 hover:border-blue-300"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </section>

          {/* Source */}
          <section>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              新闻来源
            </p>
            <input
              type="text"
              placeholder="输入来源筛选..."
              value={local.source ?? ""}
              onChange={(e) => update({ source: e.target.value || undefined })}
              className="w-full text-xs border border-gray-200 rounded-lg px-3 py-1.5 text-gray-700 focus:outline-none focus:border-blue-400 placeholder-gray-400"
            />
          </section>

          {/* Action Buttons */}
          <div className="flex gap-2 pt-1">
            <button
              onClick={handleApply}
              className="flex-1 py-2 bg-blue-600 text-white text-xs font-semibold rounded-xl hover:bg-blue-700 transition-colors"
            >
              应用筛选
            </button>
            <button
              onClick={handleReset}
              className="flex items-center gap-1 px-3 py-2 border border-gray-200 text-gray-600 text-xs rounded-xl hover:bg-gray-50 transition-colors"
            >
              <RotateCcw className="w-3 h-3" />
              重置
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
}
