/**
 * Frontend analytics tracking SDK.
 *
 * Tracks user interactions (search, click, view, subscribe) and sends
 * them to the backend analytics endpoint. Events are batched and
 * debounced to avoid excessive API calls.
 */

type EventType = "search" | "click" | "view" | "subscribe";

interface TrackEvent {
  event_type: EventType;
  session_id: string;
  user_id?: string;
  query?: string;
  article_id?: string;
  position?: number;
  duration_ms?: number;
  metadata?: Record<string, unknown>;
}

let _sessionId: string | null = null;

function getSessionId(): string {
  if (_sessionId) return _sessionId;
  if (typeof window !== "undefined") {
    _sessionId = sessionStorage.getItem("analytics_session_id");
    if (!_sessionId) {
      _sessionId = `s_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      sessionStorage.setItem("analytics_session_id", _sessionId);
    }
  }
  return _sessionId ?? "unknown";
}

const eventQueue: TrackEvent[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;

async function flush(): Promise<void> {
  if (eventQueue.length === 0) return;
  const batch = eventQueue.splice(0, eventQueue.length);

  for (const event of batch) {
    try {
      await fetch("/api/analytics/track", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(event),
      });
    } catch {
      // Analytics failures are non-critical
    }
  }
}

function scheduleFlush(): void {
  if (flushTimer) return;
  flushTimer = setTimeout(() => {
    flushTimer = null;
    flush();
  }, 1000);
}

export function trackEvent(
  type: EventType,
  data: Omit<TrackEvent, "event_type" | "session_id"> = {}
): void {
  if (typeof window === "undefined") return;

  const event: TrackEvent = {
    event_type: type,
    session_id: getSessionId(),
    ...data,
  };
  eventQueue.push(event);
  scheduleFlush();
}

export function trackSearch(
  query: string,
  resultsCount: number,
  tookMs: number
): void {
  trackEvent("search", {
    query,
    metadata: { results_count: resultsCount, took_ms: tookMs },
  });
}

export function trackClick(
  query: string,
  articleId: string,
  position: number
): void {
  trackEvent("click", { query, article_id: articleId, position });
}

export function trackView(articleId: string, durationMs: number): void {
  trackEvent("view", { article_id: articleId, duration_ms: durationMs });
}

export function trackSubscribe(query: string): void {
  trackEvent("subscribe", { query });
}
