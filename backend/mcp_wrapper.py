#!/usr/bin/env python
"""
Cross-platform repo-local MCP wrapper.

This wrapper exists for IDE hosts and native Windows flows that need a Python
entrypoint instead of the bash launcher. It also keeps the runtime behavior
aligned with scripts/run_memory_palace_mcp_stdio.sh:

- reuse the repo .env / DATABASE_URL when present
- reject Docker-internal sqlite database paths such as /app/... or /data/...
- fall back to demo.db only when neither .env nor .env.docker exists
- run the backend with the repo-local virtualenv interpreter
- normalize CRLF on stdio for hosts with Windows line-ending quirks
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import List, Tuple

from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
ENV_FILE = PROJECT_ROOT / ".env"
DOCKER_ENV_FILE = PROJECT_ROOT / ".env.docker"
DEFAULT_DB_PATH = PROJECT_ROOT / "demo.db"
WINDOWS_VENV_PYTHON = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
POSIX_VENV_PYTHON = BACKEND_DIR / ".venv" / "bin" / "python"
DOCKER_INTERNAL_SQLITE_PREFIXES = ("/app/", "/data/")


def read_env_value(file_path: Path, key: str) -> str:
    if not file_path.is_file():
        return ""
    parsed = dotenv_values(file_path)
    value = parsed.get(key)
    if value is None:
        return ""
    return str(value)


def _normalize_env_string_value(value: str | None) -> str:
    normalized = (value or "").strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {'"', "'"}:
        normalized = normalized[1:-1]
    return normalized.strip()


def is_docker_internal_database_url(value: str | None) -> bool:
    normalized = _normalize_env_string_value(value)
    return any(
        normalized.startswith(f"sqlite+aiosqlite:///{prefix}")
        or normalized.startswith(f"sqlite+aiosqlite://{prefix}")
        for prefix in DOCKER_INTERNAL_SQLITE_PREFIXES
    )


def sqlite_database_url(path: Path) -> str:
    normalized = path.resolve().as_posix()
    return f"sqlite+aiosqlite:///{normalized}"


def resolve_backend_python() -> Path:
    candidates = (
        (WINDOWS_VENV_PYTHON, POSIX_VENV_PYTHON)
        if os.name == "nt"
        else (POSIX_VENV_PYTHON, WINDOWS_VENV_PYTHON)
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SystemExit(
        "Missing backend virtualenv python: "
        f"{WINDOWS_VENV_PYTHON} or {POSIX_VENV_PYTHON}"
    )


def build_runtime_env() -> dict[str, str]:
    runtime_env = os.environ.copy()
    effective_database_url = _normalize_env_string_value(
        runtime_env.get("DATABASE_URL", "")
    )
    if not effective_database_url and ENV_FILE.is_file():
        effective_database_url = _normalize_env_string_value(
            read_env_value(ENV_FILE, "DATABASE_URL")
        )
        if effective_database_url:
            runtime_env["DATABASE_URL"] = effective_database_url

    runtime_remote_timeout = str(
        runtime_env.get("RETRIEVAL_REMOTE_TIMEOUT_SEC", "")
    ).strip()
    if not runtime_remote_timeout and ENV_FILE.is_file():
        runtime_remote_timeout = _normalize_env_string_value(
            read_env_value(ENV_FILE, "RETRIEVAL_REMOTE_TIMEOUT_SEC")
        )
        if runtime_remote_timeout:
            runtime_env["RETRIEVAL_REMOTE_TIMEOUT_SEC"] = runtime_remote_timeout

    if is_docker_internal_database_url(effective_database_url):
        print(
            "Refusing to start repo-local stdio MCP with Docker-internal DATABASE_URL: "
            f"{_normalize_env_string_value(effective_database_url)}",
            file=sys.stderr,
        )
        print(
            "The current .env points to a container-only sqlite path "
            "(for example /app/... or /data/...).",
            file=sys.stderr,
        )
        print(
            "For local stdio, regenerate .env with 'bash scripts/apply_profile.sh macos b' "
            "or '.\\scripts\\apply_profile.ps1 -Platform windows -Profile b', or set "
            "DATABASE_URL to a host absolute path.",
            file=sys.stderr,
        )
        print(
            "If you want the containerized database/service, connect your client to the Docker "
            "/sse endpoint instead.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    has_runtime_database_url = bool(
        _normalize_env_string_value(runtime_env.get("DATABASE_URL", ""))
    )
    if not has_runtime_database_url and not ENV_FILE.is_file():
        if DOCKER_ENV_FILE.is_file():
            print(
                f"Refusing to fall back to demo.db while {DOCKER_ENV_FILE} exists.",
                file=sys.stderr,
            )
            print(
                "The repo-local stdio wrapper does not reuse Docker's /app/data database path.",
                file=sys.stderr,
            )
            print(
                "Create a local .env for the SQLite file you want, or connect your client to the "
                "Docker /sse endpoint instead.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        runtime_env["DATABASE_URL"] = sqlite_database_url(DEFAULT_DB_PATH)

    runtime_env["RETRIEVAL_REMOTE_TIMEOUT_SEC"] = (
        runtime_remote_timeout or "8"
    )
    runtime_env.setdefault("PYTHONIOENCODING", "utf-8")
    runtime_env.setdefault("PYTHONUTF8", "1")
    return runtime_env


def spawn_backend_process() -> subprocess.Popen[bytes]:
    backend_python = resolve_backend_python()
    runtime_env = build_runtime_env()
    mcp_server_path = BACKEND_DIR / "mcp_server.py"
    try:
        return subprocess.Popen(
            [str(backend_python), str(mcp_server_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            bufsize=0,
            cwd=str(BACKEND_DIR),
            env=runtime_env,
        )
    except OSError as exc:
        print(f"Failed to start MCP server: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


_IO_CHUNK_SIZE = 4096


def _read_stream_chunk(stream) -> bytes:
    read1 = getattr(stream, "read1", None)
    if callable(read1):
        return read1(_IO_CHUNK_SIZE)
    return stream.read(_IO_CHUNK_SIZE)


def _forward_stream_chunked(source, destination, *, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        data = _read_stream_chunk(source)
        if not data:
            break
        cleaned = data.replace(b"\r", b"")
        if not cleaned:
            continue
        destination.write(cleaned)
        destination.flush()


def main() -> None:
    process = spawn_backend_process()

    io_errors: List[Tuple[str, str]] = []
    stop_forwarding = threading.Event()

    def record_io_error(channel: str, exc: Exception) -> None:
        io_errors.append((channel, str(exc)))
        stop_forwarding.set()

    def forward_stdin() -> None:
        try:
            if process.stdin is not None:
                _forward_stream_chunked(
                    sys.stdin.buffer, process.stdin, stop_event=stop_forwarding
                )
        except Exception as exc:  # pragma: no cover
            record_io_error("stdin", exc)
        finally:
            try:
                if process.stdin is not None:
                    process.stdin.close()
            except Exception:  # pragma: no cover
                pass

    def forward_stdout() -> None:
        try:
            if process.stdout is not None:
                _forward_stream_chunked(
                    process.stdout, sys.stdout.buffer, stop_event=stop_forwarding
                )
        except Exception as exc:  # pragma: no cover
            record_io_error("stdout", exc)

    stdin_thread = threading.Thread(target=forward_stdin, daemon=True)
    stdout_thread = threading.Thread(target=forward_stdout, daemon=True)
    stdin_thread.start()
    stdout_thread.start()

    process.wait()
    stop_forwarding.set()
    stdout_thread.join(timeout=1)
    stdin_thread.join(timeout=1)

    return_code = int(process.returncode or 0)
    if io_errors:
        channel, message = io_errors[0]
        print(f"Wrapper I/O error ({channel}): {message}", file=sys.stderr)
        if return_code == 0:
            return_code = 1
    sys.exit(return_code)


if __name__ == "__main__":
    main()
