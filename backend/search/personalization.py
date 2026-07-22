"""Personalized ranking module.

Adjusts search result scores based on user profile and reading history:
- Category affinity: boost results matching user's preferred categories
- Source preference: boost results from user's preferred sources
- Interest matching: boost results containing user's interest keywords
- Diversity: avoid over-representing already-read content
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_WEIGHT_CATEGORY = 0.04
_WEIGHT_SOURCE = 0.03
_WEIGHT_INTEREST = 0.03
_PENALTY_ALREADY_READ = 0.10


def personalize(
    results: list[dict],
    user_profile: dict | None = None,
    reading_history: list[str] | None = None,
) -> list[dict]:
    """Apply personalization boosts to ranked results.

    Mutates each result's ``final_score`` and returns re-sorted results.
    Only applies when a user profile is available.
    """
    if not user_profile or not results:
        return results

    preferred_categories = set(user_profile.get("preferred_categories", []))
    preferred_sources = set(user_profile.get("preferred_sources", []))
    interests = set(
        kw.lower() for kw in user_profile.get("interests", [])
    )
    history_set = set(reading_history or [])

    personalized: list[dict] = []
    for result in results:
        doc = dict(result)
        boost = 0.0

        category = doc.get("category", "")
        if category and category in preferred_categories:
            boost += _WEIGHT_CATEGORY

        source = doc.get("source", "")
        if source and source in preferred_sources:
            boost += _WEIGHT_SOURCE

        if interests:
            title = (doc.get("title", "") or "").lower()
            content_preview = (doc.get("content", "") or "")[:300].lower()
            text = f"{title} {content_preview}"
            matched = sum(1 for kw in interests if kw in text)
            if matched > 0:
                boost += min(matched * 0.01, _WEIGHT_INTEREST)

        doc_id = doc.get("id", "")
        if doc_id and doc_id in history_set:
            boost -= _PENALTY_ALREADY_READ

        current_score = doc.get("final_score", 0.5)
        doc["final_score"] = current_score + boost
        doc["personalization_boost"] = round(boost, 4)
        personalized.append(doc)

    personalized.sort(key=lambda d: d["final_score"], reverse=True)
    return personalized


def build_user_profile_from_history(
    articles: list[dict],
) -> dict:
    """Infer user interests from reading history articles.

    Returns a profile dict with inferred categories, sources, and entities.
    """
    categories: dict[str, int] = {}
    sources: dict[str, int] = {}
    entities: dict[str, int] = {}

    for article in articles:
        cat = article.get("category", "")
        if cat:
            categories[cat] = categories.get(cat, 0) + 1

        src = article.get("source", "")
        if src:
            sources[src] = sources.get(src, 0) + 1

        for entity in article.get("entities", []):
            entities[entity] = entities.get(entity, 0) + 1

    top_categories = sorted(categories, key=categories.get, reverse=True)[:5]
    top_sources = sorted(sources, key=sources.get, reverse=True)[:5]
    top_entities = sorted(entities, key=entities.get, reverse=True)[:10]

    return {
        "preferred_categories": top_categories,
        "preferred_sources": top_sources,
        "interests": top_entities,
    }
