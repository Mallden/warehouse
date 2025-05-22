from typing import Any

import asyncpg
from aiokafka import AIOKafkaConsumer
from fastapi import APIRouter
from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: str
    checks: dict[str, dict[str, Any]]


class HealthCheck:
    def __init__(self):
        self.router = APIRouter(prefix='/health', tags=['health'])
        self._setup_routes()
        self.db_pool = None
        self.kafka_consumer = None
        self.is_ready = False

    def _setup_routes(self):
        self.router.add_api_route(
            '/live', self.liveness_check, methods=['GET'], response_model=HealthStatus
        )
        self.router.add_api_route(
            '/ready', self.readiness_check, methods=['GET'], response_model=HealthStatus
        )

    def set_db_pool(self, pool: asyncpg.Pool):
        self.db_pool = pool

    def set_kafka_consumer(self, consumer: AIOKafkaConsumer):
        self.kafka_consumer = consumer

    def set_ready(self, is_ready: bool):
        self.is_ready = is_ready

    async def liveness_check(self) -> HealthStatus:
        checks = {'service': {'status': 'up'}}

        return HealthStatus(status='up', checks=checks)

    async def readiness_check(self) -> HealthStatus:
        checks = {}
        overall_status = 'up'

        # Проверка базы данных
        try:
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    await conn.execute('SELECT 1')
                checks['database'] = {'status': 'up'}
            else:
                checks['database'] = {
                    'status': 'unknown',
                    'reason': 'DB pool not initialized',
                }
                overall_status = 'down'
        except Exception as e:
            checks['database'] = {'status': 'down', 'reason': str(e)}
            overall_status = 'down'

        # Проверка Kafka
        try:
            if self.kafka_consumer and self.kafka_consumer._client:
                # Проверяем только если клиент инициализирован
                if self.kafka_consumer._client.cluster.brokers():
                    checks['kafka'] = {'status': 'up'}
                else:
                    checks['kafka'] = {
                        'status': 'down',
                        'reason': 'No brokers available',
                    }
                    overall_status = 'down'
            else:
                checks['kafka'] = {
                    'status': 'unknown',
                    'reason': 'Kafka consumer not initialized',
                }
                overall_status = 'down'
        except Exception as e:
            checks['kafka'] = {'status': 'down', 'reason': str(e)}
            overall_status = 'down'

        # Проверка готовности сервиса
        if not self.is_ready:
            checks['service_ready'] = {
                'status': 'down',
                'reason': 'Service initialization not complete',
            }
            overall_status = 'down'
        else:
            checks['service_ready'] = {'status': 'up'}

        return HealthStatus(status=overall_status, checks=checks)


health_check = HealthCheck()
