"use client";

import { useState, useRef, useEffect } from "react";
import { User, LogOut, Bell, BookOpen } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";

interface UserMenuProps {
  variant?: "light" | "dark";
}

export default function UserMenu({ variant = "light" }: UserMenuProps) {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const isDark = variant === "dark";

  if (!user) {
    return (
      <div className="flex items-center gap-2">
        <Link
          href="/auth/login"
          className={`px-3 py-1.5 text-sm rounded-lg transition-all duration-200 ${
            isDark
              ? "text-white/80 hover:text-white hover:bg-white/10"
              : "text-gray-600 hover:text-gray-900 hover:bg-gray-50"
          }`}
        >
          登录
        </Link>
        <Link
          href="/auth/register"
          className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-all duration-200 ${
            isDark
              ? "bg-white/15 text-white hover:bg-white/25 backdrop-blur-sm"
              : "bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:shadow-md hover:shadow-blue-500/25"
          }`}
        >
          注册
        </Link>
      </div>
    );
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-2 px-2 py-1.5 text-sm rounded-lg transition-all duration-200 ${
          isDark
            ? "text-white/80 hover:text-white hover:bg-white/10"
            : "text-gray-700 hover:bg-gray-100"
        }`}
      >
        <div
          className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
            isDark
              ? "bg-white/20 text-white"
              : "bg-gradient-to-br from-blue-500 to-indigo-500 text-white"
          }`}
        >
          {user.username.charAt(0).toUpperCase()}
        </div>
        <span className="hidden sm:inline font-medium">{user.username}</span>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-56 bg-white rounded-xl shadow-lg border border-gray-100 py-1 z-50 animate-fade-in">
          <div className="px-4 py-2.5 border-b border-gray-100">
            <p className="text-sm font-semibold text-gray-900">{user.username}</p>
            <p className="text-xs text-gray-400 mt-0.5">{user.email}</p>
          </div>

          <div className="py-1">
            <Link
              href="/subscriptions"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2.5 px-4 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-50 transition-colors"
            >
              <Bell className="w-4 h-4" />
              我的订阅
            </Link>

            <Link
              href="/events"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2.5 px-4 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-50 transition-colors"
            >
              <BookOpen className="w-4 h-4" />
              事件追踪
            </Link>
          </div>

          <div className="border-t border-gray-100 py-1">
            <button
              onClick={() => {
                logout();
                setOpen(false);
              }}
              className="flex items-center gap-2.5 px-4 py-2 text-sm text-red-500 hover:text-red-600 hover:bg-red-50 w-full transition-colors"
            >
              <LogOut className="w-4 h-4" />
              退出登录
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
