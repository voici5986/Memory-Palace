from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import setup as setup_api


def _build_client(*, client=("127.0.0.1", 50000)) -> TestClient:
    app = FastAPI()
    app.include_router(setup_api.router)
    return TestClient(app, client=client, base_url="http://127.0.0.1")


def test_setup_status_allows_loopback_without_api_key(monkeypatch, tmp_path: Path) -> None:
    env_example = tmp_path / ".env.example"
    env_example.write_text("MCP_API_KEY=\n", encoding="utf-8")
    target_env = tmp_path / ".env"

    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("MEMORY_PALACE_RUNNING_IN_DOCKER", raising=False)
    monkeypatch.setattr(setup_api, "_ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setenv("MEMORY_PALACE_SETUP_ENV_FILE", str(target_env))

    with _build_client() as client:
        response = client.get("/setup/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["apply_supported"] is True
    assert payload["target_label"] == ".env"
    assert payload["summary"]["dashboard_auth_configured"] is False


def test_setup_status_rejects_non_loopback_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("MEMORY_PALACE_RUNNING_IN_DOCKER", raising=False)

    with _build_client(client=("203.0.113.10", 50000)) as client:
        response = client.get("/setup/status")

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["error"] == "setup_access_denied"
    assert detail["reason"] == "local_loopback_or_api_key_required"


def test_setup_status_rejects_loopback_peer_when_host_header_is_not_loopback(
    monkeypatch,
) -> None:
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("MEMORY_PALACE_RUNNING_IN_DOCKER", raising=False)

    with _build_client(client=("127.0.0.1", 50000)) as client:
        response = client.get(
            "/setup/status",
            headers={"Host": "memory-palace.example"},
        )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["error"] == "setup_access_denied"
    assert detail["reason"] == "local_loopback_or_api_key_required"


def test_setup_status_allows_ipv6_loopback_without_api_key(
    monkeypatch, tmp_path: Path
) -> None:
    env_example = tmp_path / ".env.example"
    env_example.write_text("MCP_API_KEY=\n", encoding="utf-8")
    target_env = tmp_path / ".env"

    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("MEMORY_PALACE_RUNNING_IN_DOCKER", raising=False)
    monkeypatch.setattr(setup_api, "_ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setenv("MEMORY_PALACE_SETUP_ENV_FILE", str(target_env))

    with _build_client(client=("::1", 50000)) as client:
        response = client.get(
            "/setup/status",
            headers={"Host": "[::1]:8000"},
        )

    assert response.status_code == 200
    assert response.json()["apply_supported"] is True


def test_setup_status_accepts_authenticated_remote_request(monkeypatch, tmp_path: Path) -> None:
    env_example = tmp_path / ".env.example"
    env_example.write_text("MCP_API_KEY=\n", encoding="utf-8")
    target_env = tmp_path / ".env"

    monkeypatch.setenv("MCP_API_KEY", "setup-secret")
    monkeypatch.delenv("MEMORY_PALACE_RUNNING_IN_DOCKER", raising=False)
    monkeypatch.setattr(setup_api, "_ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setenv("MEMORY_PALACE_SETUP_ENV_FILE", str(target_env))

    with _build_client(client=("203.0.113.10", 50000)) as client:
        response = client.get(
            "/setup/status",
            headers={"X-MCP-API-Key": "setup-secret"},
        )

    assert response.status_code == 200


def test_setup_config_writes_seeded_env_and_refreshes_process_env(
    monkeypatch, tmp_path: Path
) -> None:
    env_example = tmp_path / ".env.example"
    env_example.write_text(
        "\n".join(
            [
                "MCP_API_KEY=",
                "MCP_API_KEY_ALLOW_INSECURE_LOCAL=false",
                "RETRIEVAL_EMBEDDING_BACKEND=hash",
                "RETRIEVAL_RERANKER_ENABLED=false",
                "WRITE_GUARD_LLM_ENABLED=false",
                "INTENT_LLM_ENABLED=false",
                "",
            ]
        ),
        encoding="utf-8",
    )
    target_env = tmp_path / ".env"

    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("MCP_API_KEY_ALLOW_INSECURE_LOCAL", raising=False)
    monkeypatch.delenv("MEMORY_PALACE_RUNNING_IN_DOCKER", raising=False)
    monkeypatch.setattr(setup_api, "_ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setenv("MEMORY_PALACE_SETUP_ENV_FILE", str(target_env))

    payload = {
        "dashboard_api_key": "local-secret",
        "allow_insecure_local": True,
        "embedding_backend": "api",
        "embedding_api_base": "http://127.0.0.1:9100/v1",
        "embedding_model": "embedding-model",
        "reranker_enabled": True,
        "reranker_api_base": "http://127.0.0.1:9200/v1",
        "reranker_model": "reranker-model",
        "write_guard_llm_enabled": True,
        "write_guard_llm_api_base": "http://127.0.0.1:9300/v1",
        "write_guard_llm_model": "guard-model",
        "intent_llm_enabled": True,
        "intent_llm_api_base": "http://127.0.0.1:9400/v1",
        "intent_llm_model": "intent-model",
    }

    with _build_client() as client:
        response = client.post("/setup/config", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["summary"]["dashboard_auth_configured"] is True
    assert body["summary"]["reranker_enabled"] is True
    assert body["summary"]["write_guard_enabled"] is True
    assert body["summary"]["intent_llm_enabled"] is True
    assert body["immediate_env_refresh"] == [
        "MCP_API_KEY",
        "MCP_API_KEY_ALLOW_INSECURE_LOCAL",
    ]

    written = target_env.read_text(encoding="utf-8")
    assert "MCP_API_KEY=local-secret" in written
    assert "MCP_API_KEY_ALLOW_INSECURE_LOCAL=true" in written
    assert "RETRIEVAL_EMBEDDING_BACKEND=api" in written
    assert "RETRIEVAL_EMBEDDING_API_BASE=http://127.0.0.1:9100/v1" in written
    assert "RETRIEVAL_RERANKER_ENABLED=true" in written
    assert "WRITE_GUARD_LLM_ENABLED=true" in written
    assert "INTENT_LLM_ENABLED=true" in written
    assert written.count("MCP_API_KEY=") == 1

    assert setup_api._get_configured_mcp_api_key() == "local-secret"
    assert setup_api._env_bool("MCP_API_KEY_ALLOW_INSECURE_LOCAL", False) is True


def test_setup_config_preserves_existing_secret_when_blank(monkeypatch, tmp_path: Path) -> None:
    env_example = tmp_path / ".env.example"
    env_example.write_text(
        "MCP_API_KEY=\nRETRIEVAL_EMBEDDING_BACKEND=hash\n",
        encoding="utf-8",
    )
    target_env = tmp_path / ".env"
    target_env.write_text(
        "MCP_API_KEY=existing-secret\nRETRIEVAL_EMBEDDING_BACKEND=hash\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("MCP_API_KEY", "existing-secret")
    monkeypatch.delenv("MEMORY_PALACE_RUNNING_IN_DOCKER", raising=False)
    monkeypatch.setattr(setup_api, "_ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setenv("MEMORY_PALACE_SETUP_ENV_FILE", str(target_env))

    with _build_client() as client:
        response = client.post(
            "/setup/config",
            json={
                "dashboard_api_key": "   ",
                "allow_insecure_local": False,
                "embedding_backend": "hash",
            },
        )

    assert response.status_code == 200
    written = target_env.read_text(encoding="utf-8")
    assert "MCP_API_KEY=existing-secret" in written
    assert written.count("MCP_API_KEY=") == 1


def test_setup_config_rejects_when_running_in_docker(monkeypatch, tmp_path: Path) -> None:
    env_example = tmp_path / ".env.example"
    env_example.write_text("MCP_API_KEY=\n", encoding="utf-8")
    target_env = tmp_path / ".env"

    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.setenv("MEMORY_PALACE_RUNNING_IN_DOCKER", "true")
    monkeypatch.setattr(setup_api, "_ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setenv("MEMORY_PALACE_SETUP_ENV_FILE", str(target_env))

    with _build_client() as client:
        response = client.post(
            "/setup/config",
            json={
                "dashboard_api_key": "local-secret",
                "allow_insecure_local": False,
                "embedding_backend": "hash",
            },
        )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error"] == "setup_apply_unsupported"
    assert detail["reason"] == "docker_runtime_not_persisted"


def test_setup_config_rejects_remote_write_even_with_valid_api_key(
    monkeypatch, tmp_path: Path
) -> None:
    env_example = tmp_path / ".env.example"
    env_example.write_text("MCP_API_KEY=\n", encoding="utf-8")
    target_env = tmp_path / ".env"

    monkeypatch.setenv("MCP_API_KEY", "setup-secret")
    monkeypatch.delenv("MEMORY_PALACE_RUNNING_IN_DOCKER", raising=False)
    monkeypatch.setattr(setup_api, "_ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setenv("MEMORY_PALACE_SETUP_ENV_FILE", str(target_env))

    with _build_client(client=("203.0.113.10", 50000)) as client:
        response = client.post(
            "/setup/config",
            headers={"X-MCP-API-Key": "setup-secret"},
            json={
                "dashboard_api_key": "remote-secret",
                "allow_insecure_local": False,
                "embedding_backend": "hash",
            },
        )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["error"] == "setup_access_denied"
    assert detail["reason"] == "local_loopback_required_for_write"


def test_setup_config_rejects_loopback_peer_when_host_header_is_not_loopback(
    monkeypatch, tmp_path: Path
) -> None:
    env_example = tmp_path / ".env.example"
    env_example.write_text("MCP_API_KEY=\n", encoding="utf-8")
    target_env = tmp_path / ".env"

    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("MEMORY_PALACE_RUNNING_IN_DOCKER", raising=False)
    monkeypatch.setattr(setup_api, "_ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setenv("MEMORY_PALACE_SETUP_ENV_FILE", str(target_env))

    with _build_client(client=("127.0.0.1", 50000)) as client:
        response = client.post(
            "/setup/config",
            headers={"Host": "memory-palace.example"},
            json={
                "dashboard_api_key": "proxy-bypass",
                "allow_insecure_local": False,
                "embedding_backend": "hash",
            },
        )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["error"] == "setup_access_denied"
    assert detail["reason"] == "local_loopback_or_api_key_required"
    assert not target_env.exists()


def test_setup_config_allows_ipv6_loopback_write_without_api_key(
    monkeypatch, tmp_path: Path
) -> None:
    env_example = tmp_path / ".env.example"
    env_example.write_text("MCP_API_KEY=\nRETRIEVAL_EMBEDDING_BACKEND=hash\n", encoding="utf-8")
    target_env = tmp_path / ".env"

    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("MEMORY_PALACE_RUNNING_IN_DOCKER", raising=False)
    monkeypatch.setattr(setup_api, "_ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setenv("MEMORY_PALACE_SETUP_ENV_FILE", str(target_env))

    with _build_client(client=("::1", 50000)) as client:
        response = client.post(
            "/setup/config",
            headers={"Host": "[::1]:8000"},
            json={
                "dashboard_api_key": "ipv6-secret",
                "allow_insecure_local": False,
                "embedding_backend": "hash",
            },
        )

    assert response.status_code == 200
    assert "MCP_API_KEY=ipv6-secret" in target_env.read_text(encoding="utf-8")
