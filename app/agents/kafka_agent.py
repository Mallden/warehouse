import json
from collections.abc import Awaitable, Callable
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from app.agents import Agent
from app.metrics import (
    KAFKA_MESSAGES_FAILED,
    KAFKA_MESSAGES_PROCESSED,
    KAFKA_MESSAGES_RECEIVED,
)
from app.models import KafkaMessage


class KafkaAgent(Agent):
    """Агент для работы с Kafka."""

    def __init__(self):
        self.consumer = None
        self.producer = None
        self.running = False
        self.message_handler = None

    async def initialize(self, config: dict[str, Any]) -> None:
        bootstrap_servers = config.get('kafka_bootstrap_servers', 'localhost:9092')
        topic = config.get('kafka_topic', 'warehouse_movements')
        group_id = config.get('kafka_group_id', 'warehouse_monitoring_service')

        self.consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            auto_offset_reset='earliest',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        )

        self.producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda m: json.dumps(m).encode('utf-8'),
        )

        await self.consumer.start()
        await self.producer.start()

        return self.consumer

    async def shutdown(self) -> None:
        self.running = False
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()

    async def send_message(self, topic: str, message: dict[str, Any]) -> None:
        await self.producer.send_and_wait(topic, message)

    async def start_consuming(self, handler: Callable[[KafkaMessage], Awaitable[None]]) -> None:
        self.message_handler = handler
        self.running = True

        try:
            async for message in self.consumer:
                try:
                    message_type = message.value.get('subject', 'unknown').split(':')[-1].lower()
                    KAFKA_MESSAGES_RECEIVED.labels(message_type=message_type).inc()

                    kafka_message = KafkaMessage(**message.value)

                    await self.message_handler(kafka_message)

                    KAFKA_MESSAGES_PROCESSED.labels(message_type=message_type).inc()

                except Exception as e:
                    error_type = type(e).__name__
                    message_type = (
                        message.value.get('subject', 'unknown').split(':')[-1].lower()
                        if hasattr(message, 'value')
                        else 'unknown'
                    )
                    KAFKA_MESSAGES_FAILED.labels(
                        message_type=message_type, error_type=error_type
                    ).inc()
                    print(f'Error processing message: {e}')

                if not self.running:
                    break
        except Exception as e:
            print(f'Kafka consumer error: {e}')
