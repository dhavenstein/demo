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
