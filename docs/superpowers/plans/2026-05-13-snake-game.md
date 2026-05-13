# Snake Game Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a server-authoritative single-player Snake game over a FastAPI WebSocket, with an in-memory top-10 leaderboard, a multi-screen SPA frontend, and i18n (en/de/es).

**Architecture:** FastAPI serves static SPA + a `/ws/play` WebSocket. Per-connection asyncio task runs the game tick loop, mutates pure `GameState`, broadcasts JSON state every tick, records final score to an in-memory leaderboard. Client renders Canvas, sends inputs, swaps between Name / Play / Game Over / Leaderboard sections via hash routing.

**Tech Stack:** Python 3.14, FastAPI, uvicorn, pytest, plain HTML/CSS/JS (no build step).

**Spec:** `docs/superpowers/specs/2026-05-13-snake-game-design.md`

---

## File Structure

| Path | Responsibility |
|---|---|
| `app/__init__.py` | Marks `app/` as a package. Empty. |
| `app/game.py` | Pure game logic: `GameState`, `step()`, apple spawn, speed curve. No I/O, no async. |
| `app/leaderboard.py` | In-memory top-10 store with async lock. `record()`, `top()`, `clear()`. |
| `app/schemas.py` | Pydantic models for WS messages and HTTP responses. |
| `app/session.py` | Per-WS asyncio session: handle incoming messages, run tick loop, dispatch state, finalize game. |
| `app/main.py` | FastAPI app, mount static, define HTTP + WS routes. |
| `app/static/index.html` | SPA: 4 `<section>`s + nav with language switcher. |
| `app/static/styles.css` | Modern-minimal theme. |
| `app/static/i18n.js` | Translation strings for en/de/es; `t(key, vars)` and `setLang(lang)`. |
| `app/static/app.js` | Hash router, WS client, canvas renderer, input handler. |
| `tests/__init__.py` | Empty package marker. |
| `tests/test_game.py` | Unit tests for `game.py`. |
| `tests/test_leaderboard.py` | Unit tests for `leaderboard.py`. |
| `tests/test_session.py` | WS integration tests using FastAPI `TestClient`. |
| `main.py` (existing) | Thin re-export `from app.main import app`. |
| `pyproject.toml` | Add `pytest` to dev dependencies. |

---

## Task 1: Project scaffolding and dev dependencies

**Files:**
- Modify: `pyproject.toml`
- Create: `app/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Add pytest + httpx as dev dependencies**

Run:
```bash
uv add --dev pytest httpx pytest-asyncio
```

(httpx is required by FastAPI's `TestClient`; `pytest-asyncio` for async leaderboard tests.)

- [ ] **Step 2: Configure pytest asyncio mode**

Append to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 3: Create package markers**

Create `app/__init__.py` (empty file).
Create `tests/__init__.py` (empty file).

- [ ] **Step 4: Verify pytest runs**

Run: `uv run pytest --collect-only`
Expected: exit 5 ("no tests collected") — pytest itself works.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock app/__init__.py tests/__init__.py
git commit -m "Scaffold app/ and tests/ packages, add pytest"
```

---

## Task 2: Pure game logic — `GameState` and initial state

**Files:**
- Create: `app/game.py`, `tests/test_game.py`

- [ ] **Step 1: Write failing test for initial state**

Create `tests/test_game.py`:
```python
import random
from app.game import GameState, new_game, GRID_SIZE


def test_new_game_initial_snake_is_three_cells_centered_facing_right():
    rng = random.Random(42)
    state = new_game(rng)
    assert state.score == 0
    assert state.direction == "right"
    assert len(state.snake) == 3
    ys = {cell[1] for cell in state.snake}
    assert len(ys) == 1
    xs = sorted(cell[0] for cell in state.snake)
    assert xs[2] - xs[0] == 2
    assert ys.pop() == GRID_SIZE // 2


def test_new_game_has_one_good_apple_and_two_bad_apples_not_on_snake():
    rng = random.Random(42)
    state = new_game(rng)
    assert state.good_apple is not None
    assert len(state.bad_apples) == 2
    occupied = set(state.snake)
    assert state.good_apple not in occupied
    for bad in state.bad_apples:
        assert bad not in occupied
        assert bad != state.good_apple
    assert state.bad_apples[0] != state.bad_apples[1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_game.py -v`
Expected: ImportError — `app.game` does not exist.

- [ ] **Step 3: Implement `GameState` + `new_game`**

Create `app/game.py`:
```python
from __future__ import annotations
import random
from dataclasses import dataclass
from typing import Literal

GRID_SIZE = 30
INITIAL_TICKS_PER_SEC = 6.0
MAX_TICKS_PER_SEC = 14.0
NUM_BAD_APPLES = 2

Cell = tuple[int, int]
Direction = Literal["up", "down", "left", "right"]


@dataclass
class GameState:
    snake: list[Cell]
    direction: Direction
    good_apple: Cell
    bad_apples: list[Cell]
    score: int = 0
    alive: bool = True
    paused: bool = False


def _random_empty_cell(rng: random.Random, occupied: set[Cell]) -> Cell:
    while True:
        cell = (rng.randrange(GRID_SIZE), rng.randrange(GRID_SIZE))
        if cell not in occupied:
            return cell


def new_game(rng: random.Random) -> GameState:
    mid = GRID_SIZE // 2
    snake: list[Cell] = [(mid - 2, mid), (mid - 1, mid), (mid, mid)]
    occupied: set[Cell] = set(snake)
    good = _random_empty_cell(rng, occupied)
    occupied.add(good)
    bad1 = _random_empty_cell(rng, occupied)
    occupied.add(bad1)
    bad2 = _random_empty_cell(rng, occupied)
    return GameState(
        snake=snake,
        direction="right",
        good_apple=good,
        bad_apples=[bad1, bad2],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_game.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/game.py tests/test_game.py
git commit -m "Add GameState + new_game with random apples"
```

---

## Task 3: Step function — movement, collisions, eating

**Files:**
- Modify: `app/game.py`, `tests/test_game.py`

- [ ] **Step 1: Write failing tests for `step()`**

Append to `tests/test_game.py`:
```python
from app.game import step, StepResult, ticks_per_sec, INITIAL_TICKS_PER_SEC, MAX_TICKS_PER_SEC


def _make_state(snake, direction="right", good=(20, 20), bads=((25, 25), (26, 26))):
    return GameState(
        snake=list(snake),
        direction=direction,
        good_apple=good,
        bad_apples=list(bads),
    )


def test_step_moves_snake_forward_and_drops_tail():
    rng = random.Random(0)
    s = _make_state([(5, 5), (6, 5), (7, 5)], direction="right")
    result = step(s, requested_direction=None, rng=rng)
    assert result.event == "moved"
    assert s.snake == [(6, 5), (7, 5), (8, 5)]
    assert s.alive is True


def test_step_dies_on_wall():
    rng = random.Random(0)
    s = _make_state([(GRID_SIZE - 3, 5), (GRID_SIZE - 2, 5), (GRID_SIZE - 1, 5)], direction="right")
    result = step(s, requested_direction=None, rng=rng)
    assert result.event == "game_over"
    assert result.reason == "wall"
    assert s.alive is False


def test_step_dies_on_self_collision():
    rng = random.Random(0)
    snake = [(5, 5), (6, 5), (6, 6), (5, 6)]  # head at (5,6) facing left
    s = _make_state(snake, direction="left")
    result = step(s, requested_direction="down", rng=rng)
    assert result.event == "game_over"
    assert result.reason == "self"


def test_step_dies_on_bad_apple():
    rng = random.Random(0)
    s = _make_state([(4, 5), (5, 5), (6, 5)], direction="right", bads=((7, 5), (10, 10)))
    result = step(s, requested_direction=None, rng=rng)
    assert result.event == "game_over"
    assert result.reason == "bad_apple"


def test_step_eats_good_apple_grows_increments_score_respawns_apples():
    rng = random.Random(123)
    s = _make_state([(4, 5), (5, 5), (6, 5)], direction="right", good=(7, 5), bads=((25, 25), (26, 26)))
    original_bads = tuple(s.bad_apples)
    result = step(s, requested_direction=None, rng=rng)
    assert result.event == "ate_apple"
    assert s.score == 1
    assert len(s.snake) == 4
    assert s.snake[-1] == (7, 5)
    assert s.good_apple != (7, 5)
    assert s.good_apple not in s.snake
    assert s.good_apple not in s.bad_apples
    bad_set = set(s.bad_apples)
    assert len(bad_set) == 2
    rerolled = bad_set - set(original_bads)
    assert len(rerolled) == 1


def test_step_ignores_180_degree_reversal():
    rng = random.Random(0)
    s = _make_state([(5, 5), (6, 5), (7, 5)], direction="right")
    result = step(s, requested_direction="left", rng=rng)
    assert result.event == "moved"
    assert s.snake[-1] == (8, 5)
    assert s.direction == "right"


def test_step_applies_perpendicular_direction_change():
    rng = random.Random(0)
    s = _make_state([(5, 5), (6, 5), (7, 5)], direction="right")
    result = step(s, requested_direction="up", rng=rng)
    assert result.event == "moved"
    assert s.direction == "up"
    assert s.snake[-1] == (7, 4)


def test_ticks_per_sec_starts_at_initial_and_caps_at_max():
    assert ticks_per_sec(0) == INITIAL_TICKS_PER_SEC
    assert ticks_per_sec(4) == INITIAL_TICKS_PER_SEC
    assert ticks_per_sec(5) > INITIAL_TICKS_PER_SEC
    assert ticks_per_sec(1000) == MAX_TICKS_PER_SEC
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_game.py -v`
Expected: ImportError on `step, StepResult, ticks_per_sec`.

- [ ] **Step 3: Implement `step()` + `ticks_per_sec()`**

Append to `app/game.py`:
```python
GameOverReason = Literal["wall", "self", "bad_apple"]
StepEvent = Literal["moved", "ate_apple", "game_over"]

_DELTAS: dict[Direction, Cell] = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}

_OPPOSITE: dict[Direction, Direction] = {
    "up": "down", "down": "up", "left": "right", "right": "left",
}


@dataclass
class StepResult:
    event: StepEvent
    reason: GameOverReason | None = None


def ticks_per_sec(score: int) -> float:
    rate = INITIAL_TICKS_PER_SEC * (1.1 ** (score // 5))
    return min(MAX_TICKS_PER_SEC, rate)


def step(state: GameState, requested_direction: Direction | None, rng: random.Random) -> StepResult:
    if not state.alive:
        return StepResult(event="game_over", reason=None)

    if requested_direction is not None and requested_direction != _OPPOSITE[state.direction]:
        state.direction = requested_direction

    dx, dy = _DELTAS[state.direction]
    head = state.snake[-1]
    new_head = (head[0] + dx, head[1] + dy)

    if not (0 <= new_head[0] < GRID_SIZE and 0 <= new_head[1] < GRID_SIZE):
        state.alive = False
        return StepResult(event="game_over", reason="wall")

    will_eat = new_head == state.good_apple
    body_after = set(state.snake) if will_eat else set(state.snake[1:])
    if new_head in body_after:
        state.alive = False
        return StepResult(event="game_over", reason="self")

    if new_head in state.bad_apples:
        state.alive = False
        return StepResult(event="game_over", reason="bad_apple")

    state.snake.append(new_head)
    if will_eat:
        state.score += 1
        occupied: set[Cell] = set(state.snake) | set(state.bad_apples)
        state.good_apple = _random_empty_cell(rng, occupied)
        occupied = set(state.snake) | {state.good_apple, state.bad_apples[1]}
        state.bad_apples[0] = _random_empty_cell(rng, occupied)
        return StepResult(event="ate_apple")

    state.snake.pop(0)
    return StepResult(event="moved")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_game.py -v`
Expected: 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/game.py tests/test_game.py
git commit -m "Implement game step() with collisions, eating, speed curve"
```

---

## Task 4: Leaderboard

**Files:**
- Create: `app/leaderboard.py`, `tests/test_leaderboard.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_leaderboard.py`:
```python
from app.leaderboard import Leaderboard


async def test_record_returns_rank_for_qualifying_score():
    lb = Leaderboard(capacity=3)
    assert await lb.record("Alice", 10) == 1
    assert await lb.record("Bob", 20) == 1
    assert await lb.record("Carol", 15) == 2


async def test_record_returns_none_when_score_does_not_qualify():
    lb = Leaderboard(capacity=2)
    await lb.record("Alice", 10)
    await lb.record("Bob", 20)
    rank = await lb.record("Carol", 5)
    assert rank is None
    entries = await lb.top()
    assert [e.name for e in entries] == ["Bob", "Alice"]


async def test_top_returns_descending_by_score():
    lb = Leaderboard(capacity=10)
    await lb.record("A", 5)
    await lb.record("B", 50)
    await lb.record("C", 25)
    top = await lb.top()
    assert [e.score for e in top] == [50, 25, 5]


async def test_ties_are_ordered_by_recency_oldest_first():
    lb = Leaderboard(capacity=10)
    await lb.record("A", 10)
    await lb.record("B", 10)
    top = await lb.top()
    assert [e.name for e in top] == ["A", "B"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_leaderboard.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement leaderboard**

Create `app/leaderboard.py`:
```python
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
            # Stable sort by -score keeps earlier entries first on ties.
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_leaderboard.py -v`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/leaderboard.py tests/test_leaderboard.py
git commit -m "Add in-memory top-N leaderboard"
```

---

## Task 5: Schemas

**Files:**
- Create: `app/schemas.py`

- [ ] **Step 1: Create message schemas**

Create `app/schemas.py`:
```python
from __future__ import annotations
import re
from typing import Literal
from pydantic import BaseModel, field_validator

Direction = Literal["up", "down", "left", "right"]
GameOverReason = Literal["wall", "self", "bad_apple"]

NAME_PATTERN = re.compile(r"^[\w\s\-]+$", re.UNICODE)


class StartMessage(BaseModel):
    type: Literal["start"]
    name: str

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        if len(v) > 20:
            raise ValueError("name must be 20 characters or fewer")
        if not NAME_PATTERN.match(v):
            raise ValueError("name contains invalid characters")
        return v


class InputMessage(BaseModel):
    type: Literal["input"]
    dir: Direction


class PauseMessage(BaseModel):
    type: Literal["pause"]


class ResumeMessage(BaseModel):
    type: Literal["resume"]


class StateMessage(BaseModel):
    type: Literal["state"] = "state"
    tick: int
    snake: list[list[int]]
    apple: list[int]
    bad: list[list[int]]
    score: int
    speed: float
    paused: bool


class GameOverMessage(BaseModel):
    type: Literal["game_over"] = "game_over"
    score: int
    rank: int | None
    reason: GameOverReason


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    message: str
```

- [ ] **Step 2: Sanity import**

Run: `uv run python -c "from app import schemas; print(schemas.StartMessage(type='start', name='Diego'))"`
Expected: prints `type='start' name='Diego'` with no exception.

- [ ] **Step 3: Commit**

```bash
git add app/schemas.py
git commit -m "Add Pydantic schemas for WS protocol"
```

---

## Task 6: Session — per-WS game loop

**Files:**
- Create: `app/session.py`

- [ ] **Step 1: Implement session class**

Create `app/session.py`:
```python
from __future__ import annotations
import asyncio
import random
from fastapi import WebSocket, WebSocketDisconnect

from app.game import GameState, StepResult, new_game, step, ticks_per_sec
from app.leaderboard import Leaderboard
from app.schemas import (
    StartMessage,
    InputMessage,
    PauseMessage,
    ResumeMessage,
    StateMessage,
    GameOverMessage,
    ErrorMessage,
)


class Session:
    def __init__(self, ws: WebSocket, leaderboard: Leaderboard, rng: random.Random | None = None) -> None:
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
```

- [ ] **Step 2: Sanity import**

Run: `uv run python -c "from app import session; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add app/session.py
git commit -m "Add per-WebSocket Session game loop"
```

---

## Task 7: FastAPI app — routes and static mount

**Files:**
- Create: `app/main.py`
- Modify: `main.py`

- [ ] **Step 1: Implement FastAPI app**

Create `app/main.py`:
```python
from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.leaderboard import Leaderboard
from app.session import Session

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI()
leaderboard = Leaderboard(capacity=10)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/leaderboard")
async def get_leaderboard() -> list[dict]:
    entries = await leaderboard.top()
    return [{"name": e.name, "score": e.score, "timestamp": e.timestamp} for e in entries]


@app.websocket("/ws/play")
async def ws_play(ws: WebSocket) -> None:
    await ws.accept()
    session = Session(ws, leaderboard)
    await session.run()
```

- [ ] **Step 2: Replace existing `main.py` with re-export**

Overwrite `main.py`:
```python
from app.main import app

__all__ = ["app"]
```

- [ ] **Step 3: Sanity import**

Run: `uv run python -c "from main import app; print(len(app.routes), 'routes')"`
Expected: prints a route count > 0.

- [ ] **Step 4: Commit**

```bash
git add app/main.py main.py
git commit -m "Wire FastAPI routes and WebSocket endpoint"
```

---

## Task 8: WebSocket integration test

**Files:**
- Create: `tests/test_session.py`

- [ ] **Step 1: Write integration test**

Create `tests/test_session.py`:
```python
import asyncio
from fastapi.testclient import TestClient
from app.main import app, leaderboard


def test_websocket_end_to_end_wall_collision_records_score():
    asyncio.new_event_loop().run_until_complete(leaderboard.clear())

    client = TestClient(app)
    with client.websocket_connect("/ws/play") as ws:
        ws.send_json({"type": "start", "name": "Tester"})
        first = ws.receive_json()
        assert first["type"] == "state"
        assert first["score"] == 0
        assert len(first["snake"]) == 3

        game_over = None
        for _ in range(200):
            msg = ws.receive_json()
            if msg["type"] == "game_over":
                game_over = msg
                break
        assert game_over is not None
        assert game_over["reason"] == "wall"
        assert game_over["score"] == 0

    entries = asyncio.new_event_loop().run_until_complete(leaderboard.top())
    assert any(e.name == "Tester" for e in entries)
```

- [ ] **Step 2: Run integration test**

Run: `uv run pytest tests/test_session.py -v`
Expected: PASS.

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_session.py
git commit -m "Add WebSocket integration smoke test"
```

---

## Task 9: Frontend — HTML scaffold

**Files:**
- Create: `app/static/index.html`

- [ ] **Step 1: Create HTML**

Create `app/static/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Snake</title>
  <link rel="stylesheet" href="/static/styles.css" />
</head>
<body>
  <header>
    <nav>
      <a href="#/name" data-i18n="nav.name">Name</a>
      <a href="#/play" data-i18n="nav.play">Play</a>
      <a href="#/leaderboard" data-i18n="nav.leaderboard">Leaderboard</a>
    </nav>
    <select id="lang-select" aria-label="Language">
      <option value="en">EN</option>
      <option value="de">DE</option>
      <option value="es">ES</option>
    </select>
  </header>

  <main>
    <section id="screen-name" class="screen">
      <h1 data-i18n="name.title">Enter your name</h1>
      <input id="name-input" maxlength="20" data-i18n-placeholder="name.placeholder" placeholder="Your name" />
      <p id="name-error" class="error" hidden></p>
      <button id="start-btn" data-i18n="name.start">Play</button>
    </section>

    <section id="screen-play" class="screen" hidden>
      <div class="hud">
        <span id="score-line">Apples: 0</span>
        <span id="paused-line" hidden data-i18n="play.paused">Paused</span>
      </div>
      <canvas id="game-canvas" width="600" height="600"></canvas>
      <p class="hint" data-i18n="play.resume_hint">Press Space to pause/resume</p>
    </section>

    <section id="screen-over" class="screen" hidden>
      <h1 data-i18n="over.title">Game Over</h1>
      <p id="over-score">You ate 0 apples</p>
      <p id="over-reason"></p>
      <p id="over-rank"></p>
      <button id="again-btn" data-i18n="over.play_again">Play again</button>
    </section>

    <section id="screen-leaderboard" class="screen" hidden>
      <h1 data-i18n="lb.title">Leaderboard</h1>
      <table id="lb-table">
        <thead>
          <tr>
            <th data-i18n="lb.col_rank">#</th>
            <th data-i18n="lb.col_name">Name</th>
            <th data-i18n="lb.col_score">Apples</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
      <p id="lb-empty" hidden data-i18n="lb.empty">No scores yet.</p>
    </section>
  </main>

  <script src="/static/i18n.js"></script>
  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add app/static/index.html
git commit -m "Add SPA HTML scaffold"
```

---

## Task 10: Frontend — i18n module

**Files:**
- Create: `app/static/i18n.js`

- [ ] **Step 1: Create translation module**

Create `app/static/i18n.js`:
```javascript
const TRANSLATIONS = {
  en: {
    "nav.name": "Name",
    "nav.play": "Play",
    "nav.leaderboard": "Leaderboard",
    "name.title": "Enter your name",
    "name.placeholder": "Your name",
    "name.start": "Play",
    "name.error_empty": "Please enter a name.",
    "name.error_too_long": "Name must be 20 characters or fewer.",
    "name.error_invalid_chars": "Name contains invalid characters.",
    "play.score": "Apples: {score}",
    "play.paused": "Paused",
    "play.resume_hint": "Press Space to pause/resume",
    "over.title": "Game Over",
    "over.score": "You ate {score} apples",
    "over.reason_wall": "You hit a wall.",
    "over.reason_self": "You ran into yourself.",
    "over.reason_bad_apple": "You ate a bad apple.",
    "over.rank": "Rank: #{rank}",
    "over.no_rank": "Not in top 10.",
    "over.play_again": "Play again",
    "lb.title": "Leaderboard",
    "lb.col_rank": "#",
    "lb.col_name": "Name",
    "lb.col_score": "Apples",
    "lb.empty": "No scores yet.",
  },
  de: {
    "nav.name": "Name",
    "nav.play": "Spielen",
    "nav.leaderboard": "Bestenliste",
    "name.title": "Gib deinen Namen ein",
    "name.placeholder": "Dein Name",
    "name.start": "Spielen",
    "name.error_empty": "Bitte gib einen Namen ein.",
    "name.error_too_long": "Name darf höchstens 20 Zeichen lang sein.",
    "name.error_invalid_chars": "Name enthält ungültige Zeichen.",
    "play.score": "Äpfel: {score}",
    "play.paused": "Pausiert",
    "play.resume_hint": "Leertaste zum Pausieren/Fortsetzen",
    "over.title": "Spiel vorbei",
    "over.score": "Du hast {score} Äpfel gegessen",
    "over.reason_wall": "Du bist gegen eine Wand gestoßen.",
    "over.reason_self": "Du bist in dich selbst gelaufen.",
    "over.reason_bad_apple": "Du hast einen schlechten Apfel gegessen.",
    "over.rank": "Platz: #{rank}",
    "over.no_rank": "Nicht in den Top 10.",
    "over.play_again": "Nochmal spielen",
    "lb.title": "Bestenliste",
    "lb.col_rank": "#",
    "lb.col_name": "Name",
    "lb.col_score": "Äpfel",
    "lb.empty": "Noch keine Ergebnisse.",
  },
  es: {
    "nav.name": "Nombre",
    "nav.play": "Jugar",
    "nav.leaderboard": "Clasificación",
    "name.title": "Introduce tu nombre",
    "name.placeholder": "Tu nombre",
    "name.start": "Jugar",
    "name.error_empty": "Introduce un nombre.",
    "name.error_too_long": "El nombre debe tener 20 caracteres o menos.",
    "name.error_invalid_chars": "El nombre contiene caracteres no válidos.",
    "play.score": "Manzanas: {score}",
    "play.paused": "Pausado",
    "play.resume_hint": "Pulsa Espacio para pausar/reanudar",
    "over.title": "Fin del juego",
    "over.score": "Comiste {score} manzanas",
    "over.reason_wall": "Chocaste con una pared.",
    "over.reason_self": "Chocaste contigo mismo.",
    "over.reason_bad_apple": "Comiste una manzana mala.",
    "over.rank": "Puesto: #{rank}",
    "over.no_rank": "No estás en el top 10.",
    "over.play_again": "Jugar otra vez",
    "lb.title": "Clasificación",
    "lb.col_rank": "#",
    "lb.col_name": "Nombre",
    "lb.col_score": "Manzanas",
    "lb.empty": "Aún no hay puntuaciones.",
  },
};

const SUPPORTED = ["en", "de", "es"];
let currentLang = "en";

function detectLang() {
  const stored = localStorage.getItem("lang");
  if (stored && SUPPORTED.includes(stored)) return stored;
  for (const candidate of navigator.languages || [navigator.language || "en"]) {
    const short = candidate.slice(0, 2).toLowerCase();
    if (SUPPORTED.includes(short)) return short;
  }
  return "en";
}

function t(key, vars) {
  vars = vars || {};
  const dict = TRANSLATIONS[currentLang] || TRANSLATIONS.en;
  let str = dict[key] || TRANSLATIONS.en[key] || key;
  for (const k of Object.keys(vars)) {
    str = str.split("{" + k + "}").join(String(vars[k]));
  }
  return str;
}

function applyTranslations(root) {
  root = root || document;
  for (const el of root.querySelectorAll("[data-i18n]")) {
    el.textContent = t(el.dataset.i18n);
  }
  for (const el of root.querySelectorAll("[data-i18n-placeholder]")) {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  }
}

function setLang(lang) {
  if (!SUPPORTED.includes(lang)) return;
  currentLang = lang;
  localStorage.setItem("lang", lang);
  document.documentElement.lang = lang;
  applyTranslations();
  document.dispatchEvent(new CustomEvent("langchange", { detail: { lang } }));
}

window.i18n = { t, setLang, applyTranslations, detectLang, getLang: function () { return currentLang; } };
```

- [ ] **Step 2: Commit**

```bash
git add app/static/i18n.js
git commit -m "Add i18n module with en/de/es translations"
```

---

## Task 11: Frontend — styles

**Files:**
- Create: `app/static/styles.css`

- [ ] **Step 1: Create stylesheet**

Create `app/static/styles.css`:
```css
:root {
  --bg: #0f172a;
  --bg-2: #1e293b;
  --fg: #e2e8f0;
  --accent: #84cc16;
  --danger: #ef4444;
  --muted: #64748b;
  --border: #334155;
  --radius: 10px;
  --font: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
}

* { box-sizing: border-box; }

html, body {
  margin: 0;
  padding: 0;
  background: var(--bg);
  color: var(--fg);
  font-family: var(--font);
  min-height: 100vh;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border);
  background: var(--bg-2);
}

nav a {
  color: var(--fg);
  text-decoration: none;
  margin-right: 1.25rem;
  font-weight: 500;
  opacity: 0.75;
}
nav a:hover, nav a.active { opacity: 1; color: var(--accent); }

#lang-select {
  background: var(--bg);
  color: var(--fg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.35rem 0.6rem;
  font-family: inherit;
}

main {
  display: flex;
  justify-content: center;
  padding: 2rem 1rem;
}

.screen {
  width: 100%;
  max-width: 640px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

h1 { margin: 0.5rem 0; font-weight: 600; letter-spacing: -0.01em; }

input, button {
  font-family: inherit;
  font-size: 1rem;
  border-radius: var(--radius);
  padding: 0.6rem 0.9rem;
  border: 1px solid var(--border);
}

input {
  background: var(--bg-2);
  color: var(--fg);
  width: 100%;
  max-width: 320px;
}

button {
  background: var(--accent);
  color: #0a0f1e;
  border: none;
  font-weight: 600;
  cursor: pointer;
  padding: 0.7rem 1.4rem;
}
button:hover { filter: brightness(1.08); }

.error { color: var(--danger); margin: 0; min-height: 1.2em; }
.hint { color: var(--muted); font-size: 0.875rem; }

.hud {
  display: flex;
  gap: 1.5rem;
  font-variant-numeric: tabular-nums;
  font-size: 1.125rem;
}

#game-canvas {
  background: var(--bg-2);
  border-radius: var(--radius);
  border: 1px solid var(--border);
  max-width: 100%;
  height: auto;
  aspect-ratio: 1 / 1;
}

#lb-table {
  width: 100%;
  border-collapse: collapse;
}
#lb-table th, #lb-table td {
  text-align: left;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border);
}
#lb-table th { color: var(--muted); font-weight: 500; }
```

- [ ] **Step 2: Commit**

```bash
git add app/static/styles.css
git commit -m "Add modern-minimal stylesheet"
```

---

## Task 12: Frontend — application JS

**Files:**
- Create: `app/static/app.js`

**Note:** DOM elements are built with `document.createElement` + `textContent` everywhere — no `innerHTML` with interpolated user data (XSS safety, even though the names round-trip through the server's validator).

- [ ] **Step 1: Implement client**

Create `app/static/app.js`:
```javascript
(function () {
  const GRID_SIZE = 30;
  const SCREENS = ["name", "play", "over", "leaderboard"];
  const VALID_NAME_RE = /^[\p{L}\p{N} _\-]+$/u;

  const canvas = document.getElementById("game-canvas");
  const ctx = canvas.getContext("2d");
  const cellSize = canvas.width / GRID_SIZE;

  const nameInput = document.getElementById("name-input");
  const nameError = document.getElementById("name-error");
  const startBtn = document.getElementById("start-btn");
  const againBtn = document.getElementById("again-btn");
  const scoreLine = document.getElementById("score-line");
  const pausedLine = document.getElementById("paused-line");
  const overScore = document.getElementById("over-score");
  const overReason = document.getElementById("over-reason");
  const overRank = document.getElementById("over-rank");
  const lbBody = document.querySelector("#lb-table tbody");
  const lbEmpty = document.getElementById("lb-empty");
  const langSelect = document.getElementById("lang-select");

  let ws = null;
  let lastState = null;
  let lastGameOver = null;
  let storedName = localStorage.getItem("playerName") || "";
  nameInput.value = storedName;

  // ---- i18n bootstrap ----
  const initialLang = window.i18n.detectLang();
  langSelect.value = initialLang;
  window.i18n.setLang(initialLang);
  langSelect.addEventListener("change", function () { window.i18n.setLang(langSelect.value); });
  document.addEventListener("langchange", function () {
    refreshDynamicTexts();
    if (currentScreen() === "leaderboard") loadLeaderboard();
  });

  // ---- router ----
  function currentScreen() {
    const hash = location.hash.replace(/^#\//, "");
    return SCREENS.indexOf(hash) >= 0 ? hash : "name";
  }
  function showScreen(name) {
    for (const id of SCREENS) {
      document.getElementById("screen-" + id).hidden = id !== name;
    }
    for (const link of document.querySelectorAll("nav a")) {
      link.classList.toggle("active", link.getAttribute("href") === "#/" + name);
    }
    if (name !== "play") disconnect();
    if (name === "play") onEnterPlay();
    if (name === "over") onEnterOver();
    if (name === "leaderboard") loadLeaderboard();
  }
  function navigate(name) {
    if (location.hash !== "#/" + name) location.hash = "#/" + name;
    else showScreen(name);
  }
  window.addEventListener("hashchange", function () { showScreen(currentScreen()); });

  // ---- name screen ----
  function validateName(name) {
    const trimmed = name.trim();
    if (!trimmed) return "name.error_empty";
    if (trimmed.length > 20) return "name.error_too_long";
    if (!VALID_NAME_RE.test(trimmed)) return "name.error_invalid_chars";
    return null;
  }
  startBtn.addEventListener("click", function () {
    const err = validateName(nameInput.value);
    if (err) {
      nameError.textContent = window.i18n.t(err);
      nameError.hidden = false;
      return;
    }
    nameError.hidden = true;
    storedName = nameInput.value.trim();
    localStorage.setItem("playerName", storedName);
    navigate("play");
  });
  againBtn.addEventListener("click", function () { navigate("play"); });

  // ---- play screen ----
  function onEnterPlay() {
    if (!storedName) { navigate("name"); return; }
    connectAndStart();
  }

  function connectAndStart() {
    disconnect();
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(proto + "//" + location.host + "/ws/play");
    ws.addEventListener("open", function () {
      ws.send(JSON.stringify({ type: "start", name: storedName }));
    });
    ws.addEventListener("message", function (ev) {
      const msg = JSON.parse(ev.data);
      if (msg.type === "state") {
        lastState = msg;
        render(msg);
      } else if (msg.type === "game_over") {
        lastGameOver = msg;
        navigate("over");
      } else if (msg.type === "error") {
        console.warn("server error:", msg.message);
      }
    });
    ws.addEventListener("close", function () { ws = null; });
  }
  function disconnect() {
    if (ws && ws.readyState <= 1) { try { ws.close(); } catch (e) {} }
    ws = null;
  }

  // ---- renderer ----
  function render(state) {
    ctx.fillStyle = "#1e293b";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    for (const cell of state.bad) {
      drawCell(cell[0], cell[1], "#4c1d95");
      ctx.fillStyle = "#e2e8f0";
      ctx.font = Math.floor(cellSize * 0.7) + "px " + getComputedStyle(document.body).fontFamily;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("✕", cell[0] * cellSize + cellSize / 2, cell[1] * cellSize + cellSize / 2 + 1);
    }
    drawCell(state.apple[0], state.apple[1], "#ef4444");
    for (let i = 0; i < state.snake.length; i++) {
      const c = state.snake[i];
      const isHead = i === state.snake.length - 1;
      drawCell(c[0], c[1], isHead ? "#bef264" : "#84cc16");
    }
    scoreLine.textContent = window.i18n.t("play.score", { score: state.score });
    pausedLine.hidden = !state.paused;
  }
  function drawCell(x, y, color) {
    ctx.fillStyle = color;
    const pad = 1;
    ctx.fillRect(x * cellSize + pad, y * cellSize + pad, cellSize - 2 * pad, cellSize - 2 * pad);
  }

  // ---- input ----
  const KEY_DIR = {
    ArrowUp: "up", w: "up", W: "up",
    ArrowDown: "down", s: "down", S: "down",
    ArrowLeft: "left", a: "left", A: "left",
    ArrowRight: "right", d: "right", D: "right",
  };
  let paused = false;
  document.addEventListener("keydown", function (e) {
    if (currentScreen() !== "play" || !ws || ws.readyState !== 1) return;
    if (e.key === " " || e.key === "Spacebar") {
      paused = !paused;
      ws.send(JSON.stringify({ type: paused ? "pause" : "resume" }));
      e.preventDefault();
      return;
    }
    const dir = KEY_DIR[e.key];
    if (dir) {
      ws.send(JSON.stringify({ type: "input", dir: dir }));
      e.preventDefault();
    }
  });

  // ---- game over screen ----
  function onEnterOver() {
    if (!lastGameOver) { navigate("name"); return; }
    overScore.textContent = window.i18n.t("over.score", { score: lastGameOver.score });
    overReason.textContent = window.i18n.t("over.reason_" + lastGameOver.reason);
    overRank.textContent = lastGameOver.rank
      ? window.i18n.t("over.rank", { rank: lastGameOver.rank })
      : window.i18n.t("over.no_rank");
  }

  // ---- leaderboard ----
  async function loadLeaderboard() {
    const resp = await fetch("/leaderboard");
    const rows = await resp.json();
    while (lbBody.firstChild) lbBody.removeChild(lbBody.firstChild);
    lbEmpty.hidden = rows.length > 0;
    rows.forEach(function (r, idx) {
      const tr = document.createElement("tr");
      const td1 = document.createElement("td");
      const td2 = document.createElement("td");
      const td3 = document.createElement("td");
      td1.textContent = String(idx + 1);
      td2.textContent = r.name;
      td3.textContent = String(r.score);
      tr.appendChild(td1);
      tr.appendChild(td2);
      tr.appendChild(td3);
      lbBody.appendChild(tr);
    });
  }

  function refreshDynamicTexts() {
    if (lastState) {
      scoreLine.textContent = window.i18n.t("play.score", { score: lastState.score });
    }
    if (lastGameOver && currentScreen() === "over") onEnterOver();
  }

  // ---- boot ----
  showScreen(currentScreen());
})();
```

- [ ] **Step 2: Commit**

```bash
git add app/static/app.js
git commit -m "Add SPA client: router, WS, renderer, input"
```

---

## Task 13: Manual smoke test and finalize

**Files:** none

- [ ] **Step 1: Run full test suite one more time**

Run: `uv run pytest -v`
Expected: all tests PASS.

- [ ] **Step 2: Start the server locally**

Run: `uv run uvicorn main:app --port 8000` (run in background)
Expected: server starts on http://localhost:8000.

- [ ] **Step 3: Probe the HTTP endpoints**

Run: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/`
Expected: `200`.

Run: `curl -s http://localhost:8000/leaderboard`
Expected: `[]` (or whatever entries the integration test left).

- [ ] **Step 4: Stop the server**

Kill the background uvicorn process.

- [ ] **Step 5: Report to user with manual play checklist**

Tell the user: server is ready. To smoke-test in a browser, run `uv run uvicorn main:app --port 8000` and verify:
1. Default language matches browser locale or English fallback
2. Language dropdown re-translates all labels
3. Enter name and click Play — game starts
4. Arrow keys / WASD move the snake
5. Eat a good apple — score increments
6. Steer into a wall — Game Over with correct reason
7. Steer into a bad apple — Game Over with reason "bad apple"
8. Visit Leaderboard — your scores listed
9. Mid-game nav forfeits the round (no score recorded)

---

## Self-Review Notes

- All spec requirements covered: server-auth WS (Task 6), in-memory leaderboard (Task 4), 30×30 grid + 1 good + 2 bad apples + reroll-on-eat (Task 3), wall/self/bad-apple death (Task 3), multi-screen with free nav (Task 12), 6→14 ticks/sec speed curve (Task 3), arrow + WASD + Space (Task 12), modern minimal visuals (Task 11), i18n en/de/es (Task 10).
- Forfeit-on-disconnect handled by `Session.run()` `WebSocketDisconnect` catch (Task 6) + client `disconnect()` on screen change (Task 12).
- Function/property names consistent across tasks: `Leaderboard.record/top/clear`, `GameState.snake/score/...`, `StateMessage.tick/snake/apple/bad/score/speed/paused`, `GameOverMessage.score/rank/reason`.
- No `innerHTML` with interpolated data in client (XSS-safe DOM construction).
- No TBDs / placeholders.
