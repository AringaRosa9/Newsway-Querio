"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Sparkles, Search, Layers, Bell, MessageCircle } from "lucide-react";
import UserMenu from "./UserMenu";

interface NavbarProps {
  variant?: "solid" | "transparent";
  children?: React.ReactNode;
}

const NAV_LINKS = [
  { href: "/search?q=", label: "搜索", icon: Search },
  { href: "/chat", label: "对话", icon: MessageCircle },
  { href: "/events", label: "事件追踪", icon: Layers },
  { href: "/subscriptions", label: "订阅", icon: Bell },
];

export default function Navbar({ variant = "solid", children }: NavbarProps) {
  const pathname = usePathname();

  const isTransparent = variant === "transparent";

  return (
    <header
      className={`sticky top-0 z-50 transition-all duration-300 ${
        isTransparent
          ? "bg-transparent"
          : "bg-white/80 backdrop-blur-xl border-b border-gray-100/80 shadow-sm"
      }`}
    >
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-14">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 flex-shrink-0 group">
            <div
              className={`w-8 h-8 rounded-lg flex items-center justify-center transition-transform group-hover:scale-105 ${
                isTransparent
                  ? "bg-white/15 backdrop-blur-sm"
                  : "bg-gradient-to-br from-blue-600 to-indigo-600 shadow-md"
              }`}
            >
              <Sparkles className={`w-4 h-4 ${isTransparent ? "text-white" : "text-white"}`} />
            </div>
            <span
              className={`text-lg font-bold tracking-tight hidden sm:inline ${
                isTransparent ? "text-white" : "text-gray-900"
              }`}
            >
              AI 新闻搜索
            </span>
          </Link>

          {/* Center: optional children (e.g. search box) */}
          {children && <div className="flex-1 max-w-2xl mx-4 hidden md:block">{children}</div>}

          {/* Nav Links */}
          <nav className="flex items-center gap-1">
            {NAV_LINKS.map((link) => {
              const isActive = pathname === link.href || pathname.startsWith(link.href.split("?")[0]);
              const Icon = link.icon;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-all duration-200 ${
                    isTransparent
                      ? isActive
                        ? "text-white bg-white/15"
                        : "text-white/70 hover:text-white hover:bg-white/10"
                      : isActive
                      ? "text-blue-600 bg-blue-50 font-medium"
                      : "text-gray-500 hover:text-gray-800 hover:bg-gray-50"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span className="hidden lg:inline">{link.label}</span>
                </Link>
              );
            })}

            <div className={`ml-2 pl-2 ${isTransparent ? "border-l border-white/20" : "border-l border-gray-200"}`}>
              <UserMenu variant={isTransparent ? "dark" : "light"} />
            </div>
          </nav>
        </div>
      </div>
    </header>
  );
}
