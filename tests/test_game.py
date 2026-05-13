import random

from app.game import (
    GRID_SIZE,
    INITIAL_TICKS_PER_SEC,
    MAX_TICKS_PER_SEC,
    GameState,
    new_game,
    step,
    ticks_per_sec,
)


def _make_state(snake, direction="right", good=(20, 20), bads=((25, 25), (26, 26))):
    return GameState(
        snake=list(snake),
        direction=direction,
        good_apple=good,
        bad_apples=list(bads),
    )


def test_new_game_initial_snake_is_three_cells_centered_facing_right():
    state = new_game(random.Random(42))
    assert state.score == 0
    assert state.direction == "right"
    assert len(state.snake) == 3
    ys = {cell[1] for cell in state.snake}
    assert len(ys) == 1
    xs = sorted(cell[0] for cell in state.snake)
    assert xs[2] - xs[0] == 2
    assert ys.pop() == GRID_SIZE // 2


def test_new_game_has_one_good_apple_and_two_bad_apples_not_on_snake():
    state = new_game(random.Random(42))
    assert state.good_apple is not None
    assert len(state.bad_apples) == 2
    occupied = set(state.snake)
    assert state.good_apple not in occupied
    for bad in state.bad_apples:
        assert bad not in occupied
        assert bad != state.good_apple
    assert state.bad_apples[0] != state.bad_apples[1]


def test_step_moves_snake_forward_and_drops_tail():
    s = _make_state([(5, 5), (6, 5), (7, 5)], direction="right")
    result = step(s, requested_direction=None, rng=random.Random(0))
    assert result.event == "moved"
    assert s.snake == [(6, 5), (7, 5), (8, 5)]
    assert s.alive is True


def test_step_dies_on_wall():
    s = _make_state(
        [(GRID_SIZE - 3, 5), (GRID_SIZE - 2, 5), (GRID_SIZE - 1, 5)],
        direction="right",
    )
    result = step(s, requested_direction=None, rng=random.Random(0))
    assert result.event == "game_over"
    assert result.reason == "wall"
    assert s.alive is False


def test_step_dies_on_self_collision():
    # 5-cell snake forming a U; head at (6,6) moving left, request "up" so head
    # turns into (6,5) which is in the body.
    snake = [(5, 5), (6, 5), (7, 5), (7, 6), (6, 6)]
    s = _make_state(snake, direction="left")
    result = step(s, requested_direction="up", rng=random.Random(0))
    assert result.event == "game_over"
    assert result.reason == "self"


def test_step_dies_on_bad_apple():
    s = _make_state(
        [(4, 5), (5, 5), (6, 5)],
        direction="right",
        bads=((7, 5), (10, 10)),
    )
    result = step(s, requested_direction=None, rng=random.Random(0))
    assert result.event == "game_over"
    assert result.reason == "bad_apple"


def test_step_eats_good_apple_grows_increments_score_respawns_apples():
    s = _make_state(
        [(4, 5), (5, 5), (6, 5)],
        direction="right",
        good=(7, 5),
        bads=((25, 25), (26, 26)),
    )
    original_bads = tuple(s.bad_apples)
    result = step(s, requested_direction=None, rng=random.Random(123))
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
    s = _make_state([(5, 5), (6, 5), (7, 5)], direction="right")
    result = step(s, requested_direction="left", rng=random.Random(0))
    assert result.event == "moved"
    assert s.snake[-1] == (8, 5)
    assert s.direction == "right"


def test_step_applies_perpendicular_direction_change():
    s = _make_state([(5, 5), (6, 5), (7, 5)], direction="right")
    result = step(s, requested_direction="up", rng=random.Random(0))
    assert result.event == "moved"
    assert s.direction == "up"
    assert s.snake[-1] == (7, 4)


def test_ticks_per_sec_starts_at_initial_and_caps_at_max():
    assert ticks_per_sec(0) == INITIAL_TICKS_PER_SEC
    assert ticks_per_sec(4) == INITIAL_TICKS_PER_SEC
    assert ticks_per_sec(5) > INITIAL_TICKS_PER_SEC
    assert ticks_per_sec(1000) == MAX_TICKS_PER_SEC
