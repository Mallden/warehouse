import time

from prometheus_client import Counter, Gauge, Histogram

# Счетчики для сообщений Kafka
KAFKA_MESSAGES_RECEIVED = Counter(
    'warehouse_kafka_messages_received_total',
    'Total number of Kafka messages received',
    ['message_type'],
)

KAFKA_MESSAGES_PROCESSED = Counter(
    'warehouse_kafka_messages_processed_total',
    'Total number of Kafka messages successfully processed',
    ['message_type'],
)

KAFKA_MESSAGES_FAILED = Counter(
    'warehouse_kafka_messages_failed_total',
    'Total number of Kafka messages that failed to process',
    ['message_type', 'error_type'],
)

# Метрики для API запросов
API_REQUESTS = Counter(
    'warehouse_api_requests_total',
    'Total number of API requests',
    ['endpoint', 'method', 'status_code'],
)

# Гистограмма для времени ответа API
API_RESPONSE_TIME = Histogram(
    'warehouse_api_response_time_seconds',
    'API response time in seconds',
    ['endpoint', 'method'],
    buckets=[
        0.001,
        0.005,
        0.01,
        0.025,
        0.05,
        0.075,
        0.1,
        0.25,
        0.5,
        0.75,
        1.0,
        2.5,
        5.0,
        7.5,
        10.0,
    ],
)

# Гистограмма для времени обработки сообщений Kafka
KAFKA_PROCESSING_TIME = Histogram(
    'warehouse_kafka_processing_time_seconds',
    'Kafka message processing time in seconds',
    ['message_type'],
    buckets=[
        0.001,
        0.005,
        0.01,
        0.025,
        0.05,
        0.075,
        0.1,
        0.25,
        0.5,
        0.75,
        1.0,
        2.5,
        5.0,
        7.5,
        10.0,
    ],
)

# Метрики для отслеживания состояния базы данных
DB_CONNECTIONS = Gauge('warehouse_db_connections', 'Number of active database connections')

# Метрики для кеша
CACHE_SIZE = Gauge('warehouse_cache_size', 'Number of items in the cache')

CACHE_HITS = Counter('warehouse_cache_hits_total', 'Total number of cache hits')

CACHE_MISSES = Counter('warehouse_cache_misses_total', 'Total number of cache misses')

# Метрики для складов и товаров
WAREHOUSE_PRODUCT_QUANTITY = Gauge(
    'warehouse_product_quantity',
    'Current quantity of a product in a warehouse',
    ['warehouse_id', 'product_id'],
)


class Timer:
    def __init__(self, metric, labels=None):
        self.metric = metric
        self.labels = labels or {}
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            self.metric.labels(**self.labels).observe(duration)
