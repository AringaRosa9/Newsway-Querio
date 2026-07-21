"""
tests/test_search.py — Unit tests for search modules.

Covers:
  - Query parsing (time extraction, keyword extraction, intent classification)
  - RRF (Reciprocal Rank Fusion) score computation
  - Reranking score computation
  - Freshness decay

External services (ES, Qdrant, Redis) are fully mocked so these tests run
without any running infrastructure.

Expected backend module layout (adapt imports as you implement):
  backend/search/query_parser.py   → parse_query(text) → ParsedQuery
  backend/search/fusion.py         → rrf_score(rankings, k) → dict[id, float]
  backend/search/reranker.py       → rerank_score(bm25, semantic, rrf, ...) → float
  backend/search/freshness.py      → freshness_decay(published_at, half_life_days) → float
"""

from __future__ import annotations

import math
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Make backend importable
# ---------------------------------------------------------------------------
_BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


# ---------------------------------------------------------------------------
# Lazy imports — mark entire module XFAIL until implementation exists
# ---------------------------------------------------------------------------
_MISSING_MODULES: list[str] = []

try:
    from search.query_parser import parse_query  # type: ignore[import]
except ImportError:
    _MISSING_MODULES.append("search.query_parser")

try:
    from search.fusion import rrf_score  # type: ignore[import]
except ImportError:
    _MISSING_MODULES.append("search.fusion")

try:
    from search.reranker import rerank_score  # type: ignore[import]
except ImportError:
    _MISSING_MODULES.append("search.reranker")

try:
    from search.freshness import freshness_decay  # type: ignore[import]
except ImportError:
    _MISSING_MODULES.append("search.freshness")

pytestmark = pytest.mark.xfail(
    bool(_MISSING_MODULES),
    reason=f"Missing modules: {_MISSING_MODULES}",
    strict=False,
)


# ===========================================================================
# Query Parser
# ===========================================================================

class TestQueryParser:
    """Tests for parse_query — returns a ParsedQuery object (or dict)."""

    def _parse(self, text: str):
        """Thin wrapper so tests still work if parse_query returns a dict."""
        result = parse_query(text)
        if isinstance(result, dict):
            return result
        # Assume dataclass / pydantic model
        return result.__dict__

    # --- Keyword extraction ---

    def test_basic_keyword_extraction(self):
        pq = self._parse("OpenAI GPT-5 release date")
        keywords = pq.get("keywords", [])
        assert any("gpt" in k.lower() or "openai" in k.lower() for k in keywords)

    def test_chinese_keyword_extraction(self):
        pq = self._parse("人工智能最新进展 2024")
        keywords = pq.get("keywords", [])
        assert len(keywords) > 0

    def test_stopwords_removed(self):
        pq = self._parse("the latest news about AI")
        keywords = pq.get("keywords", [])
        assert "the" not in [k.lower() for k in keywords]
        assert "about" not in [k.lower() for k in keywords]

    # --- Time extraction ---

    def test_time_extraction_today(self):
        pq = self._parse("today's AI news")
        time_filter = pq.get("time_filter") or pq.get("time_range")
        assert time_filter is not None

    def test_time_extraction_this_week(self):
        pq = self._parse("machine learning news this week")
        time_filter = pq.get("time_filter") or pq.get("time_range")
        assert time_filter is not None

    def test_time_extraction_specific_year(self):
        pq = self._parse("AI breakthroughs in 2024")
        # Year-based filter may or may not be extracted depending on impl
        # Just assert no crash
        assert pq is not None

    def test_no_time_filter_when_absent(self):
        pq = self._parse("artificial intelligence news")
        time_filter = pq.get("time_filter") or pq.get("time_range")
        # Either None or empty/default value
        assert time_filter is None or time_filter == "" or time_filter == {}

    # --- Intent classification ---

    def test_factual_intent(self):
        pq = self._parse("what is the latest GPT-4 benchmark score")
        intent = pq.get("intent", "")
        assert intent in ("factual", "search", "question", "qa", "")

    def test_news_intent(self):
        pq = self._parse("latest news about Tesla stock")
        intent = pq.get("intent", "")
        # Intent detection is implementation-specific; just assert no crash
        assert isinstance(intent, str)

    def test_summary_intent(self):
        pq = self._parse("summarize recent AI funding rounds")
        intent = pq.get("intent", "")
        assert isinstance(intent, str)

    def test_empty_query(self):
        pq = self._parse("")
        assert pq is not None

    def test_very_long_query(self):
        long_q = "artificial intelligence " * 50
        pq = self._parse(long_q)
        assert pq is not None

    def test_query_with_special_characters(self):
        pq = self._parse("C++ vs Python 3.12 performance 2024?")
        assert pq is not None

    def test_language_detection_english(self):
        pq = self._parse("AI regulation news")
        lang = pq.get("language", "")
        if lang:
            assert lang in ("en", "english", "")

    def test_language_detection_chinese(self):
        pq = self._parse("人工智能监管最新动态")
        lang = pq.get("language", "")
        if lang:
            assert lang in ("zh", "chinese", "zh-cn", "")


# ===========================================================================
# RRF Fusion
# ===========================================================================

class TestRRFFusion:
    """Tests for Reciprocal Rank Fusion score computation."""

    # Standard RRF formula: score(d) = Σ 1/(k + rank(d, r)) for each ranking r
    # Default k in most implementations: 60

    def test_single_ranking(self):
        """RRF of a single ranking reproduces 1/(k+rank) ordering."""
        ranking = ["a", "b", "c", "d"]
        scores = rrf_score([ranking])
        assert scores["a"] > scores["b"] > scores["c"] > scores["d"]

    def test_two_identical_rankings(self):
        """Two identical rankings should double the scores but keep the order."""
        ranking = ["a", "b", "c"]
        scores_one = rrf_score([ranking])
        scores_two = rrf_score([ranking, ranking])
        assert scores_two["a"] > scores_one["a"]
        # Order must be preserved
        assert scores_two["a"] > scores_two["b"] > scores_two["c"]

    def test_doc_missing_from_some_rankings(self):
        """Docs not present in a ranking should still get a score from others."""
        ranking1 = ["a", "b"]
        ranking2 = ["b", "c"]
        scores = rrf_score([ranking1, ranking2])
        assert "a" in scores
        assert "b" in scores
        assert "c" in scores
        # b appears in both → should score higher than a or c (each in only one)
        assert scores["b"] >= scores["a"]
        assert scores["b"] >= scores["c"]

    def test_empty_rankings(self):
        """Empty input should return an empty dict."""
        assert rrf_score([]) == {}

    def test_empty_individual_ranking(self):
        """A ranking that is an empty list should be ignored."""
        scores = rrf_score([[], ["a", "b"]])
        assert "a" in scores
        assert "b" in scores

    def test_scores_are_positive(self):
        ranking = ["x", "y", "z"]
        scores = rrf_score([ranking])
        for v in scores.values():
            assert v > 0

    def test_custom_k(self):
        """Smaller k amplifies rank differences; check scores still ordered."""
        ranking = ["a", "b", "c"]
        scores_k1 = rrf_score([ranking], k=1)
        scores_k60 = rrf_score([ranking], k=60)
        # With k=1: rank differences matter more
        ratio_k1 = scores_k1["a"] / scores_k1["b"]
        ratio_k60 = scores_k60["a"] / scores_k60["b"]
        assert ratio_k1 > ratio_k60

    def test_three_rankings_merged(self):
        """Merging three rankings returns all unique docs."""
        r1 = ["a", "b"]
        r2 = ["b", "c"]
        r3 = ["c", "d"]
        scores = rrf_score([r1, r2, r3])
        assert set(scores.keys()) == {"a", "b", "c", "d"}

    def test_single_doc(self):
        scores = rrf_score([["only"]])
        assert "only" in scores
        assert scores["only"] > 0


# ===========================================================================
# Reranking Score
# ===========================================================================

class TestRerankScore:
    """Tests for the composite reranking score function."""

    # Expected signature: rerank_score(bm25, semantic, rrf, freshness, ...) → float
    # All inputs are normalised floats in [0, 1].

    def test_all_zero_inputs(self):
        score = rerank_score(bm25=0.0, semantic=0.0, rrf=0.0, freshness=0.0)
        assert score == 0.0

    def test_all_one_inputs(self):
        score = rerank_score(bm25=1.0, semantic=1.0, rrf=1.0, freshness=1.0)
        assert score > 0.0

    def test_higher_bm25_gives_higher_score(self):
        score_high = rerank_score(bm25=0.9, semantic=0.5, rrf=0.5, freshness=0.5)
        score_low = rerank_score(bm25=0.1, semantic=0.5, rrf=0.5, freshness=0.5)
        assert score_high > score_low

    def test_higher_semantic_gives_higher_score(self):
        score_high = rerank_score(bm25=0.5, semantic=0.9, rrf=0.5, freshness=0.5)
        score_low = rerank_score(bm25=0.5, semantic=0.1, rrf=0.5, freshness=0.5)
        assert score_high > score_low

    def test_score_bounded(self):
        import random
        random.seed(0)
        for _ in range(20):
            args = {k: random.random() for k in ("bm25", "semantic", "rrf", "freshness")}
            score = rerank_score(**args)
            assert 0.0 <= score <= 1.0, f"Out of range: {score} for {args}"

    def test_custom_weights(self):
        """If weights are supported, higher weight on one component dominates."""
        try:
            s_bm25 = rerank_score(bm25=0.9, semantic=0.1, rrf=0.1, freshness=0.1,
                                   weights={"bm25": 1.0, "semantic": 0.0, "rrf": 0.0, "freshness": 0.0})
            s_sem = rerank_score(bm25=0.1, semantic=0.9, rrf=0.1, freshness=0.1,
                                  weights={"bm25": 0.0, "semantic": 1.0, "rrf": 0.0, "freshness": 0.0})
            assert s_bm25 > s_sem  # bm25=0.9 > semantic=0.9 when only that channel is on
        except TypeError:
            pytest.skip("rerank_score does not support custom weights parameter")


# ===========================================================================
# Freshness Decay
# ===========================================================================

class TestFreshnessDecay:
    """Tests for time-based freshness decay f(age) → [0, 1]."""

    # Expected signature: freshness_decay(published_at: datetime, half_life_days: float) → float

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def test_just_published_score_near_one(self):
        now = self._now()
        score = freshness_decay(now, half_life_days=7)
        assert score > 0.9

    def test_old_article_score_near_zero(self):
        old = self._now() - timedelta(days=365)
        score = freshness_decay(old, half_life_days=7)
        assert score < 0.05

    def test_half_life_is_half(self):
        at_half_life = self._now() - timedelta(days=7)
        score = freshness_decay(at_half_life, half_life_days=7)
        assert abs(score - 0.5) < 0.02  # allow ±2% tolerance

    def test_score_monotonically_decreasing(self):
        """Older articles must always score lower."""
        now = self._now()
        scores = [
            freshness_decay(now - timedelta(days=d), half_life_days=7)
            for d in [0, 1, 3, 7, 14, 30, 90]
        ]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], f"Not monotone at index {i}"

    def test_score_bounded(self):
        now = self._now()
        for days in [0, 1, 7, 30, 180, 365, 1000]:
        	score = freshness_decay(now - timedelta(days=days), half_life_days=7)
        	assert 0.0 <= score <= 1.0, f"Out of range for {days}d: {score}"

    def test_longer_half_life_decays_slower(self):
        one_week_ago = self._now() - timedelta(days=7)
        score_short = freshness_decay(one_week_ago, half_life_days=3)
        score_long = freshness_decay(one_week_ago, half_life_days=30)
        assert score_long > score_short

    def test_future_date_handled_gracefully(self):
        future = self._now() + timedelta(days=1)
        score = freshness_decay(future, half_life_days=7)
        # Should not crash; score should be ≥ 1.0 capped to 1.0, or just 1.0
        assert 0.0 <= score <= 1.0

    def test_naive_datetime_handled(self):
        """Naive datetime (no tzinfo) should not cause a crash."""
        naive = datetime.utcnow()
        try:
            score = freshness_decay(naive, half_life_days=7)
            assert 0.0 <= score <= 1.0
        except TypeError:
            # Also acceptable: implementation requires tz-aware datetime
            pass


# ===========================================================================
# Integration-style smoke tests (mocked services)
# ===========================================================================

class TestSearchPipelineSmoke:
    """Light integration tests that mock ES and Qdrant."""

    @pytest.fixture()
    def mock_es(self):
        es = AsyncMock()
        es.search.return_value = {
            "hits": {
                "total": {"value": 3},
                "hits": [
                    {"_id": "doc1", "_score": 0.9, "_source": {"title": "AI news", "published_at": "2024-01-01"}},
                    {"_id": "doc2", "_score": 0.7, "_source": {"title": "Tech update", "published_at": "2024-01-02"}},
                    {"_id": "doc3", "_score": 0.5, "_source": {"title": "Finance", "published_at": "2024-01-03"}},
                ],
            }
        }
        return es

    @pytest.fixture()
    def mock_qdrant(self):
        qdrant = MagicMock()
        qdrant.search.return_value = [
            MagicMock(id=1, score=0.85, payload={"doc_id": "doc1"}),
            MagicMock(id=3, score=0.6, payload={"doc_id": "doc3"}),
        ]
        return qdrant

    def test_rrf_fusion_with_es_and_qdrant_results(self, mock_es, mock_qdrant):
        """Simulate merging BM25 and semantic rankings via RRF."""
        es_ranking = ["doc1", "doc2", "doc3"]
        qdrant_ranking = ["doc1", "doc3"]
        scores = rrf_score([es_ranking, qdrant_ranking])
        # doc1 in both rankings → highest combined score
        assert scores["doc1"] >= scores["doc2"]
        assert scores["doc1"] >= scores["doc3"]

    def test_freshness_penalty_on_old_article(self):
        """Freshness decay should significantly penalise week-old articles."""
        now = datetime.now(timezone.utc)
        fresh_score = freshness_decay(now, half_life_days=1)
        stale_score = freshness_decay(now - timedelta(days=30), half_life_days=1)
        assert fresh_score > 5 * stale_score  # fresh is at least 5× higher
