from abc import ABCMeta, abstractmethod
from typing import Any


class AgentMeta(ABCMeta):
    """Метакласс для агентов."""

    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)
        if not name.startswith('Abstract'):
            if not hasattr(cls, 'initialize'):
                raise NotImplementedError(f'Agent class {name} must implement initialize method')
            if not hasattr(cls, 'shutdown'):
                raise NotImplementedError(f'Agent class {name} must implement shutdown method')


class Agent(metaclass=AgentMeta):
    """Базовый класс для всех агентов."""

    @abstractmethod
    async def initialize(self, config: dict[str, Any]) -> None:
        """Инициализация агента."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Завершение работы агента."""
        pass
