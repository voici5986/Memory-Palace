from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time

import pytest
from sqlalchemy import text

import db.sqlite_client as sqlite_client_module
from db.sqlite_client import Memory, SQLiteClient


def _sqlite_url(db_path: Path) -> str:
    return f"sqlite+aiosqlite:///{db_path}"


@pytest.fixture(autouse=True)
def _force_local_retrieval_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_BACKEND", "hash")
    monkeypatch.setenv("RETRIEVAL_RERANKER_ENABLED", "false")


@pytest.mark.asyncio
async def test_get_index_status_does_not_persist_missing_fts_state(
    tmp_path: Path,
) -> None:
    client = SQLiteClient(_sqlite_url(tmp_path / "fts-status-regression.db"))
    await client.init_db()

    if not client._fts_available:
        await client.close()
        pytest.skip("SQLite FTS5 not available in this environment")

    async with client.session() as session:
        await session.execute(text("DROP TABLE IF EXISTS memory_chunks_fts"))

    missing_status = await client.get_index_status()
    assert missing_status["capabilities"]["fts_available"] is False
    assert client._fts_available is True

    async with client.session() as session:
        await session.execute(
            text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS memory_chunks_fts "
                "USING fts5(chunk_id UNINDEXED, memory_id UNINDEXED, chunk_text)"
            )
        )

    restored_status = await client.get_index_status()
    await client.close()

    assert restored_status["capabilities"]["fts_available"] is True


@pytest.mark.asyncio
async def test_resolve_migration_chain_supports_long_noncyclic_chains(
    tmp_path: Path,
) -> None:
    client = SQLiteClient(_sqlite_url(tmp_path / "migration-chain-regression.db"))
    await client.init_db()

    async with client.session() as session:
        chain = [Memory(content=f"version-{idx}", deprecated=(idx < 59)) for idx in range(60)]
        session.add_all(chain)
        await session.flush()

        for idx, memory in enumerate(chain[:-1]):
            memory.migrated_to = chain[idx + 1].id
            session.add(memory)

        resolved = await client._resolve_migration_chain(session, chain[0].id)

    await client.close()

    assert resolved is not None
    assert resolved["id"] == chain[-1].id


@pytest.mark.asyncio
async def test_legacy_search_forwards_requested_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = SQLiteClient(_sqlite_url(tmp_path / "legacy-search-mode.db"))
    await client.init_db()

    captured: dict[str, object] = {}

    async def _fake_search_advanced(**kwargs):
        captured.update(kwargs)
        return {"results": []}

    monkeypatch.setattr(client, "search_advanced", _fake_search_advanced)

    await client.search("legacy mode sample", limit=3, domain="core", mode="hybrid")
    await client.close()

    assert captured["mode"] == "hybrid"
    assert captured["filters"] == {"domain": "core"}
    assert captured["max_results"] == 3


@pytest.mark.asyncio
async def test_permanently_delete_memory_rejects_referenced_orphan_chain_tail(
    tmp_path: Path,
) -> None:
    client = SQLiteClient(_sqlite_url(tmp_path / "chain-tail-guard.db"))
    await client.init_db()

    await client.create_memory(
        parent_path="",
        content="version-1",
        priority=1,
        title="chain_tail_guard",
        domain="core",
    )
    await client.update_memory(path="chain_tail_guard", content="version-2", domain="core")
    second = await client.update_memory(
        path="chain_tail_guard",
        content="version-3",
        domain="core",
    )
    tail_id = int(second["new_memory_id"])

    await client.remove_path(path="chain_tail_guard", domain="core")

    with pytest.raises(PermissionError, match="final target"):
        await client.permanently_delete_memory(tail_id, require_orphan=True)

    async with client.session() as session:
        still_exists = await session.get(Memory, tail_id)

    await client.close()

    assert still_exists is not None


def test_get_sqlite_client_initializes_singleton_once_under_thread_race(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_urls: list[str] = []
    original_client = sqlite_client_module._sqlite_client
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:////tmp/threadsafe-singleton.db")

    class _FakeClient:
        def __init__(self, database_url: str) -> None:
            created_urls.append(database_url)
            time.sleep(0.02)
            self.database_url = database_url

        async def close(self) -> None:
            return None

    monkeypatch.setattr(sqlite_client_module, "SQLiteClient", _FakeClient)
    sqlite_client_module._sqlite_client = None

    def _resolve_client():
        return sqlite_client_module.get_sqlite_client()

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            clients = list(pool.map(lambda _: _resolve_client(), range(8)))
    finally:
        sqlite_client_module._sqlite_client = original_client

    assert len(created_urls) == 1
    assert len({id(client) for client in clients}) == 1


def test_parse_iso_datetime_normalizes_timezone_offsets_to_utc_naive() -> None:
    parsed = SQLiteClient._parse_iso_datetime("2026-03-21T16:30:00+08:00")

    assert parsed == sqlite_client_module.datetime(2026, 3, 21, 8, 30, 0)
    assert parsed.tzinfo is None


def test_mmr_tokens_keep_cjk_chunks_and_bigrams() -> None:
    tokens = SQLiteClient._mmr_tokens(
        {
            "snippet": "部署 deployment guide",
            "metadata": {"path": "部署/指南"},
        }
    )

    assert "deployment" in tokens
    assert "guide" in tokens
    assert "部署" in tokens
    assert "部" not in tokens


def test_jaccard_similarity_detects_overlap_for_pure_cjk_results() -> None:
    first = SQLiteClient._mmr_tokens(
        {
            "snippet": "部署指南",
            "metadata": {"path": "部署/手册"},
        }
    )
    second = SQLiteClient._mmr_tokens(
        {
            "snippet": "部署文档",
            "metadata": {"path": "部署/教程"},
        }
    )

    assert first
    assert second
    assert SQLiteClient._jaccard_similarity(first, second) > 0.0


def test_hash_embedding_keeps_cjk_tokens_in_mixed_text() -> None:
    client = SQLiteClient("sqlite+aiosqlite:///:memory:")

    mixed = client._hash_embedding("部署 deployment guide", dim=64)
    latin_only = client._hash_embedding("deployment guide", dim=64)
    pure_cjk = client._hash_embedding("部署 指南", dim=64)

    assert mixed != latin_only
    assert any(value != 0.0 for value in pure_cjk)


def test_hash_embedding_normalizes_fullwidth_latin_tokens() -> None:
    client = SQLiteClient("sqlite+aiosqlite:///:memory:")

    fullwidth = client._hash_embedding("ＡＰＩ 错误", dim=64)
    ascii_text = client._hash_embedding("API 错误", dim=64)
    tokens = SQLiteClient._mmr_tokens(
        {
            "snippet": "ＡＰＩ 错误 修复记录",
            "metadata": {"path": "api/错误"},
        }
    )

    assert fullwidth == ascii_text
    assert "api" in tokens


def test_apply_mmr_rerank_avoids_duplicate_pure_cjk_results() -> None:
    client = SQLiteClient("sqlite+aiosqlite:///:memory:")

    selected, metadata = client._apply_mmr_rerank(
        [
            {
                "uri": "core://a",
                "snippet": "部署指南",
                "metadata": {"path": "部署/指南"},
                "scores": {"final": 1.0},
            },
            {
                "uri": "core://b",
                "snippet": "部署指南",
                "metadata": {"path": "部署/指南-副本"},
                "scores": {"final": 0.99},
            },
            {
                "uri": "core://c",
                "snippet": "恢复手册",
                "metadata": {"path": "恢复/手册"},
                "scores": {"final": 0.95},
            },
        ],
        max_results=2,
    )

    assert metadata["mmr_applied"] is True
    assert [row["uri"] for row in selected] == ["core://a", "core://c"]
