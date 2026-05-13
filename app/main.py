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
    return [
        {"name": e.name, "score": e.score, "timestamp": e.timestamp}
        for e in entries
    ]


@app.websocket("/ws/play")
async def ws_play(ws: WebSocket) -> None:
    await ws.accept()
    session = Session(ws, leaderboard)
    await session.run()
