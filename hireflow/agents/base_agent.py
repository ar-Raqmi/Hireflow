from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """Base class for all Hireflow agents."""

    name: str = "base"

    @abstractmethod
    async def run(self, context: dict) -> dict:
        """Execute the agent's step and return its outcome."""
        ...

    async def pre_run(self, context: dict) -> None:
        """Hook before run. Override to log, enrich, or validate."""

    async def post_run(self, context: dict, outcome: dict) -> None:
        """Hook after run. Override to persist audit events."""