from pathlib import Path

import run_sse
from starlette.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_sse_main_falls_back_to_8010_when_loopback_8000_is_busy(monkeypatch) -> None:
    call_order = []

    def _fake_create_sse_app(**kwargs):
        call_order.append(("create_sse_app", kwargs))
        return {"app": "fake"}

    def _fake_uvicorn_run(app, host, port):
        call_order.append(("uvicorn", host, port, app))

    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setattr(run_sse, "create_sse_app", _fake_create_sse_app)
    monkeypatch.setattr(run_sse.uvicorn, "run", _fake_uvicorn_run)
    monkeypatch.setattr(run_sse, "_is_loopback_port_available", lambda port: port != 8000)

    run_sse.main()

    assert call_order[0] == ("create_sse_app", {"initialize_runtime_on_startup": True})
    assert call_order[1][0] == "uvicorn"
    assert call_order[1][1] == "127.0.0.1"
    assert call_order[1][2] == 8010


def test_sse_app_lifespan_initializes_runtime_when_enabled(monkeypatch) -> None:
    call_order = []

    async def _fake_initialize_runtime(*, ensure_runtime_started: bool = True) -> None:
        call_order.append(("startup", ensure_runtime_started))

    async def _fake_drain_pending_flush_summaries(*, reason: str) -> None:
        call_order.append(("drain", reason))

    async def _fake_shutdown() -> None:
        call_order.append(("shutdown", "runtime"))

    async def _fake_close_sqlite_client() -> None:
        call_order.append(("shutdown", "db"))

    monkeypatch.setattr(run_sse, "initialize_backend_runtime", _fake_initialize_runtime)
    monkeypatch.setattr(run_sse, "drain_pending_flush_summaries", _fake_drain_pending_flush_summaries)
    monkeypatch.setattr(run_sse.runtime_state, "shutdown", _fake_shutdown)
    monkeypatch.setattr(run_sse, "close_sqlite_client", _fake_close_sqlite_client)

    app = run_sse.create_sse_app(initialize_runtime_on_startup=True)

    with TestClient(app):
        assert call_order[0] == ("startup", True)

    assert ("drain", "runtime.shutdown") in call_order
    assert ("shutdown", "runtime") in call_order
    assert ("shutdown", "db") in call_order


def test_compose_pins_sse_internal_port_to_proxy_contract() -> None:
    compose_text = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    backend_block = compose_text.split("\n  backend:\n", 1)[1].split("\n  frontend:\n", 1)[0]
    frontend_block = compose_text.split("\n  frontend:\n", 1)[1]

    assert "\n  sse:\n" not in compose_text
    assert "HOST: 0.0.0.0" in backend_block
    assert "RUNTIME_WRITE_WAL_ENABLED: ${MEMORY_PALACE_DOCKER_WAL_ENABLED:-true}" in backend_block
    assert "backend:\n        condition: service_healthy" in frontend_block


def test_pull_based_ghcr_compose_matches_backend_frontend_proxy_topology() -> None:
    compose_text = (PROJECT_ROOT / "docker-compose.ghcr.yml").read_text(encoding="utf-8")
    backend_block = compose_text.split("\n  backend:\n", 1)[1].split("\n  frontend:\n", 1)[0]
    frontend_block = compose_text.split("\n  frontend:\n", 1)[1]

    assert "\n  sse:\n" not in compose_text
    assert "http://127.0.0.1:8000/health" in backend_block
    assert "RUNTIME_WRITE_WAL_ENABLED: ${MEMORY_PALACE_DOCKER_WAL_ENABLED:-true}" in backend_block
    assert "backend:\n        condition: service_healthy" in frontend_block


def test_frontend_nginx_template_targets_repo_managed_sse_port() -> None:
    template_text = (
        PROJECT_ROOT / "deploy" / "docker" / "nginx.conf.template"
    ).read_text(encoding="utf-8")

    assert "proxy_pass http://backend:8000/sse/;" in template_text
    assert template_text.count("proxy_pass http://backend:8000;") == 2
    assert "location = /sse/ {" in template_text
    assert "return 307 /sse;" in template_text


def test_frontend_entrypoint_escapes_dollar_signs_in_api_key() -> None:
    script_text = (
        PROJECT_ROOT / "deploy" / "docker" / "frontend-entrypoint.sh"
    ).read_text(encoding="utf-8")

    assert "sed 's/[\\\\\\\"$]/\\\\&/g'" in script_text
    assert "carriage_return=\"$(printf '\\r')\"" in script_text
    assert "MCP_API_KEY contains unsupported control characters." in script_text
