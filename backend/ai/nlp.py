"""NLP processing module.

Rule-based text analysis for news articles: category classification,
sentiment analysis, and entity extraction. No LLM calls – designed for
high-throughput batch processing during ingestion.
"""

from __future__ import annotations

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

CATEGORIES: list[str] = [
    "政治", "经济", "科技", "社会", "国际", "体育", "娱乐", "健康", "教育", "环境",
    "politics", "economy", "technology", "society", "international",
    "sports", "entertainment", "health", "education", "environment",
]

# Keyword sets per category (Chinese then English per category)
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "politics": [
        "政治", "政府", "总统", "主席", "总理", "国会", "议会", "选举", "党", "法律",
        "外交", "联合国", "制裁", "政策", "立法", "民主", "共和",
        "politics", "government", "president", "prime minister", "congress",
        "parliament", "election", "law", "policy", "diplomacy", "UN", "treaty",
        "minister", "senate", "democrat", "republican",
    ],
    "economy": [
        "经济", "GDP", "通胀", "货币", "股市", "金融", "银行", "贸易", "出口", "进口",
        "税收", "预算", "债务", "投资", "企业", "市场", "价格", "供应链",
        "economy", "GDP", "inflation", "currency", "stock", "finance", "bank",
        "trade", "export", "import", "tax", "budget", "debt", "investment",
        "market", "price", "supply chain", "interest rate", "recession",
    ],
    "technology": [
        "科技", "技术", "人工智能", "AI", "芯片", "半导体", "互联网", "软件", "硬件",
        "数据", "云计算", "机器学习", "算法", "机器人", "电动车", "航天",
        "technology", "tech", "artificial intelligence", "AI", "chip",
        "semiconductor", "internet", "software", "hardware", "data",
        "cloud", "machine learning", "algorithm", "robot", "EV", "space",
        "startup", "silicon valley", "cybersecurity",
    ],
    "society": [
        "社会", "民众", "生活", "文化", "习俗", "移民", "人口", "社区", "犯罪",
        "公共安全", "住房", "贫困", "不平等",
        "society", "people", "life", "culture", "immigration", "population",
        "community", "crime", "public safety", "housing", "poverty",
        "inequality", "social",
    ],
    "international": [
        "国际", "全球", "世界", "外国", "海外", "跨国", "多边",
        "international", "global", "world", "foreign", "overseas",
        "multinational", "bilateral", "multilateral", "geopolitics",
    ],
    "sports": [
        "体育", "足球", "篮球", "网球", "田径", "游泳", "奥运", "世界杯",
        "比赛", "冠军", "运动员", "联赛", "赛事",
        "sports", "football", "basketball", "tennis", "athletics", "swimming",
        "olympics", "world cup", "championship", "athlete", "league",
        "tournament", "game", "match",
    ],
    "entertainment": [
        "娱乐", "电影", "音乐", "明星", "艺人", "综艺", "电视剧", "演员",
        "导演", "票房", "演唱会", "流行",
        "entertainment", "movie", "film", "music", "celebrity", "star",
        "TV show", "actor", "director", "box office", "concert", "pop",
        "streaming", "netflix", "award",
    ],
    "health": [
        "健康", "医疗", "医院", "疾病", "药物", "疫苗", "癌症", "病毒",
        "心脏", "糖尿病", "研究", "临床", "治疗",
        "health", "medical", "hospital", "disease", "drug", "vaccine",
        "cancer", "virus", "heart", "diabetes", "clinical", "treatment",
        "mental health", "FDA", "WHO", "pandemic",
    ],
    "education": [
        "教育", "学校", "大学", "学生", "教师", "学习", "考试", "课程",
        "高考", "留学", "奖学金",
        "education", "school", "university", "student", "teacher",
        "learning", "exam", "curriculum", "scholarship", "college",
        "academic", "degree",
    ],
    "environment": [
        "环境", "气候", "温室", "碳排放", "污染", "绿色", "可再生能源",
        "太阳能", "风能", "生态", "森林", "海洋",
        "environment", "climate", "greenhouse", "carbon", "emission",
        "pollution", "green", "renewable", "solar", "wind", "ecology",
        "forest", "ocean", "sustainability", "COP",
    ],
}

# Chinese->English canonical name mapping for display
_ZH_TO_EN_CATEGORY: dict[str, str] = {
    "政治": "politics",
    "经济": "economy",
    "科技": "technology",
    "社会": "society",
    "国际": "international",
    "体育": "sports",
    "娱乐": "entertainment",
    "健康": "health",
    "教育": "education",
    "环境": "environment",
}

# ---------------------------------------------------------------------------
# Sentiment keywords
# ---------------------------------------------------------------------------

SENTIMENT_KEYWORDS: dict[str, list[str]] = {
    "positive": [
        # Chinese
        "增长", "突破", "创新", "成功", "获奖", "盈利", "上涨", "好消息",
        "进步", "合作", "发展", "优秀", "领先", "提升", "改善",
        # English
        "growth", "breakthrough", "innovation", "success", "award",
        "profit", "rise", "good news", "progress", "cooperation",
        "development", "excellent", "leading", "improve", "recover",
        "gain", "surge", "advance", "launch", "record high",
    ],
    "negative": [
        # Chinese
        "下跌", "亏损", "失败", "危机", "灾难", "冲突", "制裁", "警告",
        "风险", "问题", "争议", "抗议", "事故", "崩溃", "衰退",
        # English
        "drop", "loss", "failure", "crisis", "disaster", "conflict",
        "sanction", "warning", "risk", "problem", "controversy",
        "protest", "accident", "crash", "recession", "layoff",
        "decline", "fall", "collapse", "threat", "attack", "war",
        "corruption", "fraud", "scandal",
    ],
}


# ---------------------------------------------------------------------------
# Entity extraction patterns
# ---------------------------------------------------------------------------

# English: sequences of 2+ Title-Cased words (proper nouns)
_EN_ENTITY_PATTERN = re.compile(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")
# Single capitalized word that looks like a proper name/acronym
_EN_SINGLE_CAP = re.compile(r"\b[A-Z]{2,}\b")

# Chinese: words/phrases before common org/person suffixes
_ZH_ORG_PATTERN = re.compile(
    r"[一-鿿]{2,8}(?:公司|集团|大学|政府|机构|部门|研究院|实验室"
    r"|银行|基金|协会|委员会|联合会|局|部|院|所|厅|处)"
)
# Chinese person names: 2–4 character sequences preceded by honorifics or job titles
_ZH_PERSON_PATTERN = re.compile(
    r"(?:总统|总理|主席|部长|总裁|CEO|董事长|教授|博士)"
    r"\s*([一-鿿]{2,4})"
)
# Quoted entities (any language)
_QUOTED_ENTITY_PATTERN = re.compile(r'["""「」\'\']((?:[^"""「」\'\']{2,50}))["""「」\'\']')


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def _keyword_in_text(kw: str, text_lower: str) -> bool:
    """Check if a keyword appears in text, using word-boundary matching for
    short all-ASCII keywords (len <= 3) to avoid false substring matches."""
    kw_lower = kw.lower()
    if re.match(r"^[a-z]{1,3}$", kw_lower):
        # Use word boundary to avoid e.g. "UN" matching "announced"
        return bool(re.search(r"\b" + re.escape(kw_lower) + r"\b", text_lower))
    return kw_lower in text_lower


def classify_category(text: str) -> str:
    """Classify article into a news category using keyword matching.

    Returns the English category name that best matches the text.
    Defaults to 'society' if no category has a clear winner.
    """
    text_lower = text.lower()

    scores: dict[str, int] = {cat: 0 for cat in _CATEGORY_KEYWORDS}
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if _keyword_in_text(kw, text_lower):
                scores[cat] += 1

    best_cat = max(scores, key=lambda c: scores[c])
    if scores[best_cat] == 0:
        return "society"
    return best_cat


def analyze_sentiment(text: str) -> str:
    """Rule-based sentiment analysis.

    Counts positive and negative keyword occurrences and returns the
    dominant sentiment. Returns 'neutral' on a tie or when both counts are 0.
    """
    text_lower = text.lower()

    pos_count = sum(
        1 for kw in SENTIMENT_KEYWORDS["positive"] if kw.lower() in text_lower
    )
    neg_count = sum(
        1 for kw in SENTIMENT_KEYWORDS["negative"] if kw.lower() in text_lower
    )

    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    return "neutral"


def extract_entities(text: str) -> list[str]:
    """Simple regex-based named entity extraction.

    Extracts:
    - Multi-word English proper nouns (TitleCase sequences)
    - English acronyms (ALL CAPS, 2+ chars)
    - Chinese organisations (matched by suffix patterns)
    - Chinese person names (matched by preceding title)
    - Quoted strings (likely proper nouns or titles)
    """
    entities: list[str] = []

    # English multi-word proper nouns
    entities.extend(_EN_ENTITY_PATTERN.findall(text))

    # English acronyms (filter common English words that are all-caps in headlines)
    _COMMON_CAPS = {"US", "UK", "EU", "UN", "WHO", "GDP", "AI", "IT", "TV", "PM"}
    for m in _EN_SINGLE_CAP.finditer(text):
        word = m.group()
        if len(word) >= 2 and (word in _COMMON_CAPS or len(word) >= 3):
            entities.append(word)

    # Chinese organisations
    entities.extend(_ZH_ORG_PATTERN.findall(text))

    # Chinese person names after title
    for m in _ZH_PERSON_PATTERN.finditer(text):
        entities.append(m.group(1))

    # Quoted strings
    entities.extend(_QUOTED_ENTITY_PATTERN.findall(text))

    # Deduplicate, preserve order, strip whitespace
    seen: set[str] = set()
    unique: list[str] = []
    for e in entities:
        e_stripped = e.strip()
        if e_stripped and e_stripped not in seen:
            seen.add(e_stripped)
            unique.append(e_stripped)

    return unique


def process_article(article_dict: dict[str, Any]) -> dict[str, Any]:
    """Run NLP analysis on a raw article dict.

    Fills in ``category``, ``sentiment``, and ``entities`` fields from the
    article's ``title`` and ``content``.  Only fills in missing values;
    existing non-empty values are preserved.
    """
    title = article_dict.get("title", "") or ""
    content = article_dict.get("content", "") or ""
    combined_text = f"{title} {content}"

    result = dict(article_dict)

    if not result.get("category"):
        result["category"] = classify_category(combined_text)

    if not result.get("sentiment"):
        result["sentiment"] = analyze_sentiment(combined_text)

    if not result.get("entities"):
        result["entities"] = extract_entities(combined_text)

    return result
