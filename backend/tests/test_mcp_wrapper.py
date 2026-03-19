from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_module():
    project_root = Path(__file__).resolve().parents[2]
    script_path = project_root / "backend" / "mcp_wrapper.py"
    spec = importlib.util.spec_from_file_location("mcp_wrapper", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_resolve_backend_python_accepts_windows_virtualenv_layout(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    windows_python = tmp_path / "backend" / ".venv" / "Scripts" / "python.exe"
    windows_python.parent.mkdir(parents=True, exist_ok=True)
    windows_python.write_text("", encoding="utf-8")

    monkeypatch.setattr(module, "WINDOWS_VENV_PYTHON", windows_python)
    monkeypatch.setattr(module, "POSIX_VENV_PYTHON", tmp_path / "missing" / "python")

    assert module.resolve_backend_python() == windows_python


def test_resolve_backend_python_prefers_posix_layout_on_non_windows_when_both_exist(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    windows_python = tmp_path / "backend" / ".venv" / "Scripts" / "python.exe"
    posix_python = tmp_path / "backend" / ".venv" / "bin" / "python"
    windows_python.parent.mkdir(parents=True, exist_ok=True)
    posix_python.parent.mkdir(parents=True, exist_ok=True)
    windows_python.write_text("", encoding="utf-8")
    posix_python.write_text("", encoding="utf-8")

    monkeypatch.setattr(module, "WINDOWS_VENV_PYTHON", windows_python)
    monkeypatch.setattr(module, "POSIX_VENV_PYTHON", posix_python)
    monkeypatch.setattr(module.os, "name", "posix", raising=False)

    assert module.resolve_backend_python() == posix_python


def test_build_runtime_env_rejects_docker_internal_database_url(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=sqlite+aiosqlite:////app/data/memory_palace.db\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "ENV_FILE", env_file)
    monkeypatch.setattr(module, "DOCKER_ENV_FILE", tmp_path / ".env.docker")
    monkeypatch.setattr(module, "DEFAULT_DB_PATH", tmp_path / "demo.db")
    monkeypatch.setattr(module.os, "environ", {})

    with pytest.raises(SystemExit) as excinfo:
        module.build_runtime_env()

    assert str(excinfo.value) == "1"


def test_build_runtime_env_rejects_data_prefixed_docker_internal_database_url(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=sqlite+aiosqlite:////data/memory_palace.db\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "ENV_FILE", env_file)
    monkeypatch.setattr(module, "DOCKER_ENV_FILE", tmp_path / ".env.docker")
    monkeypatch.setattr(module, "DEFAULT_DB_PATH", tmp_path / "demo.db")
    monkeypatch.setattr(module.os, "environ", {})

    with pytest.raises(SystemExit) as excinfo:
        module.build_runtime_env()

    assert str(excinfo.value) == "1"


def test_build_runtime_env_uses_last_database_url_from_env_file_when_runtime_value_is_missing(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    env_file = tmp_path / ".env"
    host_db = tmp_path / "host.db"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=sqlite+aiosqlite:////app/data/stale.db",
                f"DATABASE_URL=sqlite+aiosqlite:///{host_db.as_posix()}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "ENV_FILE", env_file)
    monkeypatch.setattr(module, "DOCKER_ENV_FILE", tmp_path / ".env.docker")
    monkeypatch.setattr(module, "DEFAULT_DB_PATH", tmp_path / "demo.db")
    monkeypatch.setattr(module.os, "environ", {})

    runtime_env = module.build_runtime_env()

    assert runtime_env["DATABASE_URL"] == f"sqlite+aiosqlite:///{host_db.as_posix()}"


def test_build_runtime_env_sets_demo_db_when_no_env_exists(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    demo_db = tmp_path / "demo.db"

    monkeypatch.setattr(module, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(module, "DOCKER_ENV_FILE", tmp_path / ".env.docker")
    monkeypatch.setattr(module, "DEFAULT_DB_PATH", demo_db)
    monkeypatch.setattr(module.os, "environ", {})

    runtime_env = module.build_runtime_env()

    assert runtime_env["DATABASE_URL"] == f"sqlite+aiosqlite:///{demo_db.as_posix()}"
    assert runtime_env["RETRIEVAL_REMOTE_TIMEOUT_SEC"] == "8"


def test_build_runtime_env_treats_empty_database_url_as_missing_when_no_env_exists(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    demo_db = tmp_path / "demo.db"

    monkeypatch.setattr(module, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(module, "DOCKER_ENV_FILE", tmp_path / ".env.docker")
    monkeypatch.setattr(module, "DEFAULT_DB_PATH", demo_db)
    monkeypatch.setattr(module.os, "environ", {"DATABASE_URL": ""})

    runtime_env = module.build_runtime_env()

    assert runtime_env["DATABASE_URL"] == f"sqlite+aiosqlite:///{demo_db.as_posix()}"


def test_read_env_value_parses_quoted_value_with_inline_comment(tmp_path: Path) -> None:
    module = _load_module()
    env_file = tmp_path / ".env"
    env_file.write_text(
        'DATABASE_URL="sqlite+aiosqlite:////tmp/memory_palace.db" # local db\n',
        encoding="utf-8",
    )

    assert (
        module.read_env_value(env_file, "DATABASE_URL")
        == "sqlite+aiosqlite:////tmp/memory_palace.db"
    )
