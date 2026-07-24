# API Reference

> Base URL: `http://localhost:8000`  
> Interactive Swagger UI: `http://localhost:8000/docs`

---

## Search

### `GET /api/search`

Full hybrid search with AI-generated summary.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | Yes | Search query (min 1 char) |
| `time_from` | datetime | No | Filter articles from (ISO 8601) |
| `time_to` | datetime | No | Filter articles until (ISO 8601) |
| `source` | string | No | Filter by news source |
| `category` | string | No | Filter by category |
| `sentiment` | string | No | `positive` / `negative` / `neutral` |
| `language` | string | No | `zh` / `en` |
| `page` | int | No | Page number (default: 1) |
| `page_size` | int | No | Results per page (default: 20, max: 100) |

**Response:**
```json
{
  "query": "AI news",
  "parsed_query": { "intent": "EVENT", "keywords": [...], ... },
  "summary": {
    "summary_text": "...",
    "citations": [{ "index": 1, "title": "...", "source": "...", "url": "..." }],
    "generated_at": "2026-07-24T12:00:00Z"
  },
  "results": [{ "id": "...", "title": "...", "content": "...", ... }],
  "total": 42,
  "page": 1,
  "page_size": 20,
  "took_ms": 1234.56
}
```

### `GET /api/search/stream`

Streaming search with SSE for summary generation.

Same parameters as `/api/search`. Returns `text/event-stream`.

Events: `citations`, `chunk`, `done`, `error`.

### `GET /api/article/{article_id}`

Get a single article by ID.

---

## Chat (Multi-turn Dialogue)

### `POST /api/chat/sessions`

Create a new conversation session. Returns `session_id`.

### `GET /api/chat/sessions`

List recent sessions for the authenticated user.

### `GET /api/chat/sessions/{session_id}`

Get session details including message history.

### `POST /api/chat/sessions/{session_id}/messages`

Send a message and receive an AI response with search results.

| Field | Type | Description |
|-------|------|-------------|
| `message` | string | User message |

**Response:**
```json
{
  "response": "AI response text...",
  "follow_up_query": "resolved search query or null",
  "session_id": "...",
  "citations": [...],
  "search_results": [...]
}
```

### `DELETE /api/chat/sessions/{session_id}`

Delete a conversation session.

---

## Events

### `GET /api/events`

Aggregate recent articles into event clusters.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hours` | int | 72 | Look-back window (1–168) |

---

## Authentication

### `POST /api/auth/register`

| Field | Type | Required |
|-------|------|----------|
| `email` | string | Yes |
| `username` | string | Yes |
| `password` | string | Yes |

### `POST /api/auth/login`

| Field | Type | Required |
|-------|------|----------|
| `email` | string | Yes |
| `password` | string | Yes |

### `GET /api/auth/me`

Get current user profile. Requires `Authorization: Bearer <token>`.

### `PUT /api/auth/me`

Update user profile (username, interests, preferences).

---

## Subscriptions

All endpoints require authentication.

### `POST /api/subscriptions`

Create a subscription.

### `GET /api/subscriptions`

List user's subscriptions.

### `PUT /api/subscriptions/{id}`

Update a subscription.

### `DELETE /api/subscriptions/{id}`

Delete a subscription.

### `GET /api/subscriptions/notifications/list`

List notifications. Query param: `unread_only=true`.

### `POST /api/subscriptions/notifications/{id}/read`

Mark a notification as read.

---

## A/B Testing

### `POST /api/ab-test/experiments`

Create an experiment (requires auth).

### `GET /api/ab-test/experiments`

List all experiments.

### `GET /api/ab-test/experiments/{id}/assign`

Assign current user to a variant (requires auth).

### `POST /api/ab-test/experiments/{id}/metrics`

Record a metric observation (requires auth).

### `GET /api/ab-test/experiments/{id}/results`

Get experiment results with statistical significance.

---

## Analytics

### `POST /api/analytics/track`

Record a frontend event (search, click, view, subscribe).

### `GET /api/analytics/summary`

Get daily analytics summary.

### `GET /api/analytics/metrics`

Get online evaluation metrics (latency, CTR, search success rate).

---

## Operations

### `GET /health`

Health check.

### `GET /api/stats`

System statistics (article count, vector count, source count).

### `POST /api/ingest/trigger`

Manually trigger an ingestion cycle.

### `GET /api/eval/run`

Run offline evaluation against a test dataset.

---

## Rate Limits

- Default: 60 requests/minute per IP
- Burst: 10 additional requests allowed
- Response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- HTTP 429 when limit exceeded
