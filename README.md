# Snake

A browser-based, single-player Snake game with a server-authoritative game loop over WebSockets, a multi-language UI (English, German, Spanish), bad apples that end the round, and an in-memory top-10 leaderboard.

Built with **FastAPI** + plain HTML/CSS/JS. Auto-deployed on Render.

## Gameplay

- Enter your name, click **Play**, and steer the snake with **Arrow keys** or **WASD**.
- Eat the red apples to grow and score.
- Avoid:
  - **Walls** — instant game over.
  - **Your own tail** — instant game over.
  - **Dark-purple apples marked `✕`** — bad apples; eating one ends the round.
- Press **Space** to pause / resume.
- After every 5 apples, the snake speeds up (capped so the game stays playable).
- The top 10 scores are kept in memory and displayed on the **Leaderboard** screen.

### Languages

Use the language dropdown in the top-right to switch between **English / Deutsch / Español**. The initial language is taken from your browser locale and remembered in `localStorage`.

## Running locally

Requires Python 3.14+ and [uv](https://github.com/astral-sh/uv).

```bash
uv sync
uv run uvicorn main:app --port 8000
```

Then open <http://localhost:8000>.

### Tests

```bash
uv run pytest
```

15 tests cover the pure game logic, the leaderboard, and a WebSocket end-to-end smoke test.

## Architecture

```
Browser  ──HTTP──▶  FastAPI  ──serves──▶  app/static/* (HTML, CSS, JS)
   │
   │  WebSocket  /ws/play
   ▼
FastAPI  ──spawns──▶  Session (asyncio task)
                          │
                          ├── GameState (pure logic in app/game.py)
                          └── Leaderboard (in-memory top-10)
```

- The **server owns truth**: it ticks the game, applies queued inputs, broadcasts full state every tick (~6–14 Hz), and records the final score when the snake dies.
- The **client is a thin renderer**: it draws state on a 600×600 canvas, sends key events, and swaps between four screens (Name / Play / Game Over / Leaderboard) via hash-based routing.
- **No database.** Scores live in a process-local Python list, wiped on restart.

### Project layout

```
app/
  game.py          # pure game logic (GameState, step, speed curve)
  leaderboard.py   # in-memory top-N store with asyncio lock
  schemas.py       # Pydantic models for the WebSocket protocol
  session.py       # per-WebSocket asyncio game loop
  main.py          # FastAPI app, routes, static mount
  static/
    index.html
    styles.css
    i18n.js        # en/de/es translations
    app.js         # router, WS client, canvas renderer, input handler
tests/
  test_game.py
  test_leaderboard.py
  test_session.py
main.py            # thin re-export of app.main:app (kept for Render)
docs/superpowers/
  specs/           # design specification
  plans/           # implementation plan
```

### WebSocket protocol

**Client → Server**

```json
{"type": "start",  "name": "Diego"}
{"type": "input",  "dir":  "up" | "down" | "left" | "right"}
{"type": "pause"}
{"type": "resume"}
```

**Server → Client** (broadcast every tick)

```json
{
  "type": "state",
  "tick": 42,
  "snake": [[x, y], ...],
  "apple": [x, y],
  "bad":   [[x, y], [x, y]],
  "score": 7,
  "speed": 7.32,
  "paused": false
}
```

**Server → Client** (on game over, then socket closes)

```json
{"type": "game_over", "score": 7, "rank": 3, "reason": "bad_apple"}
```

`reason` is one of `"wall"`, `"self"`, `"bad_apple"`. `rank` is the 1-based leaderboard position if the score qualified for the top 10, otherwise `null`.

## Deployment

The repository is auto-deployed on Render. The service start command is `uvicorn main:app` (root `main.py` is a thin re-export so the start command did not need to change when the app was modularised).

Render's free tier puts the service to sleep after ~15 min of idle; the first request after sleep takes a few seconds to wake it.

## Design and implementation docs

- Design spec: [`docs/superpowers/specs/2026-05-13-snake-game-design.md`](docs/superpowers/specs/2026-05-13-snake-game-design.md)
- Implementation plan: [`docs/superpowers/plans/2026-05-13-snake-game.md`](docs/superpowers/plans/2026-05-13-snake-game.md)

## License

See [LICENSE](LICENSE).
