"""
Browse API - Clean URI-based memory navigation

This replaces the old Entity/Relation/Chapter conceptual split with a simple
hierarchical browser. Every path is just a node with content and children.
"""

import os
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Any
from db import get_sqlite_client
from db.snapshot import _resolve_current_database_scope, get_snapshot_manager
from db.sqlite_client import Path as PathModel
from runtime_state import runtime_state
from .maintenance import require_maintenance_api_key
from sqlalchemy import select

router = APIRouter(prefix="/browse", tags=["browse"])
_READ_ONLY_DOMAINS = {"system"}
_VALID_DOMAINS = list(
    dict.fromkeys(
        [
            d.strip().lower()
            for d in str(os.getenv("VALID_DOMAINS", "core,writer,game,notes,system")).split(",")
            if d.strip()
        ]
        + sorted(_READ_ONLY_DOMAINS)
    )
)


class NodeUpdate(BaseModel):
    content: str | None = None
    priority: int | None = None
    disclosure: str | None = None


class NodeCreate(BaseModel):
    parent_path: str = ""
    title: str | None = None
    content: str
    priority: int = 0
    disclosure: str | None = None
    domain: str = "core"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}


ENABLE_WRITE_LANE_QUEUE = _env_bool("RUNTIME_WRITE_LANE_QUEUE", True)
_DASHBOARD_WRITE_SESSION_ID = "dashboard"


def _normalize_domain_or_422(domain: str) -> str:
    normalized = str(domain or "").strip().lower()
    if not normalized:
        normalized = "core"
    if normalized not in _VALID_DOMAINS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown domain '{normalized}'. Valid domains: {', '.join(_VALID_DOMAINS)}",
        )
    return normalized


def _ensure_writable_domain_or_422(domain: str, *, operation: str) -> str:
    normalized = _normalize_domain_or_422(domain)
    if normalized in _READ_ONLY_DOMAINS:
        raise HTTPException(
            status_code=422,
            detail=f"{operation} does not allow writes to '{normalized}://'. system:// is read-only.",
        )
    return normalized


def _normalize_guard_decision(payload: Any, *, allow_bypass: bool = False) -> dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}
    reason = str(payload.get("reason") or "").strip()
    has_action = "action" in payload
    raw_action = str(payload.get("action") or "").strip().upper() if has_action else ""
    action = raw_action
    valid_actions = {"ADD", "UPDATE", "NOOP", "DELETE"}
    if allow_bypass:
        valid_actions.add("BYPASS")
    if action not in valid_actions:
        action = "NOOP"
        marker_value = raw_action or ("EMPTY" if has_action else "MISSING")
        marker = f"invalid_guard_action:{marker_value}"
        reason = marker if not reason else f"{marker}; {reason}"
    method = str(payload.get("method") or "none").strip().lower() or "none"
    target_id = payload.get("target_id")
    if not isinstance(target_id, int) or target_id <= 0:
        target_id = None
    target_uri = payload.get("target_uri")
    if not isinstance(target_uri, str) or not target_uri.strip():
        target_uri = None
    return {
        "action": action,
        "reason": reason,
        "method": method,
        "target_id": target_id,
        "target_uri": target_uri,
    }


def _guard_fields(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "guard_action": payload.get("action"),
        "guard_reason": payload.get("reason"),
        "guard_method": payload.get("method"),
        "guard_target_id": payload.get("target_id"),
        "guard_target_uri": payload.get("target_uri"),
    }


async def _record_guard_event(operation: str, decision: dict[str, Any], blocked: bool) -> None:
    try:
        await runtime_state.guard_tracker.record_event(
            operation=operation,
            action=str(decision.get("action") or "UNKNOWN"),
            method=str(decision.get("method") or "unknown"),
            reason=str(decision.get("reason") or ""),
            target_id=decision.get("target_id"),
            blocked=blocked,
        )
    except Exception:
        # Observability should not block write paths.
        return


async def _run_write_lane(operation: str, task):
    if not ENABLE_WRITE_LANE_QUEUE:
        return await task()
    return await runtime_state.write_lanes.run_write(
        session_id=_DASHBOARD_WRITE_SESSION_ID,
        operation=operation,
        task=task,
    )


def _make_uri(domain: str, path: str) -> str:
    return f"{domain}://{path.strip('/')}" if path else f"{domain}://"


def _parse_uri(uri: str) -> tuple[str, str]:
    domain, _, remainder = str(uri).partition("://")
    return domain.strip().lower(), remainder.strip().strip("/")


def _snapshot_session_id() -> str:
    scope = _resolve_current_database_scope()
    fingerprint = str(scope.get("database_fingerprint") or "").strip()
    if not fingerprint:
        return _DASHBOARD_WRITE_SESSION_ID
    return f"{_DASHBOARD_WRITE_SESSION_ID}-{fingerprint[:12]}"


async def _snapshot_memory_content(client: Any, uri: str) -> bool:
    manager = get_snapshot_manager()
    session_id = _snapshot_session_id()
    domain, path = _parse_uri(uri)
    memory = await client.get_memory_by_path(path, domain, reinforce_access=False)
    if not memory:
        return False

    resource_id = f"memory:{memory['id']}"
    if manager.has_snapshot(session_id, resource_id):
        return False
    if manager.find_memory_snapshot_by_uri(session_id, uri):
        return False

    all_paths: list[str] = []
    get_memory_by_id = getattr(client, "get_memory_by_id", None)
    if callable(get_memory_by_id):
        memory_full = await get_memory_by_id(memory["id"])
        if isinstance(memory_full, dict):
            raw_paths = memory_full.get("paths") or []
            if isinstance(raw_paths, list):
                all_paths = [str(item) for item in raw_paths if str(item).strip()]

    return manager.create_snapshot(
        session_id=session_id,
        resource_id=resource_id,
        resource_type="memory",
        snapshot_data={
            "operation_type": "modify_content",
            "memory_id": memory["id"],
            "uri": uri,
            "domain": domain,
            "path": path,
            "all_paths": all_paths,
        },
    )


async def _snapshot_path_meta(client: Any, uri: str) -> bool:
    manager = get_snapshot_manager()
    session_id = _snapshot_session_id()
    if manager.has_snapshot(session_id, uri):
        return False

    domain, path = _parse_uri(uri)
    memory = await client.get_memory_by_path(path, domain, reinforce_access=False)
    if not memory:
        return False

    return manager.create_snapshot(
        session_id=session_id,
        resource_id=uri,
        resource_type="path",
        snapshot_data={
            "operation_type": "modify_meta",
            "domain": domain,
            "path": path,
            "uri": uri,
            "memory_id": memory["id"],
            "priority": memory.get("priority"),
            "disclosure": memory.get("disclosure"),
        },
    )


def _snapshot_path_create(
    uri: str,
    memory_id: int,
    *,
    operation_type: str = "create",
    target_uri: str | None = None,
) -> bool:
    manager = get_snapshot_manager()
    session_id = _snapshot_session_id()
    domain, path = _parse_uri(uri)
    snapshot_data = {
        "operation_type": operation_type,
        "domain": domain,
        "path": path,
        "uri": uri,
        "memory_id": memory_id,
    }
    if target_uri:
        snapshot_data["target_uri"] = target_uri
    return manager.create_snapshot(
        session_id=session_id,
        resource_id=uri,
        resource_type="path",
        snapshot_data=snapshot_data,
    )


async def _snapshot_path_delete(client: Any, uri: str) -> bool:
    manager = get_snapshot_manager()
    session_id = _snapshot_session_id()
    existing = manager.get_snapshot(session_id, uri)
    if existing:
        existing_op = existing.get("data", {}).get("operation_type")
        if existing_op in ("create", "create_alias"):
            content_snap_id = manager.find_memory_snapshot_by_uri(session_id, uri)
            if content_snap_id:
                manager.delete_snapshot(session_id, content_snap_id)
            manager.delete_snapshot(session_id, uri)
            return False

    domain, path = _parse_uri(uri)
    memory = await client.get_memory_by_path(path, domain, reinforce_access=False)
    if not memory:
        return False

    priority = memory.get("priority")
    disclosure = memory.get("disclosure")
    if existing and existing.get("data", {}).get("operation_type") == "modify_meta":
        priority = existing["data"].get("priority", priority)
        disclosure = existing["data"].get("disclosure", disclosure)

    return manager.create_snapshot(
        session_id=session_id,
        resource_id=uri,
        resource_type="path",
        snapshot_data={
            "operation_type": "delete",
            "domain": domain,
            "path": path,
            "uri": uri,
            "memory_id": memory["id"],
            "priority": priority,
            "disclosure": disclosure,
        },
        force=True,
    )


@router.get("/node")
async def get_node(
    path: str = Query("", description="URI path like 'memory-palace' or 'memory-palace/salem'"),
    domain: str = Query("core"),
    _auth: None = Depends(require_maintenance_api_key),
):
    """
    Get a node's content and its direct children.
    
    This is the only read endpoint you need - it gives you:
    - The current node's full content (or virtual root)
    - Preview of all children (next level)
    - Breadcrumb trail for navigation
    """
    client = get_sqlite_client()
    domain = _normalize_domain_or_422(domain)
    
    if not path:
        # Virtual Root Node
        memory = {
            "content": "",
            "priority": 0,
            "disclosure": None,
            "created_at": None
        }
        # Get roots as children (no memory_id = virtual root)
        children_raw = await client.get_children(None, domain=domain)
        breadcrumbs = [{"path": "", "label": "root"}]
    else:
        # Get the node itself
        memory = await client.get_memory_by_path(
            path, domain=domain, reinforce_access=False
        )
        
        if not memory:
            raise HTTPException(status_code=404, detail=f"Path not found: {domain}://{path}")
        
        # Get children across all aliases of this memory
        children_raw = await client.get_children(memory["id"])
        
        # Build breadcrumbs
        segments = path.split("/")
        breadcrumbs = [{"path": "", "label": "root"}]
        accumulated = ""
        for seg in segments:
            accumulated = f"{accumulated}/{seg}" if accumulated else seg
            breadcrumbs.append({"path": accumulated, "label": seg})
    
    children = [
        {
            "domain": c["domain"],
            "path": c["path"],
            "uri": f"{c['domain']}://{c['path']}",
            "name": c["path"].split("/")[-1],  # Last segment
            "priority": c["priority"],
            "disclosure": c.get("disclosure"),
            "content_snippet": c["content_snippet"],
            "gist_text": c.get("gist_text"),
            "gist_method": c.get("gist_method"),
            "gist_quality": c.get("gist_quality"),
            "source_hash": c.get("gist_source_hash"),
        }
        for c in children_raw
    ]
    children.sort(key=lambda x: (x["priority"] if x["priority"] is not None else 999, x["path"]))
    
    # Get all aliases (other paths pointing to the same memory)
    aliases = []
    if path and memory.get("id"):
        async with client.session() as session:
            result = await session.execute(
                select(PathModel.domain, PathModel.path)
                .where(PathModel.memory_id == memory["id"])
            )
            aliases = [
                f"{row[0]}://{row[1]}"
                for row in result.all()
                if not (row[0] == domain and row[1] == path)  # exclude current
            ]
    
    return {
        "node": {
            "path": path,
            "domain": domain,
            "uri": f"{domain}://{path}",
            "name": path.split("/")[-1] if path else "root",
            "content": memory["content"],
            "priority": memory["priority"],
            "disclosure": memory["disclosure"],
            "created_at": memory["created_at"],
            "aliases": aliases,
            "gist_text": memory.get("gist_text"),
            "gist_method": memory.get("gist_method"),
            "gist_quality": memory.get("gist_quality"),
            "source_hash": memory.get("gist_source_hash"),
        },
        "children": children,
        "breadcrumbs": breadcrumbs
    }


@router.post("/node")
async def create_node(
    body: NodeCreate,
    _auth: None = Depends(require_maintenance_api_key),
):
    """
    Create a new node under a parent path.
    """
    client = get_sqlite_client()
    parent_path = body.parent_path.strip().strip("/")
    domain = _ensure_writable_domain_or_422(body.domain, operation="create_node")
    title = (body.title or "").strip() or None

    async def _write_task():
        try:
            guard_decision = _normalize_guard_decision(
                await client.write_guard(
                    content=body.content,
                    domain=domain,
                    path_prefix=parent_path if parent_path else None,
                )
            )
        except Exception as exc:
            guard_decision = _normalize_guard_decision(
                {
                    "action": "NOOP",
                    "reason": f"write_guard_unavailable: {exc}",
                    "method": "exception",
                }
            )

        guard_action = str(guard_decision.get("action") or "NOOP").upper()
        blocked = guard_action != "ADD"
        await _record_guard_event("browse.create_node", guard_decision, blocked=blocked)
        if blocked:
            return {
                "success": False,
                "created": False,
                "reason": "write_guard_blocked",
                "message": (
                    "Skipped: write_guard blocked create_node "
                    f"(action={guard_action}, method={guard_decision.get('method')})."
                ),
                **_guard_fields(guard_decision),
            }

        result = await client.create_memory(
            parent_path=parent_path,
            content=body.content,
            priority=body.priority,
            title=title,
            disclosure=body.disclosure,
            domain=domain,
        )
        created_uri = str(result.get("uri") or _make_uri(domain, result["path"]))
        _snapshot_path_create(created_uri, int(result["id"]), operation_type="create")
        return {
            "success": True,
            "created": True,
            **result,
            **_guard_fields(guard_decision),
        }

    try:
        result = await _run_write_lane("browse.create_node", _write_task)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return result


@router.put("/node")
async def update_node(
    path: str = Query(...),
    domain: str = Query("core"),
    body: NodeUpdate = ...,
    _auth: None = Depends(require_maintenance_api_key),
):
    """
    Update a node's content.
    """
    client = get_sqlite_client()
    domain = _ensure_writable_domain_or_422(domain, operation="update_node")
    
    # Check exists
    memory = await client.get_memory_by_path(
        path, domain=domain, reinforce_access=False
    )
    if not memory:
        raise HTTPException(status_code=404, detail=f"Path not found: {domain}://{path}")

    async def _write_task():
        lane_memory = await client.get_memory_by_path(
            path, domain=domain, reinforce_access=False
        )
        if not lane_memory:
            raise HTTPException(
                status_code=404, detail=f"Path not found: {domain}://{path}"
            )

        if body.content is not None:
            try:
                guard_decision = _normalize_guard_decision(
                    await client.write_guard(
                        content=body.content,
                        domain=domain,
                        path_prefix=path.rsplit("/", 1)[0] if "/" in path else None,
                        exclude_memory_id=lane_memory.get("id"),
                    )
                )
            except Exception as exc:
                guard_decision = _normalize_guard_decision(
                    {
                        "action": "NOOP",
                        "reason": f"write_guard_unavailable: {exc}",
                        "method": "exception",
                    }
                )
        else:
            guard_decision = _normalize_guard_decision(
                {"action": "BYPASS", "reason": "metadata_only_update", "method": "none"},
                allow_bypass=True,
            )

        guard_action = str(guard_decision.get("action") or "NOOP").upper()
        blocked = False
        if body.content is not None:
            if guard_action == "ADD":
                blocked = False
            elif guard_action == "UPDATE":
                target_id = guard_decision.get("target_id")
                current_memory_id = lane_memory.get("id")
                if (
                    not isinstance(target_id, int)
                    or not isinstance(current_memory_id, int)
                    or target_id != current_memory_id
                ):
                    blocked = True
            else:
                blocked = True

        await _record_guard_event("browse.update_node", guard_decision, blocked=blocked)
        if blocked:
            return {
                "success": False,
                "updated": False,
                "reason": "write_guard_blocked",
                "message": (
                    "Skipped: write_guard blocked update_node "
                    f"(action={guard_action}, method={guard_decision.get('method')})."
                ),
                **_guard_fields(guard_decision),
            }

        full_uri = _make_uri(domain, path)
        if body.content is not None:
            await _snapshot_memory_content(client, full_uri)
        if body.priority is not None or body.disclosure is not None:
            await _snapshot_path_meta(client, full_uri)

        result = await client.update_memory(
            path=path,
            domain=domain,
            content=body.content,
            priority=body.priority,
            disclosure=body.disclosure,
        )
        return {
            "success": True,
            "updated": True,
            "memory_id": result["new_memory_id"],
            **_guard_fields(guard_decision),
        }

    # Update (creates new version if content changed, updates path metadata otherwise)
    try:
        result = await _run_write_lane("browse.update_node", _write_task)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return result


@router.delete("/node")
async def delete_node(
    path: str = Query(...),
    domain: str = Query("core"),
    _auth: None = Depends(require_maintenance_api_key),
):
    """
    Delete a single path. If the path has children, this operation is rejected.
    """
    client = get_sqlite_client()
    domain = _ensure_writable_domain_or_422(domain, operation="delete_node")
    full_uri = _make_uri(domain, path)

    async def _write_task():
        await _snapshot_path_delete(client, full_uri)
        return await client.remove_path(path=path, domain=domain)

    try:
        result = await _run_write_lane("browse.delete_node", _write_task)
    except ValueError as e:
        message = str(e)
        if "not found" in message:
            raise HTTPException(status_code=404, detail=message)
        raise HTTPException(status_code=409, detail=message)

    return {"success": True, **result}
