import os
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
    assert payload["write_supported"] is True
    assert payload["write_reason"] == "local_env_file"
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
    payload = response.json()
    assert payload["apply_supported"] is True
    assert payload["write_supported"] is False
    assert payload["write_reason"] == "local_loopback_required_for_write"


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
    monkeypatch.delenv("RETRIEVAL_EMBEDDING_BACKEND", raising=False)
    monkeypatch.delenv("RETRIEVAL_EMBEDDING_DIM", raising=False)
    monkeypatch.setattr(setup_api, "_ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setenv("MEMORY_PALACE_SETUP_ENV_FILE", str(target_env))

    payload = {
        "dashboard_api_key": "local-secret",
        "allow_insecure_local": True,
        "embedding_backend": "api",
        "embedding_api_base": "http://127.0.0.1:9100/v1",
        "embedding_model": "local-embedding-model",
        "reranker_enabled": True,
        "reranker_api_base": "http://127.0.0.1:9200/v1",
        "reranker_model": "local-reranker-model",
        "write_guard_llm_enabled": True,
        "write_guard_llm_api_base": "http://127.0.0.1:9300/v1",
        "write_guard_llm_model": "local-guard-model",
        "intent_llm_enabled": True,
        "intent_llm_api_base": "http://127.0.0.1:9400/v1",
        "intent_llm_model": "local-intent-model",
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


def test_setup_status_refreshes_setup_managed_env_from_target_file_after_restart(
    monkeypatch, tmp_path: Path
) -> None:
    env_example = tmp_path / ".env.example"
    env_example.write_text("MCP_API_KEY=\n", encoding="utf-8")
    target_env = tmp_path / ".env"
    target_env.write_text(
        "\n".join(
            [
                "MCP_API_KEY=",
                "MCP_API_KEY_ALLOW_INSECURE_LOCAL=false",
                "RETRIEVAL_EMBEDDING_BACKEND=hash",
                "RETRIEVAL_EMBEDDING_DIM=64",
                "RETRIEVAL_RERANKER_ENABLED=false",
                "ROUTER_API_BASE=",
                "ROUTER_API_KEY=",
                "ROUTER_CHAT_MODEL=",
                "ROUTER_EMBEDDING_MODEL=",
                "ROUTER_RERANKER_MODEL=",
                "WRITE_GUARD_LLM_ENABLED=false",
                "WRITE_GUARD_LLM_API_BASE=",
                "WRITE_GUARD_LLM_API_KEY=",
                "WRITE_GUARD_LLM_MODEL=",
                "",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("RETRIEVAL_EMBEDDING_BACKEND", "router")
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_DIM", "1024")
    monkeypatch.setenv("ROUTER_API_BASE", "https://stale-router.example/v1")
    monkeypatch.setenv("ROUTER_EMBEDDING_MODEL", "stale-router-model")
    monkeypatch.setenv("WRITE_GUARD_LLM_ENABLED", "true")
    monkeypatch.setenv("WRITE_GUARD_LLM_API_BASE", "https://stale-guard.example/v1")
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("MEMORY_PALACE_RUNNING_IN_DOCKER", raising=False)
    monkeypatch.setattr(setup_api, "_ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setenv("MEMORY_PALACE_SETUP_ENV_FILE", str(target_env))

    with _build_client() as client:
        response = client.get("/setup/status")

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["embedding_backend"] == "hash"
    assert summary["embedding_dim"] == 64
    assert summary["router_configured"] is False
    assert summary["write_guard_enabled"] is False
    assert setup_api._read_optional_env("RETRIEVAL_EMBEDDING_BACKEND") == "hash"
    assert setup_api._read_optional_env("RETRIEVAL_EMBEDDING_DIM") == "64"
    assert os.getenv("ROUTER_API_BASE") is None
    assert os.getenv("ROUTER_EMBEDDING_MODEL") is None
    assert os.getenv("WRITE_GUARD_LLM_API_BASE") is None
    assert os.getenv("WRITE_GUARD_LLM_ENABLED") == "false"


def test_setup_config_rejects_router_profile_without_required_remote_fields(
    monkeypatch, tmp_path: Path
) -> None:
    env_example = tmp_path / ".env.example"
    env_example.write_text(
        "\n".join(
            [
                "MCP_API_KEY=",
                "RETRIEVAL_EMBEDDING_BACKEND=hash",
                "RETRIEVAL_RERANKER_ENABLED=false",
                "",
            ]
        ),
        encoding="utf-8",
    )
    target_env = tmp_path / ".env"

    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("MEMORY_PALACE_RUNNING_IN_DOCKER", raising=False)
    monkeypatch.setattr(setup_api, "_ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setenv("MEMORY_PALACE_SETUP_ENV_FILE", str(target_env))

    with _build_client() as client:
        response = client.post(
            "/setup/config",
            json={
                "dashboard_api_key": "router-secret",
                "allow_insecure_local": False,
                "embedding_backend": "router",
                "reranker_enabled": True,
            },
        )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "setup_validation_failed"
    assert "router_api_base" in detail["missing_fields"]
    assert "router_embedding_model" in detail["missing_fields"]
    assert "router_reranker_model" in detail["missing_fields"]


def test_setup_config_clears_hidden_router_and_llm_fields_when_switching_back_to_hash(
    monkeypatch, tmp_path: Path
) -> None:
    env_example = tmp_path / ".env.example"
    env_example.write_text(
        "\n".join(
            [
                "MCP_API_KEY=",
                "RETRIEVAL_EMBEDDING_BACKEND=router",
                "RETRIEVAL_EMBEDDING_DIM=1024",
                "RETRIEVAL_RERANKER_ENABLED=true",
                "ROUTER_API_BASE=https://router.example/v1",
                "ROUTER_API_KEY=router-secret",
                "ROUTER_CHAT_MODEL=router-chat",
                "ROUTER_EMBEDDING_MODEL=router-embed",
                "ROUTER_RERANKER_MODEL=router-rerank",
                "WRITE_GUARD_LLM_ENABLED=true",
                "WRITE_GUARD_LLM_API_BASE=https://guard.example/v1",
                "WRITE_GUARD_LLM_API_KEY=guard-secret",
                "WRITE_GUARD_LLM_MODEL=guard-model",
                "INTENT_LLM_ENABLED=true",
                "INTENT_LLM_API_BASE=https://intent.example/v1",
                "INTENT_LLM_API_KEY=intent-secret",
                "INTENT_LLM_MODEL=intent-model",
                "",
            ]
        ),
        encoding="utf-8",
    )
    target_env = tmp_path / ".env"
    target_env.write_text(env_example.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("MEMORY_PALACE_RUNNING_IN_DOCKER", raising=False)
    monkeypatch.setattr(setup_api, "_ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setenv("MEMORY_PALACE_SETUP_ENV_FILE", str(target_env))

    with _build_client() as client:
        response = client.post(
            "/setup/config",
            json={
                "dashboard_api_key": "local-secret",
                "allow_insecure_local": False,
                "embedding_backend": "hash",
                "reranker_enabled": False,
                "write_guard_llm_enabled": False,
                "intent_llm_enabled": False,
            },
        )

    assert response.status_code == 200
    written = target_env.read_text(encoding="utf-8")
    assert "RETRIEVAL_EMBEDDING_BACKEND=hash" in written
    assert "RETRIEVAL_EMBEDDING_DIM=64" in written
    assert "RETRIEVAL_RERANKER_ENABLED=false" in written
    assert "ROUTER_API_BASE=" in written
    assert "ROUTER_API_KEY=" in written
    assert "ROUTER_CHAT_MODEL=" in written
    assert "ROUTER_EMBEDDING_MODEL=" in written
    assert "ROUTER_RERANKER_MODEL=" in written
    assert "WRITE_GUARD_LLM_ENABLED=false" in written
    assert "WRITE_GUARD_LLM_API_BASE=" in written
    assert "WRITE_GUARD_LLM_API_KEY=" in written
    assert "WRITE_GUARD_LLM_MODEL=" in written
    assert "INTENT_LLM_ENABLED=false" in written
    assert "INTENT_LLM_API_BASE=" in written
    assert "INTENT_LLM_API_KEY=" in written
    assert "INTENT_LLM_MODEL=" in written


def test_setup_config_accepts_openai_backend_and_persists_embedding_dim(
    monkeypatch, tmp_path: Path
) -> None:
    env_example = tmp_path / ".env.example"
    env_example.write_text(
        "\n".join(
            [
                "MCP_API_KEY=",
                "MCP_API_KEY_ALLOW_INSECURE_LOCAL=false",
                "RETRIEVAL_EMBEDDING_BACKEND=hash",
                "RETRIEVAL_EMBEDDING_DIM=64",
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
        "dashboard_api_key": "openai-secret",
        "allow_insecure_local": False,
        "embedding_backend": "openai",
        "embedding_api_base": "https://api.openai.com/v1",
        "embedding_api_key": "sk-test",
        "embedding_model": "text-embedding-3-large",
        "embedding_dim": 3072,
    }

    with _build_client() as client:
        response = client.post("/setup/config", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["summary"]["embedding_backend"] == "openai"
    written = target_env.read_text(encoding="utf-8")
    assert "RETRIEVAL_EMBEDDING_BACKEND=openai" in written
    assert "RETRIEVAL_EMBEDDING_DIM=3072" in written


def test_setup_config_accepts_openai_backend_without_embedding_dim_and_autofills_default(
    monkeypatch, tmp_path: Path
) -> None:
    env_example = tmp_path / ".env.example"
    env_example.write_text(
        "\n".join(
            [
                "MCP_API_KEY=",
                "MCP_API_KEY_ALLOW_INSECURE_LOCAL=false",
                "RETRIEVAL_EMBEDDING_BACKEND=hash",
                "RETRIEVAL_EMBEDDING_DIM=64",
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
    monkeypatch.delenv("RETRIEVAL_EMBEDDING_BACKEND", raising=False)
    monkeypatch.delenv("RETRIEVAL_EMBEDDING_DIM", raising=False)
    monkeypatch.setattr(setup_api, "_ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setenv("MEMORY_PALACE_SETUP_ENV_FILE", str(target_env))

    payload = {
        "dashboard_api_key": "openai-secret",
        "allow_insecure_local": False,
        "embedding_backend": "openai",
        "embedding_api_base": "https://api.openai.com/v1",
        "embedding_api_key": "sk-test",
        "embedding_model": "text-embedding-3-large",
    }

    with _build_client() as client:
        response = client.post("/setup/config", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["summary"]["embedding_backend"] == "openai"
    assert body["summary"]["embedding_dim"] == 1024
    written = target_env.read_text(encoding="utf-8")
    assert "RETRIEVAL_EMBEDDING_BACKEND=openai" in written
    assert "RETRIEVAL_EMBEDDING_DIM=1024" in written


def test_setup_config_accepts_real_local_router_endpoint_with_real_models(
    monkeypatch, tmp_path: Path
) -> None:
    env_example = tmp_path / ".env.example"
    env_example.write_text(
        "MCP_API_KEY=\nRETRIEVAL_EMBEDDING_BACKEND=hash\nRETRIEVAL_EMBEDDING_DIM=64\n",
        encoding="utf-8",
    )
    target_env = tmp_path / ".env"

    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("MEMORY_PALACE_RUNNING_IN_DOCKER", raising=False)
    monkeypatch.setattr(setup_api, "_ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setenv("MEMORY_PALACE_SETUP_ENV_FILE", str(target_env))

    with _build_client() as client:
        response = client.post(
            "/setup/config",
            json={
                "dashboard_api_key": "router-secret",
                "allow_insecure_local": False,
                "embedding_backend": "router",
                "embedding_dim": 1024,
                "reranker_enabled": True,
                "router_api_base": "http://127.0.0.1:8001/v1",
                "router_embedding_model": "local-router-embed",
                "router_reranker_model": "local-router-rerank",
            },
        )

    assert response.status_code == 200
    written = target_env.read_text(encoding="utf-8")
    assert "ROUTER_API_BASE=http://127.0.0.1:8001/v1" in written
    assert "ROUTER_EMBEDDING_MODEL=local-router-embed" in written
    assert "ROUTER_RERANKER_MODEL=local-router-rerank" in written


def test_setup_config_rejects_example_router_model_ids(
    monkeypatch, tmp_path: Path
) -> None:
    env_example = tmp_path / ".env.example"
    env_example.write_text(
        "MCP_API_KEY=\nRETRIEVAL_EMBEDDING_BACKEND=hash\nRETRIEVAL_EMBEDDING_DIM=64\n",
        encoding="utf-8",
    )
    target_env = tmp_path / ".env"

    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("MEMORY_PALACE_RUNNING_IN_DOCKER", raising=False)
    monkeypatch.setattr(setup_api, "_ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setenv("MEMORY_PALACE_SETUP_ENV_FILE", str(target_env))

    with _build_client() as client:
        response = client.post(
            "/setup/config",
            json={
                "dashboard_api_key": "router-secret",
                "allow_insecure_local": False,
                "embedding_backend": "router",
                "embedding_dim": 1024,
                "reranker_enabled": True,
                "router_api_base": "http://127.0.0.1:8001/v1",
                "router_embedding_model": "router-embedding-model",
                "router_reranker_model": "router-reranker-model",
            },
        )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "setup_validation_failed"
    assert "router_embedding_model" in detail["placeholder_fields"]
    assert "router_reranker_model" in detail["placeholder_fields"]


def test_setup_config_rejects_invalid_openai_embedding_dim_without_backend_literal_errors(
    monkeypatch, tmp_path: Path
) -> None:
    env_example = tmp_path / ".env.example"
    env_example.write_text(
        "MCP_API_KEY=\nRETRIEVAL_EMBEDDING_BACKEND=hash\nRETRIEVAL_EMBEDDING_DIM=64\n",
        encoding="utf-8",
    )
    target_env = tmp_path / ".env"

    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("MEMORY_PALACE_RUNNING_IN_DOCKER", raising=False)
    monkeypatch.setattr(setup_api, "_ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setenv("MEMORY_PALACE_SETUP_ENV_FILE", str(target_env))

    with _build_client() as client:
        response = client.post(
            "/setup/config",
            json={
                "dashboard_api_key": "openai-secret",
                "allow_insecure_local": False,
                "embedding_backend": "openai",
                "embedding_api_base": "https://api.openai.com/v1",
                "embedding_model": "text-embedding-3-large",
                "embedding_dim": 0,
            },
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert [tuple(item["loc"]) for item in detail] == [("body", "embedding_dim")]


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
