"""Information retrieval evaluation metrics.

All functions handle edge cases gracefully (empty input, all-zero relevance,
k larger than the list, etc.).
"""

from __future__ import annotations

import math


def _dcg(relevance_scores: list[int], k: int) -> float:
    """Discounted Cumulative Gain at k."""
    total = 0.0
    for i, rel in enumerate(relevance_scores[:k], start=1):
        total += rel / math.log2(i + 1)
    return total


def ndcg_at_k(relevance_scores: list[int], k: int = 10) -> float:
    """Normalised Discounted Cumulative Gain at k.

    Args:
        relevance_scores: Ordered list of relevance grades (0, 1, 2, …) for
                          retrieved documents. Grade 0 = not relevant.
        k: Cut-off rank.

    Returns:
        NDCG@k in [0, 1]. Returns 0.0 for empty input or all-zero relevance.
    """
    if not relevance_scores or k <= 0:
        return 0.0

    dcg = _dcg(relevance_scores, k)

    # Ideal DCG: sort relevance scores descending, compute DCG
    ideal_scores = sorted(relevance_scores, reverse=True)
    idcg = _dcg(ideal_scores, k)

    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def mean_average_precision(relevance_scores: list[int]) -> float:
    """Mean Average Precision (MAP) over a single ranked list.

    Treats any score >= 1 as relevant.  For a single-query list this
    equals Average Precision (AP).

    Args:
        relevance_scores: Ordered list of binary-like relevance grades.

    Returns:
        MAP in [0, 1]. Returns 0.0 for empty input.
    """
    if not relevance_scores:
        return 0.0

    num_relevant = sum(1 for r in relevance_scores if r >= 1)
    if num_relevant == 0:
        return 0.0

    precision_sum = 0.0
    relevant_seen = 0
    for i, rel in enumerate(relevance_scores, start=1):
        if rel >= 1:
            relevant_seen += 1
            precision_sum += relevant_seen / i

    return precision_sum / num_relevant


def recall_at_k(relevant_ids: set[str], retrieved_ids: list[str], k: int = 50) -> float:
    """Recall at k.

    Args:
        relevant_ids: Ground-truth set of relevant document IDs.
        retrieved_ids: Ordered list of retrieved document IDs.
        k: Cut-off rank.

    Returns:
        Recall@k in [0, 1]. Returns 0.0 if no relevant docs exist.
    """
    if not relevant_ids or k <= 0:
        return 0.0

    top_k_ids = set(retrieved_ids[:k])
    hits = len(relevant_ids & top_k_ids)
    return hits / len(relevant_ids)


def mrr(relevance_scores: list[int]) -> float:
    """Mean Reciprocal Rank (MRR).

    For a single-query ranked list, finds the first relevant document and
    returns 1 / rank.

    Args:
        relevance_scores: Ordered list of relevance grades (>= 1 = relevant).

    Returns:
        MRR in [0, 1]. Returns 0.0 if no relevant document is found.
    """
    for i, rel in enumerate(relevance_scores, start=1):
        if rel >= 1:
            return 1.0 / i
    return 0.0


def precision_at_k(relevance_scores: list[int], k: int = 5) -> float:
    """Precision at k.

    Args:
        relevance_scores: Ordered list of relevance grades (>= 1 = relevant).
        k: Cut-off rank.

    Returns:
        P@k in [0, 1]. Returns 0.0 for empty input or k <= 0.
    """
    if not relevance_scores or k <= 0:
        return 0.0

    top_k = relevance_scores[:k]
    relevant = sum(1 for r in top_k if r >= 1)
    return relevant / len(top_k)
