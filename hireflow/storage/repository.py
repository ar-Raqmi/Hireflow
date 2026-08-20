from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class Repository(ABC, Generic[T]):
    """Contract for persisting entities (profiles, jobs, applications, events)."""

    @abstractmethod
    async def get(self, entity_id: str) -> T | None: ...

    @abstractmethod
    async def put(self, entity: T) -> None: ...

    @abstractmethod
    async def delete(self, entity_id: str) -> None: ...

    @abstractmethod
    async def list_all(self) -> list[T]: ...