from __future__ import annotations

import importlib.util
from pathlib import Path
import urllib.error


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "deploy" / "docker" / "backend-healthcheck.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "memory_palace_backend_healthcheck",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        return self._payload


def test_backend_healthcheck_returns_zero_for_ok_status(monkeypatch) -> None:
    module = _load_module()

    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda request, timeout=3: _FakeResponse(b'{"status":"ok"}'),
    )

    assert module.main() == 0


def test_backend_healthcheck_logs_request_errors(monkeypatch, capsys) -> None:
    module = _load_module()

    def _raise_url_error(request, timeout=3):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(module.urllib.request, "urlopen", _raise_url_error)

    assert module.main() == 1
    assert "backend healthcheck failed: request error: connection refused" in capsys.readouterr().err


def test_backend_healthcheck_logs_invalid_json(monkeypatch, capsys) -> None:
    module = _load_module()

    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda request, timeout=3: _FakeResponse(b"not-json"),
    )

    assert module.main() == 1
    assert "backend healthcheck failed: invalid JSON response:" in capsys.readouterr().err


def test_backend_healthcheck_logs_unhealthy_status(monkeypatch, capsys) -> None:
    module = _load_module()

    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda request, timeout=3: _FakeResponse(b'{"status":"degraded"}'),
    )

    assert module.main() == 1
    assert "backend healthcheck failed: status=degraded" in capsys.readouterr().err
