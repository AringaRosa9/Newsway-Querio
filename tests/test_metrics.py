"""
tests/test_metrics.py — Unit tests for IR evaluation metrics.

The metrics module (backend/evaluation/metrics.py) is expected to expose:
  ndcg(relevance_grades, ranked_ids, k)  → float
  average_precision(relevant_ids, ranked_ids)  → float
  recall_at_k(relevant_ids, ranked_ids, k)  → float
  mrr(relevant_ids, ranked_ids)  → float
  precision_at_k(relevant_ids, ranked_ids, k)  → float

All return floats in [0, 1].

We import with a try/except so that the test file can be discovered and
marked XFAIL gracefully when the module doesn't exist yet.
"""

from __future__ import annotations

import math
import sys
import os
import pytest

# ---------------------------------------------------------------------------
# Make backend importable when pytest is run from the project root
# ---------------------------------------------------------------------------
_BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


# ---------------------------------------------------------------------------
# Lazy import — mark the whole module as XFAIL until the impl exists
# ---------------------------------------------------------------------------
try:
    from evaluation.metrics import (  # type: ignore[import]
        ndcg,
        average_precision,
        recall_at_k,
        mrr,
        precision_at_k,
    )
    _MISSING = False
except ImportError:
    _MISSING = True

pytestmark = pytest.mark.xfail(
    _MISSING,
    reason="evaluation.metrics module not yet implemented",
    strict=False,
)


# ===========================================================================
# Helper
# ===========================================================================

def _approx(expected: float, actual: float, tol: float = 1e-4) -> bool:
    return abs(actual - expected) <= tol


# ===========================================================================
# NDCG@k
# ===========================================================================

class TestNDCG:
    """Tests for Normalised Discounted Cumulative Gain."""

    def test_perfect_ranking_binary(self):
        """All relevant docs first → NDCG = 1.0."""
        grades = {"a": 1, "b": 1, "c": 1}
        ranked = ["a", "b", "c", "d", "e"]
        assert _approx(1.0, ndcg(grades, ranked, k=3))

    def test_perfect_ranking_graded(self):
        """Highest-grade doc first, then lower grades → NDCG = 1.0."""
        grades = {"a": 3, "b": 2, "c": 1}
        ranked = ["a", "b", "c", "d"]
        assert _approx(1.0, ndcg(grades, ranked, k=3))

    def test_reversed_ranking(self):
        """Worst-first ordering → NDCG < 1.0 but > 0."""
        grades = {"a": 3, "b": 2, "c": 1}
        ranked = ["c", "b", "a"]
        score = ndcg(grades, ranked, k=3)
        assert 0.0 < score < 1.0

    def test_all_irrelevant(self):
        """No relevant docs in ranking → NDCG = 0.0."""
        grades = {"a": 2, "b": 1}
        ranked = ["x", "y", "z"]
        assert _approx(0.0, ndcg(grades, ranked, k=3))

    def test_empty_ranking(self):
        """Empty ranked list → NDCG = 0.0."""
        grades = {"a": 1}
        assert _approx(0.0, ndcg(grades, [], k=5))

    def test_empty_grades(self):
        """No relevant docs defined → NDCG = 0.0 or 1.0 (implementation choice)."""
        score = ndcg({}, ["a", "b"], k=2)
        assert score in (0.0, 1.0)  # both are defensible

    def test_k_truncation(self):
        """Only top-k positions matter."""
        grades = {"a": 1, "b": 1}
        # Both relevant docs outside top-1 window
        ranked = ["x", "a", "b"]
        score_k1 = ndcg(grades, ranked, k=1)
        score_k3 = ndcg(grades, ranked, k=3)
        assert score_k1 == 0.0
        assert score_k3 > 0.0

    def test_single_relevant_doc(self):
        """Exactly one relevant doc at position 1 → NDCG = 1.0."""
        grades = {"a": 1}
        assert _approx(1.0, ndcg(grades, ["a", "b", "c"], k=3))

    def test_single_relevant_doc_at_position_2(self):
        """Single relevant doc at position 2 → NDCG < 1.0."""
        grades = {"a": 1}
        score = ndcg(grades, ["x", "a", "b"], k=3)
        assert 0.0 < score < 1.0

    def test_k_larger_than_ranking(self):
        """k > len(ranked) should not crash."""
        grades = {"a": 1}
        score = ndcg(grades, ["a"], k=100)
        assert _approx(1.0, score)


# ===========================================================================
# Average Precision (MAP component)
# ===========================================================================

class TestAP:
    """Tests for Average Precision."""

    def test_all_relevant_first(self):
        relevant = {"a", "b", "c"}
        ranked = ["a", "b", "c", "d", "e"]
        assert _approx(1.0, average_precision(relevant, ranked))

    def test_all_irrelevant(self):
        relevant = {"a", "b"}
        ranked = ["x", "y", "z"]
        assert _approx(0.0, average_precision(relevant, ranked))

    def test_empty_relevant(self):
        score = average_precision(set(), ["a", "b"])
        assert score in (0.0, 1.0)

    def test_empty_ranking(self):
        assert _approx(0.0, average_precision({"a"}, []))

    def test_single_relevant_at_position_1(self):
        assert _approx(1.0, average_precision({"a"}, ["a", "b", "c"]))

    def test_single_relevant_at_position_3(self):
        # AP = 1/3
        assert _approx(1 / 3, average_precision({"c"}, ["a", "b", "c"]))

    def test_two_relevant_interleaved(self):
        # P@1 = 1, P@3 = 2/3 → AP = (1 + 2/3) / 2 = 5/6
        relevant = {"a", "c"}
        ranked = ["a", "b", "c", "d"]
        assert _approx(5 / 6, average_precision(relevant, ranked))

    def test_duplicate_ids_in_ranking(self):
        """Duplicates should not inflate the score."""
        relevant = {"a"}
        ranked = ["a", "a", "b"]  # 'a' appears twice
        score = average_precision(relevant, ranked)
        assert 0.0 <= score <= 1.0


# ===========================================================================
# Recall@k
# ===========================================================================

class TestRecallAtK:
    """Tests for Recall@k."""

    def test_all_found_in_top_k(self):
        assert _approx(1.0, recall_at_k({"a", "b"}, ["a", "b", "c"], k=2))

    def test_none_found(self):
        assert _approx(0.0, recall_at_k({"a", "b"}, ["x", "y"], k=2))

    def test_partial_recall(self):
        assert _approx(0.5, recall_at_k({"a", "b"}, ["a", "x", "y"], k=3))

    def test_empty_relevant(self):
        score = recall_at_k(set(), ["a", "b"], k=2)
        assert score in (0.0, 1.0)

    def test_empty_ranking(self):
        assert _approx(0.0, recall_at_k({"a"}, [], k=5))

    def test_k_zero(self):
        assert _approx(0.0, recall_at_k({"a"}, ["a", "b"], k=0))

    def test_k_larger_than_list(self):
        score = recall_at_k({"a", "b"}, ["a", "b"], k=100)
        assert _approx(1.0, score)


# ===========================================================================
# MRR
# ===========================================================================

class TestMRR:
    """Tests for Mean Reciprocal Rank (single-query variant)."""

    def test_first_relevant_at_rank_1(self):
        assert _approx(1.0, mrr({"a"}, ["a", "b", "c"]))

    def test_first_relevant_at_rank_2(self):
        assert _approx(0.5, mrr({"b"}, ["a", "b", "c"]))

    def test_first_relevant_at_rank_3(self):
        assert _approx(1 / 3, mrr({"c"}, ["a", "b", "c"]))

    def test_no_relevant_found(self):
        assert _approx(0.0, mrr({"z"}, ["a", "b", "c"]))

    def test_empty_relevant(self):
        score = mrr(set(), ["a", "b"])
        assert score in (0.0, 1.0)

    def test_empty_ranking(self):
        assert _approx(0.0, mrr({"a"}, []))

    def test_multiple_relevant_first_rank_counts(self):
        """MRR uses the first relevant hit, regardless of how many follow."""
        assert _approx(1.0, mrr({"a", "b"}, ["a", "b", "c"]))
        assert _approx(0.5, mrr({"b", "c"}, ["a", "b", "c"]))


# ===========================================================================
# Precision@k
# ===========================================================================

class TestPrecisionAtK:
    """Tests for Precision@k."""

    def test_perfect(self):
        assert _approx(1.0, precision_at_k({"a", "b", "c"}, ["a", "b", "c"], k=3))

    def test_zero_precision(self):
        assert _approx(0.0, precision_at_k({"a"}, ["x", "y", "z"], k=3))

    def test_half_precision(self):
        assert _approx(0.5, precision_at_k({"a", "c"}, ["a", "b", "c", "d"], k=4))

    def test_k_equals_one(self):
        assert _approx(1.0, precision_at_k({"a"}, ["a", "b", "c"], k=1))
        assert _approx(0.0, precision_at_k({"b"}, ["a", "b", "c"], k=1))

    def test_k_zero(self):
        score = precision_at_k({"a"}, ["a", "b"], k=0)
        assert score in (0.0, 1.0)

    def test_k_larger_than_list(self):
        score = precision_at_k({"a"}, ["a", "b"], k=100)
        assert 0.0 <= score <= 1.0

    def test_empty_ranking(self):
        assert _approx(0.0, precision_at_k({"a"}, [], k=5))

    def test_empty_relevant(self):
        score = precision_at_k(set(), ["a", "b"], k=2)
        assert score in (0.0, 1.0)


# ===========================================================================
# Cross-metric sanity checks
# ===========================================================================

class TestCrossMetric:
    """Invariants that must hold across all metrics."""

    RELEVANT = {"a", "b", "c"}
    RANKED_PERFECT = ["a", "b", "c", "d", "e"]
    RANKED_NONE = ["x", "y", "z", "w", "v"]
    K = 3

    def test_perfect_ranking_all_metrics(self):
        grades = {d: 1 for d in self.RELEVANT}
        assert _approx(1.0, ndcg(grades, self.RANKED_PERFECT, k=self.K))
        assert _approx(1.0, average_precision(self.RELEVANT, self.RANKED_PERFECT))
        assert _approx(1.0, recall_at_k(self.RELEVANT, self.RANKED_PERFECT, k=self.K))
        assert _approx(1.0, mrr(self.RELEVANT, self.RANKED_PERFECT))
        assert _approx(1.0, precision_at_k(self.RELEVANT, self.RANKED_PERFECT, k=self.K))

    def test_no_hits_all_metrics(self):
        grades = {d: 1 for d in self.RELEVANT}
        assert _approx(0.0, ndcg(grades, self.RANKED_NONE, k=self.K))
        assert _approx(0.0, average_precision(self.RELEVANT, self.RANKED_NONE))
        assert _approx(0.0, recall_at_k(self.RELEVANT, self.RANKED_NONE, k=self.K))
        assert _approx(0.0, mrr(self.RELEVANT, self.RANKED_NONE))
        assert _approx(0.0, precision_at_k(self.RELEVANT, self.RANKED_NONE, k=self.K))

    def test_scores_are_bounded(self):
        import random
        random.seed(42)
        all_docs = list("abcdefghijklmnop")
        relevant = set(random.sample(all_docs, 4))
        ranked = random.sample(all_docs, 8)
        grades = {d: random.randint(1, 3) for d in relevant}

        for fn, args in [
            (ndcg, (grades, ranked, 5)),
            (average_precision, (relevant, ranked)),
            (recall_at_k, (relevant, ranked, 5)),
            (mrr, (relevant, ranked)),
            (precision_at_k, (relevant, ranked, 5)),
        ]:
            score = fn(*args)
            assert 0.0 <= score <= 1.0, f"{fn.__name__} returned {score}"
