"""A/B testing API routes.

All experiment-management endpoints require authentication.  Variant assignment
and metric recording also require the caller to be logged in so that user_id is
always a stable, real identifier rather than an anonymous session token.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth.routes import require_current_user
from core.deps import get_redis_client
from .service import ABTestService, Experiment, Variant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ab-test", tags=["ab-test"])


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


def _get_ab_service(
    redis: aioredis.Redis = Depends(get_redis_client),
) -> ABTestService:
    return ABTestService(redis)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateExperimentRequest(BaseModel):
    id: str
    name: str
    description: str
    variants: list[Variant]
    status: str = "draft"


class UpdateExperimentRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[str] = None   # ISO-8601 string; service accepts dict
    end_date: Optional[str] = None


class RecordMetricRequest(BaseModel):
    variant_id: str
    metric_name: str
    value: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/experiments", summary="Create a new A/B experiment (auth required)")
async def create_experiment(
    req: CreateExperimentRequest,
    _user: dict = Depends(require_current_user),
    ab_svc: ABTestService = Depends(_get_ab_service),
) -> dict[str, Any]:
    """Create a new experiment.  Status must be one of draft/running/paused/completed.

    At most ``MAX_RUNNING_EXPERIMENTS`` (3) experiments may be in the ``running``
    state at the same time.
    """
    try:
        experiment = Experiment(**req.model_dump())
        created = await ab_svc.create_experiment(experiment)
        return created.model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error creating experiment: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/experiments", summary="List all experiments")
async def list_experiments(
    ab_svc: ABTestService = Depends(_get_ab_service),
) -> list[dict[str, Any]]:
    experiments = await ab_svc.list_experiments()
    return [e.model_dump(mode="json") for e in experiments]


@router.get("/experiments/{experiment_id}", summary="Get experiment details")
async def get_experiment(
    experiment_id: str,
    ab_svc: ABTestService = Depends(_get_ab_service),
) -> dict[str, Any]:
    experiment = await ab_svc.get_experiment(experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return experiment.model_dump(mode="json")


@router.put("/experiments/{experiment_id}", summary="Update an experiment (auth required)")
async def update_experiment(
    experiment_id: str,
    req: UpdateExperimentRequest,
    _user: dict = Depends(require_current_user),
    ab_svc: ABTestService = Depends(_get_ab_service),
) -> dict[str, Any]:
    """Update mutable fields of an experiment.

    Only non-None fields in the request body are applied.  Transitioning to
    ``running`` will fail if the running-experiment cap is already reached.
    """
    updates: dict[str, Any] = {
        k: v for k, v in req.model_dump().items() if v is not None
    }
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")
    try:
        updated = await ab_svc.update_experiment(experiment_id, updates)
        return updated.model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error updating experiment '%s': %s", experiment_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/experiments/{experiment_id}/assign",
    summary="Assign current user to a variant (auth required)",
)
async def assign_variant(
    experiment_id: str,
    user: dict = Depends(require_current_user),
    ab_svc: ABTestService = Depends(_get_ab_service),
) -> dict[str, str]:
    """Return the variant id assigned to the authenticated user.

    The assignment is deterministic and sticky — the same user always receives
    the same variant for a given experiment.
    """
    try:
        variant_id = await ab_svc.assign_variant(experiment_id, user["id"])
        return {"experiment_id": experiment_id, "variant_id": variant_id, "user_id": user["id"]}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception(
            "Unexpected error assigning variant for experiment '%s': %s", experiment_id, exc
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/experiments/{experiment_id}/metrics",
    summary="Record a metric observation (auth required)",
)
async def record_metric(
    experiment_id: str,
    req: RecordMetricRequest,
    _user: dict = Depends(require_current_user),
    ab_svc: ABTestService = Depends(_get_ab_service),
) -> dict[str, str]:
    """Append a single metric value for a variant within the given experiment."""
    try:
        await ab_svc.record_metric(
            experiment_id=experiment_id,
            variant_id=req.variant_id,
            metric_name=req.metric_name,
            value=req.value,
        )
        return {"status": "ok"}
    except Exception as exc:
        logger.exception(
            "Unexpected error recording metric for experiment '%s': %s", experiment_id, exc
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/experiments/{experiment_id}/results",
    summary="Get statistical results for an experiment",
)
async def get_results(
    experiment_id: str,
    ab_svc: ABTestService = Depends(_get_ab_service),
) -> dict[str, Any]:
    """Return per-variant sample sizes, metric means, and Welch t-test p-values.

    The control group is always the first variant in the experiment definition.
    P-values are computed using a normal approximation — most reliable when
    each variant has at least 30 observations.
    """
    try:
        return await ab_svc.get_results(experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception(
            "Unexpected error computing results for experiment '%s': %s", experiment_id, exc
        )
        raise HTTPException(status_code=500, detail="Internal server error")
