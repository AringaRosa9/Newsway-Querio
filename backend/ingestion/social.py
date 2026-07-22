"""Social media monitoring module.

Fetches posts from social media APIs (Twitter/X, Weibo) and normalizes
them into the standard Article format for indexing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from core.config import get_settings
from ingestion.cleaner import Article, clean_html

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


class SocialFetcher:
    """Fetches and normalizes social media posts."""

    def __init__(self) -> None:
        self._settings = get_settings()

    async def fetch_twitter(self, query: str = "AI OR 人工智能", max_results: int = 50) -> list[Article]:
        """Fetch recent tweets matching a query via Twitter API v2."""
        bearer = self._settings.TWITTER_BEARER_TOKEN
        if not bearer:
            logger.debug("Twitter bearer token not configured, skipping")
            return []

        url = "https://api.twitter.com/2/tweets/search/recent"
        params = {
            "query": f"{query} -is:retweet lang:en OR lang:zh",
            "max_results": min(max_results, 100),
            "tweet.fields": "created_at,author_id,text,public_metrics",
            "expansions": "author_id",
            "user.fields": "name,username",
        }
        headers = {"Authorization": f"Bearer {bearer}"}

        try:
            async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error("Twitter API error: %s", exc)
            return []

        users = {}
        for u in data.get("includes", {}).get("users", []):
            users[u["id"]] = u.get("name", u.get("username", ""))

        articles: list[Article] = []
        for tweet in data.get("data", []):
            author = users.get(tweet.get("author_id", ""), "")
            articles.append(
                Article(
                    title=tweet.get("text", "")[:100],
                    content=tweet.get("text", ""),
                    source="Twitter",
                    url=f"https://twitter.com/i/web/status/{tweet['id']}",
                    published_at=tweet.get("created_at", datetime.now(timezone.utc).isoformat()),
                    author=author,
                    category="social",
                )
            )

        logger.info("Fetched %d tweets for query: %s", len(articles), query)
        return articles

    async def fetch_weibo(self, query: str = "AI", count: int = 50) -> list[Article]:
        """Fetch recent Weibo posts via public search API."""
        token = self._settings.WEIBO_ACCESS_TOKEN
        if not token:
            logger.debug("Weibo access token not configured, skipping")
            return []

        url = "https://api.weibo.com/2/search/topics.json"
        params = {"q": query, "count": min(count, 50), "access_token": token}

        try:
            async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error("Weibo API error: %s", exc)
            return []

        articles: list[Article] = []
        for post in data.get("statuses", []):
            text = clean_html(post.get("text", ""))
            user = post.get("user", {})
            articles.append(
                Article(
                    title=text[:100],
                    content=text,
                    source="微博",
                    url=f"https://weibo.com/{user.get('id', '')}/{post.get('idstr', '')}",
                    published_at=post.get("created_at", datetime.now(timezone.utc).isoformat()),
                    author=user.get("screen_name", ""),
                    category="social",
                )
            )

        logger.info("Fetched %d weibo posts for query: %s", len(articles), query)
        return articles

    async def fetch_all(self, queries: list[str] | None = None) -> list[Article]:
        """Fetch from all configured social platforms."""
        if queries is None:
            queries = ["AI", "人工智能", "科技"]

        all_articles: list[Article] = []
        for q in queries:
            all_articles.extend(await self.fetch_twitter(q))
            all_articles.extend(await self.fetch_weibo(q))

        return all_articles
