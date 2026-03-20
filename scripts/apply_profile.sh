#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

dry_run="false"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      dry_run="true"
      shift
      ;;
    --help|-h)
      cat <<'EOF'
Usage: bash scripts/apply_profile.sh [--dry-run] [platform] [profile] [target-file]

Examples:
  bash scripts/apply_profile.sh macos b
  bash scripts/apply_profile.sh --dry-run docker c .env.docker
EOF
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
    *)
      break
      ;;
  esac
done

platform_input="${1:-macos}"
profile_input="${2:-b}"
target_file_input="${3:-}"

platform="$(printf '%s' "${platform_input}" | tr '[:upper:]' '[:lower:]')"
profile="$(printf '%s' "${profile_input}" | tr '[:upper:]' '[:lower:]')"

case "${platform}" in
  macos|linux|windows|docker) ;;
  *)
    echo "Unsupported platform: ${platform}. Expected one of: macos | linux | windows | docker" >&2
    exit 2
    ;;
esac

case "${profile}" in
  a|b|c|d) ;;
  *)
    echo "Unsupported profile: ${profile}. Expected one of: a | b | c | d" >&2
    exit 2
    ;;
esac

if [[ -n "${target_file_input}" ]]; then
  target_file="${target_file_input}"
elif [[ "${platform}" == "docker" ]]; then
  target_file="${PROJECT_ROOT}/.env.docker"
else
  target_file="${PROJECT_ROOT}/.env"
fi

base_env="${PROJECT_ROOT}/.env.example"
template_platform="${platform}"
if [[ "${template_platform}" == "linux" ]]; then
  echo "[profile] linux currently reuses the macos local profile template and fills a host DATABASE_URL." >&2
  template_platform="macos"
fi
override_env="${PROJECT_ROOT}/deploy/profiles/${template_platform}/profile-${profile}.env"

normalize_cli_path() {
  local raw_path="${1:-}"
  if [[ -z "${raw_path}" ]]; then
    printf '%s\n' "${raw_path}"
    return 0
  fi

  if [[ "${raw_path}" =~ ^[A-Za-z]:[\\/].* ]]; then
    if command -v cygpath >/dev/null 2>&1; then
      cygpath -u "${raw_path}"
      return 0
    fi
    if command -v wslpath >/dev/null 2>&1; then
      wslpath -u "${raw_path}"
      return 0
    fi
  fi

  printf '%s\n' "${raw_path//\\//}"
}

target_file="$(normalize_cli_path "${target_file}")"

log_info() {
  if [[ "${dry_run}" == "true" ]]; then
    printf '%s\n' "$*" >&2
    return 0
  fi
  printf '%s\n' "$*"
}

backup_target_file() {
  local file_path="$1"
  local backup_path="${file_path}.bak"
  cp "${file_path}" "${backup_path}"
  chmod 600 "${backup_path}" 2>/dev/null || true
  log_info "[backup] Existing ${file_path} saved to ${backup_path}"
}

set_env_value() {
  local file_path="$1"
  local key="$2"
  local value="$3"
  local tmp_file
  tmp_file="$(mktemp "${TMPDIR:-/tmp}/${file_path##*/}.XXXXXX")"
  awk -v key="${key}" -v value="${value}" '
    BEGIN { replaced = 0 }
    $0 ~ ("^[[:space:]]*" key "[[:space:]]*=") {
      if (!replaced) {
        print key "=" value
        replaced = 1
      }
      next
    }
    { print }
    END {
      if (!replaced) {
        print key "=" value
      }
    }
  ' "${file_path}" > "${tmp_file}"
  mv "${tmp_file}" "${file_path}"
  chmod 600 "${file_path}" 2>/dev/null || true
}

generate_random_mcp_api_key() {
  local generated=""

  if command -v openssl >/dev/null 2>&1; then
    generated="$(openssl rand -hex 24 2>/dev/null | tr -d '\r\n' || true)"
    if [[ -n "${generated}" ]]; then
      printf '%s\n' "${generated}"
      return 0
    fi
  fi

  local python_candidate
  for python_candidate in python3 python; do
    if ! command -v "${python_candidate}" >/dev/null 2>&1; then
      continue
    fi
    generated="$("${python_candidate}" -c 'import secrets; print(secrets.token_hex(24))' 2>/dev/null || true)"
    generated="$(printf '%s' "${generated}" | tr -d '\r\n')"
    if [[ -n "${generated}" ]]; then
      printf '%s\n' "${generated}"
      return 0
    fi
  done

  if command -v py >/dev/null 2>&1; then
    for python_candidate in "-3" ""; do
      if [[ -n "${python_candidate}" ]]; then
        generated="$(py "${python_candidate}" -c 'import secrets; print(secrets.token_hex(24))' 2>/dev/null || true)"
      else
        generated="$(py -c 'import secrets; print(secrets.token_hex(24))' 2>/dev/null || true)"
      fi
      generated="$(printf '%s' "${generated}" | tr -d '\r\n')"
      if [[ -n "${generated}" ]]; then
        printf '%s\n' "${generated}"
        return 0
      fi
    done
  fi

  echo "Failed to generate MCP_API_KEY: no usable openssl/python3/python/py runtime is available." >&2
  return 1
}

get_env_value() {
  local file_path="$1"
  local key="$2"
  local raw_value
  raw_value="$(
    awk -v key="${key}" '
      $0 ~ ("^[[:space:]]*" key "[[:space:]]*=") {
        line = $0
        sub("^[[:space:]]*" key "[[:space:]]*=[[:space:]]*", "", line)
        value = line
      }
      END { print value }
    ' "${file_path}"
  )"
  printf '%s\n' "${raw_value%$'\r'}"
}

trim_env_value() {
  local value="${1:-}"
  value="${value%$'\r'}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s\n' "${value}"
}

validate_database_url_placeholder() {
  local file_path="$1"
  local display_path="${2:-${file_path}}"
  local database_url_line=""
  database_url_line="$(
    awk '
      /^[[:space:]]*DATABASE_URL[[:space:]]*=/ {
        line = $0
      }
      END { print line }
    ' "${file_path}"
  )"
  database_url_line="${database_url_line%$'\r'}"
  if [[ -z "${database_url_line}" ]]; then
    return 0
  fi
  if [[ "${database_url_line}" == *"__REPLACE_ME__"* || "${database_url_line}" == *"<"*">"* ]] \
    || printf '%s\n' "${database_url_line}" | grep -Eq '[Pp][Ll][Aa][Cc][Ee][Hh][Oo][Ll][Dd][Ee][Rr]'; then
    {
      echo "Generated ${display_path}, but DATABASE_URL still contains unresolved placeholders:"
      echo "  ${database_url_line}"
      echo "Replace DATABASE_URL with a real host sqlite path before using this env file."
    } >&2
    return 1
  fi
}

ensure_default_env_value() {
  local file_path="$1"
  local key="$2"
  local default_value="$3"
  local current_value
  current_value="$(trim_env_value "$(get_env_value "${file_path}" "${key}")")"
  if [[ -n "${current_value}" ]]; then
    return 0
  fi
  set_env_value "${file_path}" "${key}" "${default_value}"
}

sync_docker_wal_overrides() {
  local file_path="$1"
  local wal_enabled
  local journal_mode
  wal_enabled="$(trim_env_value "$(get_env_value "${file_path}" "RUNTIME_WRITE_WAL_ENABLED")")"
  journal_mode="$(trim_env_value "$(get_env_value "${file_path}" "RUNTIME_WRITE_JOURNAL_MODE")")"
  if [[ -n "${wal_enabled}" ]]; then
    set_env_value "${file_path}" "MEMORY_PALACE_DOCKER_WAL_ENABLED" "${wal_enabled}"
  fi
  if [[ -n "${journal_mode}" ]]; then
    set_env_value "${file_path}" "MEMORY_PALACE_DOCKER_JOURNAL_MODE" "${journal_mode}"
  fi
}

resolve_windows_db_path() {
  local db_path="${PROJECT_ROOT}/demo.db"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -am "${db_path}"
    return 0
  fi
  case "${db_path}" in
    /mnt/[a-zA-Z]/*)
      printf '%s\n' "${db_path}" | sed -E 's#^/mnt/([a-zA-Z])/#\1:/#'
      return 0
      ;;
    /[a-zA-Z]/*)
      printf '%s\n' "${db_path}" | sed -E 's#^/([a-zA-Z])/#\1:/#'
      return 0
      ;;
  esac
  printf '%s\n' 'C:/memory_palace/demo.db'
}

dedupe_env_keys() {
  local file_path="$1"
  local key value
  while IFS= read -r key; do
    [[ -n "${key}" ]] || continue
    value="$(
      awk -v key="${key}" '
        $0 ~ ("^[[:space:]]*" key "[[:space:]]*=") {
          line = $0
          sub("^[[:space:]]*" key "[[:space:]]*=[[:space:]]*", "", line)
          value = line
        }
        END { print value }
      ' "${file_path}"
    )"
    set_env_value "${file_path}" "${key}" "${value}"
  done < <(
    awk '
      /^[[:space:]]*[A-Z0-9_]+[[:space:]]*=/ {
        line = $0
        sub(/^[[:space:]]*/, "", line)
        sub(/[[:space:]]*=.*$/, "", line)
        count[line]++
      }
      END { for (key in count) if (count[key] > 1) print key }
    ' "${file_path}" | sort
  )
}

validate_profile_placeholders() {
  local file_path="$1"
  local selected_profile="$2"
  local display_path="${3:-${file_path}}"
  if [[ "${selected_profile}" != "c" && "${selected_profile}" != "d" ]]; then
    return 0
  fi

  local -a unresolved_lines=()
  local line normalized_line
  while IFS= read -r line; do
    normalized_line="${line%$'\r'}"
    if [[ "${normalized_line}" =~ ^[[:space:]]*(ROUTER_API_BASE|RETRIEVAL_EMBEDDING_API_BASE|RETRIEVAL_RERANKER_API_BASE)[[:space:]]*=[[:space:]]*.*:PORT/ ]] \
      || [[ "${normalized_line}" =~ =[[:space:]]*(replace-with-your-key|your-embedding-model-id|your-reranker-model-id)([[:space:]]+#.*)?[[:space:]]*$ ]] \
      || [[ "${normalized_line}" =~ =[[:space:]]*https://router\.example\.com/ ]]; then
      unresolved_lines+=("${line}")
    fi
  done < "${file_path}"

  if [[ "${#unresolved_lines[@]}" -eq 0 ]]; then
    return 0
  fi

  {
    echo "Generated ${display_path}, but profile ${selected_profile} still contains unresolved placeholders:"
    printf '  %s\n' "${unresolved_lines[@]}"
    echo "Fill the placeholder values before using profile ${selected_profile}."
  } >&2
  return 1
}

if [[ ! -f "${base_env}" ]]; then
  echo "Missing base env template: ${base_env}" >&2
  exit 1
fi

if [[ ! -f "${override_env}" ]]; then
  echo "Missing profile template: ${override_env}" >&2
  exit 1
fi

staged_file="$(mktemp "${TMPDIR:-/tmp}/${target_file##*/}.staged.XXXXXX")"
cleanup_staged_file() {
  if [[ -n "${staged_file:-}" && -f "${staged_file}" ]]; then
    rm -f "${staged_file}"
  fi
}
trap cleanup_staged_file EXIT

cp "${base_env}" "${staged_file}"
{
  echo
  echo "# -----------------------------------------------------------------------------"
  echo "# Appended profile overrides (${platform}/profile-${profile})"
  echo "# -----------------------------------------------------------------------------"
  cat "${override_env}"
} >> "${staged_file}"
chmod 600 "${staged_file}" 2>/dev/null || true

if [[ "${platform}" == "macos" || "${platform}" == "linux" ]]; then
  if grep -Eq '^[[:space:]]*DATABASE_URL[[:space:]]*=[[:space:]]*sqlite\+aiosqlite:////Users/[^/]+/memory_palace/agent_memory\.db([[:space:]]+#.*)?[[:space:]]*\r?$' "${staged_file}"; then
    db_path="${PROJECT_ROOT}/demo.db"
    set_env_value "${staged_file}" "DATABASE_URL" "sqlite+aiosqlite:////${db_path#/}"
    log_info "[auto-fill] DATABASE_URL set to ${db_path}"
  fi
elif [[ "${platform}" == "windows" ]]; then
  if grep -Eq '^[[:space:]]*DATABASE_URL[[:space:]]*=[[:space:]]*sqlite\+aiosqlite:///[A-Za-z]:/memory_palace/agent_memory\.db([[:space:]]+#.*)?[[:space:]]*\r?$' "${staged_file}"; then
    if db_path="$(resolve_windows_db_path)"; then
      set_env_value "${staged_file}" "DATABASE_URL" "sqlite+aiosqlite:///${db_path}"
      log_info "[auto-fill] DATABASE_URL set to ${db_path}"
    fi
  fi
fi

if [[ "${platform}" == "docker" ]]; then
  current_mcp_api_key="$(get_env_value "${staged_file}" "MCP_API_KEY")"
  if [[ -z "${current_mcp_api_key}" ]]; then
    generated_mcp_api_key="$(generate_random_mcp_api_key)"
    set_env_value "${staged_file}" "MCP_API_KEY" "${generated_mcp_api_key}"
    log_info "[auto-fill] MCP_API_KEY generated for docker profile"
  fi
  sync_docker_wal_overrides "${staged_file}"
fi

ensure_default_env_value "${staged_file}" "RUNTIME_AUTO_FLUSH_ENABLED" "true"

dedupe_env_keys "${staged_file}"
validate_database_url_placeholder "${staged_file}" "${target_file}"
validate_profile_placeholders "${staged_file}" "${profile}" "${target_file}"

if [[ "${dry_run}" == "true" ]]; then
  cat "${staged_file}"
  exit 0
fi

if [[ -e "${target_file}" ]]; then
  backup_target_file "${target_file}"
fi

mv "${staged_file}" "${target_file}"
chmod 600 "${target_file}" 2>/dev/null || true
staged_file=""

log_info "Generated ${target_file} from ${override_env}"
