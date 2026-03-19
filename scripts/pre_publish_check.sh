#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

EXIT_CODE=0
WARNINGS=0
PYTHON_CMD=""
PYTHON_PROJECT_ROOT=""

print_section() {
  printf "\n[%s]\n" "$1"
}

fail() {
  echo "FAIL: $*"
  EXIT_CODE=1
}

warn() {
  echo "WARN: $*"
  WARNINGS=$((WARNINGS + 1))
}

pass() {
  echo "PASS: $*"
}

resolve_python_cmd() {
  if [[ -n "${PYTHON_CMD}" ]]; then
    printf '%s\n' "${PYTHON_CMD}"
    return 0
  fi

  local candidate
  for candidate in python3 python; do
    local resolved
    resolved="$(command -v "${candidate}" 2>/dev/null || true)"
    if [[ -z "${resolved}" ]]; then
      continue
    fi

    local normalized
    normalized="$(printf '%s' "${resolved}" | tr '[:upper:]' '[:lower:]')"
    if [[ "${normalized}" == *"/windowsapps/"* ]]; then
      continue
    fi

    if [[ -x "${resolved}" || "${resolved}" == "${candidate}" || "${resolved}" == */python* ]]; then
      PYTHON_CMD="${candidate}"
      printf '%s\n' "${PYTHON_CMD}"
      return 0
    fi
  done

  fail "未找到 python3/python，无法执行当前发布前检查"
  return 1
}

resolve_python_project_root() {
  if [[ -n "${PYTHON_PROJECT_ROOT}" ]]; then
    printf '%s\n' "${PYTHON_PROJECT_ROOT}"
    return 0
  fi

  if command -v cygpath >/dev/null 2>&1; then
    PYTHON_PROJECT_ROOT="$(cygpath -w "${PROJECT_ROOT}")"
  else
    PYTHON_PROJECT_ROOT="${PROJECT_ROOT}"
  fi

  printf '%s\n' "${PYTHON_PROJECT_ROOT}"
}

build_personal_path_scan_regex() {
  local python_cmd
  python_cmd="$(resolve_python_cmd)" || return 1

  MSYS2_ARG_CONV_EXCL="*" "${python_cmd}" - <<'PY'
import os
import re
import subprocess


def add_candidate(bucket: list[str], raw: str) -> None:
    value = raw.strip()
    if value and value not in bucket:
        bucket.append(value)


def regex_literal(value: str) -> str:
    return re.escape(value).replace("\\", "\\\\")


candidates: list[str] = []
for raw in (os.environ.get("USERNAME", ""), os.environ.get("USER", "")):
    add_candidate(candidates, raw)

try:
    current_user = subprocess.run(
        ["id", "-un"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout
except Exception:
    current_user = ""
add_candidate(candidates, current_user)

home = os.environ.get("HOME", "").replace("\\", "/").rstrip("/")
if home:
    add_candidate(candidates, home.rsplit("/", 1)[-1])

parts: list[str] = []
for candidate in candidates:
    parts.extend(
        [
            regex_literal(f"/Users/{candidate}"),
            regex_literal(f"C:/Users/{candidate}"),
            regex_literal(f"file:///Users/{candidate}"),
            regex_literal(f"file:///C:/Users/{candidate}"),
        ]
    )

print("|".join(parts))
PY
}

check_local_artifacts() {
  local -a paths=(
    ".env"
    ".venv"
    ".claude"
    ".codex"
    ".cursor"
    ".opencode"
    ".gemini"
    ".agent"
    ".mcp.json"
    ".mcp.json.bak"
    ".playwright-cli"
    ".tmp"
    ".pytest_cache"
    "demo.db"
    "snapshots"
    "backups"
    "backend/backend.log"
    "frontend/frontend.log"
    "backend/.pytest_cache"
    "backend/tests/benchmark/.real_profile_cache"
    "frontend/node_modules"
    "frontend/dist"
    "docs/skills/TRIGGER_SMOKE_REPORT.md"
    "docs/skills/MCP_LIVE_E2E_REPORT.md"
    "docs/skills/CLAUDE_SKILLS_AUDIT.md"
  )
  local -a glob_paths=(
    ".env.*"
    "backend/*.db"
    "backend/*.sqlite"
    "backend/*.sqlite3"
  )

  local found_any=0
  local path
  for path in "${paths[@]}"; do
    if [[ -e "${path}" ]]; then
      warn "本地文件存在（上传前建议移除或确认未纳入提交）: ${path}"
      found_any=1
    fi
  done

  local pattern match
  for pattern in "${glob_paths[@]}"; do
    while IFS= read -r match; do
      [[ -n "${match}" ]] || continue
      if [[ "${match}" == ".env.example" ]]; then
        continue
      fi
      warn "本地文件存在（上传前建议移除或确认未纳入提交）: ${match}"
      found_any=1
    done < <(compgen -G "${pattern}" || true)
  done

  if [[ "${found_any}" -eq 0 ]]; then
    pass "未发现高风险本地产物目录"
  fi
}

check_tracked_forbidden_paths() {
  local -a pathspecs=(
    ".env"
    ".env.*"
    ".venv"
    ".claude"
    ".codex"
    ".cursor"
    ".opencode"
    ".gemini"
    ".agent"
    ".mcp.json"
    ".mcp.json.bak"
    ".playwright-cli"
    ".tmp"
    ".pytest_cache"
    "demo.db"
    "snapshots"
    "backups"
    "backend/backend.log"
    "frontend/frontend.log"
    "backend/.pytest_cache"
    "backend/tests/benchmark/.real_profile_cache"
    "frontend/node_modules"
    "frontend/dist"
    "docs/skills/TRIGGER_SMOKE_REPORT.md"
    "docs/skills/MCP_LIVE_E2E_REPORT.md"
    "docs/skills/CLAUDE_SKILLS_AUDIT.md"
    "backend/*.db"
    "backend/*.sqlite"
    "backend/*.sqlite3"
  )

  local hit=0
  local tracked
  while IFS= read -r tracked; do
    [[ -n "${tracked}" ]] || continue
    if [[ "${tracked}" == ".env.example" ]]; then
      continue
    fi
    fail "以下敏感/本地产物已被跟踪，请先移出版本库: ${tracked}"
    hit=1
  done < <(git ls-files -- "${pathspecs[@]}" || true)

  if [[ "${hit}" -eq 0 ]]; then
    pass "敏感本地产物未被跟踪"
  fi
}

check_untracked_unignored_files() {
  local -a hits=()
  local item
  while IFS= read -r item; do
    [[ -n "${item}" ]] || continue
    hits+=("${item}")
  done < <(git ls-files --others --exclude-standard)

  if [[ "${#hits[@]}" -gt 0 ]]; then
    local path
    for path in "${hits[@]}"; do
      warn "发现未跟踪且未忽略的文件（上传前请确认是否需要加入 .gitignore 或移走）: ${path}"
    done
  else
    pass "未发现未跟踪且未忽略的文件"
  fi
}

collect_existing_tracked_files() {
  local file
  while IFS= read -r -d '' file; do
    if [[ -f "${file}" ]]; then
      printf '%s\0' "${file}"
    fi
  done < <(git ls-files -z)
}

is_scan_target_excluded() {
  local scan_key="$1"
  local file="$2"

  case "${scan_key}:${file}" in
    secret_scan:scripts/pre_publish_check.sh)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

collect_scannable_tracked_files() {
  local scan_key="$1"
  local file
  while IFS= read -r -d '' file; do
    if is_scan_target_excluded "${scan_key}" "${file}"; then
      continue
    fi
    printf '%s\0' "${file}"
  done < <(collect_existing_tracked_files)
}

scan_tracked_files() {
  local scan_key="$1"
  local label="$2"
  local regex="$3"
  local python_cmd
  local python_root
  python_cmd="$(resolve_python_cmd)" || return
  python_root="$(resolve_python_project_root)" || return

  local output
  output="$(
    MSYS2_ARG_CONV_EXCL="*" "${python_cmd}" - "${python_root}" "${scan_key}" "${regex}" <<'PY'
import re
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
scan_key = sys.argv[2]
pattern = re.compile(sys.argv[3], re.MULTILINE)
tracked_output = subprocess.run(
    ["git", "-C", str(root), "ls-files", "-z"],
    check=True,
    capture_output=True,
).stdout.split(b"\0")
hits = set()

for item in tracked_output:
    if not item:
        continue
    relative = item.decode("utf-8", "replace")
    if scan_key == "secret_scan" and relative == "scripts/pre_publish_check.sh":
        continue
    path = root / relative
    if not path.is_file():
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    if scan_key == "personal_path_scan":
        text = text.replace("\\", "/")
    if pattern.search(text):
        hits.add(relative)

if hits:
    print("\n".join(sorted(hits)))
PY
  )" || {
    fail "${label} 扫描执行失败"
    return
  }

  local -a hits=()
  while IFS= read -r line; do
    [[ -n "${line}" ]] && hits+=("${line}")
  done <<< "${output}"

  if [[ "${#hits[@]}" -gt 0 ]]; then
    fail "${label} 命中以下文件："
    printf '  - %s\n' "${hits[@]}"
  else
    pass "${label} 未命中"
  fi
}

check_env_example_api_keys() {
  if [[ ! -f ".env.example" ]]; then
    fail "缺少 .env.example"
    return
  fi

  local python_cmd
  local python_root
  python_cmd="$(resolve_python_cmd)" || return
  python_root="$(resolve_python_project_root)" || return

  local output
  output="$(
    MSYS2_ARG_CONV_EXCL="*" "${python_cmd}" - "${python_root}" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1]).resolve() / ".env.example"
if not path.is_file():
    print("__MISSING__")
    raise SystemExit(0)

pattern = re.compile(r"^([A-Z0-9_]*API_KEY)=(.*)$")
hits = []
for lineno, raw_line in enumerate(
    path.read_text(encoding="utf-8", errors="replace").splitlines(),
    start=1,
):
    line = raw_line.rstrip("\r")
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        continue
    match = pattern.match(line)
    if not match:
        continue
    if match.group(2).strip():
        hits.append(f"{lineno}:{line}")

if hits:
    print("\n".join(hits))
PY
  )" || {
    fail ".env.example 占位检查执行失败"
    return
  }

  if [[ "${output}" == "__MISSING__" ]]; then
    fail "缺少 .env.example"
    return
  fi

  local -a hits=()
  while IFS= read -r line; do
    [[ -n "${line}" ]] && hits+=("${line}")
  done <<< "${output}"

  if [[ "${#hits[@]}" -gt 0 ]]; then
    fail ".env.example 中发现非空 API_KEY，请改为空值占位"
    printf '  - %s\n' "${hits[@]}"
  else
    pass ".env.example 的 API_KEY 均为空占位"
  fi
}

check_required_public_files_tracked() {
  local -a required_paths=(
    "backend/tests/benchmark/baseline_manifest.md"
    "backend/tests/benchmark/thresholds_v1.json"
  )
  local path
  local hit=0
  for path in "${required_paths[@]}"; do
    if [[ ! -f "${path}" ]]; then
      fail "缺少公开仓必须包含的文件: ${path}"
      hit=1
      continue
    fi
    if ! git ls-files --error-unmatch "${path}" >/dev/null 2>&1; then
      fail "公开仓必须包含的文件尚未被跟踪: ${path}"
      hit=1
    fi
  done

  if [[ "${hit}" -eq 0 ]]; then
    pass "公开 benchmark 基线文件存在且已被跟踪"
  fi
}

check_public_doc_local_references_tracked() {
  local python_cmd
  local python_root
  python_cmd="$(resolve_python_cmd)" || return
  python_root="$(resolve_python_project_root)" || return

  local issues
  issues="$(
    MSYS2_ARG_CONV_EXCL="*" "${python_cmd}" - "${python_root}" <<'PY'
import re
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
tracked_output = subprocess.run(
    ["git", "-C", str(root), "ls-files", "-z"],
    check=True,
    capture_output=True,
).stdout.split(b"\0")
tracked = set(tracked_output)
docs = [
    item.decode("utf-8")
    for item in tracked_output
    if item
    and (
        item.decode("utf-8") in {"README.md", "README_CN.md"}
        or (item.decode("utf-8").startswith("docs/") and item.decode("utf-8").endswith(".md"))
    )
]
markdown_link = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
html_src = re.compile(r"""src=["']([^"']+)["']""")
issues = set()

def normalize_target(raw: str) -> str:
    target = raw.strip()
    if not target:
        return ""
    if target.startswith(("http://", "https://", "mailto:", "#", "data:")):
        return ""
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    target = target.split("#", 1)[0].strip()
    return target

for doc in docs:
    doc_path = root / doc
    text = doc_path.read_text(encoding="utf-8")
    for raw in markdown_link.findall(text) + html_src.findall(text):
        target = normalize_target(raw)
        if not target:
            continue
        resolved = (doc_path.parent / target).resolve()
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError:
            continue
        if not resolved.exists():
            issues.add(f"MISSING {doc} -> {relative}")
        elif relative.encode("utf-8") not in tracked:
            issues.add(f"UNTRACKED {doc} -> {relative}")

if issues:
    print("\n".join(sorted(issues)))
PY
  )"

  if [[ -n "${issues}" ]]; then
    fail "公开文档引用了缺失或未跟踪的本地文件："
    printf '  - %s\n' "${issues}"
  else
    pass "公开文档引用的本地文件均存在且已被跟踪"
  fi
}

print_section "1) 本地敏感产物检查"
check_local_artifacts

print_section "2) Git 跟踪状态检查"
check_tracked_forbidden_paths

print_section "3) 未跟踪未忽略文件检查"
check_untracked_unignored_files

print_section "4) 密钥模式扫描（仅扫描已跟踪文件）"
scan_tracked_files \
  "secret_scan" \
  "密钥/凭证模式" \
  'BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{16,}|AIza[0-9A-Za-z_-]{35}|-----BEGIN PGP PRIVATE KEY BLOCK-----'

PERSONAL_PATH_SCAN_REGEX="$(build_personal_path_scan_regex || true)"
if [[ -n "${PERSONAL_PATH_SCAN_REGEX}" ]]; then
  print_section "5) 个人路径泄露扫描（仅扫描已跟踪文件）"
  scan_tracked_files \
    "personal_path_scan" \
    "个人绝对路径（当前环境）" \
    "${PERSONAL_PATH_SCAN_REGEX}"
fi

print_section "6) .env.example 占位检查"
check_env_example_api_keys

print_section "7) 公开基线文件检查"
check_required_public_files_tracked

print_section "8) 公开文档引用检查"
check_public_doc_local_references_tracked

echo
if [[ "${EXIT_CODE}" -ne 0 ]]; then
  echo "RESULT: FAIL"
  echo "建议先执行：git status --short，并清理上面列出的命中项后再上传。"
  exit "${EXIT_CODE}"
fi

echo "RESULT: PASS"
if [[ "${WARNINGS}" -gt 0 ]]; then
  echo "注意：存在 ${WARNINGS} 个警告项（通常是本地文件存在但未被跟踪）。"
fi
echo "可安全继续执行上传前流程。"
