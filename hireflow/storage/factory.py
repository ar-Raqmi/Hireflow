from __future__ import annotations

from hireflow.domain import Application, JobPosting, Profile
from hireflow.storage.memory_repository import InMemoryRepository
from hireflow.storage.repository import Repository


class StorageFactory:
    """Builds in-memory repositories for each entity.

    The backend is stateless by design (AGENTS.md §5): nothing sensitive is
    stored server-side. Repositories are cached so repeated access returns the
    same instance.
    """

    def __init__(self) -> None:
        self._cache: dict[str, Repository] = {}

    def profiles(self) -> Repository:
        return self._get("profiles", Profile)

    def jobs(self) -> Repository:
        return self._get("jobs", JobPosting)

    def applications(self) -> Repository:
        return self._get("applications", Application)

    def _get(self, collection: str, entity_type: type) -> Repository:
        if collection not in self._cache:
            self._cache[collection] = InMemoryRepository(entity_type)
        return self._cache[collection]