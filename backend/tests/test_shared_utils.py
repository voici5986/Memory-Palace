from datetime import datetime

import pytest

import mcp_server
from shared_utils import (
    env_bool,
    env_int,
    is_loopback_hostname,
    parse_iso_datetime,
    utc_iso_now,
)


def test_env_bool_uses_shared_truthy_values(monkeypatch) -> None:
    monkeypatch.setenv("MP_SHARED_BOOL", "enabled")
    assert env_bool("MP_SHARED_BOOL", False) is True
    monkeypatch.setenv("MP_SHARED_BOOL", "off")
    assert env_bool("MP_SHARED_BOOL", True) is False


def test_env_int_keeps_runtime_style_default_fallback(monkeypatch) -> None:
    monkeypatch.delenv("MP_SHARED_INT", raising=False)
    assert env_int("MP_SHARED_INT", 3, minimum=5) == 3
    monkeypatch.setenv("MP_SHARED_INT", "2")
    assert env_int("MP_SHARED_INT", 3, minimum=5) == 5


def test_env_int_supports_sse_style_clamped_default(monkeypatch) -> None:
    monkeypatch.delenv("MP_SHARED_INT", raising=False)
    assert env_int("MP_SHARED_INT", 3, minimum=5, clamp_default=True) == 5
    monkeypatch.setenv("MP_SHARED_INT", "invalid")
    assert env_int("MP_SHARED_INT", 3, minimum=5, clamp_default=True) == 5


def test_is_loopback_hostname_handles_ipv6_and_host_ports() -> None:
    assert is_loopback_hostname("[::1]:8000") is True
    assert is_loopback_hostname("127.0.0.1:5173") is True
    assert is_loopback_hostname("memory-palace.example") is False


def test_utc_iso_now_returns_utc_z_suffix() -> None:
    assert utc_iso_now().endswith("Z")


def test_parse_iso_datetime_normalizes_timezone_offsets_to_utc_naive() -> None:
    parsed = parse_iso_datetime(
        "2026-03-21T16:30:00+08:00",
        normalize_to_utc_naive=True,
    )

    assert parsed == datetime(2026, 3, 21, 8, 30, 0)
    assert parsed.tzinfo is None


def test_parse_iso_datetime_raises_friendly_error_when_strict() -> None:
    with pytest.raises(ValueError, match="Invalid datetime 'not-a-datetime'"):
        parse_iso_datetime("not-a-datetime", strict=True)


def test_mcp_server_parse_iso_datetime_reuses_shared_normalization() -> None:
    assert mcp_server._parse_iso_datetime("2026-03-21T16:30:00+08:00") == datetime(
        2026, 3, 21, 8, 30, 0
    )
