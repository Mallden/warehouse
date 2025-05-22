import time

from fastapi import APIRouter, HTTPException, Request

from app.api.base import ApiBase
from app.metrics import API_REQUESTS, API_RESPONSE_TIME
from app.models import WarehouseProductInfo
from app.service import WarehouseMonitoringService


class WarehousesApi(ApiBase):
    """API для работы со складами."""

    def _create_router(self) -> None:
        self.router = APIRouter(prefix='/api/warehouses', tags=['warehouses'])

    def _setup_routes(self) -> None:
        self.router.add_api_route(
            '/{warehouse_id}/products/{product_id}',
            self.get_warehouse_product,
            methods=['GET'],
            response_model=WarehouseProductInfo,
            summary='Получение информации о товаре на складе',
        )

    def initialize(self, service: WarehouseMonitoringService) -> None:
        self.service = service

    async def get_warehouse_product(self, warehouse_id: str, product_id: str, request: Request):
        """
        Получение информации о текущем количестве товара на складе.

        - **warehouse_id**: Идентификатор склада
        - **product_id**: Идентификатор товара

        Возвращает текущее количество указанного товара на указанном складе.
        """
        start_time = time.time()
        endpoint = f'/api/warehouses/{{{warehouse_id}}}/products/{{{product_id}}}'
        method = request.method

        try:
            if self.service is None:
                raise HTTPException(status_code=500, detail='Service not initialized')

            result = await self.service.get_warehouse_product_info(warehouse_id, product_id)

            API_REQUESTS.labels(endpoint=endpoint, method=method, status_code=200).inc()
            return result

        except Exception as e:
            API_REQUESTS.labels(endpoint=endpoint, method=method, status_code=500).inc()
            raise HTTPException(status_code=500, detail=f'Internal server error: {str(e)}')  # noqa: B904
        finally:
            duration = time.time() - start_time
            API_RESPONSE_TIME.labels(endpoint=endpoint, method=method).observe(duration)
