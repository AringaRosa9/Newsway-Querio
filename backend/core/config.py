from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "AI News Search"

    # Elasticsearch
    ES_URL: str = "http://localhost:9200"
    ES_INDEX: str = "news_articles"

    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "news_vectors"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Anthropic / Claude
    ANTHROPIC_API_KEY: str = ""

    # Embeddings
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIM: int = 1024

    # Ingestion
    RSS_FETCH_INTERVAL: int = 900  # seconds (15 min)

    # Search
    MAX_SEARCH_RESULTS: int = 50

    # AI summarization
    SUMMARY_MAX_DOCS: int = 10

    # Authentication
    JWT_SECRET: str = "change-me-in-production-use-a-real-secret"

    # Social media
    TWITTER_BEARER_TOKEN: str = ""
    WEIBO_ACCESS_TOKEN: str = ""

    # Email (for subscription notifications)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@ainews.local"

    # Logging
    LOG_LEVEL: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
