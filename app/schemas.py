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
