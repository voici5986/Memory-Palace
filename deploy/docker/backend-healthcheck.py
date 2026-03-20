#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def _log_failure(message: str) -> None:
    print(f"backend healthcheck failed: {message}", file=sys.stderr)


def main() -> int:
    url = str(os.getenv("MEMORY_PALACE_BACKEND_HEALTHCHECK_URL") or "").strip()
    if not url:
        url = "http://127.0.0.1:8000/health"

    headers = {}
    api_key = str(os.getenv("MCP_API_KEY") or "").strip()
    if api_key:
        headers["X-MCP-API-Key"] = api_key

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            raw_payload = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None) or exc
        _log_failure(f"request error: {reason}")
        return 1
    try:
        payload = json.loads(raw_payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _log_failure(f"invalid JSON response: {exc}")
        return 1

    if payload.get("status") != "ok":
        _log_failure(f"status={payload.get('status', 'unknown')}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
