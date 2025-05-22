import logging

from fastapi import FastAPI
from prometheus_client import make_asgi_app
from prometheus_fastapi_instrumentator import Instrumentator

from app.api import movements_api, warehouses_api
from app.health import health_check
from app.service import WarehouseMonitoringService

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

config = {
    'db_host': 'db',
    'db_port': 5432,
    'db_user': 'postgres',
    'db_password': 'postgres',
    'db_name': 'warehouse',
    'kafka_bootstrap_servers': 'localhost:9092',
    'kafka_topic': 'warehouse_movements',
    'kafka_group_id': 'warehouse_monitoring_service',
    'cache_ttl': 300,
    'cache_cleanup_interval': 60,
    'db_min_connections': 5,
    'db_max_connections': 20,
}

# Создание экземпляра сервиса
service = WarehouseMonitoringService(config)

app = FastAPI(
    title='Warehouse Monitoring Service',
    description='Сервис мониторинга состояния складов',
    version='1.0.0',
)

instrumentator = Instrumentator().instrument(app)


@app.on_event('startup')
async def startup_event():
    """Событие запуска приложения."""
    logger.info('Starting up the application')

    # Инициализируем инструментарий для метрик
    instrumentator.expose(app)

    # Создаем endpoint для метрик Prometheus
    metrics_app = make_asgi_app()
    app.mount('/metrics', metrics_app)

    # Инициализация сервиса
    resources = await service.initialize()

    # Инициализация API компонентов
    movements_api.initialize(service)
    warehouses_api.initialize(service)

    # Настройка health check
    health_check.set_db_pool(resources['db_pool'])
    health_check.set_kafka_consumer(resources['kafka_consumer'])

    # Отмечаем сервис как готовый к работе
    health_check.set_ready(True)


@app.on_event('shutdown')
async def shutdown_event():
    """Событие завершения приложения."""
    logger.info('Shutting down the application')

    # Отмечаем сервис как не активный
    health_check.set_ready(False)

    await service.shutdown()


# Подключение API маршрутов
app.include_router(movements_api.get_router())
app.include_router(warehouses_api.get_router())
app.include_router(health_check.router)
