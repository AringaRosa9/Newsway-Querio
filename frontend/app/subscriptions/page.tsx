"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Bell,
  Plus,
  Trash2,
  Loader2,
  X,
  BellOff,
  BellRing,
} from "lucide-react";
import { useAuth, getAuthHeaders } from "@/lib/auth";
import Navbar from "@/components/Navbar";

interface Subscription {
  id: string;
  name: string;
  subscription_type: string;
  query: string;
  frequency: string;
  notify_email: boolean;
  is_active: boolean;
  created_at: string;
}

interface Notification {
  id: string;
  title: string;
  body: string;
  is_read: boolean;
  created_at: string;
}

export default function SubscriptionsPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [subs, setSubs] = useState<Subscription[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [tab, setTab] = useState<"subscriptions" | "notifications">("subscriptions");

  const [newName, setNewName] = useState("");
  const [newQuery, setNewQuery] = useState("");
  const [newType, setNewType] = useState("keyword");
  const [newFrequency, setNewFrequency] = useState("realtime");
  const [creating, setCreating] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const headers = getAuthHeaders();
    try {
      const [subsRes, notifsRes] = await Promise.all([
        fetch("/api/subscriptions", { headers }),
        fetch("/api/subscriptions/notifications/list", { headers }),
      ]);
      if (subsRes.ok) setSubs((await subsRes.json()).subscriptions ?? []);
      if (notifsRes.ok) setNotifications((await notifsRes.json()).notifications ?? []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!user) {
      router.push("/auth/login");
      return;
    }
    fetchData();
  }, [user, router, fetchData]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      const res = await fetch("/api/subscriptions", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify({ name: newName, query: newQuery, subscription_type: newType, frequency: newFrequency }),
      });
      if (res.ok) {
        setShowCreate(false);
        setNewName("");
        setNewQuery("");
        fetchData();
      }
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (subId: string) => {
    await fetch(`/api/subscriptions/${subId}`, { method: "DELETE", headers: getAuthHeaders() });
    fetchData();
  };

  const handleToggle = async (sub: Subscription) => {
    await fetch(`/api/subscriptions/${sub.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify({ is_active: !sub.is_active }),
    });
    fetchData();
  };

  const handleMarkRead = async (notifId: string) => {
    await fetch(`/api/subscriptions/notifications/${notifId}/read`, { method: "POST", headers: getAuthHeaders() });
    setNotifications((prev) => prev.map((n) => (n.id === notifId ? { ...n, is_read: true } : n)));
  };

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  if (!user) return null;

  return (
    <div className="min-h-screen bg-gray-50/50">
      <Navbar />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6">
        {/* Page header */}
        <div className="mb-6">
          <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center">
              <Bell className="w-4 h-4 text-white" />
            </div>
            订阅管理
          </h1>
          <p className="text-sm text-gray-400 mt-1">管理你的新闻订阅和通知</p>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 mb-6 bg-white rounded-xl border border-gray-200 p-1 w-fit">
          <button
            onClick={() => setTab("subscriptions")}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
              tab === "subscriptions"
                ? "bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-sm"
                : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
            }`}
          >
            我的订阅 ({subs.length})
          </button>
          <button
            onClick={() => setTab("notifications")}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 flex items-center gap-1.5 ${
              tab === "notifications"
                ? "bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-sm"
                : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
            }`}
          >
            通知
            {unreadCount > 0 && (
              <span className={`px-1.5 py-0.5 text-xs rounded-full font-semibold ${
                tab === "notifications" ? "bg-white/25 text-white" : "bg-red-500 text-white"
              }`}>
                {unreadCount}
              </span>
            )}
          </button>
        </div>

        {loading && (
          <div className="flex justify-center py-24">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          </div>
        )}

        {/* Subscriptions Tab */}
        {!loading && tab === "subscriptions" && (
          <div className="animate-fade-in">
            <button
              onClick={() => setShowCreate(!showCreate)}
              className="mb-4 flex items-center gap-1.5 px-4 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-sm font-medium rounded-xl hover:shadow-lg hover:shadow-blue-500/25 transition-all"
            >
              <Plus className="w-4 h-4" />
              新建订阅
            </button>

            {/* Create form */}
            {showCreate && (
              <form onSubmit={handleCreate} className="card card-elevated rounded-2xl p-5 mb-4 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-gray-900">新建订阅</h3>
                  <button
                    type="button"
                    onClick={() => setShowCreate(false)}
                    className="p-1 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-gray-500 mb-1.5 block">订阅名称</label>
                    <input
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      required
                      placeholder="例如：AI行业动态"
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 text-gray-900 bg-gray-50/50"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-500 mb-1.5 block">关键词/查询</label>
                    <input
                      value={newQuery}
                      onChange={(e) => setNewQuery(e.target.value)}
                      required
                      placeholder="例如：人工智能 大模型"
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 text-gray-900 bg-gray-50/50"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-gray-500 mb-1.5 block">类型</label>
                    <select
                      value={newType}
                      onChange={(e) => setNewType(e.target.value)}
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 text-gray-900 bg-gray-50/50"
                    >
                      <option value="keyword">关键词</option>
                      <option value="topic">话题</option>
                      <option value="event">事件</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-500 mb-1.5 block">推送频率</label>
                    <select
                      value={newFrequency}
                      onChange={(e) => setNewFrequency(e.target.value)}
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 text-gray-900 bg-gray-50/50"
                    >
                      <option value="realtime">实时</option>
                      <option value="daily">每日汇总</option>
                      <option value="weekly">每周汇总</option>
                    </select>
                  </div>
                </div>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-sm font-medium rounded-xl hover:shadow-md hover:shadow-blue-500/20 disabled:opacity-50 transition-all flex items-center gap-1.5"
                >
                  {creating && <Loader2 className="w-3 h-3 animate-spin" />}
                  创建
                </button>
              </form>
            )}

            {/* Subscription list */}
            {subs.length === 0 ? (
              <div className="text-center py-20 animate-fade-in">
                <div className="w-16 h-16 rounded-2xl bg-gray-100 flex items-center justify-center mx-auto mb-4">
                  <BellOff className="w-8 h-8 text-gray-300" />
                </div>
                <p className="text-gray-500 text-sm font-medium">暂无订阅</p>
                <p className="text-gray-400 text-xs mt-1">创建订阅后，系统会在有新动态时通知你</p>
              </div>
            ) : (
              <div className="space-y-3">
                {subs.map((sub) => (
                  <div
                    key={sub.id}
                    className={`card card-elevated rounded-2xl p-4 flex items-center justify-between transition-opacity ${
                      sub.is_active ? "" : "opacity-50"
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="text-sm font-semibold text-gray-900">{sub.name}</h3>
                        <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded-full">
                          {sub.subscription_type === "keyword" ? "关键词" : sub.subscription_type === "topic" ? "话题" : "事件"}
                        </span>
                        <span className="px-2 py-0.5 text-xs bg-blue-50 text-blue-600 rounded-full">
                          {sub.frequency === "realtime" ? "实时" : sub.frequency === "daily" ? "每日" : "每周"}
                        </span>
                      </div>
                      <p className="text-xs text-gray-400">查询：{sub.query}</p>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleToggle(sub)}
                        className={`p-2 rounded-lg transition-all ${
                          sub.is_active
                            ? "text-emerald-600 hover:bg-emerald-50"
                            : "text-gray-400 hover:bg-gray-50"
                        }`}
                        title={sub.is_active ? "暂停" : "启用"}
                      >
                        {sub.is_active ? <BellRing className="w-4 h-4" /> : <BellOff className="w-4 h-4" />}
                      </button>
                      <button
                        onClick={() => handleDelete(sub.id)}
                        className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all"
                        title="删除"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Notifications Tab */}
        {!loading && tab === "notifications" && (
          <div className="animate-fade-in">
            {notifications.length === 0 ? (
              <div className="text-center py-20">
                <div className="w-16 h-16 rounded-2xl bg-gray-100 flex items-center justify-center mx-auto mb-4">
                  <Bell className="w-8 h-8 text-gray-300" />
                </div>
                <p className="text-gray-500 text-sm">暂无通知</p>
              </div>
            ) : (
              <div className="space-y-2">
                {notifications.map((n) => (
                  <div
                    key={n.id}
                    className={`card rounded-xl p-4 transition-all ${
                      n.is_read ? "" : "border-blue-200 bg-blue-50/50"
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-900">{n.title}</p>
                        <p className="text-xs text-gray-500 mt-0.5">{n.body}</p>
                        <p className="text-xs text-gray-400 mt-1">
                          {new Date(n.created_at).toLocaleString("zh-CN")}
                        </p>
                      </div>
                      {!n.is_read && (
                        <button
                          onClick={() => handleMarkRead(n.id)}
                          className="text-xs text-blue-600 hover:text-blue-700 font-medium px-2 py-1 rounded-lg hover:bg-blue-100 transition-colors"
                        >
                          标为已读
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
