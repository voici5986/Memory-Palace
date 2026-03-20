import hashlib
import json
from pathlib import Path

import httpx
import pytest

import db.sqlite_client as sqlite_client_module
from db.sqlite_client import EmbeddingCache, SQLiteClient


def _sqlite_url(db_path: Path) -> str:
    return f"sqlite+aiosqlite:///{db_path}"


def _clear_embedding_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "RETRIEVAL_EMBEDDING_API_BASE",
        "RETRIEVAL_EMBEDDING_BASE",
        "ROUTER_API_BASE",
        "OPENAI_BASE_URL",
        "OPENAI_API_BASE",
        "RETRIEVAL_EMBEDDING_API_KEY",
        "RETRIEVAL_EMBEDDING_KEY",
        "ROUTER_API_KEY",
        "OPENAI_API_KEY",
        "RETRIEVAL_EMBEDDING_MODEL",
        "ROUTER_EMBEDDING_MODEL",
        "OPENAI_EMBEDDING_MODEL",
        "RETRIEVAL_EMBEDDING_DIM",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.asyncio
async def test_embedding_provider_chain_disabled_keeps_legacy_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_embedding_env(monkeypatch)
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_BACKEND", "api")
    monkeypatch.setenv("EMBEDDING_PROVIDER_CHAIN_ENABLED", "false")

    client = SQLiteClient(_sqlite_url(tmp_path / "provider-chain-disabled.db"))
    await client.init_db()

    degrade_reasons: list[str] = []
    async with client.session() as session:
        embedding = await client._get_embedding(
            session,
            "provider chain disabled fallback sample",
            degrade_reasons=degrade_reasons,
        )
    await client.close()

    assert len(embedding) == client._embedding_dim
    assert "embedding_config_missing" in degrade_reasons
    assert "embedding_fallback_hash" in degrade_reasons


@pytest.mark.asyncio
async def test_embedding_provider_chain_uses_configured_fallback_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_embedding_env(monkeypatch)
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_BACKEND", "router")
    monkeypatch.setenv("EMBEDDING_PROVIDER_CHAIN_ENABLED", "true")
    monkeypatch.setenv("EMBEDDING_PROVIDER_FAIL_OPEN", "false")
    monkeypatch.setenv("EMBEDDING_PROVIDER_FALLBACK", "api")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_API_BASE", "https://embedding.example/v1")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_MODEL", "chain-model")

    client = SQLiteClient(_sqlite_url(tmp_path / "provider-chain-fallback-api.db"))
    await client.init_db()

    call_meta: dict[str, str] = {"base": "", "endpoint": "", "api_key": ""}

    async def _fake_post_json(base: str, endpoint: str, payload, api_key: str = ""):
        call_meta["base"] = base
        call_meta["endpoint"] = endpoint
        call_meta["api_key"] = api_key
        assert payload["model"] == "chain-model"
        assert payload["dimensions"] == client._embedding_dim
        return {"data": [{"embedding": [0.11, 0.22, 0.33]}]}

    monkeypatch.setattr(client, "_post_json", _fake_post_json)
    degrade_reasons: list[str] = []
    async with client.session() as session:
        embedding = await client._get_embedding(
            session,
            "provider chain fallback provider sample",
            degrade_reasons=degrade_reasons,
        )
    await client.close()

    assert embedding == [0.11, 0.22, 0.33]
    assert call_meta["base"] == "https://embedding.example/v1"
    assert call_meta["endpoint"] == "/embeddings"
    assert call_meta["api_key"] == "test-key"
    assert "embedding_fallback_hash" not in degrade_reasons


@pytest.mark.asyncio
async def test_post_json_retries_embedding_without_dimensions_when_provider_rejects_them(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_BACKEND", "api")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_API_BASE", "https://embedding.example/v1")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_MODEL", "retry-model")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_DIM", "1024")

    client = SQLiteClient(_sqlite_url(tmp_path / "embedding-dim-retry.db"))
    await client.init_db()

    calls: list[dict[str, object]] = []

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json=None, headers=None):
            calls.append(dict(json or {}))
            request = httpx.Request("POST", url)
            if len(calls) == 1:
                return httpx.Response(
                    400,
                    json={"error": {"message": "unsupported field: dimensions"}},
                    request=request,
                )
            return httpx.Response(
                200,
                json={"data": [{"embedding": [0.5] * 1024}]},
                request=request,
            )

    monkeypatch.setattr(sqlite_client_module.httpx, "AsyncClient", _FakeAsyncClient)

    degrade_reasons: list[str] = []
    embedding = await client._fetch_remote_embedding(
        "embedding dimensions retry sample",
        degrade_reasons=degrade_reasons,
    )
    await client.close()

    assert len(calls) == 2
    assert calls[0]["dimensions"] == 1024
    assert "dimensions" not in calls[1]
    assert embedding == [0.5] * 1024
    assert degrade_reasons == []


@pytest.mark.asyncio
async def test_embedding_provider_chain_fail_closed_when_fallback_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_BACKEND", "api")
    monkeypatch.setenv("EMBEDDING_PROVIDER_CHAIN_ENABLED", "true")
    monkeypatch.setenv("EMBEDDING_PROVIDER_FAIL_OPEN", "false")
    monkeypatch.setenv("EMBEDDING_PROVIDER_FALLBACK", "none")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_API_BASE", "https://embedding.example/v1")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_MODEL", "chain-model")

    client = SQLiteClient(_sqlite_url(tmp_path / "provider-chain-fail-closed.db"))
    await client.init_db()

    async def _always_fail(*_args, **_kwargs):
        return None

    monkeypatch.setattr(client, "_post_json", _always_fail)
    degrade_reasons: list[str] = []
    async with client.session() as session:
        with pytest.raises(RuntimeError, match="embedding_provider_chain_blocked"):
            await client._get_embedding(
                session,
                "provider chain fail closed sample",
                degrade_reasons=degrade_reasons,
            )
    await client.close()

    assert "embedding_provider_chain_blocked" in degrade_reasons


@pytest.mark.asyncio
async def test_embedding_provider_chain_fail_open_still_hash_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_BACKEND", "api")
    monkeypatch.setenv("EMBEDDING_PROVIDER_CHAIN_ENABLED", "true")
    monkeypatch.setenv("EMBEDDING_PROVIDER_FAIL_OPEN", "true")
    monkeypatch.setenv("EMBEDDING_PROVIDER_FALLBACK", "none")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_API_BASE", "https://embedding.example/v1")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_MODEL", "chain-model")

    client = SQLiteClient(_sqlite_url(tmp_path / "provider-chain-fail-open.db"))
    await client.init_db()

    async def _always_fail(*_args, **_kwargs):
        return None

    monkeypatch.setattr(client, "_post_json", _always_fail)
    degrade_reasons: list[str] = []
    async with client.session() as session:
        embedding = await client._get_embedding(
            session,
            "provider chain fail open hash fallback sample",
            degrade_reasons=degrade_reasons,
        )
    await client.close()

    assert len(embedding) == client._embedding_dim
    assert "embedding_fallback_hash" in degrade_reasons


@pytest.mark.asyncio
async def test_embedding_provider_chain_cache_hit_avoids_second_remote_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_BACKEND", "api")
    monkeypatch.setenv("EMBEDDING_PROVIDER_CHAIN_ENABLED", "true")
    monkeypatch.setenv("EMBEDDING_PROVIDER_FAIL_OPEN", "false")
    monkeypatch.setenv("EMBEDDING_PROVIDER_FALLBACK", "hash")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_API_BASE", "https://embedding.example/v1")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_MODEL", "cache-model")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_DIM", "16")

    client = SQLiteClient(_sqlite_url(tmp_path / "provider-chain-cache.db"))
    await client.init_db()

    call_counter = {"value": 0}

    async def _fake_post_json(*_args, **_kwargs):
        call_counter["value"] += 1
        return {"data": [{"embedding": [0.5] * 16}]}

    monkeypatch.setattr(client, "_post_json", _fake_post_json)
    async with client.session() as session:
        first = await client._get_embedding(session, "provider chain cache sample")
        await session.flush()
        second = await client._get_embedding(session, "provider chain cache sample")
    await client.close()

    assert first == [0.5] * 16
    assert second == [0.5] * 16
    assert call_counter["value"] == 1


@pytest.mark.asyncio
async def test_embedding_provider_chain_refreshes_stale_cached_embedding_dimension(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_embedding_env(monkeypatch)
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_BACKEND", "hash")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_DIM", "64")

    client = SQLiteClient(_sqlite_url(tmp_path / "provider-chain-cache-dim.db"))
    await client.init_db()

    async with client.session() as session:
        first = await client._get_embedding(session, "provider chain cache dim sample")
        await session.flush()

        client._embedding_dim = 1024
        normalized = "provider chain cache dim sample"
        text_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        cache_key = (
            f"{client._embedding_backend}:{client._embedding_model}:"
            f"{client._embedding_dim}:{text_hash}"
        )
        session.add(
            EmbeddingCache(
                cache_key=cache_key,
                text_hash=text_hash,
                model=client._embedding_model,
                embedding=json.dumps(first),
            )
        )
        await session.flush()
        degrade_reasons: list[str] = []
        refreshed = await client._get_embedding(
            session,
            normalized,
            degrade_reasons=degrade_reasons,
        )

    await client.close()

    assert len(first) == 64
    assert len(refreshed) == 1024
    assert "embedding_cache_dim_mismatch" in degrade_reasons
    assert "embedding_cache_dim_mismatch:64!=1024" in degrade_reasons


@pytest.mark.asyncio
async def test_embedding_cache_key_includes_dimension(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_BACKEND", "api")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_API_BASE", "https://embedding.example/v1")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_MODEL", "cache-model")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_DIM", "16")

    db_path = tmp_path / "provider-chain-cache-dim.db"
    client64 = SQLiteClient(_sqlite_url(db_path))
    await client64.init_db()

    call_counter = {"value": 0}

    async def _fake_post_json_64(*_args, **_kwargs):
        call_counter["value"] += 1
        return {"data": [{"embedding": [0.64] * 16}]}

    monkeypatch.setattr(client64, "_post_json", _fake_post_json_64)
    async with client64.session() as session:
        first = await client64._get_embedding(session, "dimension-sensitive sample")
        await session.flush()
    await client64.close()

    monkeypatch.setenv("RETRIEVAL_EMBEDDING_DIM", "32")
    client1024 = SQLiteClient(_sqlite_url(db_path))
    await client1024.init_db()

    async def _fake_post_json_1024(*_args, **_kwargs):
        call_counter["value"] += 1
        return {"data": [{"embedding": [1.024] * 32}]}

    monkeypatch.setattr(client1024, "_post_json", _fake_post_json_1024)
    async with client1024.session() as session:
        second = await client1024._get_embedding(session, "dimension-sensitive sample")
    await client1024.close()

    assert first == [0.64] * 16
    assert second == [1.024] * 32
    assert call_counter["value"] == 2
