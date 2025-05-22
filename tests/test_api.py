from datetime import datetime

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.models import MovementInfo

# Создаем простой тестовый маршрутизатор
app_test = FastAPI()
router_test = APIRouter()


@router_test.get('/api/movements/{movement_id}')
async def get_movement_test(movement_id: str):
    """Тестовый маршрут для получения информации о перемещении."""

    return MovementInfo(
        movement_id=movement_id,
        source_warehouse='warehouse-1',
        destination_warehouse='warehouse-2',
        departure_time=datetime(2025, 2, 18, 12, 12, 56, tzinfo=datetime.UTC),
        arrival_time=datetime(2025, 2, 18, 14, 34, 56, tzinfo=datetime.UTC),
        transit_time_seconds=8520,
        product_id='product-1',
        quantity=100,
        quantity_difference=0,
    )


app_test.include_router(router_test)
client_test = TestClient(app_test)


def test_get_movement_info_success():
    """Тест успешного получения информации о перемещении."""

    response = client_test.get('/api/movements/test-movement')

    assert response.status_code == 200
    data = response.json()
    assert data['movement_id'] == 'test-movement'
    assert data['source_warehouse'] == 'warehouse-1'
    assert data['destination_warehouse'] == 'warehouse-2'
    assert data['product_id'] == 'product-1'
    assert data['quantity'] == 100
    assert data['quantity_difference'] == 0
