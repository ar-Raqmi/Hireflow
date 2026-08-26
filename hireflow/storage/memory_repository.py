from __future__ import annotations

from hireflow.storage.repository import Repository


class InMemoryRepository(Repository):
    """Dict-backed repository for local development and tests (no credentials)."""

    def __init__(self, entity_type: type) -> None:
        self._store: dict[str, object] = {}

    async def get(self, entity_id: str):
        return self._store.get(entity_id)

    async def put(self, entity) -> None:
        self._store[entity.id] = entity

    async def delete(self, entity_id: str) -> None:
        self._store.pop(entity_id, None)

    async def list_all(self) -> list:
        return list(self._store.values())
