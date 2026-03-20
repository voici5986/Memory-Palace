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


def test_apply_profile_powershell_declares_utf8_no_bom_and_placeholder_guard() -> None:
    script_text = (
        PROJECT_ROOT / "scripts" / "apply_profile.ps1"
    ).read_text(encoding="utf-8")

    assert "[System.Text.UTF8Encoding]::new($false)" in script_text
    assert "function Write-LinesUtf8" in script_text
    assert "function Assert-ResolvedProfilePlaceholders" in script_text
