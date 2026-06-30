import hashlib
import json
import logging
import os
from typing import Optional

import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "86400"))

try:
    _redis_client: Optional[redis.Redis] = redis.Redis.from_url(
        REDIS_URL, decode_responses=True, socket_connect_timeout=2
    )
    _redis_client.ping()
    logger.info("Connected to Redis at %s", REDIS_URL)
except Exception as error:  # pragma: no cover - depends on runtime environment
    logger.warning("Redis unavailable (%s); caching disabled.", error)
    _redis_client = None


def _build_key(namespace: str, payload: str) -> str:
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{namespace}:{digest}"


def get_cached(namespace: str, payload: str) -> Optional[str]:
    if _redis_client is None:
        return None
    try:
        return _redis_client.get(_build_key(namespace, payload))
    except redis.RedisError as error:
        logger.warning("Redis get failed (%s); skipping cache.", error)
        return None


def set_cached(namespace: str, payload: str, value: str) -> None:
    if _redis_client is None:
        return
    try:
        _redis_client.set(_build_key(namespace, payload), value, ex=CACHE_TTL_SECONDS)
    except redis.RedisError as error:
        logger.warning("Redis set failed (%s); skipping cache.", error)


def cached_llm_call(namespace: str, payload: str, compute):
    """Return ``(value, was_cached)`` for ``payload``, computing and storing on miss."""
    cached = get_cached(namespace, payload)
    if cached is not None:
        logger.info("Cache hit for namespace=%s", namespace)
        return cached, True

    value = compute()
    set_cached(namespace, payload, value)
    return value, False
