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


class _FakeOpener:
    def __init__(
        self,
        payload: bytes | None = None,
        *,
        error: Exception | None = None,
        capture: dict[str, object] | None = None,
    ) -> None:
        self._payload = payload
        self._error = error
        self._capture = capture

    def open(self, request, timeout=3):
        if self._capture is not None:
            self._capture["request"] = request
            self._capture["timeout"] = timeout
        if self._error is not None:
            raise self._error
        assert self._payload is not None
        return _FakeResponse(self._payload)


def test_backend_healthcheck_returns_zero_for_ok_status(monkeypatch) -> None:
    module = _load_module()

    monkeypatch.setattr(
        module,
        "_proxyless_opener",
        lambda: _FakeOpener(b'{"status":"ok"}'),
    )

    assert module.main() == 0


def test_backend_healthcheck_logs_request_errors(monkeypatch, capsys) -> None:
    module = _load_module()

    monkeypatch.setattr(
        module,
        "_proxyless_opener",
        lambda: _FakeOpener(error=urllib.error.URLError("connection refused")),
    )

    assert module.main() == 1
    assert "backend healthcheck failed: request error: connection refused" in capsys.readouterr().err


def test_backend_healthcheck_logs_invalid_json(monkeypatch, capsys) -> None:
    module = _load_module()

    monkeypatch.setattr(
        module,
        "_proxyless_opener",
        lambda: _FakeOpener(b"not-json"),
    )

    assert module.main() == 1
    assert "backend healthcheck failed: invalid JSON response:" in capsys.readouterr().err


def test_backend_healthcheck_logs_unhealthy_status(monkeypatch, capsys) -> None:
    module = _load_module()

    monkeypatch.setattr(
        module,
        "_proxyless_opener",
        lambda: _FakeOpener(b'{"status":"degraded"}'),
    )

    assert module.main() == 1
    assert "backend healthcheck failed: status=degraded" in capsys.readouterr().err


def test_backend_healthcheck_uses_configured_timeout(monkeypatch) -> None:
    module = _load_module()
    captured: dict[str, float] = {}

    def _fake_urlopen(request, timeout=3):
        captured["timeout"] = timeout
        return _FakeResponse(b'{"status":"ok"}')

    monkeypatch.setenv("MEMORY_PALACE_BACKEND_HEALTHCHECK_TIMEOUT_SEC", "7")
    monkeypatch.setattr(
        module,
        "_proxyless_opener",
        lambda: _FakeOpener(b'{"status":"ok"}', capture=captured),
    )

    assert module.main() == 0
    assert captured["timeout"] == 7.0


def test_backend_healthcheck_builds_proxyless_opener(monkeypatch) -> None:
    module = _load_module()
    captured: dict[str, object] = {}

    class _FakeOpener:
        def open(self, request, timeout=3):
            captured["request"] = request
            captured["timeout"] = timeout
            return _FakeResponse(b'{"status":"ok"}')

    def _fake_proxy_handler(proxies):
        captured["proxies"] = proxies
        return ("proxy-handler", proxies)

    def _fake_build_opener(*handlers):
        captured["handlers"] = handlers
        return _FakeOpener()

    monkeypatch.setattr(module.urllib.request, "ProxyHandler", _fake_proxy_handler)
    monkeypatch.setattr(module.urllib.request, "build_opener", _fake_build_opener)

    assert module.main() == 0
    assert captured["proxies"] == {}
    assert captured["timeout"] == 5.0
