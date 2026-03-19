#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
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
  "${VENV_PYTHON}" - "${file_path}" "${key}" <<'PY'
from dotenv import dotenv_values
import sys

file_path, key = sys.argv[1], sys.argv[2]
value = dotenv_values(file_path).get(key)
if value is not None:
    print(value, end="")
PY
}

normalize_database_url() {
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

is_docker_internal_database_url() {
  local value
  value="$(normalize_database_url "${1:-}")"
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

runtime_database_url="$(normalize_database_url "${DATABASE_URL:-}")"
effective_database_url="${runtime_database_url}"
if [[ -z "${runtime_database_url}" && -f "${ENV_FILE}" ]]; then
  effective_database_url="$(normalize_database_url "$(read_env_value "${ENV_FILE}" "DATABASE_URL")")"
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
if [[ -z "$(normalize_database_url "${DATABASE_URL:-}")" && ! -f "${ENV_FILE}" ]]; then
  if [[ -f "${DOCKER_ENV_FILE}" ]]; then
    echo "Refusing to fall back to demo.db while ${DOCKER_ENV_FILE} exists." >&2
    echo "The repo-local stdio wrapper does not reuse Docker's /app/data database path." >&2
    echo "Create a local .env for the SQLite file you want, or connect your client to the Docker /sse endpoint instead." >&2
    exit 1
  fi
  export DATABASE_URL="sqlite+aiosqlite:////${DEFAULT_DB_PATH#/}"
fi
export RETRIEVAL_REMOTE_TIMEOUT_SEC="${RETRIEVAL_REMOTE_TIMEOUT_SEC:-8}"

exec "${VENV_PYTHON}" mcp_server.py
