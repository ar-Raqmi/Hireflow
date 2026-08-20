from __future__ import annotations

import os

from hireflow.config import SETTINGS
from hireflow.domain import Application, JobPosting, Profile
from hireflow.storage.firestore_repository import FirestoreRepository
from hireflow.storage.memory_repository import InMemoryRepository
from hireflow.storage.repository import Repository


class StorageFactory:
    """Builds repositories for each entity, choosing Firestore or in-memory.

    Falls back to in-memory when no Google Cloud credentials are configured so
    the app runs locally without Zach's service account. Repositories are cached
    so repeated access returns the same instance.
    """

    def __init__(self) -> None:
        self._use_firestore = bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")) and bool(SETTINGS.project_id)
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
