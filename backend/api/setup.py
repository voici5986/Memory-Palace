import hmac
import os
import tempfile
from ipaddress import ip_address
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from .maintenance import (
    _MCP_API_KEY_HEADER,
    _extract_bearer_token,
    _get_configured_mcp_api_key,
    _is_loopback_request,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ENV_PATH = _PROJECT_ROOT / ".env"
_ENV_EXAMPLE_PATH = _PROJECT_ROOT / ".env.example"
_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_TRUTHY_ENV_VALUES = {"1", "true", "yes", "on", "enabled"}
_RESTART_TARGETS_LOCAL = ["backend", "sse"]
_RESTART_TARGETS_DOCKER = ["backend", "sse", "frontend"]


class SetupConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dashboard_api_key: Optional[str] = None
    allow_insecure_local: bool = False

    embedding_backend: Literal["none", "hash", "api", "router"] = "hash"
    embedding_api_base: Optional[str] = None
    embedding_api_key: Optional[str] = None
    embedding_model: Optional[str] = None

    reranker_enabled: bool = False
    reranker_api_base: Optional[str] = None
    reranker_api_key: Optional[str] = None
    reranker_model: Optional[str] = None

    write_guard_llm_enabled: bool = False
    write_guard_llm_api_base: Optional[str] = None
    write_guard_llm_api_key: Optional[str] = None
    write_guard_llm_model: Optional[str] = None

    intent_llm_enabled: bool = False
    intent_llm_api_base: Optional[str] = None
    intent_llm_api_key: Optional[str] = None
    intent_llm_model: Optional[str] = None

    router_api_base: Optional[str] = None
    router_api_key: Optional[str] = None
    router_chat_model: Optional[str] = None
    router_embedding_model: Optional[str] = None
    router_reranker_model: Optional[str] = None


router = APIRouter(
    prefix="/setup",
    tags=["setup"],
)


def _bool_to_env(value: bool) -> str:
    return "true" if value else "false"


def _read_optional_env(name: str) -> Optional[str]:
    raw = str(os.getenv(name) or "").strip()
    return raw or None


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUTHY_ENV_VALUES


def _normalize_optional_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if "\n" in normalized or "\r" in normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configuration values cannot contain line breaks.",
        )
    return normalized


def _resolve_target_env_path() -> Path:
    raw_override = str(os.getenv("MEMORY_PALACE_SETUP_ENV_FILE") or "").strip()
    if not raw_override:
        return _DEFAULT_ENV_PATH
    return Path(raw_override).expanduser()


def _is_loopback_hostname(value: Optional[str]) -> bool:
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
    if hostname in _LOOPBACK_HOSTS:
        return True
    try:
        return ip_address(hostname).is_loopback
    except ValueError:
        return False


def _running_in_docker() -> bool:
    if Path("/.dockerenv").exists():
        return True
    marker = str(os.getenv("MEMORY_PALACE_RUNNING_IN_DOCKER") or "").strip().lower()
    return marker in _TRUTHY_ENV_VALUES


def _is_direct_loopback_request(request: Request) -> bool:
    if not _is_loopback_request(request):
        return False

    host_header = request.headers.get("host")
    request_host = getattr(request.url, "hostname", None)
    return _is_loopback_hostname(host_header) and _is_loopback_hostname(request_host)


def _resolve_apply_support(target_env_path: Path) -> tuple[bool, str]:
    if _running_in_docker():
        return False, "docker_runtime_not_persisted"

    if not _ENV_EXAMPLE_PATH.exists():
        return False, "env_example_missing"

    target_parent = target_env_path.parent
    try:
        target_parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False, "target_parent_unwritable"

    if target_env_path.exists():
        if not os.access(target_env_path, os.W_OK):
            return False, "env_file_not_writable"
    elif not os.access(target_parent, os.W_OK):
        return False, "target_parent_unwritable"

    return True, "local_env_file"


def _target_label(target_env_path: Path) -> str:
    if target_env_path == _DEFAULT_ENV_PATH:
        return ".env"
    return target_env_path.name


def _restart_targets() -> List[str]:
    return list(_RESTART_TARGETS_DOCKER if _running_in_docker() else _RESTART_TARGETS_LOCAL)


def _is_env_value_configured(*names: str) -> bool:
    return any(_read_optional_env(name) for name in names)


def _build_summary() -> Dict[str, Any]:
    embedding_backend = (_read_optional_env("RETRIEVAL_EMBEDDING_BACKEND") or "hash").lower()
    reranker_enabled = _env_bool("RETRIEVAL_RERANKER_ENABLED", False)
    write_guard_enabled = _env_bool("WRITE_GUARD_LLM_ENABLED", False)
    intent_llm_enabled = _env_bool("INTENT_LLM_ENABLED", False)
    return {
        "dashboard_auth_configured": bool(_get_configured_mcp_api_key()),
        "allow_insecure_local": _env_bool("MCP_API_KEY_ALLOW_INSECURE_LOCAL", False),
        "embedding_backend": embedding_backend,
        "embedding_configured": (
            embedding_backend in {"none", "hash"}
            or (
                _is_env_value_configured(
                    "RETRIEVAL_EMBEDDING_API_BASE",
                    "RETRIEVAL_EMBEDDING_BASE",
                    "ROUTER_API_BASE",
                )
                and _is_env_value_configured(
                    "RETRIEVAL_EMBEDDING_MODEL",
                    "ROUTER_EMBEDDING_MODEL",
                    "OPENAI_EMBEDDING_MODEL",
                )
            )
        ),
        "reranker_enabled": reranker_enabled,
        "reranker_configured": (
            reranker_enabled
            and _is_env_value_configured(
                "RETRIEVAL_RERANKER_API_BASE",
                "RETRIEVAL_RERANKER_BASE",
                "ROUTER_API_BASE",
            )
            and _is_env_value_configured(
                "RETRIEVAL_RERANKER_MODEL",
                "ROUTER_RERANKER_MODEL",
            )
        ),
        "write_guard_enabled": write_guard_enabled,
        "write_guard_configured": (
            write_guard_enabled
            and _is_env_value_configured(
                "WRITE_GUARD_LLM_API_BASE",
                "LLM_RESPONSES_URL",
                "OPENAI_BASE_URL",
                "OPENAI_API_BASE",
                "ROUTER_API_BASE",
            )
            and _is_env_value_configured(
                "WRITE_GUARD_LLM_MODEL",
                "LLM_MODEL_NAME",
                "OPENAI_MODEL",
                "ROUTER_CHAT_MODEL",
            )
        ),
        "intent_llm_enabled": intent_llm_enabled,
        "intent_llm_configured": (
            intent_llm_enabled
            and _is_env_value_configured(
                "INTENT_LLM_API_BASE",
                "LLM_RESPONSES_URL",
                "OPENAI_BASE_URL",
                "OPENAI_API_BASE",
                "ROUTER_API_BASE",
            )
            and _is_env_value_configured(
                "INTENT_LLM_MODEL",
                "LLM_MODEL_NAME",
                "OPENAI_MODEL",
                "ROUTER_CHAT_MODEL",
            )
        ),
        "router_configured": _is_env_value_configured("ROUTER_API_BASE"),
    }


def _load_seed_env_text(target_env_path: Path) -> str:
    if target_env_path.exists():
        return target_env_path.read_text(encoding="utf-8")
    return _ENV_EXAMPLE_PATH.read_text(encoding="utf-8")


def _upsert_env_value(text: str, key: str, value: str) -> str:
    replacement = f"{key}={value}"
    updated_lines: List[str] = []
    matched = False
    for line in text.splitlines():
        if line.startswith(f"{key}="):
            if not matched:
                updated_lines.append(replacement)
                matched = True
            continue
        updated_lines.append(line)

    if not matched:
        if updated_lines and updated_lines[-1].strip():
            updated_lines.append("")
        updated_lines.append(replacement)

    return "\n".join(updated_lines).rstrip("\n") + "\n"


def _write_env_file(target_env_path: Path, updates: Dict[str, str]) -> None:
    text = _load_seed_env_text(target_env_path)
    for key, value in updates.items():
        text = _upsert_env_value(text, key, value)

    target_env_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=target_env_path.parent,
        delete=False,
        prefix=f"{target_env_path.name}.",
        suffix=".tmp",
    ) as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    temp_path.replace(target_env_path)


def _build_env_updates(payload: SetupConfigRequest) -> Dict[str, str]:
    updates: Dict[str, str] = {
        "MCP_API_KEY_ALLOW_INSECURE_LOCAL": _bool_to_env(payload.allow_insecure_local),
        "RETRIEVAL_EMBEDDING_BACKEND": payload.embedding_backend,
        "RETRIEVAL_RERANKER_ENABLED": _bool_to_env(payload.reranker_enabled),
        "WRITE_GUARD_LLM_ENABLED": _bool_to_env(payload.write_guard_llm_enabled),
        "INTENT_LLM_ENABLED": _bool_to_env(payload.intent_llm_enabled),
    }

    optional_mappings = {
        "MCP_API_KEY": payload.dashboard_api_key,
        "RETRIEVAL_EMBEDDING_API_BASE": payload.embedding_api_base,
        "RETRIEVAL_EMBEDDING_API_KEY": payload.embedding_api_key,
        "RETRIEVAL_EMBEDDING_MODEL": payload.embedding_model,
        "RETRIEVAL_RERANKER_API_BASE": payload.reranker_api_base,
        "RETRIEVAL_RERANKER_API_KEY": payload.reranker_api_key,
        "RETRIEVAL_RERANKER_MODEL": payload.reranker_model,
        "WRITE_GUARD_LLM_API_BASE": payload.write_guard_llm_api_base,
        "WRITE_GUARD_LLM_API_KEY": payload.write_guard_llm_api_key,
        "WRITE_GUARD_LLM_MODEL": payload.write_guard_llm_model,
        "INTENT_LLM_API_BASE": payload.intent_llm_api_base,
        "INTENT_LLM_API_KEY": payload.intent_llm_api_key,
        "INTENT_LLM_MODEL": payload.intent_llm_model,
        "ROUTER_API_BASE": payload.router_api_base,
        "ROUTER_API_KEY": payload.router_api_key,
        "ROUTER_CHAT_MODEL": payload.router_chat_model,
        "ROUTER_EMBEDDING_MODEL": payload.router_embedding_model,
        "ROUTER_RERANKER_MODEL": payload.router_reranker_model,
    }

    for key, raw_value in optional_mappings.items():
        normalized = _normalize_optional_value(raw_value)
        if normalized is not None:
            updates[key] = normalized

    return updates


async def require_setup_access(
    request: Request,
    x_mcp_api_key: Optional[str] = Header(default=None, alias=_MCP_API_KEY_HEADER),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> None:
    if _is_direct_loopback_request(request):
        return

    configured = _get_configured_mcp_api_key()
    provided = str(x_mcp_api_key or "").strip() or _extract_bearer_token(authorization)

    if not configured:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "setup_access_denied",
                "reason": "local_loopback_or_api_key_required",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not provided or not hmac.compare_digest(provided, configured):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "setup_access_denied",
                "reason": "invalid_or_missing_api_key",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_local_setup_write_access(request: Request) -> None:
    if _is_direct_loopback_request(request):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "setup_access_denied",
            "reason": "local_loopback_required_for_write",
        },
    )


@router.get("/status", dependencies=[Depends(require_setup_access)])
async def get_setup_status() -> Dict[str, Any]:
    target_env_path = _resolve_target_env_path()
    apply_supported, apply_reason = _resolve_apply_support(target_env_path)
    return {
        "ok": True,
        "apply_supported": apply_supported,
        "apply_reason": apply_reason,
        "target_label": _target_label(target_env_path),
        "running_in_docker": _running_in_docker(),
        "restart_required": True,
        "restart_targets": _restart_targets(),
        "summary": _build_summary(),
    }


@router.post(
    "/config",
    dependencies=[Depends(require_setup_access), Depends(require_local_setup_write_access)],
)
async def save_setup_config(payload: SetupConfigRequest) -> Dict[str, Any]:
    target_env_path = _resolve_target_env_path()
    apply_supported, apply_reason = _resolve_apply_support(target_env_path)
    if not apply_supported:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "setup_apply_unsupported",
                "reason": apply_reason,
            },
        )

    updates = _build_env_updates(payload)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No configuration changes were provided.",
        )

    try:
        _write_env_file(target_env_path, updates)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "setup_write_failed",
                "message": str(exc),
            },
        ) from exc

    for key, value in updates.items():
        os.environ[key] = value

    return {
        "ok": True,
        "target_label": _target_label(target_env_path),
        "saved_keys": sorted(updates.keys()),
        "immediate_env_refresh": sorted(
            key
            for key in ("MCP_API_KEY", "MCP_API_KEY_ALLOW_INSECURE_LOCAL")
            if key in updates
        ),
        "restart_required": True,
        "restart_targets": _restart_targets(),
        "summary": _build_summary(),
    }
