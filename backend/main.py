import inspect
import os
import hmac
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware


def _load_project_dotenv(project_root: Optional[Path] = None) -> Optional[Path]:
    root = project_root or Path(__file__).resolve().parents[1]
    dotenv_path = root / ".env"
    if not dotenv_path.exists():
        return None
    load_dotenv(dotenv_path, override=False)
    return dotenv_path


_load_project_dotenv()

from api import review_router, browse_router, maintenance_router, setup_router
from api.maintenance import (
    _extract_bearer_token,
    _get_configured_mcp_api_key,
    _is_direct_loopback_request,
)
from db import get_sqlite_client, close_sqlite_client
from runtime_state import runtime_state
from runtime_bootstrap import (
    _extract_sqlite_file_path,
    initialize_backend_runtime,
    _try_restore_legacy_sqlite_file,
)
from run_sse import create_embedded_sse_apps


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _health_request_allows_details(
    request: Optional[Request],
    *,
    x_mcp_api_key: Optional[str],
    authorization: Optional[str],
) -> bool:
    if request is None:
        return True
    if _is_direct_loopback_request(request):
        return True

    configured_key = _get_configured_mcp_api_key()
    if not configured_key:
        return False

    provided_key = str(x_mcp_api_key or "").strip()
    if not provided_key:
        provided_key = str(_extract_bearer_token(authorization) or "").strip()
    return bool(provided_key) and hmac.compare_digest(configured_key, provided_key)


_DEFAULT_CORS_ALLOW_ORIGINS: tuple[str, ...] = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def _resolve_cors_config() -> tuple[list[str], bool]:
    raw_origins = str(os.getenv("CORS_ALLOW_ORIGINS", "") or "")
    origins = [item.strip() for item in raw_origins.split(",") if item.strip()]
    if not origins:
        origins = list(_DEFAULT_CORS_ALLOW_ORIGINS)

    allow_credentials = _env_bool("CORS_ALLOW_CREDENTIALS", True)
    if "*" in origins and allow_credentials:
        # Browsers reject '*' + credentials. Fall back to credential-less CORS.
        allow_credentials = False
    return origins, allow_credentials


def _mount_embedded_sse_apps(app: FastAPI) -> None:
    if getattr(app.state, "embedded_sse_mounted", False):
        return

    embedded_sse_stream_app, embedded_sse_message_app = create_embedded_sse_apps()
    app.mount("/sse/messages", embedded_sse_message_app)
    app.mount("/messages", embedded_sse_message_app)
    app.mount("/sse", embedded_sse_stream_app)
    app.state.embedded_sse_mounted = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    print("Memory API starting...")
    
    # Initialize SQLite
    try:
        await initialize_backend_runtime()
        _mount_embedded_sse_apps(app)
        print("SQLite database initialized.")
    except Exception as e:
        print(f"Failed to initialize SQLite: {e}")
        raise RuntimeError("Failed to initialize SQLite during startup") from e
    
    yield
    
    # 关闭时
    print("Closing database connections...")
    try:
        from mcp_server import drain_pending_flush_summaries

        await drain_pending_flush_summaries(reason="runtime.shutdown")
    except Exception as exc:
        print(f"Best-effort flush drain skipped: {type(exc).__name__}")
    await runtime_state.shutdown()
    await close_sqlite_client()


app = FastAPI(
    title="Memory Palace API",
    description="AI Agent 长期记忆系统后端",
    version="1.0.1",
    lifespan=lifespan
)

# CORS设置
_cors_origins, _cors_allow_credentials = _resolve_cors_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(review_router)
app.include_router(browse_router)
app.include_router(maintenance_router)
app.include_router(setup_router)


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Memory Palace API",
        "version": "1.0.1",
        "docs": "/docs"
    }


@app.get("/health")
async def health(
    request: Request = None,
    x_mcp_api_key: Optional[str] = Header(default=None, alias="X-MCP-API-Key"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    """健康检查"""
    payload: Dict[str, Any] = {
        "status": "ok",
        "timestamp": _utc_iso_now(),
    }
    include_details = _health_request_allows_details(
        request,
        x_mcp_api_key=x_mcp_api_key,
        authorization=authorization,
    )

    try:
        sqlite_client = get_sqlite_client()
        if not include_details:
            return payload
        index_payload: Optional[Dict[str, Any]] = None

        for method_name in (
            "get_index_status",
            "index_status",
            "get_retrieval_status",
            "get_search_index_status",
        ):
            method = getattr(sqlite_client, method_name, None)
            if not callable(method):
                continue
            try:
                result = method()
                if inspect.isawaitable(result):
                    result = await result
            except TypeError as exc:
                message = str(exc)
                if (
                    "unexpected keyword argument" in message
                    or "required positional argument" in message
                ):
                    continue
                raise

            index_payload = result if isinstance(result, dict) else {"raw_status": result}
            index_payload.setdefault("index_available", True)
            index_payload.setdefault("degraded", False)
            index_payload["source"] = f"sqlite_client.{method_name}"
            break

        if index_payload is None:
            paths = await sqlite_client.get_all_paths()
            domain_counts: Dict[str, int] = {}
            for item in paths:
                domain = item.get("domain", "core")
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
            index_payload = {
                "index_available": False,
                "degraded": True,
                "reason": "sqlite_client index status API unavailable; fallback stats only.",
                "source": "api.health.fallback",
                "stats": {
                    "total_paths": len(paths),
                    "domain_counts": domain_counts,
                },
            }

        payload["index"] = index_payload
        payload["runtime"] = {
            "write_lanes": await runtime_state.write_lanes.status(),
            "index_worker": await runtime_state.index_worker.status(),
        }
        if index_payload.get("degraded"):
            payload["status"] = "degraded"

    except Exception as exc:
        error_type = type(exc).__name__
        payload["status"] = "degraded"
        if not include_details:
            return payload
        payload["index"] = {
            "index_available": False,
            "degraded": True,
            "reason": "internal_error",
            "error_type": error_type,
            "source": "api.health.exception",
        }
        payload["runtime"] = {
            "write_lanes": {"degraded": True, "reason": "internal_error"},
            "index_worker": {"degraded": True, "reason": "internal_error"},
        }

    return payload


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
