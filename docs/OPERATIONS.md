# 运维手册 / Operations Guide

## 快速启动

### 依赖服务

```bash
docker compose up -d
```

启动 Elasticsearch (8.x)、Qdrant、Redis。

### 后端

```bash
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env  # 编辑填入 ANTHROPIC_API_KEY
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:3000`。

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ANTHROPIC_API_KEY` | Claude API 密钥 | (必填) |
| `ES_URL` | Elasticsearch 地址 | `http://localhost:9200` |
| `QDRANT_HOST` | Qdrant 主机 | `localhost` |
| `REDIS_URL` | Redis 地址 | `redis://localhost:6379` |
| `JWT_SECRET` | JWT 签名密钥 | (生产环境必须修改) |
| `LOG_LEVEL` | 日志级别 | `INFO` |

完整列表见 `.env.example`。

---

## 监控

### 健康检查

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

### 系统状态

```bash
curl http://localhost:8000/api/stats
# {"total_articles": 1234, "sources_count": 21, "total_vectors": 1234}
```

### 在线指标

```bash
curl http://localhost:8000/api/analytics/metrics
```

返回：延迟 P50/P95/P99、搜索成功率、零结果率、重搜率、位置 CTR。

---

## 压力测试

```bash
# 搜索接口压测（50 QPS，60 秒）
python scripts/load_test.py --qps 50 --duration 60

# 健康检查压测（1000 QPS）
python scripts/load_test.py --qps 1000 --duration 30 --health-only
```

---

## 安全

### 速率限制

- 默认 60 请求/分钟/IP
- 突发额外 10 请求
- 超限返回 HTTP 429

### 输入过滤

- HTML 标签自动剥离
- 脚本注入模式检测
- Elasticsearch 查询注入防护
- 请求体大小限制 1MB

### 安全响应头

自动添加：`X-Content-Type-Options`、`X-Frame-Options`、`X-XSS-Protection`、`Referrer-Policy`、`Permissions-Policy`。

---

## 缓存

| 缓存类型 | TTL | 说明 |
|----------|-----|------|
| 搜索结果 | 5 分钟 | query + filters 为键 |
| AI 摘要 | 30 分钟 | query + article IDs 为键 |

### 查看缓存状态

```bash
curl http://localhost:8000/api/cache/stats
```

### 清除缓存

```bash
curl -X POST http://localhost:8000/api/cache/invalidate
```

---

## 数据采集

- 自动：每 15 分钟 RSS 轮询（通过 `RSS_FETCH_INTERVAL` 配置）
- 手动触发：`POST /api/ingest/trigger`
- 数据源：21 个 RSS 源（中英文主流媒体 + 科技媒体）

---

## A/B 测试

- 最多同时运行 3 组实验
- 流量分配：基于用户 ID 哈希的确定性分配
- 管理接口：`/api/ab-test/experiments`
- 统计显著性：Welch's t-test

---

## 故障排查

| 症状 | 检查 |
|------|------|
| 搜索无结果 | ES 是否有数据：`GET /api/stats` |
| 摘要生成失败 | 检查 `ANTHROPIC_API_KEY` 是否配置 |
| 向量搜索超时 | 检查 Qdrant 连接和集合状态 |
| 缓存不生效 | 检查 Redis 连接：`redis-cli ping` |
| 速率限制误触发 | 检查 Redis 中 `ratelimit:*` 键 |
