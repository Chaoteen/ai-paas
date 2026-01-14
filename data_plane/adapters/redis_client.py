# D:\RD\ai-os\data_plane\adapters\redis_client.py
import logging
from typing import Optional
from redis import asyncio as aioredis

logger = logging.getLogger("DataPlaneRedis")


class RedisAsyncClient:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._client: Optional[aioredis.Redis] = None

    async def connect(self):
        if self._client is None:
            self._client = await aioredis.from_url(self.redis_url, decode_responses=True)
            logger.info("RedisAsyncClient connected")

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            raise RuntimeError("RedisAsyncClient not connected. Call connect() first.")
        return self._client

    async def close(self):
        if self._client is not None:
            await self._client.close()
            self._client = None
            logger.info("RedisAsyncClient closed")
