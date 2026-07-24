"""A/B testing service.

Experiments are stored as JSON blobs in a Redis hash (``ab_experiments``).
Variant assignments are sticky — once a user is assigned to a variant the
mapping is persisted in a Redis set so subsequent calls return the same value.
Metric values are appended to a Redis list and statistical results are computed
on-the-fly using Welch's t-test with a normal approximation for the p-value.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from datetime import datetime, timezone
from typing import Any, Optional

import redis.asyncio as aioredis
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis key constants
# ---------------------------------------------------------------------------

_EXPERIMENTS_HASH = "ab_experiments"
_ASSIGN_KEY = "ab_assign:{experiment_id}:{variant_id}"   # Redis SET
_METRICS_KEY = "ab_metrics:{experiment_id}:{variant_id}:{metric_name}"  # Redis LIST

# Maximum simultaneous running experiments (see DEVPLAN)
MAX_RUNNING_EXPERIMENTS = 3


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class Variant(BaseModel):
    id: str
    name: str
    weight: float = 1.0


class Experiment(BaseModel):
    id: str                          # slug, e.g. "ranking-v2"
    name: str
    description: str
    variants: list[Variant]
    status: str = "draft"            # draft | running | paused | completed
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))


# ---------------------------------------------------------------------------
# Helpers — Welch's t-test with normal approximation (no scipy dependency)
# ---------------------------------------------------------------------------


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _variance(values: list[float]) -> float:
    """Unbiased sample variance (Bessel-corrected)."""
    n = len(values)
    if n < 2:
        return 0.0
    mu = _mean(values)
    return sum((x - mu) ** 2 for x in values) / (n - 1)


def _welch_t_and_p(a: list[float], b: list[float]) -> tuple[float, float]:
    """Return (t_statistic, two-tailed_p_value) for Welch's t-test.

    P-value is approximated via the standard normal CDF, which is accurate
    when sample sizes are reasonably large (n >= 30 each).  For small samples
    it is a conservative approximation.
    """
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return 0.0, 1.0

    var1 = _variance(a)
    var2 = _variance(b)
    se = math.sqrt(var1 / n1 + var2 / n2)

    if se == 0.0:
        # Both groups have identical values.  If means also match there is no
        # difference; if means differ the groups are perfectly separated.
        mean_diff = _mean(a) - _mean(b)
        if mean_diff == 0.0:
            return 0.0, 1.0
        # Return a large sentinel t and a very small p to signal certain effect.
        return (1e9 if mean_diff > 0 else -1e9), 0.0

    t = (_mean(a) - _mean(b)) / se

    # Normal approximation: P(|Z| > |t|) = 2 * (1 - Φ(|t|))
    # We use the rational approximation for Φ from Abramowitz & Stegun §26.2.17
    def _std_normal_cdf(z: float) -> float:
        """Approximation of the standard normal CDF, accurate to ~7.5e-8."""
        t_coef = 1.0 / (1.0 + 0.2316419 * abs(z))
        poly = t_coef * (
            0.319381530
            + t_coef * (
                -0.356563782
                + t_coef * (
                    1.781477937
                    + t_coef * (-1.821255978 + t_coef * 1.330274429)
                )
            )
        )
        pdf = math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)
        cdf = 1.0 - pdf * poly
        return cdf if z >= 0 else 1.0 - cdf

    p_value = 2.0 * (1.0 - _std_normal_cdf(abs(t)))
    return t, p_value


# ---------------------------------------------------------------------------
# ABTestService
# ---------------------------------------------------------------------------


class ABTestService:
    """Manages A/B experiments backed by Redis."""

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_experiment(self, experiment: Experiment) -> Experiment:
        """Persist a new experiment.

        Raises ``ValueError`` if the experiment id already exists or if adding
        it would exceed MAX_RUNNING_EXPERIMENTS.
        """
        existing_raw = await self._redis.hget(_EXPERIMENTS_HASH, experiment.id)
        if existing_raw is not None:
            raise ValueError(f"Experiment '{experiment.id}' already exists.")

        if experiment.status == "running":
            await self._check_running_cap(exclude_id=None)

        payload = experiment.model_dump_json()
        await self._redis.hset(_EXPERIMENTS_HASH, experiment.id, payload)
        logger.info("Created experiment '%s'", experiment.id)
        return experiment

    async def get_experiment(self, experiment_id: str) -> Experiment | None:
        raw = await self._redis.hget(_EXPERIMENTS_HASH, experiment_id)
        if raw is None:
            return None
        return Experiment.model_validate_json(raw)

    async def list_experiments(self) -> list[Experiment]:
        all_values: dict[str, str] = await self._redis.hgetall(_EXPERIMENTS_HASH)
        experiments: list[Experiment] = []
        for raw in all_values.values():
            try:
                experiments.append(Experiment.model_validate_json(raw))
            except Exception as exc:
                logger.warning("Failed to parse experiment JSON: %s", exc)
        experiments.sort(key=lambda e: e.created_at, reverse=True)
        return experiments

    async def update_experiment(
        self, experiment_id: str, updates: dict[str, Any]
    ) -> Experiment:
        """Apply ``updates`` to an existing experiment and persist it.

        Raises ``ValueError`` if the experiment does not exist or the update
        would violate the running-experiment cap.
        """
        experiment = await self.get_experiment(experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment '{experiment_id}' not found.")

        new_status = updates.get("status", experiment.status)
        if new_status == "running" and experiment.status != "running":
            await self._check_running_cap(exclude_id=experiment_id)

        # Apply updates field by field
        data = experiment.model_dump()
        for key, value in updates.items():
            if key in data:
                data[key] = value

        updated = Experiment.model_validate(data)
        await self._redis.hset(_EXPERIMENTS_HASH, experiment_id, updated.model_dump_json())
        logger.info("Updated experiment '%s': %s", experiment_id, list(updates.keys()))
        return updated

    # ------------------------------------------------------------------
    # Assignment
    # ------------------------------------------------------------------

    async def assign_variant(self, experiment_id: str, user_id: str) -> str:
        """Return the variant id for a given user (deterministic & sticky).

        Assignment is determined by hashing ``user_id + experiment_id`` and
        bucketing into the weighted variant list.  The chosen variant is stored
        in a Redis set so the assignment sticks for subsequent calls.
        """
        experiment = await self.get_experiment(experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment '{experiment_id}' not found.")

        if experiment.status not in ("running",):
            raise ValueError(
                f"Experiment '{experiment_id}' is not running (status={experiment.status})."
            )

        # Check if user already has a sticky assignment
        for variant in experiment.variants:
            assign_key = _ASSIGN_KEY.format(
                experiment_id=experiment_id, variant_id=variant.id
            )
            is_assigned = await self._redis.sismember(assign_key, user_id)
            if is_assigned:
                logger.debug(
                    "Sticky assignment: user=%s experiment=%s variant=%s",
                    user_id,
                    experiment_id,
                    variant.id,
                )
                return variant.id

        # Deterministic new assignment via weighted hash
        total_weight = sum(v.weight for v in experiment.variants)
        digest = hashlib.md5(f"{user_id}{experiment_id}".encode()).hexdigest()
        bucket = (int(digest, 16) % 10_000) / 10_000.0 * total_weight

        cumulative = 0.0
        chosen_variant = experiment.variants[-1]  # fallback to last
        for variant in experiment.variants:
            cumulative += variant.weight
            if bucket < cumulative:
                chosen_variant = variant
                break

        # Persist sticky assignment
        assign_key = _ASSIGN_KEY.format(
            experiment_id=experiment_id, variant_id=chosen_variant.id
        )
        await self._redis.sadd(assign_key, user_id)
        logger.debug(
            "New assignment: user=%s experiment=%s variant=%s bucket=%.4f",
            user_id,
            experiment_id,
            chosen_variant.id,
            bucket,
        )
        return chosen_variant.id

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    async def record_metric(
        self,
        experiment_id: str,
        variant_id: str,
        metric_name: str,
        value: float,
    ) -> None:
        """Append a metric observation to the appropriate Redis list."""
        key = _METRICS_KEY.format(
            experiment_id=experiment_id,
            variant_id=variant_id,
            metric_name=metric_name,
        )
        await self._redis.rpush(key, str(value))
        logger.debug(
            "Recorded metric: experiment=%s variant=%s metric=%s value=%s",
            experiment_id,
            variant_id,
            metric_name,
            value,
        )

    async def get_results(self, experiment_id: str) -> dict[str, Any]:
        """Compute per-variant statistics and pairwise p-values.

        Returns a dict with:
        - ``experiment_id``
        - ``variants``: list of per-variant summaries (sample_size, metric means)
        - ``comparisons``: pairwise Welch t-test results for each metric
        """
        experiment = await self.get_experiment(experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment '{experiment_id}' not found.")

        # Collect raw metric values per variant
        variant_data: dict[str, dict[str, list[float]]] = {}
        all_metric_names: set[str] = set()

        for variant in experiment.variants:
            metrics: dict[str, list[float]] = {}
            # Scan for all metric keys belonging to this variant
            pattern = _METRICS_KEY.format(
                experiment_id=experiment_id,
                variant_id=variant.id,
                metric_name="*",
            )
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
                for key in keys:
                    # Extract metric name from the key suffix
                    prefix = _METRICS_KEY.format(
                        experiment_id=experiment_id,
                        variant_id=variant.id,
                        metric_name="",
                    )
                    metric_name = key[len(prefix):]
                    raw_values = await self._redis.lrange(key, 0, -1)
                    parsed = [float(v) for v in raw_values]
                    metrics[metric_name] = parsed
                    all_metric_names.add(metric_name)
                if cursor == 0:
                    break

            # Also count assignments from the sticky set
            assign_key = _ASSIGN_KEY.format(
                experiment_id=experiment_id, variant_id=variant.id
            )
            sample_size = await self._redis.scard(assign_key)

            variant_data[variant.id] = {
                "_sample_size": sample_size,  # type: ignore[assignment]
                **metrics,
            }

        # Build per-variant summary
        variant_summaries: list[dict[str, Any]] = []
        for variant in experiment.variants:
            vd = variant_data.get(variant.id, {})
            sample_size = vd.pop("_sample_size", 0)
            summary: dict[str, Any] = {
                "variant_id": variant.id,
                "variant_name": variant.name,
                "sample_size": sample_size,
                "metrics": {},
            }
            for metric_name, values in vd.items():
                summary["metrics"][metric_name] = {
                    "mean": round(_mean(values), 6),
                    "variance": round(_variance(values), 6),
                    "n": len(values),
                }
            variant_summaries.append(summary)
            # Restore for pairwise comparison below
            variant_data[variant.id] = {**vd, "_sample_size": sample_size}

        # Pairwise comparisons (control = first variant) for each metric
        comparisons: list[dict[str, Any]] = []
        if len(experiment.variants) >= 2:
            control_id = experiment.variants[0].id
            control_metrics = variant_data.get(control_id, {})
            for treatment in experiment.variants[1:]:
                treatment_metrics = variant_data.get(treatment.id, {})
                per_metric: dict[str, Any] = {}
                for metric_name in all_metric_names:
                    ctrl_vals = control_metrics.get(metric_name, [])
                    treat_vals = treatment_metrics.get(metric_name, [])
                    if isinstance(ctrl_vals, int):  # was _sample_size, skip
                        continue
                    t_stat, p_val = _welch_t_and_p(ctrl_vals, treat_vals)
                    per_metric[metric_name] = {
                        "t_statistic": round(t_stat, 6),
                        "p_value": round(p_val, 6),
                        "significant": p_val < 0.05,
                    }
                comparisons.append(
                    {
                        "control": control_id,
                        "treatment": treatment.id,
                        "metrics": per_metric,
                    }
                )

        return {
            "experiment_id": experiment_id,
            "experiment_name": experiment.name,
            "status": experiment.status,
            "variants": variant_summaries,
            "comparisons": comparisons,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _check_running_cap(self, exclude_id: str | None) -> None:
        """Raise ValueError if MAX_RUNNING_EXPERIMENTS would be exceeded."""
        experiments = await self.list_experiments()
        running_count = sum(
            1
            for e in experiments
            if e.status == "running" and e.id != exclude_id
        )
        if running_count >= MAX_RUNNING_EXPERIMENTS:
            raise ValueError(
                f"Cannot have more than {MAX_RUNNING_EXPERIMENTS} running experiments "
                f"simultaneously.  Pause or complete an existing one first."
            )
