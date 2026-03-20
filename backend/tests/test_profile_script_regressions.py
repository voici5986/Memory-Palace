from __future__ import annotations

import os
import subprocess
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _copy_script(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        source.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", ""),
        encoding="utf-8",
        newline="\n",
    )
    destination.chmod(0o755)


def test_apply_profile_shell_keeps_database_url_valid_when_repo_path_has_spaces(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repo with spaces"
    script_path = project_root / "scripts" / "apply_profile.sh"
    _copy_script(PROJECT_ROOT / "scripts" / "apply_profile.sh", script_path)

    (project_root / ".env.example").write_text("MCP_API_KEY=\n", encoding="utf-8")
    profile_path = project_root / "deploy" / "profiles" / "macos" / "profile-b.env"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        "\n".join(
            [
                "DATABASE_URL=sqlite+aiosqlite:////Users/<your-user>/memory_palace/agent_memory.db",
                "SEARCH_DEFAULT_MODE=hybrid",
                "RETRIEVAL_EMBEDDING_BACKEND=hash",
                "RETRIEVAL_RERANKER_ENABLED=false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", "scripts/apply_profile.sh", "macos", "b", ".env.generated"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    generated_env = project_root / ".env.generated"
    database_url = dotenv_values(generated_env).get("DATABASE_URL")
    assert isinstance(database_url, str)
    expected_db_path = (project_root / "demo.db").as_posix()
    assert database_url == f"sqlite+aiosqlite:///{expected_db_path}"
    assert make_url(database_url).database == expected_db_path


def test_apply_profile_shell_rewrites_database_url_when_placeholder_has_spacing_and_comment(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repo"
    script_path = project_root / "scripts" / "apply_profile.sh"
    _copy_script(PROJECT_ROOT / "scripts" / "apply_profile.sh", script_path)

    (project_root / ".env.example").write_text("MCP_API_KEY=\n", encoding="utf-8")
    profile_path = project_root / "deploy" / "profiles" / "macos" / "profile-b.env"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        "\n".join(
            [
                "DATABASE_URL = sqlite+aiosqlite:////Users/<your-user>/memory_palace/agent_memory.db  # local template placeholder",
                "SEARCH_DEFAULT_MODE=hybrid",
                "RETRIEVAL_EMBEDDING_BACKEND=hash",
                "RETRIEVAL_RERANKER_ENABLED=false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", "scripts/apply_profile.sh", "macos", "b", ".env.generated"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    generated_env = project_root / ".env.generated"
    generated_text = generated_env.read_text(encoding="utf-8")
    database_url = dotenv_values(generated_env).get("DATABASE_URL")
    assert isinstance(database_url, str)
    expected_db_path = (project_root / "demo.db").as_posix()
    assert database_url == f"sqlite+aiosqlite:///{expected_db_path}"
    assert make_url(database_url).database == expected_db_path
    assert "<your-user>" not in generated_text
    assert "DATABASE_URL =" not in generated_text


def test_apply_profile_shell_rejects_unresolved_profile_c_placeholders(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repo"
    script_path = project_root / "scripts" / "apply_profile.sh"
    _copy_script(PROJECT_ROOT / "scripts" / "apply_profile.sh", script_path)

    (project_root / ".env.example").write_text("MCP_API_KEY=\n", encoding="utf-8")
    profile_path = project_root / "deploy" / "profiles" / "macos" / "profile-c.env"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        "\n".join(
            [
                "DATABASE_URL=sqlite+aiosqlite:////Users/<your-user>/memory_palace/agent_memory.db",
                "ROUTER_API_BASE=http://127.0.0.1:PORT/v1",
                "ROUTER_API_KEY=replace-with-your-key",
                "ROUTER_EMBEDDING_MODEL=your-embedding-model-id",
                "RETRIEVAL_RERANKER_MODEL=your-reranker-model-id",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", "scripts/apply_profile.sh", "macos", "c", ".env.generated"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "unresolved placeholders" in result.stderr
    assert "ROUTER_API_BASE=http://127.0.0.1:PORT/v1" in result.stderr
    assert "ROUTER_API_KEY=replace-with-your-key" in result.stderr


def test_apply_profile_shell_rejects_unresolved_profile_c_placeholders_with_spacing_and_comment(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repo"
    script_path = project_root / "scripts" / "apply_profile.sh"
    _copy_script(PROJECT_ROOT / "scripts" / "apply_profile.sh", script_path)

    (project_root / ".env.example").write_text("MCP_API_KEY=\n", encoding="utf-8")
    profile_path = project_root / "deploy" / "profiles" / "macos" / "profile-c.env"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        "\n".join(
            [
                "DATABASE_URL=sqlite+aiosqlite:////Users/<your-user>/memory_palace/agent_memory.db",
                "ROUTER_API_BASE = http://127.0.0.1:PORT/v1  # unresolved router endpoint",
                "ROUTER_API_KEY = replace-with-your-key  # unresolved key",
                "ROUTER_EMBEDDING_MODEL = your-embedding-model-id",
                "RETRIEVAL_RERANKER_MODEL = your-reranker-model-id  # unresolved model",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", "scripts/apply_profile.sh", "macos", "c", ".env.generated"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "unresolved placeholders" in result.stderr
    assert "ROUTER_API_BASE = http://127.0.0.1:PORT/v1  # unresolved router endpoint" in result.stderr
    assert "ROUTER_API_KEY = replace-with-your-key  # unresolved key" in result.stderr


def test_apply_profile_shell_docker_profile_syncs_compose_wal_overrides(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repo"
    script_path = project_root / "scripts" / "apply_profile.sh"
    _copy_script(PROJECT_ROOT / "scripts" / "apply_profile.sh", script_path)

    (project_root / ".env.example").write_text("MCP_API_KEY=\n", encoding="utf-8")
    profile_path = project_root / "deploy" / "profiles" / "docker" / "profile-b.env"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        "\n".join(
            [
                "DATABASE_URL=sqlite+aiosqlite:////app/data/memory_palace.db",
                "RUNTIME_WRITE_WAL_ENABLED=false",
                "RUNTIME_WRITE_JOURNAL_MODE=delete",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", "scripts/apply_profile.sh", "docker", "b", ".env.docker"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    values = dotenv_values(project_root / ".env.docker")
    assert values.get("MEMORY_PALACE_DOCKER_WAL_ENABLED") == "false"
    assert values.get("MEMORY_PALACE_DOCKER_JOURNAL_MODE") == "delete"


def test_repo_local_stdio_wrapper_resolves_real_project_root_through_symlink(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repo"
    script_path = project_root / "scripts" / "run_memory_palace_mcp_stdio.sh"
    backend_python = project_root / "backend" / ".venv" / "bin" / "python"

    _copy_script(PROJECT_ROOT / "scripts" / "run_memory_palace_mcp_stdio.sh", script_path)
    backend_python.parent.mkdir(parents=True, exist_ok=True)
    backend_python.write_text(
        "#!/usr/bin/env bash\nprintf '%s' \"$PWD\"\n",
        encoding="utf-8",
    )
    backend_python.chmod(0o755)

    link_dir = tmp_path / "symlink launch"
    link_dir.mkdir(parents=True, exist_ok=True)
    link_path = link_dir / "memory-palace-stdio"
    link_path.symlink_to(script_path)

    result = subprocess.run(
        ["bash", str(link_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={key: value for key, value in os.environ.items() if key != "DATABASE_URL"},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == str(project_root / "backend")


def test_repo_local_stdio_wrapper_prefers_env_file_remote_timeout_when_runtime_env_absent(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repo"
    script_path = project_root / "scripts" / "run_memory_palace_mcp_stdio.sh"
    backend_python = project_root / "backend" / ".venv" / "bin" / "python"

    _copy_script(PROJECT_ROOT / "scripts" / "run_memory_palace_mcp_stdio.sh", script_path)
    backend_python.parent.mkdir(parents=True, exist_ok=True)
    backend_python.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "if [[ \"${1:-}\" == \"-\" ]]; then",
                "  exec python3 \"$@\"",
                "fi",
                "printf '%s' \"${RETRIEVAL_REMOTE_TIMEOUT_SEC:-missing}\"",
                "",
            ]
        ),
        encoding="utf-8",
    )
    backend_python.chmod(0o755)

    (project_root / ".env").write_text(
        "RETRIEVAL_REMOTE_TIMEOUT_SEC=30\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", "scripts/run_memory_palace_mcp_stdio.sh"],
        cwd=project_root,
        capture_output=True,
        text=True,
        env={key: value for key, value in os.environ.items() if key != "RETRIEVAL_REMOTE_TIMEOUT_SEC"},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "30"


def test_repo_local_stdio_wrapper_reads_env_without_python_dotenv(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repo"
    script_path = project_root / "scripts" / "run_memory_palace_mcp_stdio.sh"
    backend_python = project_root / "backend" / ".venv" / "bin" / "python"

    _copy_script(PROJECT_ROOT / "scripts" / "run_memory_palace_mcp_stdio.sh", script_path)
    backend_python.parent.mkdir(parents=True, exist_ok=True)
    backend_python.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "if [[ \"${1:-}\" == \"-\" ]]; then",
                "  exec python3 -S \"$@\"",
                "fi",
                "printf '%s' \"${RETRIEVAL_REMOTE_TIMEOUT_SEC:-missing}\"",
                "",
            ]
        ),
        encoding="utf-8",
    )
    backend_python.chmod(0o755)

    (project_root / ".env").write_text(
        "RETRIEVAL_REMOTE_TIMEOUT_SEC=37\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", "scripts/run_memory_palace_mcp_stdio.sh"],
        cwd=project_root,
        capture_output=True,
        text=True,
        env={key: value for key, value in os.environ.items() if key != "RETRIEVAL_REMOTE_TIMEOUT_SEC"},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "37"


def test_repo_local_stdio_wrapper_normalizes_double_slash_default_database_path(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repo"
    script_path = project_root / "scripts" / "run_memory_palace_mcp_stdio.sh"
    backend_python = project_root / "backend" / ".venv" / "bin" / "python"

    _copy_script(PROJECT_ROOT / "scripts" / "run_memory_palace_mcp_stdio.sh", script_path)
    script_path.write_text(
        script_path.read_text(encoding="utf-8").replace(
            'DEFAULT_DB_PATH="${PROJECT_ROOT}/demo.db"',
            'DEFAULT_DB_PATH="//tmp/memory-palace/demo.db"',
        ),
        encoding="utf-8",
    )
    backend_python.parent.mkdir(parents=True, exist_ok=True)
    backend_python.write_text(
        "#!/usr/bin/env bash\nprintf '%s' \"${DATABASE_URL:-missing}\"\n",
        encoding="utf-8",
    )
    backend_python.chmod(0o755)

    result = subprocess.run(
        ["bash", "scripts/run_memory_palace_mcp_stdio.sh"],
        cwd=project_root,
        capture_output=True,
        text=True,
        env={key: value for key, value in os.environ.items() if key != "DATABASE_URL"},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "sqlite+aiosqlite:////tmp/memory-palace/demo.db"


def test_apply_profile_powershell_declares_utf8_no_bom_and_placeholder_guard() -> None:
    script_text = (
        PROJECT_ROOT / "scripts" / "apply_profile.ps1"
    ).read_text(encoding="utf-8")

    assert "[ValidateSet('macos', 'linux', 'windows', 'docker')]" in script_text
    assert "$Platform = $Platform.ToLowerInvariant()" in script_text
    assert "if ($Platform -eq 'linux') { $Platform = 'macos' }" in script_text
    assert "[System.Text.UTF8Encoding]::new($false)" in script_text
    assert "function Write-LinesUtf8" in script_text
    assert "function Assert-ResolvedProfilePlaceholders" in script_text
    assert "function Sync-DockerWalOverrides" in script_text
    assert "MEMORY_PALACE_DOCKER_WAL_ENABLED" in script_text
    assert "MEMORY_PALACE_DOCKER_JOURNAL_MODE" in script_text
    assert "$line -match '^\\s*(ROUTER_API_BASE|RETRIEVAL_EMBEDDING_API_BASE|RETRIEVAL_RERANKER_API_BASE)\\s*=\\s*.*:PORT/'" in script_text
    assert "$line -match '=\\s*replace-with-your-key(\\s+#.*)?\\s*$'" in script_text
    assert "$line -match '=\\s*your-embedding-model-id(\\s+#.*)?\\s*$'" in script_text
    assert "$line -match '=\\s*your-reranker-model-id(\\s+#.*)?\\s*$'" in script_text
    assert "$placeholderPattern = '^\\s*DATABASE_URL\\s*=\\s*sqlite\\+aiosqlite:////Users/<your-user>/memory_palace/agent_memory\\.db(\\s+#.*)?\\s*$'" in script_text
    assert "$placeholderPattern = '^\\s*DATABASE_URL\\s*=\\s*sqlite\\+aiosqlite:///C:/memory_palace/agent_memory\\.db(\\s+#.*)?\\s*$'" in script_text


def test_docker_profiles_align_wal_defaults_with_compose_runtime_env() -> None:
    compose_text = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert (
        "RUNTIME_WRITE_WAL_ENABLED: ${MEMORY_PALACE_DOCKER_WAL_ENABLED:-true}"
        in compose_text
    )
    assert (
        "RUNTIME_WRITE_JOURNAL_MODE: ${MEMORY_PALACE_DOCKER_JOURNAL_MODE:-wal}"
        in compose_text
    )

    for profile_name in ("profile-a.env", "profile-b.env", "profile-c.env", "profile-d.env"):
        profile_text = (
            PROJECT_ROOT / "deploy" / "profiles" / "docker" / profile_name
        ).read_text(encoding="utf-8")
        assert "MEMORY_PALACE_DOCKER_WAL_ENABLED=true" in profile_text
        assert "MEMORY_PALACE_DOCKER_JOURNAL_MODE=wal" in profile_text
        assert "RUNTIME_WRITE_WAL_ENABLED=true" in profile_text
        assert "RUNTIME_WRITE_JOURNAL_MODE=wal" in profile_text
