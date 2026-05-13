import asyncio

from fastapi.testclient import TestClient

from app.main import app, leaderboard


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_websocket_end_to_end_wall_collision_records_score():
    _run(leaderboard.clear())

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

    entries = _run(leaderboard.top())
    assert any(e.name == "Tester" for e in entries)
