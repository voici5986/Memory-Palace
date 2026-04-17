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
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import List, Tuple

try:
    from dotenv import dotenv_values
except Exception:  # pragma: no cover
    dotenv_values = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
ENV_FILE = PROJECT_ROOT / ".env"
DOCKER_ENV_FILE = PROJECT_ROOT / ".env.docker"
DEFAULT_DB_PATH = PROJECT_ROOT / "demo.db"
WINDOWS_VENV_PYTHON = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
POSIX_VENV_PYTHON = BACKEND_DIR / ".venv" / "bin" / "python"
DOCKER_INTERNAL_SQLITE_PREFIXES = ("/app/", "/data/")
_LOCAL_NO_PROXY_HOSTS = ("localhost", "127.0.0.1", "::1", "host.docker.internal")

_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _read_env_value_without_dotenv(file_path: Path, key: str) -> str:
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""

    last_value = ""
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in raw_line:
            continue
        raw_key, raw_value = raw_line.split("=", 1)
        candidate_key = raw_key.strip()
        if not _ENV_KEY_RE.match(candidate_key) or candidate_key != key:
            continue
        candidate_value = raw_value.strip()
        if not candidate_value:
            last_value = ""
            continue
        if candidate_value[0] in {'"', "'"}:
            quote = candidate_value[0]
            closing_idx = candidate_value.find(quote, 1)
            if closing_idx > 0:
                last_value = candidate_value[1:closing_idx]
                continue
        comment_idx = len(candidate_value)
        for marker in (" #", "\t#", "  #"):
            idx = candidate_value.find(marker)
            if idx != -1:
                comment_idx = min(comment_idx, idx)
        last_value = candidate_value[:comment_idx].strip()
    return last_value


def read_env_value(file_path: Path, key: str) -> str:
    if not file_path.is_file():
        return ""
    if dotenv_values is not None:
        try:
            parsed = dotenv_values(file_path)
            value = parsed.get(key)
            if value is not None:
                return str(value)
        except Exception:
            pass
    return _read_env_value_without_dotenv(file_path, key)


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


def _csv_list_contains_case_insensitive(csv: str, item: str) -> bool:
    normalized_item = _normalize_env_string_value(item)
    if not normalized_item:
        return True
    target = normalized_item.lower()
    for entry in csv.split(","):
        if _normalize_env_string_value(entry).lower() == target:
            return True
    return False


def _append_csv_item_if_missing(csv: str, item: str) -> str:
    normalized_item = _normalize_env_string_value(item)
    if not normalized_item or _csv_list_contains_case_insensitive(csv, normalized_item):
        return csv
    if csv:
        return f"{csv},{normalized_item}"
    return normalized_item


def _merge_local_no_proxy_defaults(*values: str | None) -> str:
    merged = ""
    for value in values:
        normalized_value = _normalize_env_string_value(value)
        if not normalized_value:
            continue
        for entry in normalized_value.split(","):
            merged = _append_csv_item_if_missing(merged, entry)
    for host in _LOCAL_NO_PROXY_HOSTS:
        merged = _append_csv_item_if_missing(merged, host)
    return merged


def _prefer_windows_venv_layout() -> bool:
    if os.name == "nt":
        return True

    platform_value = str(sys.platform or "").strip().lower()
    return platform_value == "cygwin" or platform_value.startswith("msys")


def resolve_backend_python() -> Path:
    candidates = (
        (WINDOWS_VENV_PYTHON, POSIX_VENV_PYTHON)
        if _prefer_windows_venv_layout()
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

    if not effective_database_url and ENV_FILE.is_file():
        print(
            f"Refusing to start repo-local stdio MCP because {ENV_FILE} exists but DATABASE_URL is empty.",
            file=sys.stderr,
        )
        print(
            "Set DATABASE_URL to a host absolute path, regenerate .env with "
            "'bash scripts/apply_profile.sh macos b' or '.\\scripts\\apply_profile.ps1 "
            "-Platform windows -Profile b', or remove the empty entry before retrying.",
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
    merged_no_proxy = _merge_local_no_proxy_defaults(
        runtime_env.get("NO_PROXY", ""),
        runtime_env.get("no_proxy", ""),
    )
    runtime_env["NO_PROXY"] = merged_no_proxy
    runtime_env["no_proxy"] = merged_no_proxy
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
    pending_cr = False
    while not stop_event.is_set():
        data = _read_stream_chunk(source)
        if not data:
            break
        if pending_cr:
            data = b"\r" + data
            pending_cr = False
        if data.endswith(b"\r"):
            data = data[:-1]
            pending_cr = True
        destination.write(data.replace(b"\r\n", b"\n"))
        destination.flush()
    if pending_cr and not stop_event.is_set():
        destination.write(b"\r")
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
