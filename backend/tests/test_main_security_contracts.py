import importlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main as main_module


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _reload_main_module():
    return importlib.reload(main_module)


def _read_cors_kwargs(module):
    for middleware in module.app.user_middleware:
        if middleware.cls.__name__ == "CORSMiddleware":
            return dict(middleware.kwargs)
    raise AssertionError("CORS middleware not configured")


def test_cors_defaults_use_restricted_local_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    monkeypatch.delenv("CORS_ALLOW_CREDENTIALS", raising=False)

    module = _reload_main_module()
    cors_kwargs = _read_cors_kwargs(module)

    assert cors_kwargs["allow_origins"] == list(module._DEFAULT_CORS_ALLOW_ORIGINS)
    assert cors_kwargs["allow_credentials"] is True


def test_cors_allows_credentials_with_explicit_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://a.example, https://b.example")
    monkeypatch.setenv("CORS_ALLOW_CREDENTIALS", "true")

    module = _reload_main_module()
    cors_kwargs = _read_cors_kwargs(module)

    assert cors_kwargs["allow_origins"] == ["https://a.example", "https://b.example"]
    assert cors_kwargs["allow_credentials"] is True


def test_cors_disables_credentials_for_explicit_wildcard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "*")
    monkeypatch.setenv("CORS_ALLOW_CREDENTIALS", "true")

    module = _reload_main_module()
    cors_kwargs = _read_cors_kwargs(module)

    assert cors_kwargs["allow_origins"] == ["*"]
    assert cors_kwargs["allow_credentials"] is False


@pytest.mark.asyncio
async def test_health_hides_internal_exception_details(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _reload_main_module()

    def _raise_client_error():
        raise RuntimeError("secret_token_should_not_leak")

    monkeypatch.setattr(module, "get_sqlite_client", _raise_client_error)
    payload = await module.health()

    assert payload["status"] == "degraded"
    assert payload["index"]["reason"] == "internal_error"
    assert payload["runtime"]["write_lanes"]["reason"] == "internal_error"
    assert "secret_token_should_not_leak" not in json.dumps(payload)


def test_env_example_documents_sse_message_rate_limit_knobs() -> None:
    env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

    assert "SSE_MESSAGE_RATE_LIMIT_WINDOW_SECONDS=10" in env_example
    assert "SSE_MESSAGE_RATE_LIMIT_MAX_REQUESTS=120" in env_example
    assert "SSE_MESSAGE_MAX_BODY_BYTES=1048576" in env_example
    assert "SSE_MESSAGE_RATE_LIMIT_MAX_KEYS" not in env_example


def test_health_returns_shallow_payload_for_unauthenticated_remote_request() -> None:
    module = _reload_main_module()

    async def _noop_initialize_backend_runtime(*, ensure_runtime_started: bool = True) -> None:
        _ = ensure_runtime_started
        return None

    module.initialize_backend_runtime = _noop_initialize_backend_runtime

    with TestClient(
        module.app,
        client=("203.0.113.10", 50000),
        base_url="http://memory-palace.example",
    ) as client:
        response = client.get("/health", headers={"Host": "memory-palace.example"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "timestamp" in payload
    assert "index" not in payload
    assert "runtime" not in payload


def test_health_returns_detailed_payload_for_authenticated_remote_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_API_KEY", "health-secret")
    module = _reload_main_module()

    async def _noop_initialize_backend_runtime(*, ensure_runtime_started: bool = True) -> None:
        _ = ensure_runtime_started
        return None

    class _FakeClient:
        async def get_index_status(self):
            return {"index_available": True, "degraded": False}

    async def _lane_status():
        return {"pending": 0}

    async def _worker_status():
        return {"running": True}

    module.initialize_backend_runtime = _noop_initialize_backend_runtime
    monkeypatch.setattr(module, "get_sqlite_client", lambda: _FakeClient())
    monkeypatch.setattr(module.runtime_state.write_lanes, "status", _lane_status)
    monkeypatch.setattr(module.runtime_state.index_worker, "status", _worker_status)

    with TestClient(
        module.app,
        client=("203.0.113.10", 50000),
        base_url="http://memory-palace.example",
    ) as client:
        response = client.get(
            "/health",
            headers={
                "Host": "memory-palace.example",
                "X-MCP-API-Key": "health-secret",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert "index" in payload
    assert "runtime" in payload
