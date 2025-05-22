import time

from fastapi import APIRouter, HTTPException, Request

from app.api.base import ApiBase
from app.metrics import API_REQUESTS, API_RESPONSE_TIME
from app.models import MovementInfo
from app.service import WarehouseMonitoringService


class MovementsApi(ApiBase):
    """API для работы с перемещениями товаров."""

    def _create_router(self) -> None:
        self.router = APIRouter(prefix='/api/movements', tags=['movements'])

    def _setup_routes(self) -> None:
        self.router.add_api_route(
            '/{movement_id}',
            self.get_movement,
            methods=['GET'],
            response_model=MovementInfo,
            summary='Получение информации о перемещении',
        )

    def initialize(self, service: WarehouseMonitoringService) -> None:
        self.service = service

    async def get_movement(self, movement_id: str, request: Request):
        """
        Получение детальной информации о перемещении товара между складами.

        - **movement_id**: Идентификатор перемещения

        Возвращает информацию о перемещении, включая отправителя, получателя,
        время отправки и прибытия, время в пути, а также информацию о товаре и его количестве.
        """
        start_time = time.time()
        endpoint = f'/api/movements/{{{movement_id}}}'
        method = request.method

        try:
            if self.service is None:
                raise HTTPException(status_code=500, detail='Service not initialized')

            movement = await self.service.get_movement_info(movement_id)
            if movement is None:
                API_REQUESTS.labels(endpoint=endpoint, method=method, status_code=404).inc()
                raise HTTPException(
                    status_code=404, detail=f'Movement with ID {movement_id} not found'
                )

            API_REQUESTS.labels(endpoint=endpoint, method=method, status_code=200).inc()
            return movement

        except HTTPException:
            # Пробрасываем HTTPException дальше
            raise
        except Exception as e:
            API_REQUESTS.labels(endpoint=endpoint, method=method, status_code=500).inc()
            raise HTTPException(status_code=500, detail=f'Internal server error: {str(e)}')  # noqa: B904
        finally:
            duration = time.time() - start_time
            API_RESPONSE_TIME.labels(endpoint=endpoint, method=method).observe(duration)
