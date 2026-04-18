import os
import math
from datetime import datetime, timezone
from ipaddress import ip_address
from typing import Any, Dict, Iterable, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit


TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on", "enabled"})
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
DEFAULT_INTERACTION_TIERS = frozenset({"fast", "deep"})


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


def resolve_interaction_tier(
    raw_filters: Optional[Dict[str, Any]],
    *,
    requested_tier: Optional[Any] = None,
    requested_scope_hint: Optional[Any] = None,
    allowed_tiers: Optional[Iterable[str]] = None,
    default_tier: str = "fast",
) -> Tuple[str, Optional[Dict[str, Any]], Optional[Any]]:
    allowed = frozenset(
        str(item).strip().lower()
        for item in (allowed_tiers or DEFAULT_INTERACTION_TIERS)
        if str(item).strip()
    ) or DEFAULT_INTERACTION_TIERS

    normalized_default = str(default_tier or "").strip().lower() or "fast"
    if normalized_default not in allowed:
        normalized_default = "fast"

    filters_copy: Optional[Dict[str, Any]] = raw_filters
    raw_value = requested_tier
    scope_hint_value = requested_scope_hint
    if isinstance(filters_copy, dict):
        filters_copy = dict(filters_copy)
        if raw_value is None and "interaction_tier" in filters_copy:
            raw_value = filters_copy.get("interaction_tier")
        filters_copy.pop("interaction_tier", None)

    if raw_value is None:
        scope_hint_tier = str(scope_hint_value or "").strip().lower()
        if scope_hint_tier in allowed:
            raw_value = scope_hint_tier
            scope_hint_value = None

    value = str(raw_value or "").strip().lower()
    if value not in allowed:
        value = normalized_default
    return value, filters_copy, scope_hint_value


def should_try_intent_llm(
    client: Any,
    rule_payload: Optional[Dict[str, Any]],
) -> bool:
    helper = getattr(client, "should_use_intent_llm", None)
    if callable(helper):
        try:
            return bool(helper(rule_payload))
        except Exception:
            pass

    if not isinstance(rule_payload, dict) or not rule_payload:
        return True

    rule_intent = str(rule_payload.get("intent") or "").strip().lower()
    try:
        rule_confidence = float(rule_payload.get("confidence") or 0.0)
    except (TypeError, ValueError):
        rule_confidence = 0.0
    return rule_intent == "unknown" or rule_confidence < 0.70
