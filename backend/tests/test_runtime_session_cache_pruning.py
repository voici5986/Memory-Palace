from datetime import datetime, timedelta, timezone

import pytest

from runtime_state import SessionSearchCache


@pytest.mark.asyncio
async def test_session_search_cache_prunes_stale_hits_before_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNTIME_SESSION_CACHE_HALF_LIFE_SECONDS", "60")
    cache = SessionSearchCache()
    stale_updated_at = (
        datetime.now(timezone.utc) - timedelta(seconds=600)
    ).isoformat().replace("+00:00", "Z")

    await cache.record_hit(
        session_id="session-a",
        uri="core://stale",
        memory_id=1,
        snippet="release checklist",
        updated_at=stale_updated_at,
    )
    await cache.record_hit(
        session_id="session-a",
        uri="core://fresh",
        memory_id=2,
        snippet="release checklist",
    )

    results = await cache.search(session_id="session-a", query="release", limit=5)

    assert [item["uri"] for item in results] == ["core://fresh"]


@pytest.mark.asyncio
async def test_session_search_cache_prunes_stale_sessions_before_capacity_eviction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNTIME_SESSION_CACHE_HALF_LIFE_SECONDS", "60")
    monkeypatch.setenv("RUNTIME_SESSION_CACHE_MAX_SESSIONS", "2")
    cache = SessionSearchCache()
    stale_updated_at = (
        datetime.now(timezone.utc) - timedelta(seconds=600)
    ).isoformat().replace("+00:00", "Z")

    await cache.record_hit(
        session_id="session-a",
        uri="core://session-a",
        memory_id=1,
        snippet="release checklist",
        updated_at=stale_updated_at,
    )
    await cache.record_hit(
        session_id="session-b",
        uri="core://session-b",
        memory_id=2,
        snippet="release checklist",
    )
    await cache.record_hit(
        session_id="session-c",
        uri="core://session-c",
        memory_id=3,
        snippet="release checklist",
    )

    assert await cache.search(session_id="session-a", query="release", limit=5) == []
    assert await cache.search(session_id="session-b", query="release", limit=5)
    assert await cache.search(session_id="session-c", query="release", limit=5)

    summary = await cache.summary()
    assert summary["session_count"] == 2
