from redis.asyncio import from_url
from distriq.config import settings

redis = from_url(settings.redis_url, decode_responses=True)

async def get_redis():
    return redis