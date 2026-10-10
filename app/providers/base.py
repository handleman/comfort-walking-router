from abc import ABC, abstractmethod


class RouteProvider(ABC):
    @abstractmethod
    def route(self, start: tuple[float, float], end: tuple[float, float]) -> dict:
        pass