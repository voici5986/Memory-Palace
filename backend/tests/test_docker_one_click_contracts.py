from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_runtime_env_injection_covers_intent_llm_and_router_fallbacks() -> None:
    shell_text = (PROJECT_ROOT / "scripts" / "docker_one_click.sh").read_text(
        encoding="utf-8"
    )
    ps1_text = (PROJECT_ROOT / "scripts" / "docker_one_click.ps1").read_text(
        encoding="utf-8"
    )

    for literal in (
        "ROUTER_CHAT_MODEL",
        "ROUTER_RERANKER_MODEL",
        "RETRIEVAL_EMBEDDING_DIM",
        "RETRIEVAL_RERANKER_ENABLED",
        "INTENT_LLM_ENABLED",
        "INTENT_LLM_API_BASE",
        "INTENT_LLM_API_KEY",
        "INTENT_LLM_MODEL",
        "--wait",
        "--wait-timeout",
        "RETRIEVAL_EMBEDDING_API_BASE copied from ROUTER_API_BASE",
        "RETRIEVAL_EMBEDDING_API_KEY copied from ROUTER_API_KEY",
        "RETRIEVAL_EMBEDDING_MODEL copied from ROUTER_EMBEDDING_MODEL",
        "RETRIEVAL_RERANKER_API_BASE copied from ROUTER_API_BASE",
        "RETRIEVAL_RERANKER_API_KEY copied from ROUTER_API_KEY",
        "RETRIEVAL_RERANKER_MODEL copied from ROUTER_RERANKER_MODEL",
    ):
        assert literal in shell_text
        assert literal in ps1_text

    assert "--no-build" in shell_text

    assert "wait_for_deployment_ready" in shell_text
    assert "Wait-DeploymentReady" in ps1_text
    assert "compose_project_has_any_container" in shell_text
    assert "Test-ComposeProjectHasAnyContainer" in ps1_text
    assert '--filter "label=com.docker.compose.project=${compose_project_name}"' in shell_text
    assert '--filter "label=com.docker.compose.service=${service}"' in shell_text
    assert "--format '{{.Ports}}'" in shell_text
    assert 'docker port "${container_name}" "${target_port}"' in shell_text
    assert '--filter "label=com.docker.compose.project=$ComposeProjectName"' in ps1_text
    assert '--filter "label=com.docker.compose.service=$Service"' in ps1_text
    assert "--format '{{.Ports}}'" in ps1_text
    assert "docker port $containerName $TargetPort" in ps1_text
    assert 'docker-compose.yml port "${service}" "${target_port}"' in shell_text
    assert "$portArgs += @('-f', 'docker-compose.yml', 'port', $Service, \"$TargetPort\")" in ps1_text
    assert 'upsert_env_value_in_file "${env_file}" "MEMORY_PALACE_FRONTEND_PORT" "${frontend_port}"' in shell_text
    assert 'upsert_env_value_in_file "${env_file}" "MEMORY_PALACE_BACKEND_PORT" "${backend_port}"' in shell_text
    assert 'planned_frontend_port="$(get_env_value_from_file "${env_file}" "MEMORY_PALACE_FRONTEND_PORT")"' in shell_text
    assert 'planned_backend_port="$(get_env_value_from_file "${env_file}" "MEMORY_PALACE_BACKEND_PORT")"' in shell_text
    assert "Set-EnvValueInFile -FilePath $envFile -Key 'MEMORY_PALACE_FRONTEND_PORT' -Value \"$FrontendPort\"" in ps1_text
    assert "Set-EnvValueInFile -FilePath $envFile -Key 'MEMORY_PALACE_BACKEND_PORT' -Value \"$BackendPort\"" in ps1_text
    assert "$plannedFrontendPort = Get-EnvValueFromFile -FilePath $envFile -Key 'MEMORY_PALACE_FRONTEND_PORT'" in ps1_text
    assert "$plannedBackendPort = Get-EnvValueFromFile -FilePath $envFile -Key 'MEMORY_PALACE_BACKEND_PORT'" in ps1_text
    assert "Get-Command -Name 'Get-NetTCPConnection'" in ps1_text
    assert "Get-Command -Name 'ss'" in ps1_text
    assert '& ss -ltnH "( sport = :$Port )"' in ps1_text
    assert '${project_name}_data' in shell_text
    assert '${project_name}_snapshots' in shell_text
    assert "${projectName}_data" in ps1_text
    assert "${projectName}_snapshots" in ps1_text
    assert "Set MEMORY_PALACE_DATA_VOLUME=" in shell_text
    assert "Set MEMORY_PALACE_SNAPSHOTS_VOLUME=" in shell_text
    assert "Set MEMORY_PALACE_DATA_VOLUME=$legacyVolume" in ps1_text
    assert "Set MEMORY_PALACE_SNAPSHOTS_VOLUME=$legacyVolume" in ps1_text
    assert (
        "[compose-up] docker compose failed before creating any service container; "
        "skipping readiness probe." in shell_text
    )
    assert (
        "[compose-up] docker compose failed before creating any service container; "
        "skipping readiness probe." in ps1_text
    )


def test_profile_external_settings_gate_checks_required_model_ids() -> None:
    shell_text = (PROJECT_ROOT / "scripts" / "docker_one_click.sh").read_text(
        encoding="utf-8"
    )
    ps1_text = (PROJECT_ROOT / "scripts" / "docker_one_click.ps1").read_text(
        encoding="utf-8"
    )

    for literal in (
        "your-embedding-model-id",
        "your-reranker-model-id",
        "RETRIEVAL_EMBEDDING_MODEL",
        "RETRIEVAL_RERANKER_MODEL",
    ):
        assert literal in shell_text
        assert literal in ps1_text


def test_default_compose_project_name_uses_sha256_and_normalized_paths_in_both_scripts() -> None:
    shell_text = (PROJECT_ROOT / "scripts" / "docker_one_click.sh").read_text(
        encoding="utf-8"
    )
    ps1_text = (PROJECT_ROOT / "scripts" / "docker_one_click.ps1").read_text(
        encoding="utf-8"
    )

    assert "normalize_project_root_for_compose_name" in shell_text
    assert "cygpath -am" in shell_text
    assert "wslpath -m" in shell_text
    assert "hashlib.sha256" in shell_text
    assert "$normalizedProjectRoot = $projectRoot -replace '\\\\', '/'" in ps1_text
    assert "SHA256" in ps1_text


def test_compose_waits_for_healthy_sse_service() -> None:
    compose_text = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    backend_block = compose_text.split("\n  backend:\n", 1)[1].split("\n  frontend:\n", 1)[0]
    frontend_block = compose_text.split("\n  frontend:\n", 1)[1]

    assert "healthcheck:" in backend_block
    assert "http://127.0.0.1:8000/health" in backend_block
    assert 'host.docker.internal:host-gateway' in backend_block
    assert "HOST: 0.0.0.0" in backend_block
    assert "RUNTIME_WRITE_WAL_ENABLED: ${MEMORY_PALACE_DOCKER_WAL_ENABLED:-true}" in backend_block
    assert "RUNTIME_WRITE_JOURNAL_MODE: ${MEMORY_PALACE_DOCKER_JOURNAL_MODE:-wal}" in backend_block
    assert "\n  sse:\n" not in compose_text
    assert "backend:\n        condition: service_healthy" in frontend_block


def test_local_compose_uses_stable_image_names_for_no_build_reuse() -> None:
    compose_text = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    shell_text = (PROJECT_ROOT / "scripts" / "docker_one_click.sh").read_text(
        encoding="utf-8"
    )
    ps1_text = (PROJECT_ROOT / "scripts" / "docker_one_click.ps1").read_text(
        encoding="utf-8"
    )

    assert "image: ${MEMORY_PALACE_BACKEND_IMAGE:-memory-palace-backend:latest}" in compose_text
    assert "image: ${MEMORY_PALACE_FRONTEND_IMAGE:-memory-palace-frontend:latest}" in compose_text
    assert 'backend_image="${MEMORY_PALACE_BACKEND_IMAGE:-${local_image_namespace}-backend:latest}"' in shell_text
    assert 'frontend_image="${MEMORY_PALACE_FRONTEND_IMAGE:-${local_image_namespace}-frontend:latest}"' in shell_text
    assert 'export MEMORY_PALACE_BACKEND_IMAGE="${backend_image}"' in shell_text
    assert 'export MEMORY_PALACE_FRONTEND_IMAGE="${frontend_image}"' in shell_text
    assert "$backendImage = [System.Environment]::GetEnvironmentVariable('MEMORY_PALACE_BACKEND_IMAGE')" in ps1_text
    assert "$frontendImage = [System.Environment]::GetEnvironmentVariable('MEMORY_PALACE_FRONTEND_IMAGE')" in ps1_text
    assert '$env:MEMORY_PALACE_BACKEND_IMAGE = $backendImage' in ps1_text
    assert '$env:MEMORY_PALACE_FRONTEND_IMAGE = $frontendImage' in ps1_text


def test_pull_based_ghcr_release_artifacts_exist() -> None:
    ghcr_compose = (PROJECT_ROOT / "docker-compose.ghcr.yml").read_text(
        encoding="utf-8"
    )
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "docker-publish.yml").read_text(
        encoding="utf-8"
    )

    assert "pull_policy: missing" in ghcr_compose
    assert "ghcr.io/agi-is-going-to-arrive/memory-palace-backend:latest" in ghcr_compose
    assert "ghcr.io/agi-is-going-to-arrive/memory-palace-frontend:latest" in ghcr_compose
    assert "docker/login-action" in workflow
    assert "docker/build-push-action" in workflow
    assert "ghcr.io/${{ github.repository_owner }}/memory-palace-${{ matrix.service }}" in workflow


def test_pull_based_ghcr_compose_matches_repo_two_service_topology() -> None:
    ghcr_compose = (PROJECT_ROOT / "docker-compose.ghcr.yml").read_text(
        encoding="utf-8"
    )
    frontend_block = ghcr_compose.split("\n  frontend:\n", 1)[1]

    assert "\n  sse:\n" not in ghcr_compose
    assert "backend:\n        condition: service_healthy" in frontend_block
    assert "sse:\n        condition: service_healthy" not in frontend_block


def test_docker_publish_workflow_uses_repo_backend_venv_for_validation() -> None:
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "docker-publish.yml").read_text(
        encoding="utf-8"
    )

    assert "python -m venv backend/.venv" in workflow
    assert "backend/.venv/bin/python -m pip install --upgrade pip" in workflow
    assert (
        "backend/.venv/bin/python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt"
        in workflow
    )
    assert "cd backend && .venv/bin/python -m pytest tests -q" in workflow


def test_compose_volume_defaults_are_project_scoped() -> None:
    compose_text = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    ghcr_compose_text = (PROJECT_ROOT / "docker-compose.ghcr.yml").read_text(
        encoding="utf-8"
    )

    expected_data = "${MEMORY_PALACE_DATA_VOLUME:-${NOCTURNE_DATA_VOLUME:-${COMPOSE_PROJECT_NAME:-memory-palace}_data}}"
    expected_snapshots = "${MEMORY_PALACE_SNAPSHOTS_VOLUME:-${NOCTURNE_SNAPSHOTS_VOLUME:-${COMPOSE_PROJECT_NAME:-memory-palace}_snapshots}}"

    for text in (compose_text, ghcr_compose_text):
        assert expected_data in text
        assert expected_snapshots in text
        assert 'host.docker.internal:host-gateway' in text


def test_profile_d_templates_use_shell_safe_router_placeholders() -> None:
    for relative_path in (
        "deploy/profiles/macos/profile-d.env",
        "deploy/profiles/windows/profile-d.env",
        "deploy/profiles/docker/profile-d.env",
    ):
        text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        assert "https://router.example.com/v1" in text
        assert "<your-router-host>" not in text


def test_frontend_nginx_template_disables_index_html_caching() -> None:
    template_text = (PROJECT_ROOT / "deploy" / "docker" / "nginx.conf.template").read_text(
        encoding="utf-8"
    )

    assert 'location = /index.html {' in template_text
    assert 'Cache-Control "no-store, no-cache, must-revalidate" always' in template_text
    assert "try_files /index.html =404;" in template_text
