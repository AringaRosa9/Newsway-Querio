import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = {
  title: {
    default: "AI News Search | AI 新闻搜索",
    template: "%s | AI News Search",
  },
  description:
    "智能 AI 驱动的新闻搜索引擎，提供实时摘要、事件追踪和多语言检索。Intelligent AI-powered news search with real-time summaries and insights.",
  keywords: [
    "AI 新闻搜索",
    "新闻搜索引擎",
    "AI news search",
    "news aggregator",
    "新闻聚合",
    "AI 摘要",
  ],
  authors: [{ name: "AI News Search" }],
  openGraph: {
    type: "website",
    locale: "zh_CN",
    alternateLocale: "en_US",
    siteName: "AI News Search",
    title: "AI News Search | AI 新闻搜索",
    description:
      "智能 AI 驱动的新闻搜索引擎，提供实时摘要、事件追踪和多语言检索。",
  },
  twitter: {
    card: "summary_large_image",
    title: "AI News Search | AI 新闻搜索",
    description:
      "智能 AI 驱动的新闻搜索引擎，提供实时摘要和洞察。",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: "#2563eb",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <head>
        <link rel="manifest" href="/manifest.json" />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "WebApplication",
              name: "AI News Search",
              alternateName: "AI 新闻搜索",
              description:
                "智能 AI 驱动的新闻搜索引擎，提供实时摘要、事件追踪和多语言检索。",
              applicationCategory: "NewsApplication",
              operatingSystem: "Web",
              offers: { "@type": "Offer", price: "0", priceCurrency: "CNY" },
              inLanguage: ["zh-CN", "en"],
            }),
          }}
        />
      </head>
      <body className="min-h-screen bg-gray-50 antialiased">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
