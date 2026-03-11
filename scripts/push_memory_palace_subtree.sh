#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
GIT_TOPLEVEL="$(git -C "${PROJECT_ROOT}" rev-parse --show-toplevel)"

REMOTE="github"
TARGET_BRANCH="main"
EXPECTED_REMOTE_FRAGMENT="AGI-is-going-to-arrive/Memory-Palace.git"
CONFIRM_PHRASE="push-memory-palace-only"
MODE="dry-run"
CONFIRM_VALUE=""
BRANCH_NAME="mp-release-$(date +%Y%m%d-%H%M%S)"

usage() {
  cat <<EOF
Usage:
  bash scripts/push_memory_palace_subtree.sh [--dry-run]
  bash scripts/push_memory_palace_subtree.sh --execute --confirm ${CONFIRM_PHRASE}

Behavior:
  - Only pushes the ${PROJECT_ROOT} subtree to remote '${REMOTE}' branch '${TARGET_BRANCH}'
  - Refuses to run if the ${PROJECT_ROOT} subtree has uncommitted changes
  - Refuses to push if remote '${REMOTE}' does not point to ${EXPECTED_REMOTE_FRAGMENT}

Options:
  --dry-run                 Print the exact commands without pushing (default)
  --execute                 Create a subtree split branch and push it
  --confirm <phrase>        Required with --execute; must equal '${CONFIRM_PHRASE}'
  --branch <name>           Override the temporary split branch name
  --remote <name>           Override remote name (default: ${REMOTE})
  --target-branch <name>    Override target branch (default: ${TARGET_BRANCH})
  -h, --help                Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      MODE="dry-run"
      ;;
    --execute)
      MODE="execute"
      ;;
    --confirm)
      shift
      CONFIRM_VALUE="${1:-}"
      ;;
    --branch)
      shift
      BRANCH_NAME="${1:-}"
      ;;
    --remote)
      shift
      REMOTE="${1:-}"
      ;;
    --target-branch)
      shift
      TARGET_BRANCH="${1:-}"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [[ -z "${BRANCH_NAME}" ]]; then
  echo "Temporary branch name must not be empty." >&2
  exit 2
fi

PREFIX="$(
  python3 - <<'PY' "${GIT_TOPLEVEL}" "${PROJECT_ROOT}"
from pathlib import Path
import sys

top = Path(sys.argv[1]).resolve()
project = Path(sys.argv[2]).resolve()
print(project.relative_to(top).as_posix())
PY
)"

REMOTE_URL="$(git -C "${GIT_TOPLEVEL}" remote get-url "${REMOTE}" 2>/dev/null || true)"
if [[ -z "${REMOTE_URL}" ]]; then
  echo "Remote '${REMOTE}' does not exist in ${GIT_TOPLEVEL}." >&2
  exit 1
fi

if [[ "${REMOTE_URL}" != *"${EXPECTED_REMOTE_FRAGMENT}"* ]]; then
  echo "Remote '${REMOTE}' points to '${REMOTE_URL}', not '${EXPECTED_REMOTE_FRAGMENT}'." >&2
  echo "Refusing to push to avoid sending unrelated top-level history." >&2
  exit 1
fi

SUBTREE_STATUS="$(
  git -C "${GIT_TOPLEVEL}" diff --name-only -- "${PREFIX}"
  git -C "${GIT_TOPLEVEL}" diff --cached --name-only -- "${PREFIX}"
)"
if [[ -n "${SUBTREE_STATUS}" ]]; then
  echo "The '${PREFIX}' subtree has tracked-but-uncommitted changes. Commit them before publishing." >&2
  echo "${SUBTREE_STATUS}" >&2
  exit 1
fi

echo "Top-level repo: ${GIT_TOPLEVEL}"
echo "Subtree prefix: ${PREFIX}"
echo "Remote: ${REMOTE} -> ${REMOTE_URL}"
echo "Target branch: ${TARGET_BRANCH}"
echo "Temporary branch: ${BRANCH_NAME}"
echo ""
echo "Commands:"
echo "  git -C ${GIT_TOPLEVEL} subtree split --prefix=${PREFIX} -b ${BRANCH_NAME}"
echo "  git -C ${GIT_TOPLEVEL} push ${REMOTE} ${BRANCH_NAME}:${TARGET_BRANCH}"
echo "  git -C ${GIT_TOPLEVEL} branch -D ${BRANCH_NAME}"

if [[ "${MODE}" != "execute" ]]; then
  echo ""
  echo "Dry run only. Re-run with '--execute --confirm ${CONFIRM_PHRASE}' to publish."
  exit 0
fi

if [[ "${CONFIRM_VALUE}" != "${CONFIRM_PHRASE}" ]]; then
  echo "Refusing to execute without the exact confirmation phrase: ${CONFIRM_PHRASE}" >&2
  exit 1
fi

if git -C "${GIT_TOPLEVEL}" show-ref --verify --quiet "refs/heads/${BRANCH_NAME}"; then
  echo "Temporary branch '${BRANCH_NAME}' already exists. Choose another name or delete it first." >&2
  exit 1
fi

git -C "${GIT_TOPLEVEL}" subtree split --prefix="${PREFIX}" -b "${BRANCH_NAME}"
git -C "${GIT_TOPLEVEL}" push "${REMOTE}" "${BRANCH_NAME}:${TARGET_BRANCH}"
git -C "${GIT_TOPLEVEL}" branch -D "${BRANCH_NAME}"

echo ""
echo "Published '${PREFIX}' to ${REMOTE}/${TARGET_BRANCH} only."
