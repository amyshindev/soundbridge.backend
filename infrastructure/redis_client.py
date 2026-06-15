# 레이어: Infrastructure — Redis 캐시 클라이언트
import redis.asyncio as aioredis

from soundbridge.infrastructure.settings import settings

redis_client: aioredis.Redis = aioredis.from_url(
    settings.redis_url,
    encoding="utf-8",
    decode_responses=True,
)

CACHE_KEYS = {
    "discover_result": "sb:discover:{input_hash}",
    "popular_tracks": "sb:popular",
    "track_detail": "sb:track:{track_id}",
    "kopis_events": "sb:kopis:{track_id}",
}
CACHE_TTL = {
    "discover_result": 3600,
    "popular_tracks": 600,
    "track_detail": 3600,
    "kopis_events": 21600,
}
