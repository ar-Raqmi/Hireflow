from __future__ import annotations

import asyncio
import time
from typing import Any


class RunLog:
    """In-memory, per-run progress log for SSE streaming of the pipeline.

    Keyed by run_id. Async-safe: every read/write is guarded by a single
    asyncio.Lock so the background pipeline task and the SSE generator can
    touch the same run concurrently. Stateless per Cloud Run instance (in-memory
    only; nothing sensitive is stored).
    """

    def __init__(self) -> None:
        self._runs: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def start(self, run_id: str) -> None:
        async with self._lock:
            self._runs.setdefault(run_id, {"events": [], "seq": 0, "done": False, "result": None})

    async def exists(self, run_id: str) -> bool:
        async with self._lock:
            return run_id in self._runs

    async def emit(self, run_id: str, stage: str, detail: str) -> dict[str, Any] | None:
        async with self._lock:
            entry = self._runs.get(run_id)
            if entry is None:
                return None
            entry["seq"] += 1
            event = {
                "seq": entry["seq"],
                "stage": stage,
                "detail": detail,
                "ts": int(time.time()),
            }
            entry["events"].append(event)
            return event

    async def events_since(self, run_id: str, seq: int) -> list[dict[str, Any]]:
        async with self._lock:
            entry = self._runs.get(run_id)
            if entry is None:
                return []
            return [event for event in entry["events"] if event["seq"] > seq]

    async def finish(self, run_id: str, result: dict[str, Any]) -> None:
        async with self._lock:
            entry = self._runs.get(run_id)
            if entry is None:
                return
            entry["done"] = True
            entry["result"] = result

    async def is_done(self, run_id: str) -> bool:
        async with self._lock:
            entry = self._runs.get(run_id)
            return bool(entry and entry["done"])

    async def result(self, run_id: str) -> dict[str, Any] | None:
        async with self._lock:
            entry = self._runs.get(run_id)
            return entry["result"] if entry else None