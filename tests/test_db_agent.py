"""
Одно из самых проблемных мест в тестах оказалось, AsyncMock не всегда корректно работает с
асинхронным контекстным менеджером, поэтому немного пришлось повозиться
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.db_agent import DBAgent


# Пришлось создавать отдельный класс для мока акм
class AsyncContextManagerMock:
    def __init__(self, return_value):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


# общая функция для создания правильно настроенных моков
def setup_db_mock():
    agent = DBAgent()
    connection = AsyncMock()

    # создем мок для метода transaction()
    transaction_ctx = AsyncContextManagerMock(return_value=None)
    connection.transaction = MagicMock(return_value=transaction_ctx)

    # создаем пул с правильно настроенным методом acquire()
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncContextManagerMock(connection))

    # Мокируем размер очереди для метрики DB_CONNECTIONS
    pool._queue = MagicMock()
    pool._queue.qsize = MagicMock(return_value=10)

    agent.pool = pool

    return agent, connection


@pytest.mark.asyncio
async def test_get_warehouse_product_quantity():
    """Тест получения количества товара на складе."""

    agent, connection = setup_db_mock()

    # Настраиваем мок для возврата данных
    connection.fetchrow.return_value = {'quantity': 100}

    # Патчим метрику, чтобы избежать ошибок
    with patch('app.agents.db_agent.DB_CONNECTIONS.set'):
        with patch('app.agents.db_agent.WAREHOUSE_PRODUCT_QUANTITY.labels') as mock_labels:
            # Настраиваем вложенный мок
            mock_metric = MagicMock()
            mock_labels.return_value.set = mock_metric

            # Вызываем тестируемый метод
            quantity = await agent.get_warehouse_product_quantity('warehouse-1', 'product-1')

    assert quantity == 100

    connection.fetchrow.assert_called_once()
    call_args = connection.fetchrow.call_args[0]
    assert 'SELECT quantity FROM warehouse_products' in call_args[0]
    assert call_args[1] == 'warehouse-1'
    assert call_args[2] == 'product-1'


@pytest.mark.asyncio
async def test_get_warehouse_product_quantity_not_found():
    """Тест получения количества товара, которого нет на складе."""

    agent, connection = setup_db_mock()

    # Настраиваем мок для возврата None (товар не найден)
    connection.fetchrow.return_value = None

    with patch('app.agents.db_agent.DB_CONNECTIONS.set'):
        with patch('app.agents.db_agent.WAREHOUSE_PRODUCT_QUANTITY.labels') as mock_labels:
            mock_metric = MagicMock()
            mock_labels.return_value.set = mock_metric

            quantity = await agent.get_warehouse_product_quantity('warehouse-1', 'product-1')

    assert quantity == 0


@pytest.mark.asyncio
async def test_update_warehouse_product_quantity():
    """Тест обновления количества товара на складе."""

    agent, connection = setup_db_mock()

    # Создаем моки для методов, которые нужно патчить
    ensure_warehouse_mock = AsyncMock()
    ensure_product_mock = AsyncMock()
    get_quantity_mock = AsyncMock(return_value=50)

    # Патчим зависимые методы
    original_ensure_warehouse = agent.ensure_warehouse_exists
    original_ensure_product = agent.ensure_product_exists
    original_get_quantity = agent.get_warehouse_product_quantity

    try:
        # Заменяем методы на моки
        agent.ensure_warehouse_exists = ensure_warehouse_mock
        agent.ensure_product_exists = ensure_product_mock
        agent.get_warehouse_product_quantity = get_quantity_mock

        with patch('app.agents.db_agent.DB_CONNECTIONS.set'):
            with patch('app.agents.db_agent.WAREHOUSE_PRODUCT_QUANTITY.labels') as mock_labels:
                mock_metric = MagicMock()
                mock_labels.return_value.set = mock_metric

                new_quantity = await agent.update_warehouse_product_quantity(
                    'warehouse-1', 'product-1', 20
                )

        assert new_quantity == 70

        ensure_warehouse_mock.assert_called_once_with('warehouse-1')
        ensure_product_mock.assert_called_once_with('product-1')
        get_quantity_mock.assert_called_once_with('warehouse-1', 'product-1')

        connection.execute.assert_called_once()
        call_args = connection.execute.call_args[0]
        assert 'INSERT INTO warehouse_products' in call_args[0]
        assert call_args[1] == 'warehouse-1'
        assert call_args[2] == 'product-1'
        assert call_args[3] == 70

    finally:
        agent.ensure_warehouse_exists = original_ensure_warehouse
        agent.ensure_product_exists = original_ensure_product
        agent.get_warehouse_product_quantity = original_get_quantity


@pytest.mark.asyncio
async def test_update_warehouse_product_quantity_negative():
    """Тест на предотвращение отрицательного количества товара на складе."""

    agent, _ = setup_db_mock()

    ensure_warehouse_mock = AsyncMock()
    ensure_product_mock = AsyncMock()
    get_quantity_mock = AsyncMock(return_value=10)

    original_ensure_warehouse = agent.ensure_warehouse_exists
    original_ensure_product = agent.ensure_product_exists
    original_get_quantity = agent.get_warehouse_product_quantity

    try:
        agent.ensure_warehouse_exists = ensure_warehouse_mock
        agent.ensure_product_exists = ensure_product_mock
        agent.get_warehouse_product_quantity = get_quantity_mock

        # Пытаемся уменьшить количество больше, чем есть на складе
        with pytest.raises(ValueError) as excinfo:
            await agent.update_warehouse_product_quantity('warehouse-1', 'product-1', -20)

        assert 'Cannot have negative quantity' in str(excinfo.value)

        ensure_warehouse_mock.assert_called_once_with('warehouse-1')
        ensure_product_mock.assert_called_once_with('product-1')
        get_quantity_mock.assert_called_once_with('warehouse-1', 'product-1')

    finally:
        agent.ensure_warehouse_exists = original_ensure_warehouse
        agent.ensure_product_exists = original_ensure_product
        agent.get_warehouse_product_quantity = original_get_quantity
