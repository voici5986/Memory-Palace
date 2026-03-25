from __future__ import annotations

import io
import importlib.util
import sys
import threading
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


@pytest.mark.parametrize("platform_value", ["msys", "msys2", "cygwin"])
def test_resolve_backend_python_prefers_windows_layout_on_msys_like_hosts(
    monkeypatch, tmp_path: Path, platform_value: str
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
    monkeypatch.setattr(module.sys, "platform", platform_value, raising=False)
    monkeypatch.delenv("MSYSTEM", raising=False)
    monkeypatch.delenv("OSTYPE", raising=False)

    assert module.resolve_backend_python() == windows_python


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


def test_build_runtime_env_prefers_env_file_remote_timeout_when_runtime_env_absent(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"DATABASE_URL=sqlite+aiosqlite:///{(tmp_path / 'memory.db').as_posix()}",
                "RETRIEVAL_REMOTE_TIMEOUT_SEC=30",
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

    assert runtime_env["RETRIEVAL_REMOTE_TIMEOUT_SEC"] == "30"


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


def test_read_env_value_falls_back_when_python_dotenv_is_unavailable(tmp_path: Path) -> None:
    module = _load_module()
    env_file = tmp_path / ".env"
    env_file.write_text(
        'DATABASE_URL="sqlite+aiosqlite:////tmp/memory_palace.db" # local db\n',
        encoding="utf-8",
    )

    module.dotenv_values = None

    assert (
        module.read_env_value(env_file, "DATABASE_URL")
        == "sqlite+aiosqlite:////tmp/memory_palace.db"
    )


def test_normalize_env_string_value_strips_quotes_and_whitespace() -> None:
    module = _load_module()

    assert (
        module._normalize_env_string_value('  "sqlite+aiosqlite:////tmp/demo.db"  ')
        == "sqlite+aiosqlite:////tmp/demo.db"
    )
    assert module._normalize_env_string_value("  '30'  ") == "30"


def test_read_stream_chunk_prefers_read1_when_available() -> None:
    module = _load_module()

    class _FakeStream:
        def __init__(self) -> None:
            self.read1_sizes: list[int] = []
            self.read_sizes: list[int] = []

        def read1(self, size: int) -> bytes:
            self.read1_sizes.append(size)
            return b"payload"

        def read(self, size: int) -> bytes:
            self.read_sizes.append(size)
            return b"fallback"

    stream = _FakeStream()

    assert module._read_stream_chunk(stream) == b"payload"
    assert stream.read1_sizes == [module._IO_CHUNK_SIZE]
    assert stream.read_sizes == []


def test_forward_stream_chunked_normalizes_crlf_without_dropping_standalone_carriage_returns() -> None:
    module = _load_module()
    source = io.BytesIO(b"line1\r\nline2\rline3")
    destination = io.BytesIO()

    module._forward_stream_chunked(
        source,
        destination,
        stop_event=threading.Event(),
    )

    assert destination.getvalue() == b"line1\nline2\rline3"


def test_forward_stream_chunked_normalizes_crlf_across_chunk_boundaries() -> None:
    module = _load_module()

    class _ChunkedStream:
        def __init__(self) -> None:
            self._chunks = [b"line1\r", b"\nline2\r", b"line3"]

        def read(self, _size: int) -> bytes:
            if not self._chunks:
                return b""
            return self._chunks.pop(0)

    destination = io.BytesIO()
    module._forward_stream_chunked(
        _ChunkedStream(),
        destination,
        stop_event=threading.Event(),
    )

    assert destination.getvalue() == b"line1\nline2\rline3"
