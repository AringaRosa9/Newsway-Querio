"use client";

import { useState } from "react";
import { Filter, RotateCcw, Check, ChevronDown, ChevronUp } from "lucide-react";

export interface Filters {
  time_from?: string;
  time_to?: string;
  category?: string;
  sentiment?: string;
  source?: string;
  language?: string;
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

  const handleApply = () => onFilterChange(local);

  const handleReset = () => {
    const empty: Filters = {};
    setLocal(empty);
    setActivePreset("");
    onFilterChange(empty);
  };

  const hasActiveFilters =
    !!filters.category || !!filters.sentiment || !!filters.time_from || !!filters.source || !!filters.language;

  return (
    <aside className="card rounded-2xl overflow-hidden">
      {/* Header */}
      <button
        className="w-full flex items-center justify-between px-5 py-3.5 text-sm font-semibold text-gray-700 hover:bg-gray-50/50 transition-colors"
        onClick={() => setIsExpanded((v) => !v)}
      >
        <span className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          筛选条件
          {hasActiveFilters && (
            <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
          )}
        </span>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        )}
      </button>

      <div className={`${isExpanded ? "block" : "hidden"} lg:block`}>
        <div className="px-5 pb-5 space-y-5 border-t border-gray-50 pt-4">
          {/* Time Range */}
          <FilterSection label="时间范围">
            <div className="flex flex-wrap gap-1.5 mb-2">
              {TIME_PRESETS.map((p) => (
                <ChipButton
                  key={p.value}
                  label={p.label}
                  active={activePreset === p.value}
                  onClick={() => handlePreset(p.value)}
                />
              ))}
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-gray-400 mb-1 block">开始</label>
                <input
                  type="date"
                  value={local.time_from ?? ""}
                  onChange={(e) => {
                    setActivePreset("custom");
                    update({ time_from: e.target.value || undefined });
                  }}
                  className="w-full text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 text-gray-700 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400/20 bg-gray-50/50"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 mb-1 block">结束</label>
                <input
                  type="date"
                  value={local.time_to ?? ""}
                  onChange={(e) => {
                    setActivePreset("custom");
                    update({ time_to: e.target.value || undefined });
                  }}
                  className="w-full text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 text-gray-700 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400/20 bg-gray-50/50"
                />
              </div>
            </div>
          </FilterSection>

          {/* Category */}
          <FilterSection label="新闻分类">
            <div className="flex flex-wrap gap-1.5">
              {CATEGORIES.map((c) => (
                <ChipButton
                  key={c.value}
                  label={c.label}
                  active={(local.category ?? "") === c.value}
                  showCheck={!!(local.category && c.value)}
                  onClick={() => update({ category: c.value || undefined })}
                />
              ))}
            </div>
          </FilterSection>

          {/* Sentiment */}
          <FilterSection label="情感倾向">
            <div className="flex flex-wrap gap-1.5">
              {SENTIMENTS.map((s) => (
                <ChipButton
                  key={s.value}
                  label={s.label}
                  active={(local.sentiment ?? "") === s.value}
                  onClick={() => update({ sentiment: s.value || undefined })}
                />
              ))}
            </div>
          </FilterSection>

          {/* Source */}
          <FilterSection label="新闻来源">
            <input
              type="text"
              placeholder="输入来源筛选..."
              value={local.source ?? ""}
              onChange={(e) => update({ source: e.target.value || undefined })}
              className="w-full text-xs border border-gray-200 rounded-lg px-3 py-2 text-gray-700 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400/20 placeholder-gray-400 bg-gray-50/50"
            />
          </FilterSection>

          {/* Language */}
          <FilterSection label="语言">
            <div className="flex flex-wrap gap-1.5">
              {[
                { label: "全部", value: "" },
                { label: "中文", value: "zh" },
                { label: "English", value: "en" },
              ].map((lang) => (
                <ChipButton
                  key={lang.value}
                  label={lang.label}
                  active={(local.language ?? "") === lang.value}
                  onClick={() => update({ language: lang.value || undefined })}
                />
              ))}
            </div>
          </FilterSection>

          {/* Actions */}
          <div className="flex gap-2 pt-1">
            <button
              onClick={handleApply}
              className="flex-1 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-xs font-semibold rounded-xl hover:shadow-md hover:shadow-blue-500/20 transition-all"
            >
              应用筛选
            </button>
            <button
              onClick={handleReset}
              className="flex items-center gap-1 px-3 py-2.5 border border-gray-200 text-gray-500 text-xs rounded-xl hover:bg-gray-50 transition-colors"
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

function FilterSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section>
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">{label}</p>
      {children}
    </section>
  );
}

function ChipButton({
  label,
  active,
  showCheck,
  onClick,
}: {
  label: string;
  active: boolean;
  showCheck?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1 text-xs rounded-full border transition-all duration-200 flex items-center gap-1 ${
        active
          ? "bg-gradient-to-r from-blue-600 to-indigo-600 text-white border-transparent shadow-sm"
          : "bg-white text-gray-600 border-gray-200 hover:border-blue-300 hover:text-blue-600"
      }`}
    >
      {active && showCheck && <Check className="w-3 h-3" />}
      {label}
    </button>
  );
}
