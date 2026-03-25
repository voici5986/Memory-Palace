import asyncio
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

import mcp_server
from api import review as review_api
from db.snapshot import SnapshotManager
from db.sqlite_client import SQLiteClient
from runtime_state import IndexTaskWorker


def _sqlite_url(db_path: Path) -> str:
    return f"sqlite+aiosqlite:///{db_path}"


class _RacyDeleteClient:
    def __init__(self) -> None:
        self.current = {
            "id": 1,
            "content": "stale before lane",
            "priority": 1,
            "created_at": "2026-03-20T11:59:00Z",
        }

    async def delete_path_atomically(self, _path: str, _domain: str, *, before_delete=None):
        memory = dict(self.current) if self.current is not None else None
        if memory is None:
            raise ValueError("Path 'core://agent/stale' not found")
        if before_delete is not None:
            await before_delete(dict(memory))
        return {
            "removed_uri": "core://agent/stale",
            "memory_id": memory["id"],
            "deleted_memory": memory,
        }


@pytest.mark.asyncio
async def test_delete_memory_reads_current_path_state_inside_write_lane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _RacyDeleteClient()
    captured: dict[str, object] = {}
    updated_memory = {
        "id": 99,
        "content": "new occupant at delete time",
        "priority": 7,
        "created_at": "2026-03-20T12:00:00Z",
    }

    async def _noop_async(*_args, **_kwargs) -> None:
        return None

    async def _run_write_lane_swap(_operation: str, task):
        client.current = updated_memory
        return await task()

    async def _capture_session_hit(**kwargs) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: client)
    monkeypatch.setattr(mcp_server, "_snapshot_path_delete", _noop_async)
    monkeypatch.setattr(mcp_server, "_run_write_lane", _run_write_lane_swap)
    monkeypatch.setattr(mcp_server, "_record_session_hit", _capture_session_hit)
    monkeypatch.setattr(mcp_server, "_record_flush_event", _noop_async)
    monkeypatch.setattr(mcp_server, "_maybe_auto_flush", _noop_async)
    monkeypatch.setattr(mcp_server, "_utc_iso_now", lambda: "2026-03-20T12:00:00Z")

    raw = await mcp_server.delete_memory("core://agent/stale")
    payload = json.loads(raw)

    assert payload["ok"] is True
    assert captured["memory_id"] == 99
    assert captured["priority"] == 7
    assert "new occupant at delete time" in str(captured["snippet"])


def test_index_worker_preserves_pending_jobs_across_event_loop_rebind() -> None:
    worker = IndexTaskWorker()

    with asyncio.Runner() as runner:
        enqueue_result = runner.run(worker.enqueue_rebuild(reason="loop-a"))
        first_status = runner.run(worker.status())

    assert enqueue_result["queued"] is True
    assert first_status["queue_depth"] == 1

    with asyncio.Runner() as runner:
        job_payload = runner.run(worker.get_job(job_id=enqueue_result["job_id"]))
        second_status = runner.run(worker.status())

    assert job_payload["ok"] is True
    assert job_payload["job"]["status"] == "queued"
    assert second_status["queue_depth"] == 1
    assert second_status["rebuild_pending"] is True


def test_snapshot_manager_rejects_zero_width_session_id(tmp_path: Path) -> None:
    manager = SnapshotManager(str(tmp_path / "snapshots"))

    with pytest.raises(ValueError, match="invisible or control characters"):
        manager.create_snapshot(
            "review\u200b-session",
            "notes://alpha",
            "path",
            {
                "uri": "notes://alpha",
                "operation_type": "create",
            },
        )


def test_review_validator_rejects_zero_width_session_id() -> None:
    with pytest.raises(HTTPException) as exc_info:
        review_api._validate_session_id_or_400("review\u200b-session")

    assert exc_info.value.status_code == 400
    assert "invisible or control characters" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_rollback_to_memory_restores_primary_metadata_without_overwriting_alias_metadata(
    tmp_path: Path,
) -> None:
    client = SQLiteClient(_sqlite_url(tmp_path / "rollback-alias-metadata.db"))
    await client.init_db()

    original = await client.create_memory(
        parent_path="",
        content="version 1",
        priority=1,
        title="agent",
        domain="core",
        disclosure="old disclosure",
    )
    await client.add_path(
        new_path="agent-alias",
        target_path="agent",
        new_domain="core",
        target_domain="core",
        priority=9,
        disclosure="alias disclosure",
    )
    await client.update_memory(
        path="agent",
        content="version 2",
        priority=5,
        disclosure="new disclosure",
        domain="core",
    )

    await client.rollback_to_memory(
        "agent",
        original["id"],
        "core",
        restore_path_metadata=True,
        restore_priority=1,
        restore_disclosure="old disclosure",
    )

    primary = await client.get_memory_by_path("agent", "core", reinforce_access=False)
    alias = await client.get_memory_by_path(
        "agent-alias",
        "core",
        reinforce_access=False,
    )
    await client.close()

    assert primary is not None
    assert alias is not None
    assert primary["id"] == original["id"]
    assert alias["id"] == original["id"]
    assert primary["priority"] == 1
    assert alias["priority"] == 9
    assert primary["disclosure"] == "old disclosure"
    assert alias["disclosure"] == "alias disclosure"
