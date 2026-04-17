import hmac
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from dotenv import dotenv_values
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from shared_utils import (
    TRUTHY_ENV_VALUES as _TRUTHY_ENV_VALUES,
    env_bool as _env_bool,
    is_loopback_hostname as _is_loopback_hostname,
)

from .maintenance import (
    _MCP_API_KEY_HEADER,
    _extract_bearer_token,
    _get_configured_mcp_api_key,
    _is_loopback_request,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ENV_PATH = _PROJECT_ROOT / ".env"
_ENV_EXAMPLE_PATH = _PROJECT_ROOT / ".env.example"
_RESTART_TARGETS_LOCAL = ["backend", "sse"]
_RESTART_TARGETS_DOCKER = ["backend", "sse", "frontend"]
_REMOTE_EMBEDDING_BACKENDS = {"api", "router", "openai"}
_SETUP_MANAGED_ENV_KEYS = {
    "MCP_API_KEY",
    "MCP_API_KEY_ALLOW_INSECURE_LOCAL",
    "RETRIEVAL_EMBEDDING_BACKEND",
    "RETRIEVAL_EMBEDDING_API_BASE",
    "RETRIEVAL_EMBEDDING_API_KEY",
    "RETRIEVAL_EMBEDDING_MODEL",
    "RETRIEVAL_EMBEDDING_DIM",
    "OPENAI_EMBEDDING_MODEL",
    "RETRIEVAL_RERANKER_ENABLED",
    "RETRIEVAL_RERANKER_API_BASE",
    "RETRIEVAL_RERANKER_API_KEY",
    "RETRIEVAL_RERANKER_MODEL",
    "WRITE_GUARD_LLM_ENABLED",
    "WRITE_GUARD_LLM_API_BASE",
    "WRITE_GUARD_LLM_API_KEY",
    "WRITE_GUARD_LLM_MODEL",
    "INTENT_LLM_ENABLED",
    "INTENT_LLM_API_BASE",
    "INTENT_LLM_API_KEY",
    "INTENT_LLM_MODEL",
    "ROUTER_API_BASE",
    "ROUTER_API_KEY",
    "ROUTER_CHAT_MODEL",
    "ROUTER_EMBEDDING_MODEL",
    "ROUTER_RERANKER_MODEL",
}
_PLACEHOLDER_FIELD_VALUES = {
    "router_api_base": {
        "https://router.example.com/v1",
    },
    "embedding_model": {"text-embedding-model"},
    "router_embedding_model": {"router-embedding-model"},
    "reranker_model": {"reranker-model"},
    "router_reranker_model": {"router-reranker-model"},
    "write_guard_llm_model": {"chat-model"},
    "intent_llm_model": {"intent-model"},
    "router_chat_model": {"router-chat-model"},
}


class SetupConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dashboard_api_key: Optional[str] = None
    allow_insecure_local: bool = False

    embedding_backend: Literal["none", "hash", "api", "router", "openai"] = "hash"
    embedding_api_base: Optional[str] = None
    embedding_api_key: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_dim: Optional[int] = Field(default=None, ge=1)

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


def _refresh_setup_managed_env_from_file(target_env_path: Path) -> None:
    if not target_env_path.exists():
        return
    parsed = dotenv_values(target_env_path)
    for key in _SETUP_MANAGED_ENV_KEYS:
        if key not in parsed:
            continue
        value = parsed.get(key)
        if value is None or value == "":
            os.environ.pop(key, None)
            continue
        os.environ[key] = str(value)


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


def _resolve_embedding_dim_update(payload: SetupConfigRequest) -> Optional[str]:
    if payload.embedding_dim is not None:
        return str(int(payload.embedding_dim))

    current_backend = (
        _read_optional_env("RETRIEVAL_EMBEDDING_BACKEND") or "hash"
    ).strip().lower()
    current_dim = _read_optional_env("RETRIEVAL_EMBEDDING_DIM")
    if payload.embedding_backend == "hash":
        return "64"

    if payload.embedding_backend == "none":
        return ""

    if (
        current_dim
        and current_backend in {"api", "router", "openai"}
        and payload.embedding_backend in {"api", "router", "openai"}
    ):
        return current_dim

    if payload.embedding_backend in {"api", "router", "openai"}:
        # Profile C/D default to 1024 unless the caller provides a provider-specific
        # dimension. This avoids silently keeping hash-mode 64-d vectors after
        # switching the setup flow to a remote embedding backend.
        return "1024"
    return None


def _build_summary() -> Dict[str, Any]:
    embedding_backend = (_read_optional_env("RETRIEVAL_EMBEDDING_BACKEND") or "hash").lower()
    raw_embedding_dim = _read_optional_env("RETRIEVAL_EMBEDDING_DIM")
    embedding_dim = int(raw_embedding_dim) if raw_embedding_dim and raw_embedding_dim.isdigit() else None
    reranker_enabled = _env_bool("RETRIEVAL_RERANKER_ENABLED", False)
    write_guard_enabled = _env_bool("WRITE_GUARD_LLM_ENABLED", False)
    intent_llm_enabled = _env_bool("INTENT_LLM_ENABLED", False)
    return {
        "dashboard_auth_configured": bool(_get_configured_mcp_api_key()),
        "allow_insecure_local": _env_bool("MCP_API_KEY_ALLOW_INSECURE_LOCAL", False),
        "embedding_backend": embedding_backend,
        "embedding_dim": embedding_dim,
        "embedding_configured": (
            embedding_backend in {"none", "hash"}
            or (
                _is_env_value_configured(
                    "RETRIEVAL_EMBEDDING_API_BASE",
                    "RETRIEVAL_EMBEDDING_BASE",
                    "ROUTER_API_BASE",
                    "OPENAI_BASE_URL",
                    "OPENAI_API_BASE",
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


def _set_optional_update(
    updates: Dict[str, str],
    key: str,
    raw_value: Optional[str],
    *,
    clear_when_blank: bool = False,
) -> None:
    normalized = _normalize_optional_value(raw_value)
    if normalized is not None:
        updates[key] = normalized
    elif clear_when_blank:
        updates[key] = ""


def _is_placeholder_setup_value(field: str, raw_value: Optional[str]) -> bool:
    if raw_value is None:
        return False
    normalized = raw_value.strip()
    if not normalized:
        return False
    return normalized in _PLACEHOLDER_FIELD_VALUES.get(field, set())


def _require_setup_text_field(
    payload: SetupConfigRequest,
    field: str,
    missing_fields: List[str],
    placeholder_fields: List[str],
) -> None:
    normalized = _normalize_optional_value(getattr(payload, field))
    if normalized is None:
        if field not in missing_fields:
            missing_fields.append(field)
        return
    if _is_placeholder_setup_value(field, normalized) and field not in placeholder_fields:
        placeholder_fields.append(field)


def _validate_setup_payload(payload: SetupConfigRequest) -> None:
    missing_fields: List[str] = []
    placeholder_fields: List[str] = []

    if payload.embedding_backend in {"api", "openai"}:
        _require_setup_text_field(payload, "embedding_api_base", missing_fields, placeholder_fields)
        _require_setup_text_field(payload, "embedding_model", missing_fields, placeholder_fields)
    elif payload.embedding_backend == "router":
        _require_setup_text_field(payload, "router_api_base", missing_fields, placeholder_fields)
        _require_setup_text_field(payload, "router_embedding_model", missing_fields, placeholder_fields)
        if payload.reranker_enabled:
            _require_setup_text_field(
                payload, "router_reranker_model", missing_fields, placeholder_fields
            )

    if payload.reranker_enabled and payload.embedding_backend != "router":
        _require_setup_text_field(payload, "reranker_api_base", missing_fields, placeholder_fields)
        _require_setup_text_field(payload, "reranker_model", missing_fields, placeholder_fields)

    if payload.write_guard_llm_enabled:
        _require_setup_text_field(
            payload, "write_guard_llm_api_base", missing_fields, placeholder_fields
        )
        _require_setup_text_field(payload, "write_guard_llm_model", missing_fields, placeholder_fields)

    if payload.intent_llm_enabled:
        _require_setup_text_field(payload, "intent_llm_api_base", missing_fields, placeholder_fields)
        _require_setup_text_field(payload, "intent_llm_model", missing_fields, placeholder_fields)

    if missing_fields or placeholder_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "setup_validation_failed",
                "missing_fields": missing_fields,
                "placeholder_fields": placeholder_fields,
                "message": "Complete the required setup fields before saving.",
            },
        )


def _build_env_updates(payload: SetupConfigRequest) -> Dict[str, str]:
    updates: Dict[str, str] = {
        "MCP_API_KEY_ALLOW_INSECURE_LOCAL": _bool_to_env(payload.allow_insecure_local),
        "RETRIEVAL_EMBEDDING_BACKEND": payload.embedding_backend,
        "RETRIEVAL_RERANKER_ENABLED": _bool_to_env(payload.reranker_enabled),
        "WRITE_GUARD_LLM_ENABLED": _bool_to_env(payload.write_guard_llm_enabled),
        "INTENT_LLM_ENABLED": _bool_to_env(payload.intent_llm_enabled),
    }

    _set_optional_update(updates, "MCP_API_KEY", payload.dashboard_api_key)

    direct_embedding_backend = payload.embedding_backend in {"api", "openai"}
    if direct_embedding_backend:
        _set_optional_update(updates, "RETRIEVAL_EMBEDDING_API_BASE", payload.embedding_api_base)
        _set_optional_update(updates, "RETRIEVAL_EMBEDDING_API_KEY", payload.embedding_api_key)
        _set_optional_update(updates, "RETRIEVAL_EMBEDDING_MODEL", payload.embedding_model)
    else:
        updates["RETRIEVAL_EMBEDDING_API_BASE"] = ""
        updates["RETRIEVAL_EMBEDDING_API_KEY"] = ""
        updates["RETRIEVAL_EMBEDDING_MODEL"] = ""

    if payload.embedding_backend == "openai":
        _set_optional_update(updates, "OPENAI_EMBEDDING_MODEL", payload.embedding_model)
    else:
        updates["OPENAI_EMBEDDING_MODEL"] = ""

    if payload.reranker_enabled and payload.embedding_backend != "router":
        _set_optional_update(updates, "RETRIEVAL_RERANKER_API_BASE", payload.reranker_api_base)
        _set_optional_update(updates, "RETRIEVAL_RERANKER_API_KEY", payload.reranker_api_key)
        _set_optional_update(updates, "RETRIEVAL_RERANKER_MODEL", payload.reranker_model)
    else:
        updates["RETRIEVAL_RERANKER_API_BASE"] = ""
        updates["RETRIEVAL_RERANKER_API_KEY"] = ""
        updates["RETRIEVAL_RERANKER_MODEL"] = ""

    if payload.write_guard_llm_enabled:
        _set_optional_update(
            updates, "WRITE_GUARD_LLM_API_BASE", payload.write_guard_llm_api_base
        )
        _set_optional_update(updates, "WRITE_GUARD_LLM_API_KEY", payload.write_guard_llm_api_key)
        _set_optional_update(updates, "WRITE_GUARD_LLM_MODEL", payload.write_guard_llm_model)
    else:
        updates["WRITE_GUARD_LLM_API_BASE"] = ""
        updates["WRITE_GUARD_LLM_API_KEY"] = ""
        updates["WRITE_GUARD_LLM_MODEL"] = ""

    if payload.intent_llm_enabled:
        _set_optional_update(updates, "INTENT_LLM_API_BASE", payload.intent_llm_api_base)
        _set_optional_update(updates, "INTENT_LLM_API_KEY", payload.intent_llm_api_key)
        _set_optional_update(updates, "INTENT_LLM_MODEL", payload.intent_llm_model)
    else:
        updates["INTENT_LLM_API_BASE"] = ""
        updates["INTENT_LLM_API_KEY"] = ""
        updates["INTENT_LLM_MODEL"] = ""

    if payload.embedding_backend == "router":
        _set_optional_update(updates, "ROUTER_API_BASE", payload.router_api_base)
        _set_optional_update(updates, "ROUTER_API_KEY", payload.router_api_key)
        _set_optional_update(updates, "ROUTER_EMBEDDING_MODEL", payload.router_embedding_model)
        if payload.reranker_enabled:
            _set_optional_update(updates, "ROUTER_RERANKER_MODEL", payload.router_reranker_model)
        else:
            updates["ROUTER_RERANKER_MODEL"] = ""
        if payload.intent_llm_enabled:
            _set_optional_update(updates, "ROUTER_CHAT_MODEL", payload.router_chat_model)
        else:
            updates["ROUTER_CHAT_MODEL"] = ""
    else:
        updates["ROUTER_API_BASE"] = ""
        updates["ROUTER_API_KEY"] = ""
        updates["ROUTER_CHAT_MODEL"] = ""
        updates["ROUTER_EMBEDDING_MODEL"] = ""
        updates["ROUTER_RERANKER_MODEL"] = ""

    embedding_dim = _resolve_embedding_dim_update(payload)
    if embedding_dim is not None:
        updates["RETRIEVAL_EMBEDDING_DIM"] = embedding_dim

    return updates


_refresh_setup_managed_env_from_file(_resolve_target_env_path())


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
async def get_setup_status(request: Request) -> Dict[str, Any]:
    target_env_path = _resolve_target_env_path()
    _refresh_setup_managed_env_from_file(target_env_path)
    apply_supported, apply_reason = _resolve_apply_support(target_env_path)
    write_supported = apply_supported and _is_direct_loopback_request(request)
    write_reason = apply_reason if not apply_supported else (
        "local_env_file" if write_supported else "local_loopback_required_for_write"
    )
    return {
        "ok": True,
        "apply_supported": apply_supported,
        "apply_reason": apply_reason,
        "write_supported": write_supported,
        "write_reason": write_reason,
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

    _validate_setup_payload(payload)
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

    _refresh_setup_managed_env_from_file(target_env_path)

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
