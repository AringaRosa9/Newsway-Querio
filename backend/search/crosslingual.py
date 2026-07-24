"""Cross-language search: Chinese-English mutual retrieval with auto-translation."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from collections import OrderedDict
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

_MODEL_ID = "claude-sonnet-4-20250514"
_TRANSLATION_CACHE: OrderedDict[str, str] = OrderedDict()
_CACHE_MAX = 1000


def detect_language(text: str) -> str:
    if not text.strip():
        return "en"
    cjk_count = sum(1 for c in text if "一" <= c <= "鿿")
    total = len(text.replace(" ", ""))
    if total == 0:
        return "en"
    ratio = cjk_count / total
    if ratio > 0.3:
        return "zh"
    if ratio < 0.05:
        return "en"
    return "mixed"


def _cache_key(text: str, src: str, tgt: str) -> str:
    return hashlib.md5(f"{src}:{tgt}:{text}".encode()).hexdigest()


async def translate_query(
    query: str, source_lang: str, target_lang: str, api_key: str
) -> str:
    if not api_key or not query.strip():
        return query

    key = _cache_key(query, source_lang, target_lang)
    if key in _TRANSLATION_CACHE:
        _TRANSLATION_CACHE.move_to_end(key)
        return _TRANSLATION_CACHE[key]

    lang_names = {"zh": "Chinese", "en": "English"}
    src_name = lang_names.get(source_lang, source_lang)
    tgt_name = lang_names.get(target_lang, target_lang)

    prompt = (
        f"Translate the following {src_name} search query to {tgt_name}. "
        f"Output only the translation, nothing else.\n\n{query}"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.messages.create(
                model=_MODEL_ID,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            ),
        )
        translated = response.content[0].text.strip() if response.content else query
    except Exception as exc:
        logger.warning("Translation failed: %s", exc)
        return query

    _TRANSLATION_CACHE[key] = translated
    if len(_TRANSLATION_CACHE) > _CACHE_MAX:
        _TRANSLATION_CACHE.popitem(last=False)

    return translated


async def crosslingual_search(
    es_client: Any,
    qdrant_client: Any,
    query: str,
    query_vector: list[float],
    filters: dict,
    top_k: int,
    api_key: str,
) -> list[dict]:
    from search.retrieval import hybrid_search, rrf_fusion
    from ai.embedding import get_embedding_service

    lang = detect_language(query)

    primary_results = await hybrid_search(
        es_client=es_client,
        qdrant_client=qdrant_client,
        query=query,
        query_vector=query_vector,
        filters=filters,
        top_k=top_k,
    )

    if lang == "mixed":
        for r in primary_results:
            r["language"] = detect_language(r.get("title", "") + r.get("content", ""))
        return primary_results

    target_lang = "en" if lang == "zh" else "zh"
    translated = await translate_query(query, lang, target_lang, api_key)

    if translated == query:
        for r in primary_results:
            r["language"] = lang
        return primary_results

    try:
        embedding_svc = get_embedding_service()
        translated_vector = embedding_svc.get_query_embedding(translated)
        secondary_results = await hybrid_search(
            es_client=es_client,
            qdrant_client=qdrant_client,
            query=translated,
            query_vector=translated_vector,
            filters=filters,
            top_k=top_k,
        )
    except Exception as exc:
        logger.warning("Secondary language search failed: %s", exc)
        for r in primary_results:
            r["language"] = lang
        return primary_results

    primary_ids = [str(r.get("id", "")) for r in primary_results]
    secondary_ids = [str(r.get("id", "")) for r in secondary_results]

    fused_scores = rrf_fusion([primary_ids, secondary_ids])

    all_docs: dict[str, dict] = {}
    for r in primary_results:
        rid = str(r.get("id", ""))
        r["language"] = detect_language(r.get("title", ""))
        all_docs[rid] = r
    for r in secondary_results:
        rid = str(r.get("id", ""))
        if rid not in all_docs:
            r["language"] = detect_language(r.get("title", ""))
            all_docs[rid] = r

    seen_urls: set[str] = set()
    merged: list[dict] = []
    for doc_id, score in sorted(fused_scores.items(), key=lambda x: -x[1]):
        if doc_id in all_docs:
            doc = all_docs[doc_id]
            url = doc.get("url", "")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            doc["cross_lingual_score"] = score
            merged.append(doc)

    return merged[:top_k]


async def translate_snippet(text: str, target_lang: str, api_key: str) -> str:
    if not text or not api_key:
        return text
    truncated = text[:200]
    return await translate_query(truncated, "auto", target_lang, api_key)
