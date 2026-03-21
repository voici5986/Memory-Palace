import importlib
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

import mcp_server as mcp_server_module
import run_sse


def _reload_mcp_server():
    return importlib.reload(mcp_server_module)


def test_remote_host_keeps_loopback_transport_security_by_default(monkeypatch) -> None:
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("MCP_ALLOWED_ORIGINS", raising=False)

    module = _reload_mcp_server()

    assert module.mcp.settings.host == "0.0.0.0"
    assert module.mcp.settings.transport_security is not None
    assert module.mcp.settings.transport_security.enable_dns_rebinding_protection is True
    assert "127.0.0.1:*" in module.mcp.settings.transport_security.allowed_hosts
    assert "http://localhost:*" in module.mcp.settings.transport_security.allowed_origins


def test_loopback_host_keeps_dns_rebinding_protection(monkeypatch) -> None:
    monkeypatch.setenv("HOST", "127.0.0.1")

    module = _reload_mcp_server()

    assert module.mcp.settings.host == "127.0.0.1"
    assert module.mcp.settings.transport_security is not None
    assert module.mcp.settings.transport_security.enable_dns_rebinding_protection is True
    assert "127.0.0.1:*" in module.mcp.settings.transport_security.allowed_hosts


def test_transport_security_appends_explicit_allowlists(monkeypatch) -> None:
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "memory.example.com:443, api.example.com:*")
    monkeypatch.setenv(
        "MCP_ALLOWED_ORIGINS",
        "https://memory.example.com,https://console.example.com",
    )

    module = _reload_mcp_server()

    assert module.mcp.settings.transport_security is not None
    assert "memory.example.com:443" in module.mcp.settings.transport_security.allowed_hosts
    assert "api.example.com:*" in module.mcp.settings.transport_security.allowed_hosts
    assert (
        "https://memory.example.com"
        in module.mcp.settings.transport_security.allowed_origins
    )
    assert (
        "https://console.example.com"
        in module.mcp.settings.transport_security.allowed_origins
    )


def test_run_sse_main_binds_loopback_by_default(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []

    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setattr(
        run_sse,
        "create_sse_app",
        lambda **kwargs: "app",
    )
    monkeypatch.setattr(run_sse, "_is_loopback_port_available", lambda port: True)
    monkeypatch.setattr(
        run_sse.uvicorn,
        "run",
        lambda app, host, port: calls.append((host, port)),
    )

    run_sse.main()

    assert calls == [("127.0.0.1", 8000)]


def test_loopback_port_probe_checks_ipv6_when_ipv4_is_free(monkeypatch) -> None:
    attempts: list[tuple[int, tuple[str, int]]] = []

    class _FakeSocket:
        def __init__(self, family: int, socktype: int):
            assert socktype == run_sse.socket.SOCK_STREAM
            self.family = family

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        def setsockopt(self, *_args, **_kwargs):
            return None

        def bind(self, address):
            attempts.append((self.family, address))
            if address[0] == "127.0.0.1":
                raise OSError(98, "address in use")
            if address[0] == "::1":
                return None
            raise AssertionError(address)

    monkeypatch.setattr(run_sse.socket, "socket", _FakeSocket)

    assert run_sse._is_loopback_port_available(8000) is False
    assert attempts == [(run_sse.socket.AF_INET, ("127.0.0.1", 8000))]


def test_run_sse_main_falls_back_for_ipv6_loopback_host(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[tuple[str, int]] = []

    monkeypatch.setenv("HOST", "::1")
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setattr(
        run_sse,
        "create_sse_app",
        lambda **kwargs: "app",
    )
    monkeypatch.setattr(run_sse, "_is_loopback_port_available", lambda port: False)
    monkeypatch.setattr(
        run_sse.uvicorn,
        "run",
        lambda app, host, port: calls.append((host, port)),
    )

    run_sse.main()
    captured = capsys.readouterr()

    assert calls == [("::1", 8010)]
    assert "Update MCP client config to http://[::1]:8010/sse or set PORT explicitly." in captured.err
    assert "Starting SSE Server on http://[::1]:8010" in captured.out
    assert "SSE Endpoint: http://[::1]:8010/sse" in captured.out


def test_sse_transport_security_rejects_invalid_host_without_traceback(tmp_path) -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    env = dict(os.environ)
    env["MCP_API_KEY"] = "transport-secret"
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path / 'transport_security.db'}"
    env["HOST"] = "127.0.0.1"
    env["PORT"] = str(port)

    server = subprocess.Popen(
        [sys.executable, "run_sse.py"],
        cwd=str(backend_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        deadline = time.time() + 10
        while time.time() < deadline:
            if server.poll() is not None:
                pytest.fail("uvicorn exited before the transport security test could connect")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail("timed out waiting for transport security test server to start")

        request = (
            "GET /sse HTTP/1.1\r\n"
            "Host: example.invalid\r\n"
            "Accept: text/event-stream\r\n"
            "X-MCP-API-Key: transport-secret\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("utf-8")

        with socket.create_connection(("127.0.0.1", port), timeout=5) as client:
            client.sendall(request)
            received = client.recv(4096).decode("utf-8", errors="ignore")

        assert "421 Misdirected Request" in received
    finally:
        server.terminate()
        try:
            output, _ = server.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            output, _ = server.communicate(timeout=5)

    assert "Request validation failed" not in output
    assert "Traceback" not in output
