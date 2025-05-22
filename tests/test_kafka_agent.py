from unittest.mock import AsyncMock, patch

import pytest

from app.agents.kafka_agent import KafkaAgent


@pytest.fixture
def config():
    return {
        'kafka_bootstrap_servers': 'localhost:9092',
        'kafka_topic': 'warehouse_movements',
        'kafka_group_id': 'warehouse_monitoring_service',
    }


@pytest.mark.asyncio
async def test_initialize(config):
    """Тест инициализации Kafka агента."""
    with (
        patch('app.agents.kafka_agent.AIOKafkaConsumer') as mock_consumer,
        patch('app.agents.kafka_agent.AIOKafkaProducer') as mock_producer,
    ):
        mock_consumer_instance = AsyncMock()
        mock_producer_instance = AsyncMock()
        mock_consumer.return_value = mock_consumer_instance
        mock_producer.return_value = mock_producer_instance

        agent = KafkaAgent()
        await agent.initialize(config)

        mock_consumer.assert_called_once()
        mock_producer.assert_called_once()

        mock_consumer_instance.start.assert_called_once()
        mock_producer_instance.start.assert_called_once()


@pytest.mark.asyncio
async def test_send_message():
    """Тест отправки сообщения в Kafka."""
    agent = KafkaAgent()
    agent.producer = AsyncMock()

    agent.producer.send_and_wait = AsyncMock()

    test_message = {'key': 'value'}
    test_topic = 'test_topic'
    await agent.send_message(test_topic, test_message)

    agent.producer.send_and_wait.assert_called_once_with(test_topic, test_message)
