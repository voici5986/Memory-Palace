#!/usr/bin/env sh
set -eu

if [ "$(id -u)" = "0" ]; then
  mkdir -p /app/data /app/snapshots
  chown -R app:app /app/data /app/snapshots
  if ! command -v gosu >/dev/null 2>&1; then
    echo "backend-entrypoint: gosu is required when running as root" >&2
    exit 1
  fi
  exec gosu app "$@"
fi

exec "$@"
