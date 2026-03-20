from pathlib import Path

import run_sse


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_sse_main_falls_back_to_8010_when_loopback_8000_is_busy(monkeypatch) -> None:
    call_order = []

    async def _fake_startup() -> None:
        call_order.append("startup")

    def _fake_create_sse_app():
        call_order.append("create_sse_app")
        return {"app": "fake"}

    def _fake_uvicorn_run(app, host, port):
        call_order.append(("uvicorn", host, port, app))

    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setattr(run_sse, "mcp_startup", _fake_startup)
    monkeypatch.setattr(run_sse, "create_sse_app", _fake_create_sse_app)
    monkeypatch.setattr(run_sse.uvicorn, "run", _fake_uvicorn_run)
    monkeypatch.setattr(run_sse, "_is_loopback_port_available", lambda port: port != 8000)

    run_sse.main()

    assert call_order[0] == "startup"
    assert call_order[1] == "create_sse_app"
    assert call_order[2][0] == "uvicorn"
    assert call_order[2][1] == "127.0.0.1"
    assert call_order[2][2] == 8010


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
    assert "return 301 /sse;" in template_text


def test_frontend_entrypoint_escapes_dollar_signs_in_api_key() -> None:
    script_text = (
        PROJECT_ROOT / "deploy" / "docker" / "frontend-entrypoint.sh"
    ).read_text(encoding="utf-8")

    assert "sed 's/[\\\\\\\"$]/\\\\&/g'" in script_text
    assert "carriage_return=\"$(printf '\\r')\"" in script_text
    assert "MCP_API_KEY contains unsupported control characters." in script_text
