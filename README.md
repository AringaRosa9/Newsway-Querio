<h1 align="center">AI News Search</h1>

<p align="center">
  <strong>用 AI 让新闻搜索"搜得准、看得快、追得住"</strong>
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

## 什么是 AI News Search？

面向媒体人、分析师、研究者的 **AI 驱动新闻搜索引擎**。与传统新闻搜索不同，本产品支持：

- **自然语言提问** — 不再拼凑关键词，用日常语言直接提问
- **AI 综合摘要** — 基于多篇报道生成全局回答，附原文引用溯源
- **事件时间线** — 自动聚合同一事件的报道，生成发展脉络
- **实时订阅推送** — 订阅关键词或事件，有实质性新进展时即时通知

| 维度 | 传统新闻搜索 | AI News Search |
|---|---|---|
| 输入方式 | 关键词 | 自然语言提问 |
| 结果形态 | 链接列表 | AI 综合摘要 + 溯源链接 |
| 信息组织 | 按篇排列 | 按事件聚合 + 时间线 |
| 持续跟踪 | 反复手动搜索 | 订阅事件，自动推送 |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    用户端 · Next.js                              │
│         搜索 + 对话  │  事件时间线  │  订阅管理  │  筛选面板       │
└───────────────────────────┬─────────────────────────────────────┘
                            │ REST API
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   后端 · FastAPI                                 │
│                                                                 │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌────────────┐  │
│  │ Query    │  │ 混合检索引擎  │  │ AI 摘要  │  │ 事件追踪   │  │
│  │ 理解     │→│ BM25 + 向量  │→│ 生成     │  │ & 订阅     │  │
│  │ & 改写   │  │ + Re-Ranking │  │ & 引用   │  │ & 推送     │  │
│  └──────────┘  └──────────────┘  └──────────┘  └────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              数据采集 · Scrapy + RSSHub                   │   │
│  │         RSS 抓取  │  API 接入  │  清洗去重  │  定时调度    │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────┬──────────────┬──────────────┬───────────────────────────┘
       │              │              │
       ▼              ▼              ▼
┌────────────┐ ┌────────────┐ ┌────────────┐
│Elasticsearch│ │   Qdrant   │ │   Redis    │
│ 关键词索引  │ │  向量索引   │ │ 缓存/队列  │
└────────────┘ └────────────┘ └────────────┘
```

### 搜索数据流

```
新闻源 → RSS/API采集 → 清洗去重 → NLP处理 → BGE-M3向量化 → 入库(ES+Qdrant)
                                                                    ↓
用户提问 → 意图识别 → Query改写 → 双路召回(BM25+向量) → Re-Ranking → AI摘要 → 返回结果
              ↓          ↓                                                     ↑
         跨语言翻译   时间/实体/                                       Top-10 文档 +
         (中↔英)     意图推断                                         引用溯源链接
                                                                        ↓
                                                              多轮对话追问 (SSE 流式)
```

---

## 核心功能

### 智能搜索

自然语言输入搜索意图，系统自动进行意图识别和 Query 改写。支持中英文混合输入。

- **Query 理解**：提取关键实体、时间范围、搜索意图
- **混合检索**：BM25 关键词 + BGE-M3 语义向量双路召回，RRF 融合
- **AI Re-Ranking**：相关性(40%) + 时效性(25%) + 权威性(20%) + 多样性(15%) 多因子排序

### AI 摘要

基于搜索结果 Top-10 文档生成综合回答，附原文引用链接。

- 多角度呈现：事实概述、各方观点、发展趋势
- 信息溯源：每条摘要标注来源，可点击跳转原文
- 幻觉控制：事实准确率目标 ≥ 95%

### 事件追踪

自动将同一事件的多篇报道聚合为事件簇，生成时间线。

- 语义聚类识别同一事件的不同报道
- 事件时间线按时间顺序展示发展脉络
- 标注关键实体（人物、机构、地点）和情感走向

### 个性化订阅

订阅关键词、话题或事件，有实质性新进展时推送通知。

- 支持邮件日报/周报和实时推送两种模式
- 智能判断"实质性进展"，过滤重复内容
- 基于阅读历史构建兴趣画像，个性化排序

### 多轮对话式搜索

基于搜索结果进行多轮追问，流式输出实时响应。

- 上下文感知的多轮对话，连续追问不丢上下文
- SSE 流式输出，实时显示 AI 回答
- 对话历史管理，随时回顾之前的对话

### 跨语言检索

支持中英文互搜，打破语言壁垒获取全球新闻。

- 中文提问检索英文报道，英文提问检索中文新闻
- 基于多语言向量模型的语义对齐
- 查询自动翻译与结果融合排序

### 行业垂直搜索

针对金融、科技等垂直领域的专业化搜索能力。

- 行业术语识别与扩展
- 领域专属的权重调优
- 垂直领域专业数据源接入

### A/B 测试框架

内置实验平台，支持搜索策略的在线对比评估。

- 流量分桶、指标追踪、显著性检验
- 支持排序算法、摘要策略等多维度实验
- 实验报告自动生成

---

## 技术栈

| 层级 | 技术 | 用途 |
|---|---|---|
| 前端 | **Next.js** | SSR 搜索页面、SEO 优化 |
| 后端 | **FastAPI (Python)** | API 服务、业务逻辑 |
| 关键词检索 | **Elasticsearch 8.x** | BM25 全文检索 |
| 向量检索 | **Qdrant** | 语义向量存储与近邻搜索 |
| Embedding | **BGE-M3** | 中英多语言文本向量化 |
| Re-Ranking | **BGE-Reranker-v2** | 搜索结果精排 |
| LLM | **Claude API** | 摘要生成、对话、Query 理解 |
| 数据采集 | **Scrapy + RSSHub** | RSS/API 新闻抓取 |
| 缓存/队列 | **Redis** | 热门 Query 缓存、任务队列 |
| 安全 | **自研中间件** | 速率限制、CORS、请求校验 |
| 监控 | **Grafana + Prometheus** | 系统监控、评估看板 |

---

## 项目结构

```
ai-news-search/
├── backend/                    # FastAPI 后端服务
│   ├── main.py                 #   应用入口
│   ├── requirements.txt        #   Python 依赖
│   ├── api/
│   │   └── routes.py           #   API 路由定义
│   ├── core/
│   │   ├── config.py           #   配置管理
│   │   └── deps.py             #   依赖注入 (ES / Qdrant / Redis)
│   ├── auth/                   #   用户认证模块
│   │   ├── models.py           #   用户数据模型
│   │   ├── service.py          #   注册/登录/JWT 认证服务
│   │   └── routes.py           #   认证 API 路由
│   ├── ingestion/
│   │   ├── rss_fetcher.py      #   RSS 源抓取
│   │   ├── cleaner.py          #   正文提取与清洗
│   │   ├── dedup.py            #   SimHash + 语义去重
│   │   ├── sources.py          #   新闻源配置
│   │   ├── social.py           #   社交媒体监听 (Twitter/微博)
│   │   └── scheduler.py        #   定时采集调度
│   ├── search/
│   │   ├── query.py            #   Query 理解与改写
│   │   ├── retrieval.py        #   混合检索 (BM25 + 向量)
│   │   ├── ranking.py          #   AI Re-Ranking
│   │   ├── personalization.py  #   个性化排序
│   │   ├── indexer.py          #   索引管理
│   │   ├── crosslingual.py     #   跨语言检索 (中英互搜)
│   │   └── vertical.py         #   行业垂直搜索 (金融/科技)
│   ├── ai/
│   │   ├── embedding.py        #   BGE-M3 向量化
│   │   ├── summary.py          #   AI 摘要生成
│   │   ├── nlp.py              #   NLP 处理 (分类/实体/情感)
│   │   ├── event.py            #   事件聚合 (语义聚类 + 时间线)
│   │   ├── processor.py        #   AI 处理管道
│   │   ├── chat_routes.py      #   对话式搜索 API 路由
│   │   ├── dialogue.py         #   多轮对话管理
│   │   └── streaming.py        #   SSE 流式输出
│   ├── ab_test/                #   A/B 测试模块
│   │   ├── routes.py           #   实验 API 路由
│   │   └── service.py          #   分桶/指标/显著性检验
│   ├── cache/                  #   缓存模块
│   │   └── service.py          #   多级缓存策略
│   ├── security/               #   安全模块
│   │   └── middleware.py       #   速率限制/CORS/请求校验
│   ├── subscription/           #   订阅推送模块
│   │   ├── models.py           #   订阅/通知数据模型
│   │   ├── service.py          #   订阅管理 & 通知服务
│   │   └── routes.py           #   订阅 API 路由
│   ├── analytics/              #   埋点分析模块
│   │   ├── service.py          #   事件追踪 & 聚合
│   │   └── routes.py           #   分析 API 路由
│   └── evaluation/
│       ├── metrics.py          #   评估指标计算
│       ├── pipeline.py         #   离线评估流水线
│       ├── online.py           #   在线评估 (成功率/CTR/延迟)
│       └── sample_queries.json #   标注数据集
├── frontend/                   # Next.js 前端
│   ├── app/
│   │   ├── layout.tsx          #   全局布局 (含 AuthProvider)
│   │   ├── page.tsx            #   搜索主页
│   │   ├── globals.css         #   全局样式
│   │   ├── search/page.tsx     #   搜索结果页
│   │   ├── chat/page.tsx       #   AI 对话搜索页
│   │   ├── events/page.tsx     #   事件追踪页
│   │   ├── subscriptions/page.tsx # 订阅管理页
│   │   ├── robots.ts           #   SEO robots 配置
│   │   ├── sitemap.ts          #   SEO sitemap 生成
│   │   └── auth/
│   │       ├── login/page.tsx  #   登录页
│   │       └── register/page.tsx # 注册页
│   ├── components/
│   │   ├── Navbar.tsx          #   顶部导航栏
│   │   ├── SearchBox.tsx       #   搜索框
│   │   ├── SummaryCard.tsx     #   AI 摘要卡片
│   │   ├── ResultCard.tsx      #   搜索结果卡片 (含点击埋点)
│   │   ├── FilterPanel.tsx     #   多维度筛选面板
│   │   ├── Pagination.tsx      #   分页组件
│   │   ├── EventTimeline.tsx   #   事件时间线组件
│   │   └── UserMenu.tsx        #   用户菜单 (登录/注册/个人)
│   ├── public/
│   │   └── manifest.json       #   PWA 配置清单
│   └── lib/
│       ├── analytics.ts        #   前端埋点 SDK
│       └── auth.tsx            #   认证上下文 & Hooks
├── docs/                       # 项目文档
│   ├── API.md                 # API 接口文档
│   ├── OPERATIONS.md          # 运维部署指南
│   └── USER_GUIDE.md          # 用户使用手册
├── scripts/
│   ├── setup.sh               # 环境初始化脚本
│   ├── start_dev.sh           # 开发环境启动
│   ├── seed_data.py           # 测试数据填充
│   └── load_test.py           # 性能压力测试
├── tests/
│   ├── conftest.py            # 测试配置
│   ├── test_search.py         # 搜索功能测试
│   └── test_metrics.py        # 指标计算测试
├── docker-compose.yml         # 基础设施编排 (ES + Qdrant + Redis)
├── .env.example               # 环境变量模板
├── PRD.md                     # 产品需求文档
└── DEVPLAN.md                 # 开发计划
```

---

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose

### 1. 克隆项目

```bash
git clone <repo-url>
cd ai-news-search
```

### 2. 启动基础设施

```bash
# 一键拉起 Elasticsearch + Qdrant + Redis
docker compose up -d
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 Anthropic API Key
```

### 4. 启动后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:3000` 开始使用。

---

## 评估体系

本项目建立了离线 + 在线 + 人工三层评估体系，持续监控搜索质量。

### 离线评估（上线前）

| 指标 | 目标值 | 说明 |
|---|---|---|
| NDCG@10 | ≥ 0.75 | 前 10 条结果的排序质量 |
| Recall@50 | ≥ 0.85 | 相关文档的召回率 |
| MAP | ≥ 0.70 | 平均精确率 |
| MRR | ≥ 0.60 | 首个相关结果的排名位置 |
| 事实准确率 | ≥ 95% | AI 摘要无幻觉比例 |
| ROUGE-L | ≥ 0.45 | 摘要与参考文本的重叠度 |

### 在线评估（上线后）

| 指标 | 目标值 | 说明 |
|---|---|---|
| 搜索成功率 | ≥ 70% | 产生点击行为的搜索占比 |
| 零结果率 | ≤ 5% | 搜索无结果的 query 占比 |
| 二次搜索率 | ≤ 20% | 换词重搜的比例 |
| P95 响应时间 | ≤ 3s | 从搜索到返回的延迟 |
| NPS | ≥ 40 | 用户净推荐值 |

---

## 开发路线图

```
Phase 0 · MVP（第 1–6 周）✅ 已完成
├── ✅ 项目脚手架 (FastAPI + Next.js)
├── ✅ Docker 基础设施编排
├── ✅ 接入 20+ 核心新闻源
├── ✅ 混合检索 + AI Re-Ranking
├── ✅ AI 摘要生成 + 引用溯源
├── ✅ 搜索页 Web UI
└── ✅ 离线评估 Pipeline

Phase 1 · 体验增强（第 7–10 周）✅ 已完成
├── ✅ 事件聚合 & 时间线 (语义聚类 + 时间线 UI)
├── ✅ 用户系统 (注册/登录/JWT 认证/用户画像)
├── ✅ 个性化排序 (阅读历史 + 兴趣画像)
├── ✅ 关键词/话题/事件订阅 & 推送通知
├── ✅ 多维度筛选面板 (时间/来源/分类/情感/语言)
├── ✅ 前端埋点 SDK (搜索/点击/浏览/订阅行为追踪)
├── ✅ 在线评估 Pipeline (成功率/CTR/零结果率/延迟)
└── ✅ 社交媒体监听 (Twitter/微博 API 接入)

Phase 2 · 深度能力（第 11–16 周）✅ 已完成
├── ✅ 多轮对话式搜索 (SSE 流式输出 + 上下文管理)
├── ✅ 跨语言检索 (中英互搜、查询翻译、结果融合)
├── ✅ 行业垂直定制 (金融/科技领域专业化搜索)
├── ✅ A/B 测试框架 (分桶/指标追踪/显著性检验)
├── ✅ 安全中间件 (速率限制/CORS/请求校验)
├── ✅ 多级缓存策略 (热门 Query 缓存加速)
├── ✅ SEO 优化 (robots.ts / sitemap.ts)
├── ✅ PWA 支持 (manifest.json)
├── ✅ 项目文档 (API 文档 / 运维指南 / 用户手册)
└── ✅ 性能压测工具 (load_test.py)

Phase 3 · 规模化（规划中）
├── 移动端原生适配
├── 多租户 SaaS 支持
├── 分布式采集集群
└── 模型微调与私有化部署
```

---

## 许可证

[MIT](LICENSE)
