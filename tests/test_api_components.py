from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import APIRouter

from app.api import movements_api, warehouses_api
from app.api.base import ApiBase
from app.service import WarehouseMonitoringService


@pytest.fixture
def mock_service():
    """Фикстура для создания мока сервиса."""
    service = MagicMock(spec=WarehouseMonitoringService)
    service.get_movement_info = AsyncMock()
    service.get_warehouse_product_info = AsyncMock()
    return service


def test_movements_api_instance():
    """Тест экземпляра API перемещений."""
    assert isinstance(movements_api, ApiBase)
    assert movements_api.get_router() is not None
    assert isinstance(movements_api.get_router(), APIRouter)


def test_warehouses_api_instance():
    """Тест экземпляра API складов."""
    assert isinstance(warehouses_api, ApiBase)
    assert warehouses_api.get_router() is not None
    assert isinstance(warehouses_api.get_router(), APIRouter)


def test_api_initialization(mock_service):
    """Тест инициализации API компонентов."""
    # Инициализация API
    movements_api.initialize(mock_service)
    warehouses_api.initialize(mock_service)

    # Проверка, что сервис был установлен
    assert movements_api.service is mock_service
    assert warehouses_api.service is mock_service
