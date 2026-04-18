import asyncio
import gc
import weakref

import pytest

import mcp_server
from api import browse as browse_api
from runtime_state import ImportLearnAuditTracker


class _FakeFlushTracker:
    def __init__(self, summary: str) -> None:
        self.summary = summary

    async def build_summary(self, *, session_id: str | None, limit: int = 12) -> str:
        _ = session_id
        _ = limit
        return self.summary


class _FallbackFlushTracker:
    async def build_summary(self, *, session_id: str | None, limit: int = 12) -> str:
        _ = limit
        if session_id == "dashboard-broken":
            raise RuntimeError("tracker unavailable")
        if session_id == "dashboard":
            return "Session compaction notes:\n- fallback dashboard summary"
        return ""


class _ReflectionClient:
    def __init__(self) -> None:
        self._next_id = 1
        self._paths = {}

    async def write_guard(self, **kwargs):
        _ = kwargs
        return {"action": "ADD", "method": "keyword", "reason": "ok"}

    async def get_memory_by_path(
        self,
        path: str,
        domain: str,
        reinforce_access: bool = False,
    ):
        _ = reinforce_access
        key = (str(domain or "notes"), str(path or ""))
        memory = self._paths.get(key)
        if not isinstance(memory, dict):
            return None
        return dict(memory)

    async def create_memory(self, **kwargs):
        domain = str(kwargs.get("domain") or "notes")
        parent_path = str(kwargs.get("parent_path") or "").strip().strip("/")
        title = str(kwargs.get("title") or "").strip()
        path = f"{parent_path}/{title}".strip("/")
        memory_id = self._next_id
        self._next_id += 1
        payload = {
            "id": memory_id,
            "domain": domain,
            "path": path,
            "uri": f"{domain}://{path}",
            "content": str(kwargs.get("content") or ""),
        }
        self._paths[(domain, path)] = payload
        return {
            "id": memory_id,
            "domain": domain,
            "path": path,
            "uri": f"{domain}://{path}",
        }


class _ConcurrentNamespaceRaceClient(_ReflectionClient):
    def __init__(self) -> None:
        super().__init__()
        self._namespace_probe_count = 0
        self._namespace_probe_ready = asyncio.Event()

    async def get_memory_by_path(
        self,
        path: str,
        domain: str,
        reinforce_access: bool = False,
    ):
        if str(domain or "notes") == "notes" and str(path or "") == "corrections":
            self._namespace_probe_count += 1
            if self._namespace_probe_count >= 2:
                self._namespace_probe_ready.set()
            await self._namespace_probe_ready.wait()
        return await super().get_memory_by_path(
            path,
            domain,
            reinforce_access=reinforce_access,
        )

    async def create_memory(self, **kwargs):
        domain = str(kwargs.get("domain") or "notes")
        parent_path = str(kwargs.get("parent_path") or "").strip().strip("/")
        title = str(kwargs.get("title") or "").strip()
        path = f"{parent_path}/{title}" if parent_path else title
        path = path.strip("/")
        await asyncio.sleep(0)
        if (domain, path) in self._paths:
            raise ValueError(f"Path '{domain}://{path}' already exists")
        return await super().create_memory(**kwargs)


@pytest.mark.asyncio
async def test_reflection_prepare_returns_reviewable_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTO_LEARN_EXPLICIT_ENABLED", "true")
    monkeypatch.setattr(
        mcp_server.runtime_state,
        "import_learn_tracker",
        ImportLearnAuditTracker(),
    )
    monkeypatch.setattr(
        mcp_server.runtime_state,
        "flush_tracker",
        _FakeFlushTracker(
            "Session compaction notes:\n- resolve duplicate preference memories"
        ),
    )

    payload = await mcp_server.run_reflection_workflow_service(
        mode="prepare",
        source="session_summary",
        reason="resolve duplicate preference memories",
        session_id="s-reflection-prepare",
        client=_ReflectionClient(),
    )

    assert payload["ok"] is True
    assert payload["prepared"] is True
    assert isinstance(payload.get("review_id"), str) and payload["review_id"]


@pytest.mark.asyncio
async def test_reflection_prepare_deduplicates_concurrent_same_session_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracker = ImportLearnAuditTracker()
    monkeypatch.setenv("AUTO_LEARN_EXPLICIT_ENABLED", "true")
    monkeypatch.setattr(mcp_server.runtime_state, "import_learn_tracker", tracker)
    monkeypatch.setattr(
        mcp_server.runtime_state,
        "flush_tracker",
        _FakeFlushTracker(
            "Session compaction notes:\n- resolve duplicate preference memories"
        ),
    )

    first, second = await asyncio.gather(
        mcp_server.run_reflection_workflow_service(
            mode="prepare",
            source="session_summary",
            reason="resolve duplicate preference memories",
            session_id="s-reflection-prepare-dedup",
            client=_ReflectionClient(),
        ),
        mcp_server.run_reflection_workflow_service(
            mode="prepare",
            source="session_summary",
            reason="resolve duplicate preference memories",
            session_id="s-reflection-prepare-dedup",
            client=_ReflectionClient(),
        ),
    )

    summary = await tracker.summary()

    assert first["ok"] is True
    assert second["ok"] is True
    assert first["prepared"] is True
    assert second["prepared"] is True
    assert first["review_id"] == second["review_id"]
    assert summary["operation_decision_breakdown"]["reflection_workflow|accepted"] == 1


@pytest.mark.asyncio
async def test_deduped_reflection_prepare_cancels_orphaned_task_when_last_waiter_cancels() -> None:
    mcp_server._REFLECTION_PREPARE_IN_FLIGHT.clear()
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def _factory() -> dict[str, object]:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    waiter = asyncio.create_task(
        mcp_server._run_deduped_reflection_prepare("cancel-me", _factory)
    )
    await started.wait()

    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter

    await asyncio.wait_for(cancelled.wait(), timeout=1.0)
    assert "cancel-me" not in mcp_server._REFLECTION_PREPARE_IN_FLIGHT


async def _capture_import_learn_lock() -> asyncio.Lock:
    return mcp_server._get_import_learn_meta_persist_lock()


def test_import_learn_meta_persist_locks_release_closed_event_loops() -> None:
    mcp_server._IMPORT_LEARN_META_PERSIST_LOCKS.clear()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_capture_import_learn_lock())
    assert len(mcp_server._IMPORT_LEARN_META_PERSIST_LOCKS) == 1

    loop_ref = weakref.ref(loop)
    asyncio.set_event_loop(None)
    loop.close()
    del loop
    gc.collect()

    assert loop_ref() is None
    assert len(mcp_server._IMPORT_LEARN_META_PERSIST_LOCKS) == 0


@pytest.mark.asyncio
async def test_reflection_execute_can_be_rolled_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracker = ImportLearnAuditTracker()
    monkeypatch.setenv("AUTO_LEARN_EXPLICIT_ENABLED", "true")
    monkeypatch.setattr(mcp_server.runtime_state, "import_learn_tracker", tracker)
    monkeypatch.setattr(
        mcp_server.runtime_state,
        "flush_tracker",
        _FakeFlushTracker(
            "Session compaction notes:\n- merge duplicate preference memories"
        ),
    )

    payload = await mcp_server.run_reflection_workflow_service(
        mode="execute",
        source="session_summary",
        reason="merge duplicate preference memories",
        session_id="s-reflection-execute",
        client=_ReflectionClient(),
    )

    summary = await tracker.summary()

    assert payload["ok"] is True
    assert payload["executed"] is True
    assert payload["snapshot_id"] > 0
    assert summary["operation_decision_breakdown"]["reflection_workflow|executed"] >= 1


@pytest.mark.asyncio
async def test_reflection_execute_exposes_review_snapshot_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot_calls: list[dict[str, object]] = []
    monkeypatch.setenv("AUTO_LEARN_EXPLICIT_ENABLED", "true")
    monkeypatch.setattr(
        mcp_server.runtime_state,
        "import_learn_tracker",
        ImportLearnAuditTracker(),
    )
    monkeypatch.setattr(
        mcp_server.runtime_state,
        "flush_tracker",
        _FakeFlushTracker("Session compaction notes:\n- track review rollback metadata"),
    )

    async def _snapshot_path_create(
        uri: str,
        memory_id: int,
        operation_type: str = "create",
        target_uri: str | None = None,
        *,
        session_id: str | None = None,
    ) -> bool:
        snapshot_calls.append(
            {
                "uri": uri,
                "memory_id": memory_id,
                "operation_type": operation_type,
                "target_uri": target_uri,
                "session_id": session_id,
            }
        )
        return True

    monkeypatch.setattr(mcp_server, "_snapshot_path_create", _snapshot_path_create)

    payload = await mcp_server.run_reflection_workflow_service(
        mode="execute",
        source="session_summary",
        reason="track review rollback metadata",
        session_id="s-reflection-review",
        client=_ReflectionClient(),
    )

    assert payload["ok"] is True
    assert payload["executed"] is True
    assert payload["review_snapshot"] == {
        "session_id": "s-reflection-review",
        "resource_id": payload["created_memory"]["uri"],
        "resource_type": "path",
    }
    assert snapshot_calls == [
        {
            "uri": payload["created_memory"]["uri"],
            "memory_id": payload["created_memory"]["id"],
            "operation_type": "create",
            "target_uri": None,
            "session_id": "s-reflection-review",
        }
    ]


@pytest.mark.asyncio
async def test_reflection_execute_routes_write_lane_through_explicit_session_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lane_calls: list[tuple[str | None, str]] = []
    monkeypatch.setenv("AUTO_LEARN_EXPLICIT_ENABLED", "true")
    monkeypatch.setattr(
        mcp_server.runtime_state,
        "ensure_started",
        lambda *_args, **_kwargs: asyncio.sleep(0),
    )
    monkeypatch.setattr(
        mcp_server.runtime_state,
        "flush_tracker",
        _FakeFlushTracker("Session compaction notes:\n- keep explicit session lane"),
    )
    monkeypatch.setattr(mcp_server, "get_session_id", lambda: "ambient-session")

    async def _run_write(*, session_id, operation, task):
        lane_calls.append((session_id, operation))
        return await task()

    monkeypatch.setattr(mcp_server.runtime_state.write_lanes, "run_write", _run_write)

    payload = await mcp_server.run_reflection_workflow_service(
        mode="execute",
        source="session_summary",
        reason="keep explicit session lane",
        session_id="explicit-session",
        client=_ReflectionClient(),
    )

    assert payload["ok"] is True
    assert payload["executed"] is True
    assert lane_calls == [("explicit-session", "reflection_workflow.execute")]


@pytest.mark.asyncio
async def test_reflection_workflow_service_rejects_invalid_session_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTO_LEARN_EXPLICIT_ENABLED", "true")

    payload = await mcp_server.run_reflection_workflow_service(
        mode="prepare",
        source="session_summary",
        reason="reject invalid session id",
        session_id="bad\u200bsession",
        client=_ReflectionClient(),
    )

    assert payload["ok"] is False
    assert payload["prepared"] is False
    assert payload["executed"] is False
    assert payload["reason"] == "session_id_invalid"
    assert "invisible or control characters" in payload["validation_error"]


@pytest.mark.asyncio
async def test_reflection_workflow_service_rejects_session_id_with_surrounding_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTO_LEARN_EXPLICIT_ENABLED", "true")
    monkeypatch.setattr(mcp_server, "get_session_id", lambda: "ambient-session")

    payload = await mcp_server.run_reflection_workflow_service(
        mode="prepare",
        source="session_summary",
        reason="reject whitespace-padded session id",
        session_id=" bad-session ",
        client=_ReflectionClient(),
    )

    assert payload["ok"] is False
    assert payload["prepared"] is False
    assert payload["executed"] is False
    assert payload["reason"] == "session_id_invalid"
    assert "whitespace" in payload["validation_error"]


@pytest.mark.asyncio
async def test_reflection_workflow_service_does_not_fallback_to_ambient_session_for_blank_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTO_LEARN_EXPLICIT_ENABLED", "true")
    monkeypatch.setattr(mcp_server, "get_session_id", lambda: "ambient-session")

    payload = await mcp_server.run_reflection_workflow_service(
        mode="prepare",
        source="session_summary",
        reason="reject blank session id",
        session_id="   ",
        client=_ReflectionClient(),
    )

    assert payload["ok"] is False
    assert payload["prepared"] is False
    assert payload["executed"] is False
    assert payload["reason"] == "session_id_invalid"
    assert payload["session_id"] == "   "
    assert "whitespace" in payload["validation_error"]


@pytest.mark.asyncio
async def test_reflection_workflow_service_requires_explicit_session_id_for_prepare_execute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTO_LEARN_EXPLICIT_ENABLED", "true")
    monkeypatch.setattr(mcp_server, "get_session_id", lambda: "ambient-session")

    payload = await mcp_server.run_reflection_workflow_service(
        mode="prepare",
        source="session_summary",
        reason="reject ambient fallback for missing session id",
        session_id=None,
        client=_ReflectionClient(),
    )

    assert payload["ok"] is False
    assert payload["prepared"] is False
    assert payload["executed"] is False
    assert payload["reason"] == "session_id_invalid"
    assert payload["session_id"] == ""
    assert payload["validation_error"] == "session_id is required"


@pytest.mark.asyncio
async def test_reflection_workflow_service_delegates_rollback_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    async def _rollback_handler(
        *,
        job_id: str,
        reason_text: str,
        session_id: str | None,
        actor_id: str | None,
    ) -> dict[str, object]:
        calls.append(
            {
                "job_id": job_id,
                "reason_text": reason_text,
                "session_id": session_id,
                "actor_id": actor_id,
            }
        )
        return {
            "ok": True,
            "status": "rolled_back",
            "job_id": job_id,
        }

    monkeypatch.setattr(mcp_server, "get_session_id", lambda: "ambient-session")

    payload = await mcp_server.run_reflection_workflow_service(
        mode="rollback",
        source="session_summary",
        reason="rollback reflection workflow",
        session_id=None,
        actor_id="reviewer-a",
        job_id="reflect-job-1234",
        rollback_handler=_rollback_handler,
    )

    assert payload == {
        "ok": True,
        "status": "rolled_back",
        "job_id": "reflect-job-1234",
    }
    assert calls == [
        {
            "job_id": "reflect-job-1234",
            "reason_text": "rollback reflection workflow",
            "session_id": "ambient-session",
            "actor_id": "reviewer-a",
        }
    ]


@pytest.mark.asyncio
async def test_same_session_concurrent_reflection_and_explicit_learn_do_not_fail_on_namespace_uniqueness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracker = ImportLearnAuditTracker()
    client = _ConcurrentNamespaceRaceClient()
    monkeypatch.setenv("AUTO_LEARN_EXPLICIT_ENABLED", "true")
    monkeypatch.setenv("AUTO_LEARN_ALLOWED_DOMAINS", "notes")
    monkeypatch.setenv("AUTO_LEARN_REQUIRE_REASON", "true")
    monkeypatch.setattr(mcp_server.runtime_state, "import_learn_tracker", tracker)
    monkeypatch.setattr(
        mcp_server.runtime_state,
        "flush_tracker",
        _FakeFlushTracker(
            "Session compaction notes:\n- browse write created a dashboard correction"
        ),
    )

    reflection_payload, explicit_payload = await asyncio.gather(
        mcp_server.run_reflection_workflow_service(
            mode="execute",
            source="session_summary",
            reason="promote concurrent dashboard corrections",
            session_id="s-concurrent",
            client=client,
        ),
        mcp_server.run_explicit_learn_service(
            content="dashboard explicit correction",
            source="manual_review",
            reason="promote concurrent dashboard corrections",
            session_id="s-concurrent",
            execute=True,
            client=client,
        ),
    )

    assert reflection_payload["ok"] is True
    assert reflection_payload["executed"] is True
    assert reflection_payload["result"]["reason"] == "executed"
    assert explicit_payload["ok"] is True
    assert explicit_payload["accepted"] is True
    assert explicit_payload["executed"] is True
    assert explicit_payload["reason"] == "executed"


@pytest.mark.asyncio
async def test_browse_write_seeds_dashboard_reflection_summary_instead_of_session_summary_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracker = ImportLearnAuditTracker()
    browse_client = _ReflectionClient()
    lane_calls: list[tuple[str | None, str]] = []

    async def _run_write(*, session_id, operation, task):
        lane_calls.append((session_id, operation))
        return await task()

    monkeypatch.setenv("AUTO_LEARN_EXPLICIT_ENABLED", "true")
    monkeypatch.setenv("AUTO_LEARN_ALLOWED_DOMAINS", "notes")
    monkeypatch.setenv("AUTO_LEARN_REQUIRE_REASON", "true")
    monkeypatch.setattr(mcp_server.runtime_state, "import_learn_tracker", tracker)
    monkeypatch.setattr(mcp_server.runtime_state, "flush_tracker", mcp_server.runtime_state.flush_tracker.__class__())
    monkeypatch.setattr(browse_api, "get_sqlite_client", lambda: browse_client)
    monkeypatch.setattr(browse_api.runtime_state.write_lanes, "run_write", _run_write)
    monkeypatch.setattr(browse_api, "ENABLE_WRITE_LANE_QUEUE", True)

    browse_result = await browse_api.create_node(
        browse_api.NodeCreate(
            parent_path="",
            title="dashboard_note",
            content="dashboard browse write that should be reflectable",
            priority=1,
            domain="notes",
        )
    )
    reflection_payload = await mcp_server.run_reflection_workflow_service(
        mode="prepare",
        source="session_summary",
        reason="review dashboard browse writes",
        session_id="dashboard",
        client=browse_client,
    )

    assert browse_result["success"] is True
    assert lane_calls == [("dashboard", "browse.create_node")]
    assert reflection_payload["ok"] is True
    assert reflection_payload["prepared"] is True
    assert reflection_payload["result"]["reason"] == "prepared"


@pytest.mark.asyncio
async def test_reflection_prepare_falls_back_to_dashboard_session_after_tracker_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracker = ImportLearnAuditTracker()
    monkeypatch.setenv("AUTO_LEARN_EXPLICIT_ENABLED", "true")
    monkeypatch.setattr(mcp_server.runtime_state, "import_learn_tracker", tracker)
    monkeypatch.setattr(
        mcp_server.runtime_state,
        "flush_tracker",
        _FallbackFlushTracker(),
    )

    payload = await mcp_server.run_reflection_workflow_service(
        mode="prepare",
        source="session_summary",
        reason="use dashboard fallback summary",
        session_id="dashboard-broken",
        client=_ReflectionClient(),
    )

    assert payload["ok"] is True
    assert payload["prepared"] is True
    assert payload["result"]["reason"] == "prepared"
