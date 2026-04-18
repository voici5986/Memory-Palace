import os
import math
from datetime import datetime, timezone
from ipaddress import ip_address
from typing import Iterable, Optional
from urllib.parse import urlsplit, urlunsplit


TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on", "enabled"})
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def env_bool(
    name: str,
    default: bool,
    truthy_values: Optional[Iterable[str]] = None,
) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    values = TRUTHY_ENV_VALUES if truthy_values is None else frozenset(truthy_values)
    return raw.strip().lower() in values


def env_int(
    name: str,
    default: int,
    minimum: int = 0,
    *,
    clamp_default: bool = False,
) -> int:
    raw = os.getenv(name)
    fallback = max(minimum, default) if clamp_default else default
    if raw is None:
        return fallback
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return fallback
    return max(minimum, value)


def env_float(
    name: str,
    default: float,
    minimum: float = 0.0,
    *,
    clamp_default: bool = False,
) -> float:
    fallback = max(minimum, default) if clamp_default else default
    raw = os.getenv(name)
    if raw is None:
        return fallback
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return fallback
    if not math.isfinite(value):
        return fallback
    return max(minimum, value)


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso_datetime(
    value: Optional[str],
    *,
    normalize_to_utc_naive: bool = False,
    strict: bool = False,
) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        if strict:
            raise ValueError(
                f"Invalid datetime '{value}'. Use ISO-8601 like '2026-01-31T12:00:00Z'."
            ) from exc
        return None
    if normalize_to_utc_naive and parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def is_loopback_hostname(
    value: Optional[str],
    loopback_hosts: Optional[Iterable[str]] = None,
) -> bool:
    if not value:
        return False
    hostname = str(value).strip().lower()
    if not hostname:
        return False
    if hostname.startswith("["):
        closing = hostname.find("]")
        if closing != -1:
            suffix = hostname[closing + 1 :]
            if not suffix or (
                suffix.startswith(":") and suffix[1:].isdigit()
            ):
                hostname = hostname[1:closing]
    if ":" in hostname and hostname.count(":") == 1 and hostname.rsplit(":", 1)[1].isdigit():
        hostname = hostname.rsplit(":", 1)[0]
    hosts = LOOPBACK_HOSTS if loopback_hosts is None else frozenset(loopback_hosts)
    if hostname in hosts:
        return True
    try:
        return ip_address(hostname).is_loopback
    except ValueError:
        return False


def normalize_http_api_base(
    value: Optional[str],
    *,
    trim_suffixes: Optional[Iterable[str]] = None,
) -> str:
    normalized = str(value or "").strip().rstrip("/")
    if not normalized:
        return ""

    parsed = urlsplit(normalized)
    scheme = str(parsed.scheme or "").strip().lower()
    if scheme not in {"http", "https"}:
        raise ValueError("API base URL must use http or https.")
    if not parsed.netloc or not parsed.hostname:
        raise ValueError("API base URL must include a host.")
    if parsed.username or parsed.password:
        raise ValueError("API base URL must not include embedded credentials.")
    if parsed.query or parsed.fragment:
        raise ValueError("API base URL must not include query parameters or fragments.")

    try:
        host_ip = ip_address(parsed.hostname)
    except ValueError:
        host_ip = None
    if host_ip is not None and (
        host_ip.is_unspecified or host_ip.is_multicast or host_ip.is_link_local
    ):
        raise ValueError(
            "API base URL cannot point to an unspecified, multicast, or link-local address."
        )

    path = str(parsed.path or "").rstrip("/")
    for suffix in trim_suffixes or ():
        suffix_text = str(suffix or "").strip()
        if not suffix_text:
            continue
        if path.lower().endswith(suffix_text.lower()):
            path = path[: -len(suffix_text)].rstrip("/")
            break

    return urlunsplit((scheme, parsed.netloc, path, "", ""))
