"""Query understanding module.

Parses a raw search query into a structured ParsedQuery object using
rule-based heuristics (no LLM calls). Handles time expressions in both
Chinese and English, intent classification, keyword extraction, and
rewritten query generation.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Stopwords (basic set for Chinese and English)
# ---------------------------------------------------------------------------

_ZH_STOPWORDS: set[str] = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你",
    "会", "着", "没有", "看", "好", "自己", "这", "那", "里", "与",
    "对", "为", "他", "她", "它", "们", "时", "从", "以", "中",
    "或", "如", "但", "而", "因", "其", "来", "被", "让", "于",
    "年", "月", "日", "号",
}

_EN_STOPWORDS: set[str] = {
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "shall", "can",
    "to", "of", "in", "on", "at", "for", "with", "about", "by", "from",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "this", "that", "these",
    "those", "i", "you", "he", "she", "it", "we", "they", "what",
    "which", "who", "when", "where", "why", "how", "all", "both",
    "each", "few", "more", "most", "other", "some", "such", "no",
    "not", "only", "same", "so", "than", "too", "very", "just",
    "news", "article", "report", "tell", "me", "about",
}

# ---------------------------------------------------------------------------
# Intent keywords
# ---------------------------------------------------------------------------

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "FACTUAL": [
        "什么", "什么是", "是什么", "如何", "怎么", "为什么", "原因",
        "解释", "定义", "概念", "what", "what is", "how", "why", "define",
        "explain", "meaning", "definition",
    ],
    "EVENT": [
        "事件", "发生", "发布", "宣布", "举行", "召开", "开幕", "闭幕",
        "爆发", "突破", "创立", "事故", "灾难",
        "happened", "occurred", "launched", "announced", "released",
        "event", "incident", "breaking", "what happened", "what occurred",
    ],
    "OPINION": [
        "观点", "看法", "评价", "评论", "认为", "批评", "支持",
        "反对", "讨论", "争议", "辩论",
        "opinion", "view", "think", "comment", "criticism",
        "debate", "controversy", "perspective",
    ],
    "TREND": [
        "趋势", "未来", "预测", "展望", "发展", "变化", "增长", "下降",
        "演变", "进化", "前景", "走势", "分析",
        "trend", "future", "forecast", "prediction", "outlook", "growth",
        "decline", "evolve", "emerging", "rise", "fall", "analysis",
    ],
}

# Priority order for tie-breaking (earlier = higher priority)
_INTENT_PRIORITY: list[str] = ["FACTUAL", "TREND", "EVENT", "OPINION"]

# ---------------------------------------------------------------------------
# Time expression patterns
# ---------------------------------------------------------------------------

# Relative Chinese time expressions (ordered most-specific first)
_ZH_TIME_PATTERNS: list[tuple[str, str]] = [
    (r"今天|今日", "today"),
    (r"昨天|昨日", "yesterday"),
    (r"本周|这周|这一周", "this_week"),
    (r"上周|上一周", "last_week"),
    (r"本月|这个月", "this_month"),
    (r"上个月|上月", "last_month"),
    (r"最近(\d+)天", "last_n_days"),
    (r"最近(\d+)周", "last_n_weeks"),
    (r"最近(\d+)个月", "last_n_months"),
    (r"最近|近期", "recent"),
]

_EN_TIME_PATTERNS: list[tuple[str, str]] = [
    (r"\btoday\b", "today"),
    (r"\byesterday\b", "yesterday"),
    (r"\bthis\s+week\b", "this_week"),
    (r"\blast\s+week\b", "last_week"),
    (r"\bthis\s+month\b", "this_month"),
    (r"\blast\s+month\b", "last_month"),
    (r"\blast\s+(\d+)\s+days?\b", "last_n_days"),
    (r"\blast\s+(\d+)\s+weeks?\b", "last_n_weeks"),
    (r"\blast\s+(\d+)\s+months?\b", "last_n_months"),
    (r"\brecently\b|\brecent\b", "recent"),
]


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _resolve_time_expression(
    kind: str, match: re.Match
) -> tuple[datetime, datetime] | None:
    """Convert a matched time expression to a (start, end) datetime range."""
    now = _now_utc()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if kind == "today":
        return today_start, now
    elif kind == "yesterday":
        start = today_start - timedelta(days=1)
        return start, today_start
    elif kind == "this_week":
        # Monday of current week
        monday = today_start - timedelta(days=today_start.weekday())
        return monday, now
    elif kind == "last_week":
        monday_this = today_start - timedelta(days=today_start.weekday())
        monday_last = monday_this - timedelta(weeks=1)
        return monday_last, monday_this
    elif kind == "this_month":
        start = today_start.replace(day=1)
        return start, now
    elif kind == "last_month":
        first_this = today_start.replace(day=1)
        last_day_prev = first_this - timedelta(days=1)
        start = last_day_prev.replace(day=1)
        return start, first_this
    elif kind == "last_n_days":
        n = int(match.group(1))
        return today_start - timedelta(days=n), now
    elif kind == "last_n_weeks":
        n = int(match.group(1))
        return today_start - timedelta(weeks=n), now
    elif kind == "last_n_months":
        n = int(match.group(1))
        return today_start - timedelta(days=n * 30), now
    elif kind == "recent":
        # Default "recent" = last 7 days
        return today_start - timedelta(days=7), now
    return None


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class QueryIntent(str, Enum):
    FACTUAL = "FACTUAL"
    EVENT = "EVENT"
    OPINION = "OPINION"
    TREND = "TREND"


class ParsedQuery(BaseModel):
    original_query: str
    rewritten_queries: list[str]
    intent: QueryIntent
    time_range: Optional[tuple[datetime, datetime]] = None
    entities: list[str]
    keywords: list[str]

    model_config = {"arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_time_range(query: str) -> tuple[tuple[datetime, datetime] | None, str]:
    """Return (time_range, cleaned_query_without_time_expr)."""
    cleaned = query
    for pattern, kind in _ZH_TIME_PATTERNS + _EN_TIME_PATTERNS:
        m = re.search(pattern, cleaned, re.IGNORECASE)
        if m:
            result = _resolve_time_expression(kind, m)
            if result:
                cleaned = cleaned[: m.start()] + cleaned[m.end() :]
                cleaned = cleaned.strip()
                return result, cleaned
    return None, cleaned


def _extract_quoted_phrases(query: str) -> tuple[list[str], str]:
    """Pull out "exact phrase" tokens, return them + query without quotes."""
    phrases = re.findall(r'"([^"]+)"', query)
    cleaned = re.sub(r'"[^"]*"', "", query).strip()
    return phrases, cleaned


def _tokenize_keywords(text: str) -> list[str]:
    """Very simple tokenizer: split on whitespace/punctuation, remove stopwords."""
    # For Chinese text, split on character-level; for mixed/English, split on spaces
    tokens: list[str] = []

    # Split on common punctuation and whitespace
    raw_tokens = re.split(r"[\s,;:.!?，。！？；：、（）()【】\[\]《》<>「」\-_/\\]+", text)

    for tok in raw_tokens:
        tok = tok.strip()
        if not tok:
            continue
        # English token: lowercase and check stopwords
        if re.match(r"^[a-zA-Z0-9]+$", tok):
            lower = tok.lower()
            if lower not in _EN_STOPWORDS and len(lower) > 1:
                tokens.append(lower)
        else:
            # Chinese or mixed: keep if not a stopword and len >= 2
            if tok not in _ZH_STOPWORDS and len(tok) >= 1:
                # Further split Chinese compound if needed (simple approach)
                tokens.append(tok)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def _extract_entities(query: str) -> list[str]:
    """Heuristic entity extraction from the query itself."""
    entities: list[str] = []

    # Capitalized English words (likely proper nouns) – 2+ chars
    cap_words = re.findall(r"\b[A-Z][a-zA-Z]{1,}\b", query)
    entities.extend(cap_words)

    # Chinese org/person patterns – words followed by org suffixes
    zh_org_pattern = r"[一-鿿]{2,}(?:公司|集团|大学|政府|机构|部门|研究院|实验室|银行|基金)"
    entities.extend(re.findall(zh_org_pattern, query))

    # Quoted names
    quoted = re.findall(r'"([^"]+)"', query)
    entities.extend(quoted)

    # Deduplicate
    seen: set[str] = set()
    unique: list[str] = []
    for e in entities:
        if e not in seen:
            seen.add(e)
            unique.append(e)
    return unique


def _classify_intent(query: str, keywords: list[str]) -> QueryIntent:
    """Rule-based intent classification."""
    lower_query = query.lower()
    combined = lower_query + " " + " ".join(keywords)

    scores: dict[str, int] = {
        "FACTUAL": 0,
        "EVENT": 0,
        "OPINION": 0,
        "TREND": 0,
    }

    for intent, kws in _INTENT_KEYWORDS.items():
        for kw in kws:
            if kw in combined:
                scores[intent] += 1

    max_score = max(scores.values())
    # Default to EVENT if all scores are 0 (it's a news search engine)
    if max_score == 0:
        return QueryIntent.EVENT
    # Break ties using the predefined priority order
    for priority_intent in _INTENT_PRIORITY:
        if scores[priority_intent] == max_score:
            return QueryIntent(priority_intent)
    # Fallback (should not reach here)
    return QueryIntent(max(scores, key=lambda k: scores[k]))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_query(query: str) -> ParsedQuery:
    """Parse a raw search query into a structured ParsedQuery.

    Steps:
    1. Extract time expressions -> time_range
    2. Extract quoted exact phrases
    3. Extract entities
    4. Tokenize remaining text -> keywords
    5. Classify intent
    6. Generate rewritten queries
    """
    # Step 1: Time range
    time_range, query_no_time = _extract_time_range(query)

    # Step 2: Quoted phrases
    quoted_phrases, query_no_quotes = _extract_quoted_phrases(query_no_time)

    # Step 3: Entity extraction (from original, before stripping)
    entities = _extract_entities(query)

    # Step 4: Keywords from the time-stripped query
    keywords = _tokenize_keywords(query_no_quotes)
    # Add quoted phrases as keywords
    keywords = quoted_phrases + [k for k in keywords if k not in quoted_phrases]

    # Step 5: Intent
    intent = _classify_intent(query, keywords)

    # Step 6: Rewritten queries
    # a) Original query (always included)
    # b) Keyword-only version (join extracted keywords)
    # c) Entity-focused version (join entities if any)
    rewritten: list[str] = [query]
    if keywords:
        kw_version = " ".join(keywords)
        if kw_version != query:
            rewritten.append(kw_version)
    if entities:
        entity_version = " ".join(entities)
        if entity_version not in rewritten:
            rewritten.append(entity_version)

    return ParsedQuery(
        original_query=query,
        rewritten_queries=rewritten,
        intent=intent,
        time_range=time_range,
        entities=entities,
        keywords=keywords,
    )
