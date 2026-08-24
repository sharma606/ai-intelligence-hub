import hashlib
import logging
import os

from redis import Redis

from app.schemas import AnalysisResult


logger = logging.getLogger(__name__)

ANALYSIS_CACHE_TTL_SECONDS = int(os.getenv("ANALYSIS_CACHE_TTL_SECONDS", "86400"))


def analysis_cache_key(document_id: int, article_text: str) -> str:
    digest = hashlib.sha256(article_text.encode("utf-8")).hexdigest()
    return f"analysis:{document_id}:{digest}"


def get_redis_client() -> Redis | None:
    url = os.getenv("REDIS_URL")
    if not url:
        return None
    return Redis.from_url(url, decode_responses=True)


class AnalysisCache:
    def __init__(
        self,
        redis_client: Redis | None,
        ttl_seconds: int = ANALYSIS_CACHE_TTL_SECONDS,
    ) -> None:
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds

    def get_analysis(self, document_id: int, article_text: str) -> AnalysisResult | None:
        if self.redis_client is None:
            return None
        key = analysis_cache_key(document_id, article_text)
        try:
            raw = self.redis_client.get(key)
        except Exception:
            logger.warning("Redis cache read failed for %s", key, exc_info=True)
            return None
        if raw is None:
            return None
        return AnalysisResult.model_validate_json(raw)

    def set_analysis(self, document_id: int, article_text: str, result: AnalysisResult) -> None:
        if self.redis_client is None:
            return
        key = analysis_cache_key(document_id, article_text)
        try:
            self.redis_client.set(key, result.model_dump_json(), ex=self.ttl_seconds)
        except Exception:
            logger.warning("Redis cache write failed for %s", key, exc_info=True)


def get_analysis_cache() -> AnalysisCache:
    return AnalysisCache(get_redis_client())
