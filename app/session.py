from __future__ import annotations

import asyncio
import random

from fastapi import WebSocket, WebSocketDisconnect

from app.game import GameState, StepResult, new_game, step, ticks_per_sec
from app.leaderboard import Leaderboard
from app.schemas import (
    ErrorMessage,
    GameOverMessage,
    InputMessage,
    PauseMessage,
    ResumeMessage,
    StartMessage,
    StateMessage,
)


class Session:
    def __init__(
        self,
        ws: WebSocket,
        leaderboard: Leaderboard,
        rng: random.Random | None = None,
    ) -> None:
        self._ws = ws
        self._leaderboard = leaderboard
        self._rng = rng or random.Random()
        self._state: GameState | None = None
        self._name: str = ""
        self._pending_direction: str | None = None
        self._tick: int = 0

    async def run(self) -> None:
        try:
            await self._wait_for_start()
            await self._game_loop()
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            await self._safe_send(ErrorMessage(message=str(exc)).model_dump())
        finally:
            await self._safe_close()

    async def _wait_for_start(self) -> None:
        raw = await self._ws.receive_json()
        msg = StartMessage.model_validate(raw)
        self._name = msg.name
        self._state = new_game(self._rng)

    async def _game_loop(self) -> None:
        assert self._state is not None
        await self._send_state()
        while self._state.alive:
            interval = 1.0 / ticks_per_sec(self._state.score)
            try:
                raw = await asyncio.wait_for(self._ws.receive_json(), timeout=interval)
                self._handle_client_message(raw)
                continue
            except asyncio.TimeoutError:
                pass

            if self._state.paused:
                continue

            self._tick += 1
            direction = self._pending_direction
            self._pending_direction = None
            result = step(self._state, direction, self._rng)
            await self._send_state()
            if result.event == "game_over":
                await self._finalize(result)
                return

    def _handle_client_message(self, raw: object) -> None:
        assert self._state is not None
        if not isinstance(raw, dict):
            raise ValueError("expected object message")
        kind = raw.get("type")
        if kind == "input":
            msg = InputMessage.model_validate(raw)
            self._pending_direction = msg.dir
        elif kind == "pause":
            PauseMessage.model_validate(raw)
            self._state.paused = True
        elif kind == "resume":
            ResumeMessage.model_validate(raw)
            self._state.paused = False
        else:
            raise ValueError(f"unknown message type: {kind!r}")

    async def _send_state(self) -> None:
        assert self._state is not None
        s = self._state
        msg = StateMessage(
            tick=self._tick,
            snake=[list(c) for c in s.snake],
            apple=list(s.good_apple),
            bad=[list(c) for c in s.bad_apples],
            score=s.score,
            speed=ticks_per_sec(s.score),
            paused=s.paused,
        )
        await self._ws.send_json(msg.model_dump())

    async def _finalize(self, result: StepResult) -> None:
        assert self._state is not None
        score = self._state.score
        rank = await self._leaderboard.record(self._name, score)
        msg = GameOverMessage(score=score, rank=rank, reason=result.reason or "wall")
        await self._safe_send(msg.model_dump())

    async def _safe_send(self, payload: dict) -> None:
        try:
            await self._ws.send_json(payload)
        except Exception:
            pass

    async def _safe_close(self) -> None:
        try:
            await self._ws.close()
        except Exception:
            pass
