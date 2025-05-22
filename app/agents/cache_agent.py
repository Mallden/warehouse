import asyncio
import contextlib
import time
from collections.abc import Awaitable
from typing import Any, Callable, Generic, Optional, TypeVar

from app.agents import Agent
from app.metrics import CACHE_HITS, CACHE_MISSES, CACHE_SIZE

T = TypeVar('T')


class CacheEntry(Generic[T]):
    """Класс для хранения кешированных значений с временем жизни."""

    def __init__(self, value: T, ttl: int):
        self.value = value
        self.expires_at = time.time() + ttl

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class CacheAgent(Agent):
    """Агент для кеширования данных в памяти."""

    def __init__(self):
        self.cache: dict[str, CacheEntry] = {}
        self.default_ttl = 300
        self.cleanup_task = None

    async def initialize(self, config: dict[str, Any]) -> None:
        self.default_ttl = config.get('cache_ttl', 300)
        self.cleanup_interval = config.get('cache_cleanup_interval', 60)
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())

        CACHE_SIZE.set(0)

    async def shutdown(self) -> None:
        if self.cleanup_task:
            self.cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.cleanup_task

    async def _cleanup_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                self._cleanup_expired()
                CACHE_SIZE.set(len(self.cache))
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f'Error in cache cleanup: {e}')

    def _cleanup_expired(self) -> None:
        expired_keys = [k for k, v in self.cache.items() if v.is_expired()]
        for key in expired_keys:
            del self.cache[key]

        CACHE_SIZE.set(len(self.cache))

    def get(self, key: str) -> Optional[Any]:
        entry = self.cache.get(key)
        if entry is None or entry.is_expired():
            if entry is not None:
                del self.cache[key]
                CACHE_SIZE.set(len(self.cache))
            CACHE_MISSES.inc()
            return None

        CACHE_HITS.inc()
        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if ttl is None:
            ttl = self.default_ttl
        self.cache[key] = CacheEntry(value, ttl)

        CACHE_SIZE.set(len(self.cache))

    def delete(self, key: str) -> None:
        if key in self.cache:
            del self.cache[key]

            CACHE_SIZE.set(len(self.cache))

    async def get_or_set(
        self, key: str, getter: Callable[[], Awaitable[T]], ttl: Optional[int] = None
    ) -> T:
        value = self.get(key)
        if value is None:
            value = await getter()
            self.set(key, value, ttl)
        return value
