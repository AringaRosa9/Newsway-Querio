"use client";

import { ExternalLink, Clock, Tag, Globe } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { zhCN } from "date-fns/locale";

interface Article {
  id: string;
  title: string;
  content: string;
  source: string;
  url: string;
  published_at: string;
  category?: string;
  sentiment?: "positive" | "neutral" | "negative" | string;
  entities?: string[];
  score?: number;
}

interface ResultCardProps {
  article: Article;
}

const SENTIMENT_CONFIG: Record<
  string,
  { color: string; label: string; dot: string }
> = {
  positive: {
    color: "text-green-700 bg-green-50 border-green-200",
    label: "正面",
    dot: "bg-green-500",
  },
  neutral: {
    color: "text-gray-600 bg-gray-50 border-gray-200",
    label: "中性",
    dot: "bg-gray-400",
  },
  negative: {
    color: "text-red-700 bg-red-50 border-red-200",
    label: "负面",
    dot: "bg-red-500",
  },
};

const CATEGORY_LABELS: Record<string, string> = {
  technology: "科技",
  finance: "财经",
  international: "国际",
  society: "社会",
  sports: "体育",
  entertainment: "娱乐",
  health: "健康",
  politics: "政治",
};

function RelativeTime({ dateStr }: { dateStr: string }) {
  if (!dateStr) return null;
  try {
    const date = new Date(dateStr);
    const rel = formatDistanceToNow(date, { addSuffix: true, locale: zhCN });
    return (
      <span title={date.toLocaleString("zh-CN")} className="text-gray-400 text-xs flex items-center gap-1">
        <Clock className="w-3 h-3" />
        {rel}
      </span>
    );
  } catch {
    return <span className="text-gray-400 text-xs">{dateStr}</span>;
  }
}

export default function ResultCard({ article }: ResultCardProps) {
  const {
    title,
    content,
    source,
    url,
    published_at,
    category,
    sentiment,
    entities,
    score,
  } = article;

  const sentimentKey = sentiment ?? "neutral";
  const sentimentCfg = SENTIMENT_CONFIG[sentimentKey] ?? SENTIMENT_CONFIG.neutral;

  const snippet =
    content && content.length > 200
      ? content.slice(0, 200).trimEnd() + "..."
      : content ?? "";

  const categoryLabel = category
    ? CATEGORY_LABELS[category] ?? category
    : null;

  const scorePercent = score != null ? Math.round(Math.min(score, 1) * 100) : null;

  return (
    <article className="bg-white border border-gray-100 rounded-2xl p-5 shadow-sm hover:shadow-md hover:border-blue-200 transition-all duration-200 group">
      {/* Title */}
      <h2 className="mb-2">
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-base font-semibold text-gray-900 group-hover:text-blue-600 transition-colors duration-150 inline-flex items-start gap-1.5 leading-snug"
        >
          <span>{title}</span>
          <ExternalLink className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 opacity-0 group-hover:opacity-60 transition-opacity" />
        </a>
      </h2>

      {/* Meta row */}
      <div className="flex flex-wrap items-center gap-2 mb-3">
        {/* Source */}
        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-700 border border-blue-100 rounded-full text-xs font-medium">
          <Globe className="w-3 h-3" />
          {source}
        </span>

        {/* Category */}
        {categoryLabel && (
          <span className="px-2 py-0.5 bg-purple-50 text-purple-700 border border-purple-100 rounded-full text-xs">
            {categoryLabel}
          </span>
        )}

        {/* Sentiment */}
        <span
          className={`inline-flex items-center gap-1 px-2 py-0.5 border rounded-full text-xs ${sentimentCfg.color}`}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${sentimentCfg.dot}`} />
          {sentimentCfg.label}
        </span>

        {/* Time */}
        <RelativeTime dateStr={published_at} />

        {/* Score bar */}
        {scorePercent != null && (
          <div className="ml-auto flex items-center gap-1" title={`相关度 ${scorePercent}%`}>
            <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-400 rounded-full"
                style={{ width: `${scorePercent}%` }}
              />
            </div>
            <span className="text-gray-400 text-xs">{scorePercent}%</span>
          </div>
        )}
      </div>

      {/* Content snippet */}
      {snippet && (
        <p className="text-sm text-gray-600 leading-relaxed mb-3 line-clamp-3">
          {snippet}
        </p>
      )}

      {/* Entity tags */}
      {entities && entities.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <Tag className="w-3 h-3 text-gray-400 flex-shrink-0" />
          {entities.slice(0, 8).map((entity, i) => (
            <span
              key={i}
              className="px-2 py-0.5 bg-gray-50 text-gray-600 border border-gray-100 rounded text-xs"
            >
              {entity}
            </span>
          ))}
        </div>
      )}
    </article>
  );
}
