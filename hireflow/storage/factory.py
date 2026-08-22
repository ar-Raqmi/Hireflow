from __future__ import annotations

from hireflow.config import SETTINGS
from hireflow.domain import Application, JobPosting, Profile
from hireflow.storage.firestore_repository import FirestoreRepository
from hireflow.storage.memory_repository import InMemoryRepository
from hireflow.storage.repository import Repository


class StorageFactory:
    """Builds repositories for each entity, choosing Firestore or in-memory.

    In-memory by default — the backend is stateless by design (AGENTS.md §5);
    the online curl e2e is the acceptance gate, not offline tests. Firestore is
    only used when ``HIREFLOW_STORAGE`` is set to ``firestore``. Repositories are
    cached so repeated access returns the same instance.
    """

    def __init__(self) -> None:
        self._use_firestore = SETTINGS.storage_backend == "firestore"
        self._cache: dict[str, Repository] = {}

    def profiles(self) -> Repository:
        return self._get(SETTINGS.firestore_collection_profiles, Profile)

    def jobs(self) -> Repository:
        return self._get(SETTINGS.firestore_collection_jobs, JobPosting)

    def applications(self) -> Repository:
        return self._get(SETTINGS.firestore_collection_applications, Application)

    def _get(self, collection: str, entity_type: type) -> Repository:
        if collection not in self._cache:
            self._cache[collection] = self._build(collection, entity_type)
        return self._cache[collection]

    def _build(self, collection: str, entity_type: type) -> Repository:
        if self._use_firestore:
            return FirestoreRepository(collection, entity_type)
        return InMemoryRepository(entity_type)
