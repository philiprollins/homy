from abc import ABC, abstractmethod


class BatteryCollector(ABC):
    @abstractmethod
    async def connect(self): ...

    @abstractmethod
    async def read(self): ...

    @abstractmethod
    async def disconnect(self): ...
