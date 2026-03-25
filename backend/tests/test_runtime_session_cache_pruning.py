from datetime import datetime, timedelta, timezone

import pytest

from runtime_state import SessionSearchCache, _tokenize_query


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


@pytest.mark.asyncio
async def test_session_search_cache_accepts_naive_updated_at_strings_from_db() -> None:
    cache = SessionSearchCache()
    naive_recent_updated_at = (
        datetime.now(timezone.utc)
        .replace(tzinfo=None, microsecond=0)
        .isoformat()
    )

    await cache.record_hit(
        session_id="session-a",
        uri="core://naive-ts",
        memory_id=1,
        snippet="release checklist",
        updated_at=naive_recent_updated_at,
    )

    results = await cache.search(session_id="session-a", query="release", limit=5)

    assert [item["uri"] for item in results] == ["core://naive-ts"]


def test_tokenize_query_keeps_cjk_japanese_korean_and_normalizes_fullwidth() -> None:
    tokens = _tokenize_query("部署 デプロイ 배포 ＡＰＩ 错误")

    assert "部署" in tokens
    assert "デプロイ" in tokens
    assert "배포" in tokens
    assert "api" in tokens
    assert "错误" in tokens


@pytest.mark.asyncio
async def test_session_search_cache_matches_japanese_korean_and_fullwidth_queries() -> None:
    cache = SessionSearchCache()
    await cache.record_hit(
        session_id="session-a",
        uri="core://jp",
        memory_id=1,
        snippet="デプロイ ガイド",
    )
    await cache.record_hit(
        session_id="session-a",
        uri="core://kr",
        memory_id=2,
        snippet="배포 가이드",
    )
    await cache.record_hit(
        session_id="session-a",
        uri="core://api",
        memory_id=3,
        snippet="API 错误 修复记录",
    )

    jp_results = await cache.search(session_id="session-a", query="デプロイ", limit=5)
    kr_results = await cache.search(session_id="session-a", query="배포", limit=5)
    fw_results = await cache.search(session_id="session-a", query="ＡＰＩ 错误", limit=5)

    assert [item["uri"] for item in jp_results] == ["core://jp"]
    assert [item["uri"] for item in kr_results] == ["core://kr"]
    assert [item["uri"] for item in fw_results] == ["core://api"]
