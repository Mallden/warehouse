from datetime import datetime
from typing import Any, Optional

import asyncpg

from app.agents import Agent
from app.metrics import (
    DB_CONNECTIONS,
    KAFKA_PROCESSING_TIME,
    WAREHOUSE_PRODUCT_QUANTITY,
    Timer,
)
from app.models import MovementInfo, WarehouseProductInfo


class DBAgent(Agent):
    """Агент для работы с базой данных PostgreSQL."""

    def __init__(self):
        self.pool = None

    async def initialize(self, config: dict[str, Any]) -> None:
        self.pool = await asyncpg.create_pool(
            user=config.get('db_user', 'postgres'),
            password=config.get('db_password', 'postgres'),
            database=config.get('db_name', 'warehouse'),
            host=config.get('db_host', 'localhost'),
            port=config.get('db_port', 5432),
            min_size=config.get('db_min_connections', 5),
            max_size=config.get('db_max_connections', 20),
        )

        DB_CONNECTIONS.set(self.pool._queue.qsize())

        # Создаем таблицы, если их еще нет
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS warehouses (
                    id VARCHAR(255) PRIMARY KEY
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id VARCHAR(255) PRIMARY KEY
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS warehouse_products (
                    warehouse_id VARCHAR(255) REFERENCES warehouses(id),
                    product_id VARCHAR(255) REFERENCES products(id),
                    quantity INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (warehouse_id, product_id)
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS movements (
                    id VARCHAR(255) PRIMARY KEY,
                    source_warehouse_id VARCHAR(255) NULL REFERENCES warehouses(id),
                    destination_warehouse_id VARCHAR(255) NULL REFERENCES warehouses(id),
                    departure_time TIMESTAMP NULL,
                    arrival_time TIMESTAMP NULL,
                    product_id VARCHAR(255) NOT NULL REFERENCES products(id),
                    departure_quantity INTEGER NULL,
                    arrival_quantity INTEGER NULL
                )
            """)

        # Возвращаем пул для использования в health check
        return self.pool

    async def shutdown(self) -> None:
        if self.pool:
            await self.pool.close()

    async def ensure_warehouse_exists(self, warehouse_id: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO warehouses (id) VALUES ($1) ON CONFLICT DO NOTHING',
                warehouse_id,
            )

            DB_CONNECTIONS.set(self.pool._queue.qsize())

    async def ensure_product_exists(self, product_id: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO products (id) VALUES ($1) ON CONFLICT DO NOTHING',
                product_id,
            )

            DB_CONNECTIONS.set(self.pool._queue.qsize())

    async def get_warehouse_product_quantity(self, warehouse_id: str, product_id: str) -> int:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT quantity FROM warehouse_products WHERE warehouse_id = $1 AND product_id = $2',  # noqa: E501
                warehouse_id,
                product_id,
            )

            DB_CONNECTIONS.set(self.pool._queue.qsize())

            quantity = row['quantity'] if row else 0

            WAREHOUSE_PRODUCT_QUANTITY.labels(warehouse_id=warehouse_id, product_id=product_id).set(
                quantity
            )

            return quantity

    async def update_warehouse_product_quantity(
        self, warehouse_id: str, product_id: str, quantity_change: int
    ) -> int:
        await self.ensure_warehouse_exists(warehouse_id)
        await self.ensure_product_exists(product_id)

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Получаем текущее количество
                current_quantity = await self.get_warehouse_product_quantity(
                    warehouse_id, product_id
                )

                # Вычисляем новое количество
                new_quantity = current_quantity + quantity_change

                # Проверяем, что количество не станет отрицательным
                if new_quantity < 0:
                    raise ValueError(
                        f'Cannot have negative quantity for product {product_id} at warehouse {warehouse_id}'  # noqa: E501
                    )

                # Обновляем или вставляем новое значение
                await conn.execute(
                    """
                    INSERT INTO warehouse_products (warehouse_id, product_id, quantity)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (warehouse_id, product_id)
                    DO UPDATE SET quantity = $3
                """,
                    warehouse_id,
                    product_id,
                    new_quantity,
                )

                DB_CONNECTIONS.set(self.pool._queue.qsize())

                WAREHOUSE_PRODUCT_QUANTITY.labels(
                    warehouse_id=warehouse_id, product_id=product_id
                ).set(new_quantity)

                return new_quantity

    async def get_warehouse_product_info(
        self, warehouse_id: str, product_id: str
    ) -> WarehouseProductInfo:
        quantity = await self.get_warehouse_product_quantity(warehouse_id, product_id)
        return WarehouseProductInfo(
            warehouse_id=warehouse_id, product_id=product_id, quantity=quantity
        )

    async def save_movement_event(
        self,
        movement_id: str,
        warehouse_id: str,
        event_type: str,
        timestamp: datetime,
        product_id: str,
        quantity: int,
    ) -> None:
        with Timer(KAFKA_PROCESSING_TIME, {'message_type': event_type}):
            await self.ensure_warehouse_exists(warehouse_id)
            await self.ensure_product_exists(product_id)

            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Проверяем, существует ли уже такое перемещение
                    existing = await conn.fetchrow(
                        'SELECT * FROM movements WHERE id = $1', movement_id
                    )

                    if event_type == 'departure':
                        if existing:
                            # Обновляем существующую запись
                            await conn.execute(
                                """
                                UPDATE movements
                                SET source_warehouse_id = $1, departure_time = $2, departure_quantity = $3
                                WHERE id = $4
                            """,  # noqa: E501
                                warehouse_id,
                                timestamp,
                                quantity,
                                movement_id,
                            )
                        else:
                            # Создаем новую запись
                            await conn.execute(
                                """
                                INSERT INTO movements 
                                (id, source_warehouse_id, departure_time, product_id, departure_quantity)
                                VALUES ($1, $2, $3, $4, $5)
                            """,  # noqa: E501
                                movement_id,
                                warehouse_id,
                                timestamp,
                                product_id,
                                quantity,
                            )

                        # Обновляем количество товара на складе-отправителе
                        await self.update_warehouse_product_quantity(
                            warehouse_id, product_id, -quantity
                        )

                    elif event_type == 'arrival':
                        if existing:
                            # Обновляем существующую запись
                            await conn.execute(
                                """
                                UPDATE movements
                                SET destination_warehouse_id = $1, arrival_time = $2, arrival_quantity = $3
                                WHERE id = $4
                            """,  # noqa: E501
                                warehouse_id,
                                timestamp,
                                quantity,
                                movement_id,
                            )
                        else:
                            # Создаем новую запись
                            await conn.execute(
                                """
                                INSERT INTO movements 
                                (id, destination_warehouse_id, arrival_time, product_id, arrival_quantity)
                                VALUES ($1, $2, $3, $4, $5)
                            """,  # noqa: E501
                                movement_id,
                                warehouse_id,
                                timestamp,
                                product_id,
                                quantity,
                            )

                        # Обновляем количество товара на складе-получателе
                        await self.update_warehouse_product_quantity(
                            warehouse_id, product_id, quantity
                        )

                    DB_CONNECTIONS.set(self.pool._queue.qsize())

    async def get_movement_info(self, movement_id: str) -> Optional[MovementInfo]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 
                    id, 
                    source_warehouse_id, 
                    destination_warehouse_id, 
                    departure_time, 
                    arrival_time, 
                    product_id, 
                    departure_quantity, 
                    arrival_quantity
                FROM movements
                WHERE id = $1
            """,
                movement_id,
            )

            if not row:
                return None

            # Вычисляем время в пути, если известны оба временных штампа
            transit_time_seconds = None
            if row['departure_time'] and row['arrival_time']:
                delta = row['arrival_time'] - row['departure_time']
                transit_time_seconds = delta.total_seconds()

            # Вычисляем разницу в количестве
            quantity_difference = 0
            if row['departure_quantity'] is not None and row['arrival_quantity'] is not None:
                quantity_difference = row['arrival_quantity'] - row['departure_quantity']

            # Определяем количество для отображения
            quantity = (
                row['departure_quantity']
                if row['departure_quantity'] is not None
                else row['arrival_quantity']
            )

            return MovementInfo(
                movement_id=row['id'],
                source_warehouse=row['source_warehouse_id'],
                destination_warehouse=row['destination_warehouse_id'],
                departure_time=row['departure_time'],
                arrival_time=row['arrival_time'],
                transit_time_seconds=transit_time_seconds,
                product_id=row['product_id'],
                quantity=quantity,
                quantity_difference=quantity_difference,
            )
