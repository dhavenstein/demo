from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    name: str
    score: int
    timestamp: float


class Leaderboard:
    def __init__(self, capacity: int = 10) -> None:
        self._capacity = capacity
        self._entries: list[Entry] = []
        self._lock = asyncio.Lock()

    async def record(self, name: str, score: int) -> int | None:
        async with self._lock:
            entry = Entry(name=name, score=score, timestamp=time.time())
            self._entries.append(entry)
            # Stable sort by -score; earlier entries keep priority on ties.
            self._entries.sort(key=lambda e: -e.score)
            if len(self._entries) > self._capacity:
                self._entries = self._entries[: self._capacity]
            if entry in self._entries:
                return self._entries.index(entry) + 1
            return None

    async def top(self) -> list[Entry]:
        async with self._lock:
            return list(self._entries)

    async def clear(self) -> None:
        async with self._lock:
            self._entries.clear()
