import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.cache_agent import CacheAgent, CacheEntry


@pytest.mark.asyncio
async def test_initialize():
    """Тест инициализации кеш-агента."""
    agent = CacheAgent()

    # Патчим метод _cleanup_loop, чтобы не запускать бесконечный цикл
    with patch.object(agent, '_cleanup_loop', AsyncMock()) as mock_cleanup_loop:
        config = {'cache_ttl': 600, 'cache_cleanup_interval': 120}
        await agent.initialize(config)

        assert agent.default_ttl == 600
        assert agent.cleanup_interval == 120

        mock_cleanup_loop.assert_called_once()


@pytest.mark.asyncio
async def test_shutdown():
    """Тест завершения работы кеш-агента."""
    agent = CacheAgent()

    # Создаем реальную задачу, которая сразу завершается
    async def dummy_task():
        return None

    task = asyncio.create_task(dummy_task())
    agent.cleanup_task = task

    await agent.shutdown()

    assert task.cancelled()


def test_get_set():
    """Тест установки и получения значений из кеша."""
    agent = CacheAgent()

    agent.set('key1', 'value1')

    value = agent.get('key1')

    assert value == 'value1'

    assert 'key1' in agent.cache
    assert isinstance(agent.cache['key1'], CacheEntry)
    assert agent.cache['key1'].value == 'value1'
    assert agent.cache['key1'].expires_at > time.time()
