"use client";

import { Clock, Globe, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { zhCN } from "date-fns/locale";

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

interface EventTimelineProps {
  event: EventData;
  defaultExpanded?: boolean;
}

const CATEGORY_LABELS: Record<string, string> = {
  technology: "科技",
  economy: "财经",
  politics: "政治",
  international: "国际",
  society: "社会",
  sports: "体育",
  entertainment: "娱乐",
  health: "健康",
  education: "教育",
  environment: "环境",
  social: "社交",
};

function SentimentBar({
  distribution,
}: {
  distribution: { positive: number; neutral: number; negative: number };
}) {
  const total = distribution.positive + distribution.neutral + distribution.negative;
  if (total === 0) return null;

  const pPos = Math.round((distribution.positive / total) * 100);
  const pNeu = Math.round((distribution.neutral / total) * 100);
  const pNeg = 100 - pPos - pNeu;

  return (
    <div className="flex items-center gap-2.5">
      <div className="flex h-2 flex-1 rounded-full overflow-hidden bg-gray-100">
        {pPos > 0 && <div className="bg-emerald-400 transition-all" style={{ width: `${pPos}%` }} />}
        {pNeu > 0 && <div className="bg-gray-300 transition-all" style={{ width: `${pNeu}%` }} />}
        {pNeg > 0 && <div className="bg-red-400 transition-all" style={{ width: `${pNeg}%` }} />}
      </div>
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <span className="flex items-center gap-0.5">
          <TrendingUp className="w-3 h-3 text-emerald-500" />
          {distribution.positive}
        </span>
        <span className="flex items-center gap-0.5">
          <Minus className="w-3 h-3 text-gray-400" />
          {distribution.neutral}
        </span>
        <span className="flex items-center gap-0.5">
          <TrendingDown className="w-3 h-3 text-red-500" />
          {distribution.negative}
        </span>
      </div>
    </div>
  );
}

function formatTime(dateStr: string): string {
  if (!dateStr) return "";
  try {
    return formatDistanceToNow(new Date(dateStr), { addSuffix: true, locale: zhCN });
  } catch {
    return dateStr;
  }
}

export default function EventTimeline({ event }: EventTimelineProps) {
  const categoryLabel = CATEGORY_LABELS[event.category] ?? event.category;

  return (
    <div className="card card-elevated rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="p-5 pb-4">
        <div className="flex items-start justify-between mb-3">
          <h3 className="text-base font-semibold text-gray-900 leading-snug flex-1">
            {event.title}
          </h3>
          <span className="ml-3 flex-shrink-0 px-2.5 py-1 text-xs bg-blue-50 text-blue-700 border border-blue-100/60 rounded-full font-medium">
            {event.article_count} 篇报道
          </span>
        </div>

        {/* Meta */}
        <div className="flex flex-wrap items-center gap-2 mb-3">
          {categoryLabel && (
            <span className="px-2.5 py-0.5 text-xs bg-purple-50 text-purple-700 border border-purple-100/60 rounded-full">
              {categoryLabel}
            </span>
          )}
          <span className="text-xs text-gray-400 flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {formatTime(event.first_seen)} 开始
          </span>
          <span className="text-xs text-gray-400">
            最近更新 {formatTime(event.last_updated)}
          </span>
        </div>

        {/* Sentiment */}
        <SentimentBar distribution={event.sentiment_distribution} />

        {/* Entities */}
        {event.entities.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-3">
            {event.entities.slice(0, 8).map((entity, i) => (
              <span
                key={i}
                className="px-2 py-0.5 text-xs bg-gray-50 text-gray-500 border border-gray-100 rounded-md"
              >
                {entity}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Timeline */}
      <div className="border-t border-gray-100 px-5 py-4 bg-gray-50/50">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">
          事件时间线
        </p>
        <div className="relative pl-6 space-y-5">
          {/* Vertical line */}
          <div className="absolute left-[7px] top-2 bottom-2 w-0.5 bg-gradient-to-b from-blue-300 via-blue-200 to-gray-200 rounded-full" />

          {event.timeline.map((entry, i) => (
            <div key={i} className="relative">
              {/* Dot */}
              <div
                className={`absolute -left-6 top-1.5 w-3.5 h-3.5 rounded-full border-2 transition-colors ${
                  i === 0
                    ? "bg-blue-500 border-blue-500 shadow-sm shadow-blue-500/30"
                    : "bg-white border-gray-300"
                }`}
              />

              <div>
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-xs text-gray-400">{formatTime(entry.published_at)}</span>
                  <span className="text-xs text-gray-400 flex items-center gap-0.5">
                    <Globe className="w-3 h-3" />
                    {entry.source}
                  </span>
                </div>
                <p className="text-sm text-gray-800 font-medium leading-snug">{entry.title}</p>
                {entry.summary && (
                  <p className="text-xs text-gray-500 mt-1 line-clamp-2 leading-relaxed">
                    {entry.summary}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
