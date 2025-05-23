import datetime
from unittest.mock import AsyncMock

import pytest

from app.models import KafkaMessage, MovementData
from app.service import WarehouseMonitoringService


@pytest.fixture
def config():
    return {
        'db_host': 'localhost',
        'db_port': 5432,
        'db_user': 'postgres',
        'db_password': 'postgres',
        'db_name': 'warehouse',
        'kafka_bootstrap_servers': 'localhost:9092',
        'kafka_topic': 'warehouse_movements',
        'kafka_group_id': 'warehouse_monitoring_service',
        'cache_ttl': 300,
        'cache_cleanup_interval': 60,
    }


@pytest.fixture
def service(config):
    service = WarehouseMonitoringService(config)
    service.db_agent = AsyncMock()
    service.kafka_agent = AsyncMock()
    service.cache_agent = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_initialize(service):
    """Тест инициализации сервиса."""
    await service.initialize()

    service.db_agent.initialize.assert_called_once_with(service.config)
    service.kafka_agent.initialize.assert_called_once_with(service.config)
    service.cache_agent.initialize.assert_called_once_with(service.config)

    service.kafka_agent.start_consuming.assert_called_once()

    assert service.running is True


@pytest.mark.asyncio
async def test_handle_kafka_message(service):
    """Тест обработки сообщения Kafka."""

    movement_data = MovementData(
        movement_id='test-movement-id',
        warehouse_id='test-warehouse-id',
        timestamp=datetime.datetime.now(datetime.UTC),
        event='arrival',
        product_id='test-product-id',
        quantity=100,
    )

    kafka_message = KafkaMessage(
        id='test-message-id',
        source='WH-1234',
        specversion='1.0',
        type='ru.retail.warehouses.movement',
        datacontenttype='application/json',
        dataschema='ru.retail.warehouses.movement.v1.0',
        time=1234567890,
        subject='WH-1234:ARRIVAL',
        destination='ru.retail.warehouses',
        data=movement_data,
    )

    await service.handle_kafka_message(kafka_message)

    service.db_agent.save_movement_event.assert_called_once_with(
        movement_id=movement_data.movement_id,
        warehouse_id=movement_data.warehouse_id,
        event_type=movement_data.event.lower(),
        timestamp=movement_data.timestamp,
        product_id=movement_data.product_id,
        quantity=movement_data.quantity,
    )
