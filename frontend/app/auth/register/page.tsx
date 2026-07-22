"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Sparkles, Loader2, Search, TrendingUp, Bell } from "lucide-react";
import { useAuth } from "@/lib/auth";

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("两次输入的密码不一致");
      return;
    }

    setLoading(true);
    try {
      await register(email, username, password);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "注册失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen flex">
      {/* Left: decorative panel */}
      <div className="hidden lg:flex lg:w-1/2 auth-bg flex-col justify-between p-12 relative">
        <div className="relative z-10">
          <Link href="/" className="inline-flex items-center gap-2">
            <div className="w-9 h-9 rounded-xl bg-white/15 backdrop-blur-sm flex items-center justify-center border border-white/20">
              <Sparkles className="w-4 h-4 text-white" />
            </div>
            <span className="text-xl font-bold text-white">AI 新闻搜索</span>
          </Link>
        </div>

        <div className="relative z-10 space-y-8">
          <h2 className="text-3xl font-bold text-white leading-snug">
            加入我们，
            <br />
            获取智能新闻体验
          </h2>
          <div className="space-y-4">
            <FeatureLine icon={<Search className="w-4 h-4" />} text="语义搜索，理解你的真正意图" />
            <FeatureLine icon={<TrendingUp className="w-4 h-4" />} text="AI 摘要，快速掌握事件脉络" />
            <FeatureLine icon={<Bell className="w-4 h-4" />} text="订阅推送，热点不再错过" />
          </div>
        </div>

        <p className="text-sm text-white/30 relative z-10">
          &copy; 2024 AI News Search
        </p>
      </div>

      {/* Right: form */}
      <div className="flex-1 flex items-center justify-center px-6 py-12 bg-gray-50">
        <div className="w-full max-w-sm">
          {/* Mobile logo */}
          <div className="text-center mb-8 lg:hidden">
            <Link href="/" className="inline-flex items-center gap-2">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center shadow-md">
                <Sparkles className="w-4 h-4 text-white" />
              </div>
              <span className="text-xl font-bold text-gray-900">AI 新闻搜索</span>
            </Link>
          </div>

          <div className="card card-elevated rounded-2xl p-8">
            <h1 className="text-xl font-bold text-gray-900 mb-1">创建账号</h1>
            <p className="text-sm text-gray-400 mb-6">注册开始使用</p>

            {error && (
              <div className="mb-4 px-4 py-2.5 text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">邮箱</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full px-4 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 text-gray-900 bg-gray-50/50"
                  placeholder="your@email.com"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">用户名</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  className="w-full px-4 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 text-gray-900 bg-gray-50/50"
                  placeholder="你的昵称"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">密码</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                  className="w-full px-4 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 text-gray-900 bg-gray-50/50"
                  placeholder="至少 6 位"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">确认密码</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  className="w-full px-4 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 text-gray-900 bg-gray-50/50"
                  placeholder="再次输入密码"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-sm font-semibold rounded-xl hover:shadow-lg hover:shadow-blue-500/25 disabled:opacity-50 transition-all duration-200 flex items-center justify-center gap-2"
              >
                {loading && <Loader2 className="w-4 h-4 animate-spin" />}
                注册
              </button>
            </form>

            <p className="text-center text-sm text-gray-400 mt-6">
              已有账号？{" "}
              <Link href="/auth/login" className="text-blue-600 hover:text-blue-700 font-medium">
                立即登录
              </Link>
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}

function FeatureLine({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center text-white/80">
        {icon}
      </div>
      <span className="text-white/70 text-sm">{text}</span>
    </div>
  );
}
