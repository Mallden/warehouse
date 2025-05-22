import asyncio
import logging
from typing import Any, Optional

from app.agents.cache_agent import CacheAgent
from app.agents.db_agent import DBAgent
from app.agents.kafka_agent import KafkaAgent
from app.metrics import (
    KAFKA_MESSAGES_FAILED,
    KAFKA_MESSAGES_PROCESSED,
    KAFKA_PROCESSING_TIME,
    Timer,
)
from app.models import KafkaMessage, MovementInfo, WarehouseProductInfo


class WarehouseMonitoringService:
    """Основной сервис для мониторинга складов."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Инициализация агентов
        self.db_agent = DBAgent()
        self.kafka_agent = KafkaAgent()
        self.cache_agent = CacheAgent()

        self.running = False
        self.db_pool = None
        self.kafka_consumer = None

    async def initialize(self) -> None:
        self.logger.info('Initializing WarehouseMonitoringService')

        # Инициализация агентов
        self.db_pool = await self.db_agent.initialize(self.config)
        self.kafka_consumer = await self.kafka_agent.initialize(self.config)
        await self.cache_agent.initialize(self.config)

        # Запуск обработки сообщений Kafka
        asyncio.create_task(self.kafka_agent.start_consuming(self.handle_kafka_message))

        self.running = True
        self.logger.info('WarehouseMonitoringService initialized successfully')

        return {'db_pool': self.db_pool, 'kafka_consumer': self.kafka_consumer}

    async def shutdown(self) -> None:
        self.logger.info('Shutting down WarehouseMonitoringService')
        self.running = False

        # Завершение работы агентов
        await self.kafka_agent.shutdown()
        await self.cache_agent.shutdown()
        await self.db_agent.shutdown()

        self.logger.info('WarehouseMonitoringService shutdown complete')

    async def handle_kafka_message(self, message: KafkaMessage) -> None:
        message_type = message.subject.split(':')[-1].lower()

        with Timer(KAFKA_PROCESSING_TIME, {'message_type': message_type}):
            try:
                self.logger.debug(f'Processing Kafka message: {message.subject}')

                movement_data = message.data
                event_type = movement_data.event.lower()

                await self.db_agent.save_movement_event(
                    movement_id=movement_data.movement_id,
                    warehouse_id=movement_data.warehouse_id,
                    event_type=event_type,
                    timestamp=movement_data.timestamp,
                    product_id=movement_data.product_id,
                    quantity=movement_data.quantity,
                )

                cache_keys = [
                    f'movement:{movement_data.movement_id}',
                    f'warehouse_product:{movement_data.warehouse_id}:{movement_data.product_id}',
                ]
                for key in cache_keys:
                    self.cache_agent.delete(key)

                self.logger.info(
                    f'Successfully processed {event_type} event for movement {movement_data.movement_id}' # noqa: E501
                )

                KAFKA_MESSAGES_PROCESSED.labels(message_type=message_type).inc()

            except Exception as e:
                self.logger.error(f'Error handling Kafka message: {e}', exc_info=True)

                error_type = type(e).__name__
                KAFKA_MESSAGES_FAILED.labels(message_type=message_type, error_type=error_type).inc()

    async def get_movement_info(self, movement_id: str) -> Optional[MovementInfo]:
        cache_key = f'movement:{movement_id}'

        return await self.cache_agent.get_or_set(
            cache_key, lambda: self.db_agent.get_movement_info(movement_id)
        )

    async def get_warehouse_product_info(
        self, warehouse_id: str, product_id: str
    ) -> WarehouseProductInfo:
        cache_key = f'warehouse_product:{warehouse_id}:{product_id}'

        return await self.cache_agent.get_or_set(
            cache_key,
            lambda: self.db_agent.get_warehouse_product_info(warehouse_id, product_id),
        )
