from redis.asyncio import from_url
from distriq.config import settings

# socket_timeout=None prevents BLPOP from timing out while waiting for jobs
redis = from_url(
    settings.redis_url,
    decode_responses=True,
    socket_timeout=None,
    socket_connect_timeout=5,
)

async def get_redis():
    return redis