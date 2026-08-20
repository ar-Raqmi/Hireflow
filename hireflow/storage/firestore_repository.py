from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

from hireflow.config import SETTINGS
from hireflow.storage.repository import Repository

if TYPE_CHECKING:
    from google.cloud import firestore

T = TypeVar("T")


class FirestoreRepository(Repository, Generic[T]):
    """Firestore-backed repository for any domain entity with from_mapping/to_mapping.

    Credentials come from GOOGLE_APPLICATION_CREDENTIALS (i nid ds Zach).
    """

    def __init__(self, collection: str, entity_type: type[T]) -> None:
        from google.cloud import firestore

        self._entity_type = entity_type
        self._client = firestore.AsyncClient(project=SETTINGS.project_id)
        self._collection = self._client.collection(collection)

    async def get(self, entity_id: str) -> T | None:
        doc = await self._collection.document(entity_id).get()
        if not doc.exists:
            return None
        return self._entity_type.from_mapping(doc.to_dict())

    async def put(self, entity: T) -> None:
        await self._collection.document(entity.id).set(entity.to_mapping())

    async def delete(self, entity_id: str) -> None:
        await self._collection.document(entity_id).delete()

    async def list_all(self) -> list[T]:
        snapshots = await self._collection.get()
        return [self._entity_type.from_mapping(doc.to_dict()) for doc in snapshots]
