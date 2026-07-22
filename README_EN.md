<h1 align="center">AI News Search</h1>

<p align="center">
  <strong>AI-powered news search — find precisely, read quickly, track continuously</strong>
</p>

<p align="center">
  <a href="README.md">简体中文</a> | <a href="README_EN.md">English</a> | <a href="README_JA.md">日本語</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Node.js-20+-green?logo=node.js&logoColor=white" alt="Node.js">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Next.js-14+-black?logo=next.js&logoColor=white" alt="Next.js">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

---

## What is AI News Search?

An **AI-powered news search engine** for journalists, analysts, and researchers. Unlike traditional news search, this product offers:

- **Natural Language Queries** — Ask questions in everyday language instead of crafting keywords
- **AI-Generated Summaries** — Comprehensive answers synthesized from multiple sources with citations
- **Event Timelines** — Automatic aggregation of reports on the same event into a chronological storyline
- **Real-time Alerts** — Subscribe to keywords or events and get notified on substantive new developments

| Aspect | Traditional News Search | AI News Search |
|---|---|---|
| Input | Keywords | Natural language questions |
| Results | List of links | AI summary + source links |
| Organization | Per-article listing | Event-based aggregation + timeline |
| Tracking | Repeated manual searches | Subscribe and get auto-notified |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Frontend · Next.js                            │
│        Search + Chat  │  Event Timeline  │  Alerts  │  Filters  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ REST API
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Backend · FastAPI                             │
│                                                                 │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌────────────┐  │
│  │ Query    │  │Hybrid Search │  │ AI       │  │ Event      │  │
│  │ Under-   │→│ BM25+Vector  │→│ Summary  │  │ Tracking   │  │
│  │ standing │  │ +Re-Ranking  │  │ +Citing  │  │ & Alerts   │  │
│  └──────────┘  └──────────────┘  └──────────┘  └────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │            Data Ingestion · Scrapy + RSSHub               │   │
│  │       RSS Fetching │ API │ Cleaning & Dedup │ Scheduler   │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────┬──────────────┬──────────────┬───────────────────────────┘
       │              │              │
       ▼              ▼              ▼
┌────────────┐ ┌────────────┐ ┌────────────┐
│Elasticsearch│ │   Qdrant   │ │   Redis    │
│Keyword Index│ │Vector Index│ │Cache/Queue │
└────────────┘ └────────────┘ └────────────┘
```

### Search Data Flow

```
News Sources → RSS/API Fetch → Clean & Dedup → NLP → BGE-M3 Embedding → Store (ES + Qdrant)
                                                                              ↓
User Query → Intent Detection → Query Rewrite → Dual Recall (BM25+Vector) → Re-Rank → AI Summary → Response
                                    ↓                                                      ↑
                             Time / Entity /                                       Top-10 docs +
                             Intent Inference                                      Citation links
```

---

## Key Features

### Intelligent Search

Natural language input with automatic intent detection and query rewriting. Supports mixed Chinese-English input.

- **Query Understanding**: Extracts key entities, time ranges, and search intent
- **Hybrid Retrieval**: BM25 keyword + BGE-M3 semantic vector dual-recall, fused via RRF
- **AI Re-Ranking**: Multi-factor ranking — relevance (40%) + recency (25%) + authority (20%) + diversity (15%)

### AI Summary

Generates comprehensive answers from the top-10 retrieved documents, with source citations.

- Multi-perspective presentation: factual overview, various viewpoints, development trends
- Source tracing: each summary includes clickable source links
- Hallucination control: factual accuracy target ≥ 95%

### Event Tracking

Automatically clusters multiple reports about the same event and generates timelines.

- Semantic clustering to identify different reports about the same event
- Chronological timeline showing event progression
- Key entity annotations (people, organizations, locations) and sentiment trends

### Personalized Alerts

Subscribe to keywords, topics, or events — get notified when there's a substantive new development.

- Email digest (daily/weekly) and real-time push notification modes
- Smart filtering of duplicate/non-substantive content
- Interest profile built from reading history for personalized ranking

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | **Next.js** | SSR search pages, SEO optimization |
| Backend | **FastAPI (Python)** | API service, business logic |
| Keyword Search | **Elasticsearch 8.x** | BM25 full-text retrieval |
| Vector Search | **Qdrant** | Semantic vector storage & ANN search |
| Embedding | **BGE-M3** | Multilingual text embedding |
| Re-Ranking | **BGE-Reranker-v2** | Search result re-ranking |
| LLM | **Claude API** | Summary generation, dialogue, query understanding |
| Data Ingestion | **Scrapy + RSSHub** | RSS/API news fetching |
| Cache / Queue | **Redis** | Hot query caching, task queue |
| Monitoring | **Grafana + Prometheus** | System monitoring, evaluation dashboards |

---

## Project Structure

```
ai-news-search/
├── backend/                    # FastAPI backend service
│   ├── main.py                 #   App entry point
│   ├── api/
│   │   └── routes.py           #   API route definitions
│   ├── core/
│   │   ├── config.py           #   Configuration management
│   │   └── deps.py             #   Dependency injection (ES / Qdrant / Redis)
│   ├── auth/                   #   Authentication module
│   │   ├── models.py           #   User data models
│   │   ├── service.py          #   Register / Login / JWT auth service
│   │   └── routes.py           #   Auth API routes
│   ├── ingestion/
│   │   ├── rss_fetcher.py      #   RSS feed fetcher
│   │   ├── cleaner.py          #   Content extraction & cleaning
│   │   ├── dedup.py            #   SimHash + semantic dedup
│   │   ├── sources.py          #   News source configuration
│   │   ├── social.py           #   Social media monitoring (Twitter / Weibo)
│   │   └── scheduler.py        #   Scheduled fetch orchestration
│   ├── search/
│   │   ├── query.py            #   Query understanding & rewriting
│   │   ├── retrieval.py        #   Hybrid retrieval (BM25 + vector)
│   │   ├── ranking.py          #   AI re-ranking
│   │   ├── personalization.py  #   Personalized ranking
│   │   └── indexer.py          #   Index management
│   ├── ai/
│   │   ├── embedding.py        #   BGE-M3 vectorization
│   │   ├── summary.py          #   AI summary generation
│   │   ├── nlp.py              #   NLP pipeline (classification / NER / sentiment)
│   │   ├── event.py            #   Event aggregation (semantic clustering + timeline)
│   │   └── processor.py        #   AI processing pipeline
│   ├── subscription/           #   Subscription & push module
│   │   ├── models.py           #   Subscription / notification models
│   │   ├── service.py          #   Subscription management & notifications
│   │   └── routes.py           #   Subscription API routes
│   ├── analytics/              #   Analytics tracking module
│   │   ├── service.py          #   Event tracking & aggregation
│   │   └── routes.py           #   Analytics API routes
│   └── evaluation/
│       ├── metrics.py          #   Evaluation metric computation
│       ├── pipeline.py         #   Offline evaluation pipeline
│       ├── online.py           #   Online evaluation (success rate / CTR / latency)
│       └── sample_queries.json #   Annotated evaluation dataset
├── frontend/                   # Next.js frontend
│   ├── app/
│   │   ├── layout.tsx          #   Global layout (with AuthProvider)
│   │   ├── page.tsx            #   Search home page
│   │   ├── search/page.tsx     #   Search results page
│   │   ├── events/page.tsx     #   Event tracking page
│   │   ├── subscriptions/page.tsx # Subscription management page
│   │   └── auth/
│   │       ├── login/page.tsx  #   Login page
│   │       └── register/page.tsx # Register page
│   ├── components/
│   │   ├── SearchBox.tsx       #   Search input
│   │   ├── SummaryCard.tsx     #   AI summary card
│   │   ├── ResultCard.tsx      #   Search result card (with click tracking)
│   │   ├── FilterPanel.tsx     #   Multi-dimensional filter panel
│   │   ├── Pagination.tsx      #   Pagination
│   │   ├── EventTimeline.tsx   #   Event timeline component
│   │   └── UserMenu.tsx        #   User menu (login / register / profile)
│   └── lib/
│       ├── analytics.ts        #   Frontend analytics SDK
│       └── auth.tsx            #   Auth context & hooks
├── scripts/
│   ├── setup.sh               # Environment setup script
│   ├── start_dev.sh           # Dev environment launcher
│   └── seed_data.py           # Test data seeder
├── tests/
│   ├── conftest.py            # Test configuration
│   ├── test_search.py         # Search feature tests
│   └── test_metrics.py        # Metric computation tests
├── docker-compose.yml         # Infrastructure (ES + Qdrant + Redis)
├── .env.example               # Environment variable template
├── PRD.md                     # Product Requirements Document
└── DEVPLAN.md                 # Development Plan
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose

### 1. Clone the Repository

```bash
git clone <repo-url>
cd ai-news-search
```

### 2. Start Infrastructure

```bash
# Spin up Elasticsearch + Qdrant + Redis
docker compose up -d
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env and fill in your Anthropic API Key
```

### 4. Start the Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### 5. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` to start using the application.

---

## Evaluation System

The project implements a three-tier evaluation framework — offline, online, and manual — for continuous search quality monitoring.

### Offline Evaluation (Pre-launch)

| Metric | Target | Description |
|---|---|---|
| NDCG@10 | ≥ 0.75 | Ranking quality of the top 10 results |
| Recall@50 | ≥ 0.85 | Recall rate of relevant documents |
| MAP | ≥ 0.70 | Mean average precision |
| MRR | ≥ 0.60 | Position of the first relevant result |
| Factual Accuracy | ≥ 95% | Percentage of hallucination-free AI summaries |
| ROUGE-L | ≥ 0.45 | Summary overlap with reference texts |

### Online Evaluation (Post-launch)

| Metric | Target | Description |
|---|---|---|
| Search Success Rate | ≥ 70% | Searches that result in user clicks |
| Zero-result Rate | ≤ 5% | Queries that return no results |
| Re-search Rate | ≤ 20% | Sessions where the user reformulates |
| P95 Latency | ≤ 3s | End-to-end search response time |
| NPS | ≥ 40 | Net Promoter Score |

---

## Roadmap

```
Phase 0 · MVP (Weeks 1–6) ✅ Complete
├── ✅ Project scaffolding (FastAPI + Next.js)
├── ✅ Docker infrastructure orchestration
├── ✅ Connect 20+ core news sources
├── ✅ Hybrid retrieval + AI re-ranking
├── ✅ AI summary generation + citations
├── ✅ Search web UI
└── ✅ Offline evaluation pipeline

Phase 1 · Enhanced Experience (Weeks 7–10) ✅ Complete
├── ✅ Event aggregation & timeline (semantic clustering + timeline UI)
├── ✅ User system (register / login / JWT auth / user profiles)
├── ✅ Personalized ranking (reading history + interest profiles)
├── ✅ Keyword / topic / event subscription & push notifications
├── ✅ Multi-dimensional filter panel (time / source / category / sentiment / language)
├── ✅ Frontend analytics SDK (search / click / view / subscribe tracking)
├── ✅ Online evaluation pipeline (success rate / CTR / zero-result rate / latency)
└── ✅ Social media monitoring (Twitter / Weibo API integration)

Phase 2 · Advanced Capabilities (Weeks 11–16)
├── Multi-turn conversational search
├── Cross-lingual retrieval (Chinese ↔ English)
├── Vertical industry customization (Finance / Tech)
├── A/B testing framework
└── Mobile responsive design
```

---

## License

[MIT](LICENSE)
