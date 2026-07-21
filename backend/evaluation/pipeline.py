"""Evaluation pipeline for offline retrieval quality assessment.

Loads a labelled evaluation dataset, runs each query through the search
function, computes standard IR metrics, and aggregates them into a report.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from pydantic import BaseModel

from .metrics import ndcg_at_k, mean_average_precision, recall_at_k, mrr, precision_at_k

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class EvalQuery(BaseModel):
    """A single labelled evaluation query."""

    query: str
    relevant_doc_ids: list[str]
    # Graded relevance: doc_id -> grade (0 = not relevant, 1 = relevant, 2 = highly relevant)
    relevance_grades: dict[str, int]


class EvalResult(BaseModel):
    """Per-query evaluation metrics."""

    query: str
    ndcg: float
    map: float
    recall: float
    mrr: float
    precision: float


class EvalReport(BaseModel):
    """Aggregated evaluation report across all queries."""

    timestamp: datetime
    num_queries: int
    results: list[EvalResult]
    avg_ndcg: float
    avg_map: float
    avg_recall: float
    avg_mrr: float
    avg_precision: float


# ---------------------------------------------------------------------------
# Dataset loader
# ---------------------------------------------------------------------------


def load_eval_dataset(path: str) -> list[EvalQuery]:
    """Load an evaluation dataset from a JSON file.

    Expected format – a JSON array of objects::

        [
          {
            "query": "...",
            "relevant_doc_ids": ["id1", "id2"],
            "relevance_grades": {"id1": 2, "id2": 1, "id3": 0}
          },
          ...
        ]

    Missing ``relevance_grades`` are derived from ``relevant_doc_ids``
    (all given IDs get grade 1).
    """
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)

    queries: list[EvalQuery] = []
    for item in raw:
        # Back-fill grades from relevant_doc_ids if not provided
        if "relevance_grades" not in item or not item["relevance_grades"]:
            item["relevance_grades"] = {
                doc_id: 1 for doc_id in item.get("relevant_doc_ids", [])
            }
        queries.append(EvalQuery(**item))

    logger.info("Loaded %d evaluation queries from %s", len(queries), path)
    return queries


# ---------------------------------------------------------------------------
# Evaluation runner
# ---------------------------------------------------------------------------


async def run_evaluation(
    eval_queries: list[EvalQuery],
    search_fn: Callable[[str], Awaitable[list[dict[str, Any]]]],
) -> EvalReport:
    """Run the evaluation pipeline.

    Args:
        eval_queries: List of labelled queries.
        search_fn: Async callable that accepts a query string and returns a
                   list of result dicts (each must have an ``id`` field).

    Returns:
        An EvalReport with per-query results and aggregate averages.
    """
    results: list[EvalResult] = []

    for eq in eval_queries:
        try:
            retrieved = await search_fn(eq.query)
        except Exception as exc:
            logger.error("Search failed for query '%s': %s", eq.query, exc)
            retrieved = []

        retrieved_ids = [str(r.get("id", "")) for r in retrieved]

        # Build graded relevance list for the retrieved order
        relevance_list = [
            eq.relevance_grades.get(doc_id, 0) for doc_id in retrieved_ids
        ]

        ndcg = ndcg_at_k(relevance_list, k=10)
        map_score = mean_average_precision(relevance_list)
        recall = recall_at_k(set(eq.relevant_doc_ids), retrieved_ids, k=50)
        mrr_score = mrr(relevance_list)
        prec = precision_at_k(relevance_list, k=5)

        results.append(
            EvalResult(
                query=eq.query,
                ndcg=round(ndcg, 4),
                map=round(map_score, 4),
                recall=round(recall, 4),
                mrr=round(mrr_score, 4),
                precision=round(prec, 4),
            )
        )

        logger.debug(
            "Query='%s' NDCG=%.4f MAP=%.4f Recall=%.4f MRR=%.4f P@5=%.4f",
            eq.query,
            ndcg,
            map_score,
            recall,
            mrr_score,
            prec,
        )

    n = len(results)

    def _avg(field: str) -> float:
        if not results:
            return 0.0
        return round(sum(getattr(r, field) for r in results) / n, 4)

    report = EvalReport(
        timestamp=datetime.now(tz=timezone.utc),
        num_queries=n,
        results=results,
        avg_ndcg=_avg("ndcg"),
        avg_map=_avg("map"),
        avg_recall=_avg("recall"),
        avg_mrr=_avg("mrr"),
        avg_precision=_avg("precision"),
    )

    logger.info(
        "Evaluation complete: %d queries | NDCG=%.4f MAP=%.4f Recall=%.4f MRR=%.4f P@5=%.4f",
        n,
        report.avg_ndcg,
        report.avg_map,
        report.avg_recall,
        report.avg_mrr,
        report.avg_precision,
    )
    return report


# ---------------------------------------------------------------------------
# Report persistence
# ---------------------------------------------------------------------------


def save_report(report: EvalReport, path: str) -> None:
    """Serialise an EvalReport to a JSON file.

    Args:
        report: The report to save.
        path: Destination file path (will be created or overwritten).
    """
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report.model_dump(mode="json"), fh, ensure_ascii=False, indent=2)
    logger.info("Evaluation report saved to %s", path)
