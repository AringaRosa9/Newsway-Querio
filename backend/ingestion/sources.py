"""Static registry of RSS news sources.

Each entry is a plain dict so callers can use it as a dataclass, TypedDict,
or simply iterate.  Add / remove sources here without touching any other
module.
"""

from __future__ import annotations

from typing import TypedDict


class NewsSource(TypedDict):
    name: str
    url: str
    category: str
    language: str


NEWS_SOURCES: list[NewsSource] = [
    # ------------------------------------------------------------------
    # International wire / general news
    # ------------------------------------------------------------------
    {
        "name": "Reuters",
        "url": "https://feeds.reuters.com/reuters/topNews",
        "category": "general",
        "language": "en",
    },
    {
        "name": "AP News",
        "url": "https://rsshub.app/apnews/topics/apf-topnews",
        "category": "general",
        "language": "en",
    },
    {
        "name": "BBC News",
        "url": "http://feeds.bbci.co.uk/news/rss.xml",
        "category": "general",
        "language": "en",
    },
    {
        "name": "CNN",
        "url": "http://rss.cnn.com/rss/edition.rss",
        "category": "general",
        "language": "en",
    },
    {
        "name": "NPR News",
        "url": "https://feeds.npr.org/1001/rss.xml",
        "category": "general",
        "language": "en",
    },
    {
        "name": "The Guardian",
        "url": "https://www.theguardian.com/world/rss",
        "category": "general",
        "language": "en",
    },
    # ------------------------------------------------------------------
    # Technology
    # ------------------------------------------------------------------
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "category": "tech",
        "language": "en",
    },
    {
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "category": "tech",
        "language": "en",
    },
    {
        "name": "Ars Technica",
        "url": "http://feeds.arstechnica.com/arstechnica/index",
        "category": "tech",
        "language": "en",
    },
    {
        "name": "Wired",
        "url": "https://www.wired.com/feed/rss",
        "category": "tech",
        "language": "en",
    },
    {
        "name": "Hacker News (top)",
        "url": "https://hnrss.org/frontpage",
        "category": "tech",
        "language": "en",
    },
    # ------------------------------------------------------------------
    # Finance
    # ------------------------------------------------------------------
    {
        "name": "Financial Times",
        "url": "https://www.ft.com/rss/home/uk",
        "category": "finance",
        "language": "en",
    },
    {
        "name": "Bloomberg Markets",
        "url": "https://feeds.bloomberg.com/markets/news.rss",
        "category": "finance",
        "language": "en",
    },
    # ------------------------------------------------------------------
    # Chinese – 综合 / 财经
    # ------------------------------------------------------------------
    {
        "name": "新华社",
        "url": "http://www.xinhuanet.com/rss/news.xml",
        "category": "general",
        "language": "zh",
    },
    {
        "name": "人民日报",
        "url": "http://www.people.com.cn/rss/politics.xml",
        "category": "general",
        "language": "zh",
    },
    {
        "name": "澎湃新闻",
        "url": "https://www.thepaper.cn/rss_www.xml",
        "category": "general",
        "language": "zh",
    },
    {
        "name": "36氪",
        "url": "https://36kr.com/feed",
        "category": "tech",
        "language": "zh",
    },
    {
        "name": "虎嗅",
        "url": "https://www.huxiu.com/rss/0.xml",
        "category": "tech",
        "language": "zh",
    },
    {
        "name": "界面新闻",
        "url": "https://www.jiemian.com/lists/rss.xml",
        "category": "finance",
        "language": "zh",
    },
    {
        "name": "财新网",
        "url": "https://www.caixin.com/rss/caixinall.xml",
        "category": "finance",
        "language": "zh",
    },
    {
        "name": "少数派",
        "url": "https://sspai.com/feed",
        "category": "tech",
        "language": "zh",
    },
]
