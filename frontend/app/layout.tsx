import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI News Search | AI 新闻搜索",
  description:
    "Intelligent AI-powered news search with real-time summaries and insights. 智能 AI 驱动的新闻搜索，提供实时摘要和洞察。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-gray-50 antialiased">{children}</body>
    </html>
  );
}
