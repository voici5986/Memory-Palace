import json
import os
import runpy
import sqlite3
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main


def _sqlite_url(path) -> str:
    return f"sqlite+aiosqlite:///{path}"


def test_load_project_dotenv_reads_repo_env_without_overriding_existing_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MAIN_BOOTSTRAP_TEST=from-dotenv\nMAIN_KEEP_EXISTING=from-dotenv\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("MAIN_BOOTSTRAP_TEST", raising=False)
    monkeypatch.setenv("MAIN_KEEP_EXISTING", "already-set")

    loaded = main._load_project_dotenv(tmp_path)

    assert loaded == env_file
    assert os.getenv("MAIN_BOOTSTRAP_TEST") == "from-dotenv"
    assert os.getenv("MAIN_KEEP_EXISTING") == "already-set"


def test_resolve_cors_uses_restricted_default_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    monkeypatch.delenv("CORS_ALLOW_CREDENTIALS", raising=False)

    origins, allow_credentials = main._resolve_cors_config()

    assert origins == list(main._DEFAULT_CORS_ALLOW_ORIGINS)
    assert allow_credentials is True


def test_resolve_cors_disables_credentials_for_wildcard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "*")
    monkeypatch.setenv("CORS_ALLOW_CREDENTIALS", "true")

    origins, allow_credentials = main._resolve_cors_config()

    assert origins == ["*"]
    assert allow_credentials is False


def test_resolve_cors_keeps_credentials_for_explicit_origins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:5173,https://example.com",
    )
    monkeypatch.setenv("CORS_ALLOW_CREDENTIALS", "true")

    origins, allow_credentials = main._resolve_cors_config()

    assert origins == ["http://localhost:5173", "https://example.com"]
    assert allow_credentials is True


def test_try_restore_legacy_sqlite_file_restores_valid_regular_file(tmp_path) -> None:
    legacy_path = tmp_path / "agent_memory.db"
    target_path = tmp_path / "memory_palace.db"
    with sqlite3.connect(legacy_path) as conn:
        conn.execute(
            "CREATE TABLE memories (id INTEGER PRIMARY KEY, title TEXT NOT NULL)"
        )
        conn.execute("INSERT INTO memories(title) VALUES ('ok')")

    main._try_restore_legacy_sqlite_file(_sqlite_url(target_path))

    assert target_path.exists()
    with sqlite3.connect(target_path) as conn:
        value = conn.execute("SELECT title FROM memories").fetchone()
    assert value == ("ok",)


def test_try_restore_legacy_sqlite_file_skips_symlink_candidate(tmp_path) -> None:
    real_db_path = tmp_path / "real_source.db"
    with sqlite3.connect(real_db_path) as conn:
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")

    symlink_path = tmp_path / "agent_memory.db"
    try:
        symlink_path.symlink_to(real_db_path)
    except OSError as exc:
        pytest.skip(f"Symlink unsupported in current environment: {exc}")

    target_path = tmp_path / "memory_palace.db"
    main._try_restore_legacy_sqlite_file(_sqlite_url(target_path))

    assert not target_path.exists()


def test_try_restore_legacy_sqlite_file_skips_invalid_sqlite_file(tmp_path) -> None:
    legacy_path = tmp_path / "agent_memory.db"
    legacy_path.write_text("not-a-sqlite-database", encoding="utf-8")
    target_path = tmp_path / "memory_palace.db"

    main._try_restore_legacy_sqlite_file(_sqlite_url(target_path))

    assert not target_path.exists()


def test_try_restore_legacy_sqlite_file_skips_sqlite_without_expected_schema(
    tmp_path,
) -> None:
    legacy_path = tmp_path / "agent_memory.db"
    with sqlite3.connect(legacy_path) as conn:
        conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO test_table(value) VALUES ('ok')")
    target_path = tmp_path / "memory_palace.db"

    main._try_restore_legacy_sqlite_file(_sqlite_url(target_path))

    assert not target_path.exists()


def test_extract_sqlite_file_path_skips_memory_targets_and_query_string() -> None:
    relative = main._extract_sqlite_file_path(
        "sqlite+aiosqlite:///relative.db?cache=shared"
    )
    absolute = main._extract_sqlite_file_path(
        "sqlite+aiosqlite:////tmp/demo.db?mode=rwc"
    )
    memory_target = main._extract_sqlite_file_path("sqlite+aiosqlite:///:memory:")
    shared_memory_target = main._extract_sqlite_file_path(
        "sqlite+aiosqlite:///file::memory:?cache=shared"
    )

    assert relative == Path("relative.db")
    assert absolute == Path("/tmp/demo.db")
    assert memory_target is None
    assert shared_memory_target is None


def test_try_restore_legacy_sqlite_file_skips_memory_database_urls(tmp_path) -> None:
    legacy_path = tmp_path / "agent_memory.db"
    with sqlite3.connect(legacy_path) as conn:
        conn.execute(
            "CREATE TABLE memories (id INTEGER PRIMARY KEY, title TEXT NOT NULL)"
        )
        conn.execute("INSERT INTO memories(title) VALUES ('ok')")

    main._try_restore_legacy_sqlite_file("sqlite+aiosqlite:///:memory:")
    main._try_restore_legacy_sqlite_file(
        "sqlite+aiosqlite:///file::memory:?cache=shared"
    )

    assert not Path(":memory:").exists()
    assert not Path("file::memory:").exists()


@pytest.mark.asyncio
async def test_health_hides_internal_exception_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom():
        raise RuntimeError("boom-secret-detail")

    monkeypatch.setattr(main, "get_sqlite_client", _boom)

    payload = await main.health()
    serialized = json.dumps(payload, ensure_ascii=False)

    assert payload["status"] == "degraded"
    assert payload["index"]["reason"] == "internal_error"
    assert payload["index"]["error_type"] == "RuntimeError"
    assert payload["runtime"]["write_lanes"]["reason"] == "internal_error"
    assert payload["runtime"]["index_worker"]["reason"] == "internal_error"
    assert "boom-secret-detail" not in serialized


def test_health_endpoint_returns_shallow_payload_without_loopback_or_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _StartupClient:
        async def init_db(self) -> None:
            return None

    async def _noop_ensure_started(_factory=None) -> None:
        return None

    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.setattr(main, "get_sqlite_client", lambda: _StartupClient())
    monkeypatch.setattr(main.runtime_state, "ensure_started", _noop_ensure_started)

    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "timestamp": response.json()["timestamp"],
    }


def test_health_endpoint_keeps_detailed_payload_when_api_key_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeClient:
        async def init_db(self) -> None:
            return None

        async def get_index_status(self):
            return {"index_available": True, "degraded": False}

    async def _noop_ensure_started(_factory=None) -> None:
        return None

    async def _lane_status():
        return {"pending": 0}

    async def _worker_status():
        return {"running": True}

    monkeypatch.setenv("MCP_API_KEY", "health-secret")
    monkeypatch.setattr(main, "get_sqlite_client", lambda: _FakeClient())
    monkeypatch.setattr(main.runtime_state, "ensure_started", _noop_ensure_started)
    monkeypatch.setattr(main.runtime_state.write_lanes, "status", _lane_status)
    monkeypatch.setattr(main.runtime_state.index_worker, "status", _worker_status)

    with TestClient(main.app) as client:
        response = client.get("/health", headers={"X-MCP-API-Key": "health-secret"})

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["index"]["index_available"] is True
    assert payload["runtime"]["write_lanes"] == {"pending": 0}
    assert payload["runtime"]["index_worker"] == {"running": True}


def test_main_script_binds_loopback_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, int]] = []
    fake_uvicorn = types.SimpleNamespace(
        run=lambda app, host, port: calls.append((host, port))
    )

    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)

    runpy.run_module("main", run_name="__main__")

    assert calls == [("127.0.0.1", 8000)]


def test_mount_embedded_sse_apps_is_lazy_and_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mounted_paths: list[str] = []

    class _FakeState:
        pass

    class _FakeApp:
        def __init__(self) -> None:
            self.state = _FakeState()

        def mount(self, path: str, _app) -> None:
            mounted_paths.append(path)

    monkeypatch.setattr(
        main,
        "create_embedded_sse_apps",
        lambda: ({"stream": True}, {"message": True}),
    )

    app = _FakeApp()
    main._mount_embedded_sse_apps(app)
    main._mount_embedded_sse_apps(app)

    assert mounted_paths == ["/sse/messages", "/messages", "/sse"]
    assert app.state.embedded_sse_mounted is True
