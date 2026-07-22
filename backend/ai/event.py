"""Event aggregation module.

Groups related news articles into event clusters using semantic similarity,
then generates event titles and summaries. Uses embedding cosine similarity
for clustering and Claude for title/summary generation.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import numpy as np
from pydantic import BaseModel, Field
from sklearn.cluster import AgglomerativeClustering

from ai.embedding import get_embedding_service
from core.config import get_settings

logger = logging.getLogger(__name__)

_CLUSTER_DISTANCE_THRESHOLD = 0.35
_MIN_CLUSTER_SIZE = 2


class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    summary: str = ""
    category: str = ""
    article_ids: list[str] = Field(default_factory=list)
    article_count: int = 0
    entities: list[str] = Field(default_factory=list)
    sentiment_distribution: dict[str, int] = Field(default_factory=dict)
    first_seen: str = ""
    last_updated: str = ""
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class EventService:
    """Clusters articles into events and manages event lifecycle."""

    def __init__(self) -> None:
        self._embedding_svc = get_embedding_service()

    def cluster_articles(self, articles: list[dict]) -> list[Event]:
        """Group articles into event clusters using semantic similarity."""
        if len(articles) < _MIN_CLUSTER_SIZE:
            return []

        texts = [
            f"{a.get('title', '')} {(a.get('content', '') or '')[:300]}"
            for a in articles
        ]
        embeddings = self._embedding_svc.encode_batch(texts)
        matrix = np.array(embeddings)

        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=_CLUSTER_DISTANCE_THRESHOLD,
            metric="cosine",
            linkage="average",
        )
        labels = clustering.fit_predict(matrix)

        clusters: dict[int, list[dict]] = {}
        for idx, label in enumerate(labels):
            clusters.setdefault(int(label), []).append(articles[idx])

        events: list[Event] = []
        for _label, cluster_articles in clusters.items():
            if len(cluster_articles) < _MIN_CLUSTER_SIZE:
                continue
            event = self._build_event(cluster_articles)
            events.append(event)

        events.sort(key=lambda e: e.last_updated, reverse=True)
        return events

    def _build_event(self, articles: list[dict]) -> Event:
        """Build an Event from a cluster of articles."""
        sorted_articles = sorted(
            articles,
            key=lambda a: a.get("published_at", ""),
        )

        all_entities: list[str] = []
        sentiments: dict[str, int] = {"positive": 0, "neutral": 0, "negative": 0}
        categories: dict[str, int] = {}

        for a in sorted_articles:
            for entity in a.get("entities", []):
                if entity not in all_entities:
                    all_entities.append(entity)
            s = a.get("sentiment", "neutral")
            sentiments[s] = sentiments.get(s, 0) + 1
            cat = a.get("category", "")
            if cat:
                categories[cat] = categories.get(cat, 0) + 1

        top_category = max(categories, key=categories.get) if categories else ""

        timeline = [
            {
                "article_id": a.get("id", ""),
                "title": a.get("title", ""),
                "source": a.get("source", ""),
                "published_at": a.get("published_at", ""),
                "summary": (a.get("content", "") or "")[:200],
            }
            for a in sorted_articles
        ]

        title = self._generate_event_title(sorted_articles)

        return Event(
            title=title,
            summary=self._generate_event_summary(sorted_articles),
            category=top_category,
            article_ids=[a.get("id", "") for a in sorted_articles],
            article_count=len(sorted_articles),
            entities=all_entities[:20],
            sentiment_distribution=sentiments,
            first_seen=sorted_articles[0].get("published_at", ""),
            last_updated=sorted_articles[-1].get("published_at", ""),
            timeline=timeline,
        )

    @staticmethod
    def _generate_event_title(articles: list[dict]) -> str:
        """Generate event title from the most representative article."""
        if not articles:
            return ""
        best = max(articles, key=lambda a: len(a.get("content", "") or ""))
        return best.get("title", "")

    @staticmethod
    def _generate_event_summary(articles: list[dict]) -> str:
        """Generate a brief event summary from article contents."""
        if not articles:
            return ""
        parts = []
        for a in articles[:5]:
            content = (a.get("content", "") or "")[:150]
            if content:
                parts.append(content)
        return " ".join(parts)[:500]


async def aggregate_events(
    es_client: Any,
    hours: int = 72,
) -> list[Event]:
    """Fetch recent articles from ES and cluster them into events."""
    settings = get_settings()
    now = datetime.now(tz=timezone.utc)

    body = {
        "query": {
            "range": {
                "published_at": {
                    "gte": f"now-{hours}h",
                    "lte": "now",
                }
            }
        },
        "size": 500,
        "sort": [{"published_at": {"order": "desc"}}],
        "_source": True,
    }

    try:
        response = await es_client.search(index=settings.ES_INDEX, body=body)
    except Exception as exc:
        logger.error("Failed to fetch articles for event aggregation: %s", exc)
        return []

    articles = []
    for hit in response.get("hits", {}).get("hits", []):
        doc = {"id": hit["_id"]}
        doc.update(hit.get("_source", {}))
        articles.append(doc)

    if not articles:
        return []

    svc = EventService()
    return svc.cluster_articles(articles)
