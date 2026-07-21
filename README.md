# AI News Search / AI ニュースサーチ

AI 驱动的新闻搜索引擎，支持自然语言查询、智能摘要和事件追踪。

An AI-powered news search engine with natural language querying, intelligent summarization, and event tracking.

AI を活用したニュース検索エンジン。自然言語クエリ、インテリジェント要約、イベントトラッキングに対応。

---

## 功能特性 / Features / 機能

### 智能搜索 / Intelligent Search / インテリジェント検索

- **自然语言查询** — 用日常语言提问，而非拼凑关键词
- **Natural Language Query** — Ask questions in everyday language instead of crafting keywords
- **自然言語クエリ** — キーワードの組み合わせではなく、日常の言葉で質問

### AI 摘要 / AI Summary / AI 要約

- **综合摘要** — 基于多篇报道生成全局视角的回答，附原文引用
- **Comprehensive Summary** — Generate holistic answers from multiple sources with citations
- **包括的な要約** — 複数の報道に基づいて全体像を回答し、出典を明記

### 事件追踪 / Event Tracking / イベントトラッキング

- **时间线** — 自动聚合同一事件的报道，生成发展脉络
- **Timeline** — Automatically aggregate reports on the same event into a chronological storyline
- **タイムライン** — 同一イベントの報道を自動集約し、時系列で展開

### 个性化订阅 / Personalized Alerts / パーソナライズ通知

- **实时推送** — 订阅关键词或话题，有新进展时即时通知
- **Real-time Alerts** — Subscribe to keywords or topics and get notified on new developments
- **リアルタイム通知** — キーワードやトピックを購読し、新しい動きがあれば即座に通知

---

## 技术栈 / Tech Stack / 技術スタック

| Layer | Technology |
|---|---|
| Search | Elasticsearch + Qdrant |
| Embedding | BGE-M3 |
| LLM | Claude API |
| Re-Ranking | BGE-Reranker-v2 |
| Backend | FastAPI (Python) |
| Frontend | Next.js |
| Data Ingestion | Scrapy + RSSHub |
| Monitoring | Grafana + Prometheus |

---

## 项目结构 / Project Structure / プロジェクト構成

```
ai-news-search/
├── backend/                # FastAPI 后端 / Backend / バックエンド
│   ├── api/                #   API 路由 / Routes / ルーティング
│   ├── core/               #   核心配置 / Core config / コア設定
│   ├── ingestion/          #   数据采集 / Data ingestion / データ取得
│   ├── search/             #   搜索引擎 / Search engine / 検索エンジン
│   ├── ai/                 #   AI 处理 / AI processing / AI 処理
│   └── evaluation/         #   效果评估 / Evaluation / 評価
├── frontend/               # Next.js 前端 / Frontend / フロントエンド
│   ├── app/                #   页面 / Pages / ページ
│   └── components/         #   组件 / Components / コンポーネント
├── scripts/                # 工具脚本 / Utility scripts / ユーティリティ
├── tests/                  # 测试 / Tests / テスト
├── docs/                   # 文档 / Documentation / ドキュメント
├── PRD.md                  # 产品需求文档 / Product Requirements / 製品要件
└── README.md
```

---

## 快速开始 / Quick Start / クイックスタート

### 环境要求 / Prerequisites / 前提条件

- Python 3.11+
- Node.js 20+
- Elasticsearch 8.x
- Qdrant 1.x

### 安装 / Installation / インストール

```bash
# 克隆项目 / Clone / クローン
git clone <repo-url>
cd ai-news-search

# 后端 / Backend / バックエンド
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 前端 / Frontend / フロントエンド
cd ../frontend
npm install
```

### 运行 / Run / 実行

```bash
# 启动后端 / Start backend / バックエンド起動
cd backend
uvicorn main:app --reload

# 启动前端 / Start frontend / フロントエンド起動
cd frontend
npm run dev
```

---

## 评估体系 / Evaluation / 評価体系

| Metric | Target | Description (中/EN/日) |
|---|---|---|
| NDCG@10 | ≥ 0.75 | 排序质量 / Ranking quality / ランキング品質 |
| Recall@50 | ≥ 0.85 | 召回率 / Recall rate / 再現率 |
| Factual Accuracy | ≥ 95% | 摘要准确率 / Summary accuracy / 要約正確性 |
| Search Success | ≥ 70% | 搜索成功率 / Search success rate / 検索成功率 |
| Response Time (P95) | ≤ 3s | 响应延迟 / Latency / レスポンス時間 |
| NPS | ≥ 40 | 用户满意度 / User satisfaction / ユーザー満足度 |

---

## 开发路线 / Roadmap / ロードマップ

- **Phase 0 (Week 1–6)** — MVP：混合检索 + AI 摘要 + Web 界面 / Hybrid search + AI summary + Web UI / ハイブリッド検索 + AI 要約 + Web UI
- **Phase 1 (Week 7–10)** — 事件追踪 + 订阅推送 + 评估看板 / Event tracking + Alerts + Eval dashboard / イベント追跡 + 通知 + 評価ダッシュボード
- **Phase 2 (Week 11+)** — 多轮对话 + 跨语言 + 行业定制 / Multi-turn dialogue + Cross-lingual + Vertical / マルチターン対話 + 多言語 + 業界特化

---

## 许可证 / License / ライセンス

MIT
