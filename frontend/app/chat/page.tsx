"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Send,
  Loader2,
  Sparkles,
  ExternalLink,
  Plus,
  MessageSquare,
  Trash2,
  ChevronLeft,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { useAuth, getAuthHeaders } from "@/lib/auth";

interface Citation {
  index: number;
  title: string;
  source: string;
  url: string;
}

interface SearchResult {
  id: string;
  title: string;
  source: string;
  url: string;
  published_at?: string;
  score?: number;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  search_results?: SearchResult[];
  timestamp: string;
}

interface SessionInfo {
  session_id: string;
  preview: string;
  created_at: string;
  message_count: number;
}

export default function ChatPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [showSidebar, setShowSidebar] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      const res = await fetch("/api/chat/sessions", {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions ?? []);
      }
    } catch {}
  };

  const createSession = async () => {
    try {
      const res = await fetch("/api/chat/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      });
      if (res.ok) {
        const data = await res.json();
        setSessionId(data.session_id);
        setMessages([]);
        loadSessions();
        return data.session_id;
      }
    } catch {}
    return null;
  };

  const loadSession = async (sid: string) => {
    setSessionId(sid);
    setShowSidebar(false);
    try {
      const res = await fetch(`/api/chat/sessions/${sid}`, {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setMessages(
          (data.messages ?? []).map((m: any, i: number) => ({
            id: `${sid}-${i}`,
            role: m.role,
            content: m.content,
            citations: m.citations,
            search_results: m.search_results,
            timestamp: m.timestamp ?? new Date().toISOString(),
          }))
        );
      }
    } catch {}
  };

  const deleteSession = async (sid: string) => {
    try {
      await fetch(`/api/chat/sessions/${sid}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });
      if (sessionId === sid) {
        setSessionId(null);
        setMessages([]);
      }
      loadSessions();
    } catch {}
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    let currentSessionId = sessionId;
    if (!currentSessionId) {
      currentSessionId = await createSession();
      if (!currentSessionId) return;
    }

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`/api/chat/sessions/${currentSessionId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify({ message: text }),
      });

      if (!res.ok) throw new Error("发送失败");
      const data = await res.json();

      const assistantMsg: Message = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: data.response,
        citations: data.citations,
        search_results: data.search_results,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      loadSessions();
    } catch {
      const errorMsg: Message = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: "抱歉，发生了错误。请稍后重试。",
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="min-h-screen bg-gray-50/50 flex flex-col">
      <Navbar />

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <aside
          className={`${
            showSidebar ? "translate-x-0" : "-translate-x-full"
          } lg:translate-x-0 fixed lg:relative z-40 w-72 h-[calc(100vh-56px)] bg-white border-r border-gray-100 flex flex-col transition-transform duration-200`}
        >
          <div className="p-3 border-b border-gray-100">
            <button
              onClick={createSession}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-sm font-medium rounded-xl hover:shadow-lg hover:shadow-blue-500/25 transition-all"
            >
              <Plus className="w-4 h-4" />
              新对话
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {sessions.map((s) => (
              <div
                key={s.session_id}
                className={`group flex items-center gap-2 px-3 py-2.5 rounded-xl cursor-pointer transition-all ${
                  sessionId === s.session_id
                    ? "bg-blue-50 text-blue-700"
                    : "hover:bg-gray-50 text-gray-600"
                }`}
                onClick={() => loadSession(s.session_id)}
              >
                <MessageSquare className="w-4 h-4 flex-shrink-0" />
                <span className="flex-1 text-sm truncate">
                  {s.preview || "新对话"}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteSession(s.session_id);
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-50 rounded transition-all"
                >
                  <Trash2 className="w-3.5 h-3.5 text-red-400" />
                </button>
              </div>
            ))}
            {sessions.length === 0 && (
              <p className="text-center text-sm text-gray-400 py-8">
                暂无对话记录
              </p>
            )}
          </div>
        </aside>

        {/* Overlay for mobile sidebar */}
        {showSidebar && (
          <div
            className="fixed inset-0 z-30 bg-black/20 lg:hidden"
            onClick={() => setShowSidebar(false)}
          />
        )}

        {/* Main Chat Area */}
        <main className="flex-1 flex flex-col min-w-0">
          {/* Mobile sidebar toggle */}
          <div className="lg:hidden flex items-center gap-2 px-4 py-2 border-b border-gray-100 bg-white">
            <button
              onClick={() => setShowSidebar(true)}
              className="p-1.5 hover:bg-gray-100 rounded-lg"
            >
              <ChevronLeft className="w-5 h-5 text-gray-500" />
            </button>
            <span className="text-sm text-gray-500">对话列表</span>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto">
            <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center py-20 text-center animate-fade-in">
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-100 to-indigo-100 flex items-center justify-center mb-4">
                    <Sparkles className="w-8 h-8 text-blue-500" />
                  </div>
                  <h2 className="text-xl font-bold text-gray-800 mb-2">
                    AI 新闻助手
                  </h2>
                  <p className="text-sm text-gray-500 max-w-md mb-8">
                    通过对话探索新闻资讯。我可以帮你搜索新闻、分析事件、追踪话题。
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
                    {[
                      "最近有哪些 AI 领域的重大进展？",
                      "分析一下今天的科技新闻",
                      "帮我追踪 OpenAI 的最新动态",
                      "总结本周的金融市场走势",
                    ].map((q) => (
                      <button
                        key={q}
                        onClick={() => {
                          setInput(q);
                          inputRef.current?.focus();
                        }}
                        className="text-left px-4 py-3 text-sm text-gray-600 bg-white border border-gray-200 rounded-xl hover:border-blue-300 hover:bg-blue-50/50 transition-all"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${
                    msg.role === "user" ? "justify-end" : "justify-start"
                  } animate-fade-in`}
                >
                  <div
                    className={`max-w-[85%] ${
                      msg.role === "user"
                        ? "bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-2xl rounded-br-md px-4 py-3"
                        : "bg-white border border-gray-100 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm"
                    }`}
                  >
                    <div
                      className={`text-sm leading-relaxed whitespace-pre-wrap ${
                        msg.role === "assistant" ? "text-gray-700" : ""
                      }`}
                    >
                      {msg.content}
                    </div>

                    {/* Search results inline */}
                    {msg.search_results && msg.search_results.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-gray-100 space-y-2">
                        <p className="text-xs font-semibold text-gray-500">
                          相关新闻
                        </p>
                        {msg.search_results.slice(0, 5).map((r, i) => (
                          <a
                            key={r.id || i}
                            href={r.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-start gap-2 p-2 rounded-lg hover:bg-gray-50 transition-colors group"
                          >
                            <span className="text-xs text-blue-500 font-medium mt-0.5">
                              [{i + 1}]
                            </span>
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-medium text-gray-700 group-hover:text-blue-600 line-clamp-1">
                                {r.title}
                              </p>
                              <p className="text-xs text-gray-400">
                                {r.source}
                              </p>
                            </div>
                            <ExternalLink className="w-3 h-3 text-gray-300 flex-shrink-0 mt-0.5" />
                          </a>
                        ))}
                      </div>
                    )}

                    {/* Citations */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-gray-100">
                        <p className="text-xs font-semibold text-gray-500 mb-1.5">
                          参考来源
                        </p>
                        <div className="space-y-1">
                          {msg.citations.map((c) => (
                            <a
                              key={c.index}
                              href={c.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-800"
                            >
                              <span className="font-medium">[{c.index}]</span>
                              <span className="truncate">{c.title}</span>
                              <span className="text-blue-400">
                                ({c.source})
                              </span>
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex justify-start animate-fade-in">
                  <div className="bg-white border border-gray-100 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm">
                    <div className="flex items-center gap-2 text-sm text-gray-500">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      正在思考...
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Input Area */}
          <div className="border-t border-gray-100 bg-white px-4 py-3">
            <div className="max-w-3xl mx-auto">
              <div className="flex items-end gap-2 bg-gray-50 rounded-2xl border border-gray-200 focus-within:border-blue-300 focus-within:ring-2 focus-within:ring-blue-500/10 px-4 py-2 transition-all">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="输入你的问题，按 Enter 发送..."
                  rows={1}
                  className="flex-1 bg-transparent text-sm text-gray-800 placeholder-gray-400 resize-none outline-none min-h-[24px] max-h-32 py-1"
                  style={{
                    height: "auto",
                    overflow: input.split("\n").length > 4 ? "auto" : "hidden",
                  }}
                  onInput={(e) => {
                    const el = e.target as HTMLTextAreaElement;
                    el.style.height = "auto";
                    el.style.height = Math.min(el.scrollHeight, 128) + "px";
                  }}
                />
                <button
                  onClick={sendMessage}
                  disabled={!input.trim() || loading}
                  className="flex-shrink-0 w-8 h-8 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed hover:shadow-lg hover:shadow-blue-500/25 transition-all"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
              <p className="text-center text-xs text-gray-400 mt-2">
                AI 助手基于新闻搜索结果回答，可能存在不准确之处
              </p>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
