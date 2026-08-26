from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Awaitable, Callable


class BaseAgent(ABC):
    """Base class for all Hireflow agents."""

    name: str = "base"
    progress: Callable[[str, str], Awaitable[None]] | None = None

    @abstractmethod
    async def run(self, context: dict) -> dict:
        """Execute the agent's step and return its outcome."""
        ...

    async def _emit(self, stage: str, detail: str) -> None:
        if self.progress is not None:
            await self.progress(stage, detail)