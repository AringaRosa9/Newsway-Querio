"""Re-ranking module.

Applies a multi-factor scoring model on top of initial retrieval scores,
combining relevance, freshness, source authority, and diversity to produce
a final ranked list.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Authority scores – map source name to 0-1 score
# ---------------------------------------------------------------------------

AUTHORITY_SCORES: dict[str, float] = {
    # International wire / broadcast
    "Reuters": 0.95,
    "AP": 0.95,
    "AFP": 0.93,
    "BBC": 0.90,
    "CNN": 0.87,
    "The New York Times": 0.90,
    "The Guardian": 0.88,
    "The Washington Post": 0.88,
    "Financial Times": 0.90,
    "The Economist": 0.90,
    "Wall Street Journal": 0.90,
    "Bloomberg": 0.92,
    # Chinese state / major outlets
    "新华社": 0.95,
    "人民日报": 0.93,
    "中央电视台": 0.90,
    "央视": 0.90,
    "光明日报": 0.88,
    "环球时报": 0.82,
    "中国日报": 0.85,
    # Chinese tech / business media
    "36氪": 0.75,
    "虎嗅": 0.72,
    "钛媒体": 0.70,
    "界面新闻": 0.78,
    "财新": 0.85,
    "第一财经": 0.83,
    # International tech media
    "TechCrunch": 0.80,
    "The Verge": 0.78,
    "Wired": 0.82,
    "Ars Technica": 0.80,
    "MIT Technology Review": 0.88,
}

_DEFAULT_AUTHORITY: float = 0.50

# ---------------------------------------------------------------------------
# Multi-factor weights
# ---------------------------------------------------------------------------

_WEIGHT_RELEVANCE: float = 0.40
_WEIGHT_FRESHNESS: float = 0.25
_WEIGHT_AUTHORITY: float = 0.20
_WEIGHT_DIVERSITY: float = 0.15  # this is a penalty weight

# Freshness decay parameters
# Half-life target: ~3 days -> lambda = ln(2) / (3 * 86400)
_FRESHNESS_LAMBDA: float = math.log(2) / (3 * 24 * 3600)

# Diversity: penalise the N-th occurrence of a source (N >= 2)
_DIVERSITY_TOP_N: int = 10  # how many top results to consider for source counts


# ---------------------------------------------------------------------------
# Pydantic model
# ---------------------------------------------------------------------------


class RankingFactors(BaseModel):
    relevance_score: float
    freshness_score: float
    authority_score: float
    diversity_penalty: float


# ---------------------------------------------------------------------------
# Individual factor computations
# ---------------------------------------------------------------------------


def compute_freshness(published_at: datetime) -> float:
    """Exponential decay freshness score.

    Returns a value in [0, 1]:
    - 1.0  for articles published right now
    - ~0.5 for articles published ~3 days ago
    - ~0.1 for articles published ~10 days ago
    """
    now = datetime.now(tz=timezone.utc)

    # Ensure published_at is timezone-aware
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    age_seconds = max((now - published_at).total_seconds(), 0.0)
    return math.exp(-_FRESHNESS_LAMBDA * age_seconds)


def compute_diversity(results: list[dict], idx: int) -> float:
    """Compute a diversity penalty for the result at position ``idx``.

    Returns a value in [0, 1] where 1.0 means no penalty (first occurrence
    of that source in the top-N) and lower values penalise repeated sources.
    """
    source = results[idx].get("source", "")
    if not source:
        return 1.0

    # Count how many times this source already appears in results[0:idx]
    # within the top-N window
    window = results[: min(idx, _DIVERSITY_TOP_N)]
    prior_count = sum(1 for r in window if r.get("source", "") == source)

    if prior_count == 0:
        return 1.0  # No penalty
    # Diminishing returns: 1 / (prior_count + 1)
    return 1.0 / (prior_count + 1)


def _normalise_scores(results: list[dict]) -> list[float]:
    """Min-max normalise the ``score`` field to [0, 1]."""
    scores = [r.get("score", 0.0) for r in results]
    if not scores:
        return []
    min_s = min(scores)
    max_s = max(scores)
    if max_s == min_s:
        return [1.0] * len(scores)
    return [(s - min_s) / (max_s - min_s) for s in scores]


def _get_authority(source: str) -> float:
    if not source:
        return _DEFAULT_AUTHORITY
    # Try exact match first, then partial (case-insensitive)
    if source in AUTHORITY_SCORES:
        return AUTHORITY_SCORES[source]
    source_lower = source.lower()
    for key, score in AUTHORITY_SCORES.items():
        if key.lower() in source_lower or source_lower in key.lower():
            return score
    return _DEFAULT_AUTHORITY


# ---------------------------------------------------------------------------
# Public rerank function
# ---------------------------------------------------------------------------


def rerank(results: list[dict], query: str) -> list[dict]:
    """Apply multi-factor re-ranking.

    Mutates each result dict to add ``final_score`` and ``ranking_factors``,
    then returns the results sorted by ``final_score`` descending.

    Weights: relevance=0.40, freshness=0.25, authority=0.20, diversity=0.15
    """
    if not results:
        return results

    # Normalise retrieval scores for the relevance component
    norm_scores = _normalise_scores(results)

    enriched: list[dict] = []
    for idx, result in enumerate(results):
        doc = dict(result)

        relevance = norm_scores[idx]

        # Freshness
        published_at = doc.get("published_at")
        if published_at:
            if isinstance(published_at, str):
                try:
                    published_at = datetime.fromisoformat(
                        published_at.replace("Z", "+00:00")
                    )
                except ValueError:
                    published_at = None
        freshness = compute_freshness(published_at) if published_at else 0.5

        # Authority
        authority = _get_authority(doc.get("source", ""))

        # Diversity (computed against the enriched list built so far)
        # We compute it against the *current* ordering so earlier positions
        # are penalised less.
        diversity = compute_diversity(results, idx)

        # Final weighted score
        # Diversity is a multiplier-style penalty; lower diversity -> lower score
        final_score = (
            _WEIGHT_RELEVANCE * relevance
            + _WEIGHT_FRESHNESS * freshness
            + _WEIGHT_AUTHORITY * authority
            + _WEIGHT_DIVERSITY * diversity
        )

        doc["final_score"] = final_score
        doc["ranking_factors"] = RankingFactors(
            relevance_score=relevance,
            freshness_score=freshness,
            authority_score=authority,
            diversity_penalty=1.0 - diversity,
        ).model_dump()
        enriched.append(doc)

    enriched.sort(key=lambda d: d["final_score"], reverse=True)
    return enriched
