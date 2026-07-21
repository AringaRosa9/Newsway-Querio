"""Embedding service using BAAI/bge-m3.

Uses sentence-transformers with a class-level singleton to avoid reloading
the model on every request. Supports both single and batch encoding.
"""

from __future__ import annotations

import logging
import threading
from typing import ClassVar

from core.config import get_settings

logger = logging.getLogger(__name__)

# Maximum characters to feed the model (approximate proxy for 512 tokens)
# bge-m3 uses ~4 chars per token on average for mixed text
_MAX_TEXT_CHARS: int = 2048
_CONTENT_PREVIEW_CHARS: int = 500


class EmbeddingService:
    """Singleton wrapper around a sentence-transformers model.

    The model is loaded lazily on first use and reused across instances
    via a class-level cache. Thread-safe initialisation is handled with a
    lock so multiple simultaneous first-calls don't double-load.
    """

    _model: ClassVar[object | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()
    _model_name: ClassVar[str] = ""

    # ------------------------------------------------------------------ #
    # Construction / singleton model loading                               #
    # ------------------------------------------------------------------ #

    def __init__(self) -> None:
        settings = get_settings()
        self._model_name_inst = settings.EMBEDDING_MODEL
        self._ensure_model_loaded()

    def _ensure_model_loaded(self) -> None:
        """Lazy-load the sentence-transformers model (thread-safe)."""
        if EmbeddingService._model is not None:
            return
        with EmbeddingService._lock:
            if EmbeddingService._model is not None:
                return
            model_name = self._model_name_inst
            logger.info("Loading embedding model: %s", model_name)
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore

                EmbeddingService._model = SentenceTransformer(model_name)
                EmbeddingService._model_name = model_name
                logger.info("Embedding model loaded: %s", model_name)
            except Exception as exc:
                logger.error("Failed to load embedding model %s: %s", model_name, exc)
                raise

    @property
    def _st_model(self):  # type: ignore[return]
        """Return the loaded SentenceTransformer model."""
        return EmbeddingService._model

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _truncate(text: str, max_chars: int = _MAX_TEXT_CHARS) -> str:
        """Truncate text to approximately ``max_chars`` characters."""
        return text[:max_chars]

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def encode(self, text: str) -> list[float]:
        """Encode a single text string into a dense vector.

        The text is truncated to ~512 tokens (approximated as 2048 chars)
        before encoding.
        """
        truncated = self._truncate(text)
        vector = self._st_model.encode(truncated, normalize_embeddings=True)
        return vector.tolist()

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """Batch-encode a list of texts.

        Each text is truncated individually before encoding. Returns a list
        of float lists in the same order as the input.
        """
        truncated = [self._truncate(t) for t in texts]
        vectors = self._st_model.encode(
            truncated,
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]

    def get_query_embedding(self, query: str) -> list[float]:
        """Encode a search query.

        Adds the ``query: `` prefix required by bge-m3's asymmetric
        retrieval mode.
        """
        prefixed = f"query: {query}"
        return self.encode(prefixed)

    def get_document_embedding(self, title: str, content: str) -> list[float]:
        """Encode a document (title + content preview) for indexing.

        Combines the title with the first 500 characters of content so the
        vector captures both the headline signal and article context.
        """
        content_preview = (content or "")[:_CONTENT_PREVIEW_CHARS]
        doc_text = f"{title} {content_preview}".strip()
        return self.encode(doc_text)


# ---------------------------------------------------------------------------
# Module-level singleton accessor (optional convenience)
# ---------------------------------------------------------------------------

_service: EmbeddingService | None = None
_service_lock = threading.Lock()


def get_embedding_service() -> EmbeddingService:
    """Return the module-level EmbeddingService singleton."""
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = EmbeddingService()
    return _service
