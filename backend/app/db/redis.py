from redis.asyncio import Redis, ConnectionPool
from app.utils.config import settings
from typing import AsyncGenerator

# 创建全局连接池
pool = ConnectionPool.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)

async def get_redis() -> AsyncGenerator[Redis, None]:
    """
    Get Redis connection from pool
    """
    redis = Redis(connection_pool=pool)
    try:
        yield redis
    finally:
        await redis.close()
