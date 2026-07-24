from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.deps import init_services

logging.basicConfig(
    level=get_settings().LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting up %s …", get_settings().APP_NAME)
    await init_services()
    yield
    logger.info("Shutting down %s …", get_settings().APP_NAME)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version="2.0.0",
    description="AI-powered news search and summarisation backend with dialogue, cross-lingual search, and industry verticals.",
    lifespan=lifespan,
)

# Security middleware (order matters: outermost first)
from security.middleware import RateLimitMiddleware, RequestValidationMiddleware  # noqa: E402

app.add_middleware(RequestValidationMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    redis_url=settings.REDIS_URL,
    requests_per_minute=60,
    burst_limit=10,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers  (imported after app is created to avoid circular imports)
# ---------------------------------------------------------------------------

from api.routes import router as api_router  # noqa: E402
from auth.routes import router as auth_router  # noqa: E402
from subscription.routes import router as subscription_router  # noqa: E402
from analytics.routes import router as analytics_router  # noqa: E402
from ab_test.routes import router as ab_test_router  # noqa: E402
from ai.chat_routes import router as chat_router  # noqa: E402

app.include_router(api_router)
app.include_router(auth_router)
app.include_router(subscription_router)
app.include_router(analytics_router)
app.include_router(ab_test_router)
app.include_router(chat_router)


# ---------------------------------------------------------------------------
# Built-in endpoints
# ---------------------------------------------------------------------------


@app.get("/health", tags=["ops"])
async def health() -> dict:
    return {"status": "ok"}


@app.get("/", tags=["ops"])
async def root() -> dict:
    return {
        "app": settings.APP_NAME,
        "version": "2.0.0",
        "docs": "/docs",
    }
