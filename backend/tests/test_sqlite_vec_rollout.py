from pathlib import Path

import pytest

from db.sqlite_client import SQLiteClient


def _sqlite_url(db_path: Path) -> str:
    return f"sqlite+aiosqlite:///{db_path}"


@pytest.mark.asyncio
async def test_sqlite_vec_rollout_defaults_keep_legacy_engine(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_BACKEND", "hash")
    monkeypatch.setenv("RETRIEVAL_SQLITE_VEC_ENABLED", "false")
    monkeypatch.setenv("RETRIEVAL_VECTOR_ENGINE", "legacy")
    monkeypatch.setenv("RETRIEVAL_SQLITE_VEC_READ_RATIO", "0")

    client = SQLiteClient(_sqlite_url(tmp_path / "sqlite-vec-defaults.db"))
    await client.init_db()
    status_payload = await client.get_index_status()
    await client.close()

    capabilities = status_payload["capabilities"]
    assert capabilities["sqlite_vec_enabled"] is False
    assert capabilities["vector_engine_requested"] == "legacy"
    assert capabilities["vector_engine_effective"] == "legacy"
    assert capabilities["sqlite_vec_status"] == "disabled"
    assert capabilities["sqlite_vec_readiness"] == "hold"
    assert capabilities["sqlite_vec_read_ratio"] == 0


@pytest.mark.asyncio
async def test_sqlite_vec_rollout_enabled_without_extension_falls_back_to_legacy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_BACKEND", "hash")
    monkeypatch.setenv("RETRIEVAL_SQLITE_VEC_ENABLED", "true")
    monkeypatch.setenv("RETRIEVAL_VECTOR_ENGINE", "vec")
    monkeypatch.setenv("RETRIEVAL_SQLITE_VEC_READ_RATIO", "100")
    monkeypatch.delenv("RETRIEVAL_SQLITE_VEC_EXTENSION_PATH", raising=False)

    client = SQLiteClient(_sqlite_url(tmp_path / "sqlite-vec-no-extension.db"))
    await client.init_db()
    await client.create_memory(
        parent_path="",
        content="sqlite vec fallback legacy sample",
        priority=1,
        title="sqlite_vec_fallback",
        domain="core",
    )

    status_payload = await client.get_index_status()
    search_payload = await client.search_advanced(
        query="sqlite vec fallback",
        mode="semantic",
        max_results=5,
        candidate_multiplier=2,
        filters={},
    )
    await client.close()

    capabilities = status_payload["capabilities"]
    assert capabilities["sqlite_vec_enabled"] is True
    assert capabilities["vector_engine_requested"] == "vec"
    assert capabilities["vector_engine_effective"] == "legacy"
    assert capabilities["sqlite_vec_status"] == "skipped_no_extension_path"
    assert capabilities["sqlite_vec_diag_code"] == "path_not_provided"
    assert "sqlite_vec_fallback_legacy" in search_payload.get("degrade_reasons", [])
    assert search_payload["results"]
    assert (
        search_payload["metadata"]["vector_engine_selected"] == "legacy"
    )


@pytest.mark.asyncio
async def test_sqlite_vec_rollout_ready_keeps_vec_selection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_BACKEND", "hash")
    monkeypatch.setenv("RETRIEVAL_SQLITE_VEC_ENABLED", "true")
    monkeypatch.setenv("RETRIEVAL_VECTOR_ENGINE", "vec")
    monkeypatch.setenv("RETRIEVAL_SQLITE_VEC_READ_RATIO", "100")
    monkeypatch.delenv("RETRIEVAL_SQLITE_VEC_EXTENSION_PATH", raising=False)

    client = SQLiteClient(_sqlite_url(tmp_path / "sqlite-vec-ready-selection.db"))
    await client.init_db()
    await client.create_memory(
        parent_path="",
        content="sqlite vec ready selection sample",
        priority=1,
        title="sqlite_vec_ready_selection",
        domain="core",
    )
    client._sqlite_vec_enabled = True
    client._vector_engine_requested = "vec"
    client._vector_engine_effective = "vec"
    client._sqlite_vec_capability = {
        **client._sqlite_vec_capability,
        "status": "ok",
        "sqlite_vec_readiness": "ready",
        "diag_code": "",
    }

    search_payload = await client.search_advanced(
        query="sqlite vec ready selection",
        mode="semantic",
        max_results=5,
        candidate_multiplier=2,
        filters={},
    )
    await client.close()

    assert search_payload["results"]
    assert search_payload["metadata"]["vector_engine_selected"] == "vec"
    assert "sqlite_vec_fallback_legacy" not in search_payload.get("degrade_reasons", [])


@pytest.mark.asyncio
async def test_sqlite_vec_rollout_invalid_extension_path_marks_hold(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_BACKEND", "hash")
    monkeypatch.setenv("RETRIEVAL_SQLITE_VEC_ENABLED", "true")
    monkeypatch.setenv("RETRIEVAL_VECTOR_ENGINE", "vec")
    monkeypatch.setenv("RETRIEVAL_SQLITE_VEC_EXTENSION_PATH", str(tmp_path / "missing_vec"))

    client = SQLiteClient(_sqlite_url(tmp_path / "sqlite-vec-invalid-path.db"))
    await client.init_db()
    status_payload = await client.get_index_status()
    await client.close()

    capabilities = status_payload["capabilities"]
    assert capabilities["vector_engine_effective"] == "legacy"
    assert capabilities["sqlite_vec_status"] == "invalid_extension_path"
    assert capabilities["sqlite_vec_diag_code"] == "path_not_found"
    assert capabilities["sqlite_vec_readiness"] == "hold"


@pytest.mark.asyncio
async def test_sqlite_vec_rollout_prefers_extension_file_over_same_name_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base = tmp_path / "sqlite_vec"
    base.mkdir()
    extension_file = tmp_path / "sqlite_vec.dylib"
    extension_file.write_bytes(b"not-a-real-extension")

    monkeypatch.setenv("RETRIEVAL_EMBEDDING_BACKEND", "hash")
    monkeypatch.setenv("RETRIEVAL_SQLITE_VEC_ENABLED", "true")
    monkeypatch.setenv("RETRIEVAL_VECTOR_ENGINE", "vec")
    monkeypatch.setenv("RETRIEVAL_SQLITE_VEC_EXTENSION_PATH", str(base))

    client = SQLiteClient(_sqlite_url(tmp_path / "sqlite-vec-prefer-file.db"))
    await client.init_db()
    status_payload = await client.get_index_status()
    await client.close()

    capabilities = status_payload["capabilities"]
    assert capabilities["sqlite_vec_status"] in {
        "ok",
        "extension_load_failed",
        "extension_loading_unavailable",
        "sqlite_runtime_error",
    }
    assert capabilities["sqlite_vec_diag_code"] != "path_not_file"


@pytest.mark.asyncio
async def test_sqlite_vec_rollout_directory_without_extension_reports_path_not_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base = tmp_path / "sqlite_vec"
    base.mkdir()

    monkeypatch.setenv("RETRIEVAL_EMBEDDING_BACKEND", "hash")
    monkeypatch.setenv("RETRIEVAL_SQLITE_VEC_ENABLED", "true")
    monkeypatch.setenv("RETRIEVAL_VECTOR_ENGINE", "vec")
    monkeypatch.setenv("RETRIEVAL_SQLITE_VEC_EXTENSION_PATH", str(base))

    client = SQLiteClient(_sqlite_url(tmp_path / "sqlite-vec-dir-only.db"))
    await client.init_db()
    status_payload = await client.get_index_status()
    await client.close()

    capabilities = status_payload["capabilities"]
    assert capabilities["sqlite_vec_status"] == "invalid_extension_path"
    assert capabilities["sqlite_vec_diag_code"] == "path_not_file"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw_ratio", "expected_ratio"),
    [
        ("180", 100),
        ("-9", 0),
    ],
)
async def test_sqlite_vec_rollout_read_ratio_is_clamped(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    raw_ratio: str,
    expected_ratio: int,
) -> None:
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_BACKEND", "hash")
    monkeypatch.setenv("RETRIEVAL_SQLITE_VEC_ENABLED", "true")
    monkeypatch.setenv("RETRIEVAL_VECTOR_ENGINE", "dual")
    monkeypatch.setenv("RETRIEVAL_SQLITE_VEC_READ_RATIO", raw_ratio)
    monkeypatch.delenv("RETRIEVAL_SQLITE_VEC_EXTENSION_PATH", raising=False)

    db_path = tmp_path / f"sqlite-vec-ratio-{raw_ratio}.db"
    client = SQLiteClient(_sqlite_url(db_path))
    await client.init_db()
    status_payload = await client.get_index_status()
    await client.close()

    assert status_payload["capabilities"]["sqlite_vec_read_ratio"] == expected_ratio
