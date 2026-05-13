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
GameOverReason = Literal["wall", "self", "bad_apple"]
StepEvent = Literal["moved", "ate_apple", "game_over"]


@dataclass
class GameState:
    snake: list[Cell]
    direction: Direction
    good_apple: Cell
    bad_apples: list[Cell]
    score: int = 0
    alive: bool = True
    paused: bool = False


@dataclass
class StepResult:
    event: StepEvent
    reason: GameOverReason | None = None


_DELTAS: dict[Direction, Cell] = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}

_OPPOSITE: dict[Direction, Direction] = {
    "up": "down",
    "down": "up",
    "left": "right",
    "right": "left",
}


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


def ticks_per_sec(score: int) -> float:
    rate = INITIAL_TICKS_PER_SEC * (1.1 ** (score // 5))
    return min(MAX_TICKS_PER_SEC, rate)


def step(
    state: GameState,
    requested_direction: Direction | None,
    rng: random.Random,
) -> StepResult:
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
