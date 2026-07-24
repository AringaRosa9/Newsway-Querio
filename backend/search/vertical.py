"""Industry vertical search module.

Provides vertical-specific configuration, query classification, result
re-scoring, and entity extraction for the Finance and Tech verticals.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_DETECT_THRESHOLD = 3


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class VerticalConfig:
    id: str
    name: str
    terminology: dict[str, list[str]]
    boost_sources: dict[str, float]
    ranking_weights: dict[str, float]
    entity_patterns: list[str]


# ---------------------------------------------------------------------------
# Built-in verticals
# ---------------------------------------------------------------------------

VERTICALS: dict[str, VerticalConfig] = {
    "finance": VerticalConfig(
        id="finance",
        name="金融财经",
        terminology={
            "stock_market": [
                "股票", "股市", "A股", "港股", "美股", "沪深", "上证", "深证",
                "创业板", "科创板", "新三板", "纳斯达克", "纽交所", "道琼斯",
                "标普500", "S&P", "Dow", "NASDAQ", "NYSE", "IPO", "上市",
                "退市", "增发", "配股", "分红", "股息", "市值", "市盈率",
                "PE", "PB", "ROE", "EPS", "做空", "做多", "牛市", "熊市",
                "大盘", "蓝筹", "白马股", "成长股", "价值股", "ETF", "指数",
            ],
            "bonds_and_rates": [
                "债券", "国债", "企业债", "可转债", "债券市场", "收益率",
                "利率", "加息", "降息", "基准利率", "联邦基金利率",
                "LPR", "MLF", "逆回购", "公开市场操作", "货币政策",
                "quantitative easing", "QE", "tapering", "yield curve",
                "bond yield", "treasury", "T-bill", "T-bond",
            ],
            "funds_and_assets": [
                "基金", "公募基金", "私募基金", "对冲基金", "养老基金",
                "主权财富基金", "风险投资", "VC", "PE", "私募股权",
                "资产管理", "AUM", "净值", "仓位", "配置", "投资组合",
                "portfolio", "hedge fund", "mutual fund", "REITs", "SPAC",
            ],
            "macro_indicators": [
                "GDP", "CPI", "PPI", "PMI", "通胀", "通货膨胀", "通缩",
                "失业率", "就业", "非农就业", "NFP", "贸易差额", "经常账户",
                "外汇储备", "汇率", "人民币", "美元", "欧元", "日元",
                "英镑", "港币", "USD", "CNY", "CNH", "EUR", "JPY", "GBP",
                "外储", "经济增长", "衰退", "recession", "stagflation",
                "inflation", "deflation", "fiscal policy", "fiscal deficit",
            ],
            "institutions": [
                "央行", "中国人民银行", "美联储", "Fed", "FOMC", "欧央行",
                "ECB", "日本央行", "BOJ", "英格兰银行", "BOE", "国际货币基金组织",
                "IMF", "世界银行", "World Bank", "BIS", "SEC", "CFTC",
                "证监会", "银保监会", "外管局", "SAFE", "财政部", "发改委",
                "高盛", "摩根大通", "摩根士丹利", "花旗", "美银", "瑞银",
                "Goldman Sachs", "JPMorgan", "Morgan Stanley", "Citigroup",
                "BlackRock", "Vanguard", "Fidelity",
            ],
            "financial_instruments": [
                "期货", "期权", "衍生品", "远期合约", "互换", "掉期",
                "CDS", "MBS", "ABS", "CLO", "CDO", "杠杆", "融资融券",
                "做空", "卖空", "保证金", "margin", "futures", "options",
                "derivatives", "swap", "leverage", "short selling",
            ],
            "corporate_finance": [
                "并购", "M&A", "收购", "重组", "分拆", "破产", "重整",
                "营收", "净利润", "毛利率", "息税前利润", "EBITDA",
                "自由现金流", "FCF", "负债率", "资产负债表", "财报",
                "季报", "年报", "业绩", "盈利", "亏损", "减值",
                "merger", "acquisition", "restructuring", "bankruptcy",
                "revenue", "earnings", "profit", "loss", "guidance",
            ],
            "crypto_and_fintech": [
                "加密货币", "比特币", "Bitcoin", "BTC", "以太坊", "Ethereum",
                "ETH", "区块链", "blockchain", "DeFi", "NFT", "Web3",
                "稳定币", "USDT", "USDC", "数字货币", "CBDC", "数字人民币",
                "e-CNY", "支付宝", "微信支付", "金融科技", "fintech",
            ],
        },
        boost_sources={
            "Bloomberg": 0.95,
            "Financial Times": 0.95,
            "财新": 0.92,
            "财新网": 0.92,
            "Wall Street Journal": 0.93,
            "Reuters": 0.90,
            "第一财经": 0.88,
            "界面新闻": 0.82,
            "证券时报": 0.85,
            "上海证券报": 0.85,
            "中国证券报": 0.85,
            "The Economist": 0.92,
            "Barron's": 0.88,
            "MarketWatch": 0.82,
            "CNBC": 0.80,
        },
        ranking_weights={
            "relevance": 0.35,
            "freshness": 0.30,
            "authority": 0.25,
            "diversity": 0.10,
        },
        entity_patterns=[
            # US stock tickers: $AAPL, $MSFT, $TSLA (1-5 uppercase letters)
            r"\$[A-Z]{1,5}\b",
            # A-share tickers: 600519.SH, 000858.SZ, 300750.SZ
            r"\b\d{6}\.[A-Z]{2}\b",
            # HK stock: 0700.HK, 9988.HK
            r"\b\d{4}\.HK\b",
            # Currency pairs: USD/CNY, EUR/USD, GBP/JPY
            r"\b[A-Z]{3}/[A-Z]{3}\b",
            # Interest rate percentages with basis points: 25bp, 50bps
            r"\b\d+(?:\.\d+)?\s*(?:bp|bps|basis points?)\b",
            # Percentage moves with sign: +3.5%, -2.1%
            r"[+-]\d+(?:\.\d+)?%",
            # Plain percentages in financial context
            r"\b\d+(?:\.\d+)?%(?!\w)",
            # Price levels: $150.25, ¥1500
            r"[$¥€£]\s*\d[\d,]*(?:\.\d{1,4})?\b",
        ],
    ),

    "tech": VerticalConfig(
        id="tech",
        name="科技互联网",
        terminology={
            "ai_and_ml": [
                "人工智能", "AI", "机器学习", "ML", "深度学习", "神经网络",
                "大模型", "LLM", "大语言模型", "生成式AI", "GenAI",
                "ChatGPT", "GPT-4", "GPT-4o", "GPT-5", "Claude", "Gemini",
                "Llama", "Mistral", "文心一言", "通义千问", "混元",
                "Kimi", "豆包", "讯飞星火", "智谱", "GLM",
                "强化学习", "RLHF", "fine-tuning", "RAG",
                "transformer", "attention", "diffusion model", "stable diffusion",
                "Midjourney", "Sora", "AGI", "通用人工智能",
                "多模态", "multimodal", "embedding", "向量数据库",
                "prompt engineering", "inference", "training",
            ],
            "chips_and_hardware": [
                "芯片", "半导体", "CPU", "GPU", "NPU", "TPU", "SoC",
                "英伟达", "NVIDIA", "AMD", "英特尔", "Intel", "高通",
                "Qualcomm", "博通", "Broadcom", "台积电", "TSMC",
                "三星", "Samsung", "SK海力士", "美光", "Micron",
                "光刻机", "ASML", "EUV", "先进制程", "7nm", "5nm", "3nm",
                "HBM", "显存", "DRAM", "NAND", "存储芯片", "功耗",
                "算力", "算力集群", "H100", "H200", "A100", "GB200",
                "国产芯片", "华为", "海思", "鲲鹏", "昇腾", "龙芯",
                "RISC-V", "ARM", "x86", "supply chain", "封装",
            ],
            "cloud_and_infrastructure": [
                "云计算", "cloud computing", "AWS", "Azure", "GCP",
                "阿里云", "腾讯云", "华为云", "百度智能云", "字节云",
                "数据中心", "data center", "服务器", "容器", "Docker",
                "Kubernetes", "K8s", "微服务", "serverless", "边缘计算",
                "CDN", "负载均衡", "数据库", "分布式系统",
                "OpenAI", "Anthropic", "Google DeepMind", "Meta AI",
                "算力租赁", "GPU集群", "inference cost",
            ],
            "software_and_dev": [
                "开源", "open source", "GitHub", "GitLab", "API",
                "SDK", "框架", "framework", "Python", "JavaScript",
                "TypeScript", "Rust", "Go", "Java", "C++",
                "React", "Vue", "Node.js", "FastAPI", "Django",
                "DevOps", "CI/CD", "agile", "软件工程", "代码",
                "编程", "算法", "数据结构", "操作系统", "Linux",
                "Android", "iOS", "跨平台", "低代码", "no-code",
            ],
            "internet_and_platforms": [
                "互联网", "平台", "社交媒体", "电商", "直播", "短视频",
                "抖音", "TikTok", "微信", "WeChat", "微博", "Weibo",
                "淘宝", "京东", "拼多多", "美团", "滴滴", "字节跳动",
                "Meta", "Facebook", "Instagram", "YouTube", "Twitter",
                "X", "LinkedIn", "Snapchat", "Reddit", "Discord",
                "苹果", "Apple", "谷歌", "Google", "微软", "Microsoft",
                "亚马逊", "Amazon", "特斯拉", "Tesla", "SpaceX",
                "月活", "DAU", "MAU", "用户增长", "变现", "广告",
                "推荐算法", "信息流", "隐私", "数据安全",
            ],
            "emerging_tech": [
                "自动驾驶", "autonomous driving", "电动车", "EV",
                "机器人", "robotics", "人形机器人", "humanoid",
                "量子计算", "quantum computing", "元宇宙", "metaverse",
                "AR", "VR", "XR", "混合现实", "MR", "空间计算",
                "Apple Vision Pro", "智能硬件", "IoT", "物联网",
                "5G", "6G", "卫星互联网", "Starlink", "航天", "商业航天",
                "生物科技", "biotech", "基因编辑", "CRISPR",
            ],
            "tech_business": [
                "估值", "独角兽", "unicorn", "融资", "A轮", "B轮", "C轮",
                "Pre-IPO", "上市", "纳斯达克", "裁员", "layoff",
                "创业", "startup", "加速器", "孵化器", "硅谷",
                "中关村", "张江", "深圳湾", "科技园",
                "出海", "全球化", "反垄断", "监管", "合规",
                "数据隐私", "GDPR", "网络安全", "cybersecurity",
                "黑客", "漏洞", "勒索软件", "ransomware",
            ],
        },
        boost_sources={
            "TechCrunch": 0.92,
            "The Verge": 0.90,
            "Ars Technica": 0.88,
            "36氪": 0.88,
            "Hacker News": 0.85,
            "虎嗅": 0.85,
            "钛媒体": 0.83,
            "MIT Technology Review": 0.92,
            "Wired": 0.88,
            "CNBC Tech": 0.82,
            "Bloomberg Technology": 0.90,
            "Reuters Technology": 0.88,
            "InfoQ": 0.82,
            "机器之心": 0.80,
            "量子位": 0.80,
        },
        ranking_weights={
            "relevance": 0.45,
            "freshness": 0.20,
            "authority": 0.20,
            "diversity": 0.15,
        },
        entity_patterns=[
            # Semantic version numbers: v1.2.3, v2.0, 1.0.0
            r"\bv?\d+\.\d+(?:\.\d+)?(?:-[a-zA-Z0-9]+)?\b",
            # Model version strings: GPT-4, GPT-4o, Claude-3, Llama-3.1
            r"\b(?:GPT|Claude|Gemini|Llama|Mistral|Qwen|GLM|Phi|Falcon|Grok)"
            r"-\d+(?:\.\d+)?(?:[a-zA-Z]*)?\b",
            # GitHub repositories: org/repo (word chars and hyphens, slash separated)
            r"\b[A-Za-z0-9_-]{1,39}/[A-Za-z0-9_.-]{1,100}\b",
            # Tech product names with numbers: iPhone 16, Pixel 9, RTX 4090
            r"\b(?:iPhone|iPad|MacBook|iMac|Mac Pro|Mac Mini|Apple Watch"
            r"|Pixel|Galaxy|Surface|ThinkPad"
            r"|RTX|GTX|RX|Radeon|GeForce"
            r"|H\d00|A\d00|GB\d00)\s*\d+\w*\b",
            # Package names: @scope/package, package-name
            r"@[a-z0-9-]+/[a-z0-9-]+",
            # Acronyms commonly used in tech (3-6 uppercase letters)
            r"\b[A-Z]{3,6}\b",
            # URL-like tech identifiers: api.example.com, npm package refs
            r"\b[a-z][a-z0-9-]*\.[a-z]{2,4}/[^\s]{0,40}",
        ],
    ),
}


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def get_vertical_config(vertical_id: str) -> VerticalConfig | None:
    return VERTICALS.get(vertical_id)


def list_verticals() -> list[dict]:
    return [{"id": v.id, "name": v.name} for v in VERTICALS.values()]


def detect_vertical(query: str, parsed_query: dict | None = None) -> str | None:
    """Score a query against each vertical's terminology.

    Returns the vertical id whose term matches exceed *_DETECT_THRESHOLD*,
    or None if no vertical reaches that threshold.  When two verticals tie,
    the one with the higher score wins.
    """
    query_lower = query.lower()

    combined_text = query_lower
    if parsed_query:
        kws = parsed_query.get("keywords", [])
        entities = parsed_query.get("entities", [])
        combined_text = query_lower + " " + " ".join(kws + entities).lower()

    scores: dict[str, int] = {}

    for vid, config in VERTICALS.items():
        score = 0
        for terms in config.terminology.values():
            for term in terms:
                term_lower = term.lower()
                # Use word-boundary matching for short all-ASCII terms
                if re.match(r"^[a-z0-9]{1,4}$", term_lower):
                    if re.search(r"\b" + re.escape(term_lower) + r"\b", combined_text):
                        score += 1
                else:
                    if term_lower in combined_text:
                        score += 1
        scores[vid] = score

    best_id = max(scores, key=lambda k: scores[k])
    if scores[best_id] >= _DETECT_THRESHOLD:
        return best_id
    return None


def apply_vertical_boost(results: list[dict], vertical_id: str) -> list[dict]:
    """Re-score and re-sort results using vertical-specific weights and source boosts.

    Reads existing ``ranking_factors`` produced by :func:`search.ranking.rerank`
    and recomputes ``final_score`` with the vertical's weight overrides and
    source authority overrides.  Falls back to the global ``final_score`` when
    ``ranking_factors`` is absent.
    """
    config = VERTICALS.get(vertical_id)
    if config is None:
        logger.warning("Unknown vertical id: %s", vertical_id)
        return results

    weights = config.ranking_weights
    w_rel = weights.get("relevance", 0.40)
    w_fresh = weights.get("freshness", 0.25)
    w_auth = weights.get("authority", 0.20)
    w_div = weights.get("diversity", 0.15)

    boosted: list[dict] = []
    for result in results:
        doc = dict(result)
        factors = doc.get("ranking_factors")
        if factors is None:
            boosted.append(doc)
            continue

        relevance = factors.get("relevance_score", 0.0)
        freshness = factors.get("freshness_score", 0.5)
        diversity = 1.0 - factors.get("diversity_penalty", 0.0)

        source = doc.get("source", "")
        authority = _resolve_authority(source, config)

        final_score = (
            w_rel * relevance
            + w_fresh * freshness
            + w_auth * authority
            + w_div * diversity
        )

        doc["final_score"] = final_score
        doc["ranking_factors"] = dict(factors, authority_score=authority)
        doc["vertical_id"] = vertical_id
        boosted.append(doc)

    boosted.sort(key=lambda d: d.get("final_score", 0.0), reverse=True)
    return boosted


def _resolve_authority(source: str, config: VerticalConfig) -> float:
    """Return authority score, preferring vertical-specific overrides."""
    if not source:
        return 0.50
    if source in config.boost_sources:
        return config.boost_sources[source]
    source_lower = source.lower()
    for key, score in config.boost_sources.items():
        if key.lower() in source_lower or source_lower in key.lower():
            return score
    return 0.50


def extract_vertical_entities(text: str, vertical_id: str) -> list[dict]:
    """Extract domain-specific entities from *text* using the vertical's regex patterns.

    Returns a list of dicts with ``text`` and ``type`` keys.  The entity type
    label is derived from a human-readable description of the matching pattern.
    """
    config = VERTICALS.get(vertical_id)
    if config is None:
        logger.warning("Unknown vertical id: %s", vertical_id)
        return []

    _PATTERN_LABELS: dict[str, dict[str, str]] = {
        "finance": {
            r"\$[A-Z]{1,5}\b": "stock_ticker",
            r"\b\d{6}\.[A-Z]{2}\b": "stock_ticker",
            r"\b\d{4}\.HK\b": "stock_ticker",
            r"\b[A-Z]{3}/[A-Z]{3}\b": "currency_pair",
            r"\b\d+(?:\.\d+)?\s*(?:bp|bps|basis points?)\b": "basis_points",
            r"[+-]\d+(?:\.\d+)?%": "percentage_change",
            r"\b\d+(?:\.\d+)?%(?!\w)": "percentage",
            r"[$¥€£]\s*\d[\d,]*(?:\.\d{1,4})?\b": "price",
        },
        "tech": {
            r"\bv?\d+\.\d+(?:\.\d+)?(?:-[a-zA-Z0-9]+)?\b": "version_number",
            (
                r"\b(?:GPT|Claude|Gemini|Llama|Mistral|Qwen|GLM|Phi|Falcon|Grok)"
                r"-\d+(?:\.\d+)?(?:[a-zA-Z]*)?\b"
            ): "model_version",
            r"\b[A-Za-z0-9_-]{1,39}/[A-Za-z0-9_.-]{1,100}\b": "github_repo",
            (
                r"\b(?:iPhone|iPad|MacBook|iMac|Mac Pro|Mac Mini|Apple Watch"
                r"|Pixel|Galaxy|Surface|ThinkPad"
                r"|RTX|GTX|RX|Radeon|GeForce"
                r"|H\d00|A\d00|GB\d00)\s*\d+\w*\b"
            ): "product_name",
            r"@[a-z0-9-]+/[a-z0-9-]+": "package_name",
            r"\b[A-Z]{3,6}\b": "acronym",
            r"\b[a-z][a-z0-9-]*\.[a-z]{2,4}/[^\s]{0,40}": "url_ref",
        },
    }

    label_map = _PATTERN_LABELS.get(vertical_id, {})

    seen: set[str] = set()
    entities: list[dict] = []

    for pattern in config.entity_patterns:
        label = label_map.get(pattern, "entity")
        try:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                matched_text = m.group().strip()
                if matched_text and matched_text not in seen:
                    seen.add(matched_text)
                    entities.append({"text": matched_text, "type": label})
        except re.error:
            logger.warning("Invalid entity pattern for vertical %s: %s", vertical_id, pattern)

    return entities
