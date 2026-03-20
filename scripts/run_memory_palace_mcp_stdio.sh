#!/usr/bin/env bash
set -euo pipefail

resolve_script_path() {
  local source_path="${1:-}"
  if [[ -z "${source_path}" ]]; then
    return 1
  fi

  while [[ -h "${source_path}" ]]; do
    local source_dir
    source_dir="$(cd -P -- "$(dirname -- "${source_path}")" && pwd)"
    local linked_path
    linked_path="$(readlink "${source_path}")"
    if [[ "${linked_path}" != /* ]]; then
      source_path="${source_dir}/${linked_path}"
    else
      source_path="${linked_path}"
    fi
  done

  local resolved_dir
  resolved_dir="$(cd -P -- "$(dirname -- "${source_path}")" && pwd)"
  printf '%s\n' "${resolved_dir}/$(basename -- "${source_path}")"
}

SCRIPT_PATH="$(resolve_script_path "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd -P -- "$(dirname -- "${SCRIPT_PATH}")" && pwd)"
PROJECT_ROOT="$(cd -P -- "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
POSIX_VENV_PYTHON="${BACKEND_DIR}/.venv/bin/python"
WINDOWS_VENV_PYTHON="${BACKEND_DIR}/.venv/Scripts/python.exe"
ENV_FILE="${PROJECT_ROOT}/.env"
DOCKER_ENV_FILE="${PROJECT_ROOT}/.env.docker"
DEFAULT_DB_PATH="${PROJECT_ROOT}/demo.db"
DOCKER_INTERNAL_SQLITE_PREFIXES=("/app/" "/data/")

read_env_value() {
  local file_path="$1"
  local key="$2"
  if [[ ! -f "${file_path}" ]]; then
    return 0
  fi
  local -a parser_candidates=()
  if [[ -n "${VENV_PYTHON:-}" ]]; then
    parser_candidates+=("${VENV_PYTHON}")
  fi
  local parser_candidate
  for parser_candidate in python3 python; do
    if command -v "${parser_candidate}" >/dev/null 2>&1; then
      parser_candidates+=("${parser_candidate}")
    fi
  done

  local parsed_value=""
  for parser_candidate in "${parser_candidates[@]}"; do
    parsed_value="$("${parser_candidate}" - "${file_path}" "${key}" <<'PY' 2>/dev/null || true
import sys

file_path, key = sys.argv[1], sys.argv[2]
try:
    from dotenv import dotenv_values  # type: ignore
except Exception:
    dotenv_values = None


def fallback_read_env(path: str, target_key: str):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return None

    last_value = None
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        current_key, current_value = line.split("=", 1)
        if current_key.strip() != target_key:
            continue
        value = current_value.strip()
        if len(value) >= 2 and value[:1] == value[-1:] and value[:1] in {"'", '"'}:
            value = value[1:-1]
        last_value = value
    return last_value


value = None
if dotenv_values is not None:
    try:
        value = dotenv_values(file_path).get(key)
    except Exception:
        value = None

if value is None:
    value = fallback_read_env(file_path, key)

if value is not None:
    print(value, end="")
PY
)"
    parsed_value="${parsed_value%$'\r'}"
    if [[ -n "${parsed_value}" ]]; then
      printf '%s' "${parsed_value}"
      return 0
    fi
  done
}

normalize_env_value() {
  local value="${1:-}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  if [[ "${#value}" -ge 2 ]]; then
    if [[ "${value:0:1}" == "\"" && "${value: -1}" == "\"" ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
      value="${value:1:${#value}-2}"
    fi
  fi
  printf '%s' "${value}"
}

format_sqlite_absolute_url() {
  local absolute_path="${1:-}"
  while [[ "${absolute_path}" == /* ]]; do
    absolute_path="${absolute_path#/}"
  done
  printf 'sqlite+aiosqlite:////%s' "${absolute_path}"
}

is_docker_internal_database_url() {
  local value
  value="$(normalize_env_value "${1:-}")"
  local prefix
  for prefix in "${DOCKER_INTERNAL_SQLITE_PREFIXES[@]}"; do
    case "${value}" in
      "sqlite+aiosqlite:///${prefix}"*|"sqlite+aiosqlite://${prefix}"*)
        return 0
        ;;
    esac
  done
  return 1
}

VENV_PYTHON=""
if [[ -x "${POSIX_VENV_PYTHON}" ]]; then
  VENV_PYTHON="${POSIX_VENV_PYTHON}"
elif [[ -x "${WINDOWS_VENV_PYTHON}" ]]; then
  VENV_PYTHON="${WINDOWS_VENV_PYTHON}"
fi

if [[ -z "${VENV_PYTHON}" ]]; then
  echo "Missing backend virtualenv python: ${POSIX_VENV_PYTHON} or ${WINDOWS_VENV_PYTHON}" >&2
  exit 1
fi

cd "${BACKEND_DIR}"

runtime_database_url="$(normalize_env_value "${DATABASE_URL:-}")"
effective_database_url="${runtime_database_url}"
if [[ -z "${runtime_database_url}" && -f "${ENV_FILE}" ]]; then
  effective_database_url="$(normalize_env_value "$(read_env_value "${ENV_FILE}" "DATABASE_URL")")"
  if [[ -n "${effective_database_url}" ]]; then
    export DATABASE_URL="${effective_database_url}"
  fi
fi

if is_docker_internal_database_url "${effective_database_url}"; then
  echo "Refusing to start repo-local stdio MCP with Docker-internal DATABASE_URL: ${effective_database_url}" >&2
  echo "The current .env points to a container-only sqlite path (for example /app/... or /data/...)." >&2
  echo "For local stdio, regenerate .env with 'bash scripts/apply_profile.sh macos b' or set DATABASE_URL to a host absolute path." >&2
  echo "If you want the containerized database/service, connect your client to the Docker /sse endpoint instead." >&2
  exit 1
fi

# Reuse the repo's configured DATABASE_URL when .env exists so MCP clients and
# the Dashboard/API keep talking to the same SQLite file. Fall back to demo.db
# only for a minimal no-.env local boot.
if [[ -z "$(normalize_env_value "${DATABASE_URL:-}")" && ! -f "${ENV_FILE}" ]]; then
  if [[ -f "${DOCKER_ENV_FILE}" ]]; then
    echo "Refusing to fall back to demo.db while ${DOCKER_ENV_FILE} exists." >&2
    echo "The repo-local stdio wrapper does not reuse Docker's /app/data database path." >&2
    echo "Create a local .env for the SQLite file you want, or connect your client to the Docker /sse endpoint instead." >&2
    exit 1
  fi
  export DATABASE_URL="$(format_sqlite_absolute_url "${DEFAULT_DB_PATH}")"
fi

runtime_remote_timeout="$(normalize_env_value "${RETRIEVAL_REMOTE_TIMEOUT_SEC:-}")"
if [[ -z "${runtime_remote_timeout}" && -f "${ENV_FILE}" ]]; then
  runtime_remote_timeout="$(normalize_env_value "$(read_env_value "${ENV_FILE}" "RETRIEVAL_REMOTE_TIMEOUT_SEC")")"
fi
if [[ -n "${runtime_remote_timeout}" ]]; then
  export RETRIEVAL_REMOTE_TIMEOUT_SEC="${runtime_remote_timeout}"
else
  export RETRIEVAL_REMOTE_TIMEOUT_SEC="8"
fi

exec "${VENV_PYTHON}" mcp_server.py
