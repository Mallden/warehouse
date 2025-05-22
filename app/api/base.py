from abc import ABCMeta, abstractmethod

from fastapi import APIRouter

from app.service import WarehouseMonitoringService


class ApiMeta(ABCMeta):
    """Метакласс для API компонентов."""

    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)
        if not name.startswith('Abstract'):
            if not hasattr(cls, 'get_router'):
                raise NotImplementedError(f'API class {name} must implement get_router method')
            if not hasattr(cls, 'initialize'):
                raise NotImplementedError(f'API class {name} must implement initialize method')
            if not hasattr(cls, '_setup_routes'):
                raise NotImplementedError(f'API class {name} must implement _setup_routes method')


class ApiBase(metaclass=ApiMeta):
    """Базовый класс для всех API компонентов."""

    def __init__(self):
        self.router = None
        self.service = None
        self._create_router()
        self._setup_routes()

    def _create_router(self) -> None:
        """Создание маршрутизатора FastAPI."""
        self.router = APIRouter()

    @abstractmethod
    def _setup_routes(self) -> None:
        """Настройка маршрутов для API."""
        pass

    @abstractmethod
    def initialize(self, service: WarehouseMonitoringService) -> None:
        """Инициализация API компонента."""
        pass

    def get_router(self) -> APIRouter:
        """Получить маршрут FastAPI."""
        if self.router is None:
            raise ValueError('Router is not initialized')
        return self.router
