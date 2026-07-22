"use client";

import { Sparkles, ExternalLink } from "lucide-react";

interface Citation {
  index: number;
  title: string;
  source: string;
  url: string;
}

interface SummaryCardProps {
  summary: string;
  citations: Citation[];
  articleCount: number;
  loading?: boolean;
}

function SummaryText({ text, citations }: { text: string; citations: Citation[] }) {
  const parts = text.split(/(\[\d+\])/g);

  return (
    <p className="text-gray-700 leading-relaxed text-sm">
      {parts.map((part, i) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (match) {
          const idx = parseInt(match[1], 10);
          const citation = citations.find((c) => c.index === idx);
          if (citation) {
            return (
              <a
                key={i}
                href={citation.url}
                target="_blank"
                rel="noopener noreferrer"
                title={citation.title}
                className="text-blue-600 hover:text-blue-800 font-medium"
              >
                <sup>[{idx}]</sup>
              </a>
            );
          }
        }
        if (part.includes("**")) {
          const boldParts = part.split(/(\*\*[^*]+\*\*)/g);
          return (
            <span key={i}>
              {boldParts.map((bp, j) => {
                const boldMatch = bp.match(/^\*\*(.+)\*\*$/);
                if (boldMatch) return <strong key={j}>{boldMatch[1]}</strong>;
                return bp;
              })}
            </span>
          );
        }
        return part;
      })}
    </p>
  );
}

export default function SummaryCard({
  summary,
  citations,
  articleCount,
  loading = false,
}: SummaryCardProps) {
  if (loading) {
    return (
      <div className="card rounded-2xl p-5 mb-4 summary-bar pl-8">
        <div className="flex items-center gap-2 mb-3">
          <div className="skeleton h-5 w-16 rounded" />
          <div className="skeleton h-4 w-24 rounded" />
        </div>
        <div className="space-y-2">
          <div className="skeleton h-4 w-full rounded" />
          <div className="skeleton h-4 w-5/6 rounded" />
          <div className="skeleton h-4 w-4/6 rounded" />
        </div>
      </div>
    );
  }

  if (!summary) return null;

  return (
    <div className="card card-elevated rounded-2xl p-5 mb-4 summary-bar pl-8 bg-gradient-to-r from-blue-50/80 to-indigo-50/50 border-blue-100/60 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-xs font-semibold rounded-full shadow-sm">
          <Sparkles className="w-3 h-3" />
          AI 摘要
        </span>
        {articleCount > 0 && (
          <span className="text-xs text-blue-500/70">
            基于 {articleCount} 篇报道生成
          </span>
        )}
      </div>

      {/* Summary Text */}
      <div className="mb-4">
        <SummaryText text={summary} citations={citations} />
      </div>

      {/* Citations */}
      {citations && citations.length > 0 && (
        <div className="border-t border-blue-100/60 pt-3">
          <p className="text-xs font-semibold text-blue-600/70 mb-2">参考来源</p>
          <ol className="space-y-1">
            {citations.map((c) => (
              <li key={c.index} className="flex items-start gap-1.5 text-xs">
                <span className="text-blue-500 font-medium flex-shrink-0 mt-0.5">
                  [{c.index}]
                </span>
                <a
                  href={c.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:text-blue-800 hover:underline line-clamp-1 flex items-center gap-1"
                >
                  <span>{c.title}</span>
                  <span className="text-blue-400">({c.source})</span>
                  <ExternalLink className="w-3 h-3 flex-shrink-0 text-blue-400" />
                </a>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
