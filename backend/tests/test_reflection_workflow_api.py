import asyncio
import importlib
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import maintenance as maintenance_api
from runtime_state import ImportLearnAuditTracker


class _ReflectionClientStub:
    def __init__(self) -> None:
        self.meta: dict[str, str] = {}
        self.deleted_memory_ids: list[int] = []

    async def set_runtime_meta(self, key: str, value: str) -> None:
        self.meta[key] = value

    async def get_runtime_meta(self, key: str):
        return self.meta.get(key)

    async def permanently_delete_memory(
        self,
        memory_id: int,
        *,
        require_orphan: bool = False,
    ):
        _ = require_orphan
        self.deleted_memory_ids.append(memory_id)
        return {"deleted_memory_id": memory_id}


def _build_client(*, raise_server_exceptions: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(maintenance_api.router)
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def test_reflection_prepare_registers_learn_job(monkeypatch: pytest.MonkeyPatch) -> None:
    client_stub = _ReflectionClientStub()
    tracker = ImportLearnAuditTracker()
    headers = {"X-MCP-API-Key": "reflection-secret"}
    monkeypatch.setattr(maintenance_api, "get_sqlite_client", lambda: client_stub)
    monkeypatch.setattr(maintenance_api.runtime_state, "import_learn_tracker", tracker)
    monkeypatch.setattr(maintenance_api, "_LEARN_JOBS", {})
    monkeypatch.setenv("MCP_API_KEY", "reflection-secret")

    async def _service(**kwargs):
        _ = kwargs
        return {
            "ok": True,
            "mode": "prepare",
            "source": "session_summary",
            "reason_text": "prepare reflection workflow",
            "session_id": "session-reflect",
            "prepared": True,
            "executed": False,
            "review_id": "reflect-job-prepare",
            "job_id": "reflect-job-prepare",
            "result": {
                "accepted": True,
                "reason": "prepared",
                "batch_id": "reflect-job-prepare",
                "domain": "notes",
                "path_prefix": "corrections",
                "target_parent_uri": "notes://corrections/session-reflect",
            },
        }

    monkeypatch.setattr(maintenance_api, "_REFLECTION_WORKFLOW_SERVICE", _service)

    with _build_client() as client:
        response = client.post(
            "/maintenance/learn/reflection",
            headers=headers,
            json={
                "mode": "prepare",
                "source": "session_summary",
                "reason": "prepare reflection workflow",
                "session_id": "session-reflect",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == "reflect-job-prepare"
    assert payload["job_type"] == "learn"
    assert payload["job"]["workflow_operation"] == "reflection_workflow"
    assert payload["rollback_endpoint"] == "/maintenance/import/jobs/reflect-job-prepare/rollback"
    assert "reflect-job-prepare" in maintenance_api._LEARN_JOBS


def test_reflection_execute_rollback_updates_reflection_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_stub = _ReflectionClientStub()
    tracker = ImportLearnAuditTracker()
    headers = {"X-MCP-API-Key": "reflection-secret"}
    monkeypatch.setattr(maintenance_api, "get_sqlite_client", lambda: client_stub)
    monkeypatch.setattr(maintenance_api.runtime_state, "import_learn_tracker", tracker)
    monkeypatch.setattr(maintenance_api, "_LEARN_JOBS", {})
    monkeypatch.setenv("MCP_API_KEY", "reflection-secret")

    async def _service(**kwargs):
        _ = kwargs
        return {
            "ok": True,
            "mode": "execute",
            "source": "session_summary",
            "reason_text": "execute reflection workflow",
            "session_id": "session-reflect",
            "prepared": False,
            "executed": True,
            "review_id": "reflect-job-execute",
            "job_id": "reflect-job-execute",
            "snapshot_id": 7,
            "review_snapshot": {
                "session_id": "session-reflect",
                "resource_id": "notes://corrections/session-reflect/learn-123",
                "resource_type": "path",
            },
            "rollback": {
                "enabled": True,
                "mode": "delete_memory_id",
                "memory_id": 7,
            },
            "result": {
                "accepted": True,
                "executed": True,
                "reason": "executed",
                "batch_id": "reflect-job-execute",
                "domain": "notes",
                "path_prefix": "corrections",
                "created_memory": {
                    "id": 7,
                    "uri": "notes://corrections/session-reflect/learn-123",
                    "path": "corrections/session-reflect/learn-123",
                },
                "created_namespace_memories": [],
                "review_snapshot": {
                    "session_id": "session-reflect",
                    "resource_id": "notes://corrections/session-reflect/learn-123",
                    "resource_type": "path",
                },
                "rollback": {
                    "enabled": True,
                    "mode": "delete_memory_id",
                    "memory_id": 7,
                },
            },
        }

    monkeypatch.setattr(maintenance_api, "_REFLECTION_WORKFLOW_SERVICE", _service)

    with _build_client() as client:
        execute = client.post(
            "/maintenance/learn/reflection",
            headers=headers,
            json={
                "mode": "execute",
                "source": "session_summary",
                "reason": "execute reflection workflow",
                "session_id": "session-reflect",
            },
        )
        assert execute.status_code == 200
        execute_payload = execute.json()
        assert execute_payload["rollback_endpoint"] == (
            "/review/sessions/session-reflect/rollback/"
            "notes%3A%2F%2Fcorrections%2Fsession-reflect%2Flearn-123"
    )
        assert execute_payload["rollback_endpoint_aliases"] == [
            "/review/sessions/session-reflect/rollback/"
            "notes%3A%2F%2Fcorrections%2Fsession-reflect%2Flearn-123",
            "/maintenance/learn/jobs/reflect-job-execute/rollback",
        ]
    assert client_stub.deleted_memory_ids == []
    summary = asyncio.run(maintenance_api.runtime_state.import_learn_tracker.summary())
    assert summary.get("operation_decision_breakdown", {}).get(
        "reflection_workflow|rolled_back", 0
    ) == 0


def test_reflection_job_rollback_route_delegates_to_review_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _MetaOnlyClient:
        async def set_runtime_meta(self, key: str, value: str) -> None:
            _ = key, value

        async def get_runtime_meta(self, key: str):
            _ = key
            return None

    tracker = ImportLearnAuditTracker()
    headers = {"X-MCP-API-Key": "reflection-secret"}
    rollback_calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(maintenance_api, "get_sqlite_client", lambda: _MetaOnlyClient())
    monkeypatch.setattr(maintenance_api.runtime_state, "import_learn_tracker", tracker)
    monkeypatch.setattr(maintenance_api, "_LEARN_JOBS", {})
    monkeypatch.setenv("MCP_API_KEY", "reflection-secret")

    async def _service(**kwargs):
        _ = kwargs
        return {
            "ok": True,
            "mode": "execute",
            "source": "session_summary",
            "reason_text": "execute reflection workflow",
            "session_id": "session-reflect",
            "prepared": False,
            "executed": True,
            "review_id": "reflect-job-execute",
            "job_id": "reflect-job-execute",
            "snapshot_id": 7,
            "review_snapshot": {
                "session_id": "session-reflect",
                "resource_id": "notes://corrections/session-reflect/learn-123",
                "resource_type": "path",
            },
            "result": {
                "accepted": True,
                "executed": True,
                "reason": "executed",
                "batch_id": "reflect-job-execute",
                "domain": "notes",
                "path_prefix": "corrections",
                "created_memory": {
                    "id": 7,
                    "uri": "notes://corrections/session-reflect/learn-123",
                    "path": "corrections/session-reflect/learn-123",
                },
                "created_namespace_memories": [],
                "review_snapshot": {
                    "session_id": "session-reflect",
                    "resource_id": "notes://corrections/session-reflect/learn-123",
                    "resource_type": "path",
                },
            },
        }

    class _FakeRollbackRequest:
        def __init__(self, task_description: str = "Rollback to snapshot by human") -> None:
            self.task_description = task_description

    async def _fake_rollback_resource(session_id: str, resource_id: str, request):
        rollback_calls.append((session_id, resource_id, request.task_description))
        return {
            "resource_id": resource_id,
            "resource_type": "path",
            "success": True,
            "message": "Rolled back through review snapshot.",
            "new_version": None,
        }

    fake_review_module = types.SimpleNamespace(
        RollbackRequest=_FakeRollbackRequest,
        rollback_resource=_fake_rollback_resource,
    )
    real_import_module = importlib.import_module

    def _fake_import_module(name: str):
        if name == "api.review":
            return fake_review_module
        return real_import_module(name)

    monkeypatch.setattr(maintenance_api, "_REFLECTION_WORKFLOW_SERVICE", _service)
    monkeypatch.setattr(maintenance_api.importlib, "import_module", _fake_import_module)

    with _build_client() as client:
        execute = client.post(
            "/maintenance/learn/reflection",
            headers=headers,
            json={
                "mode": "execute",
                "source": "session_summary",
                "reason": "execute reflection workflow",
                "session_id": "session-reflect",
            },
        )
        assert execute.status_code == 200

        rollback = client.post(
            "/maintenance/learn/jobs/reflect-job-execute/rollback",
            headers=headers,
            json={"reason": "rollback reflection workflow"},
        )

    assert rollback.status_code == 200
    assert rollback.json()["status"] == "rolled_back"
    assert rollback_calls == [
        (
            "session-reflect",
            "notes://corrections/session-reflect/learn-123",
            "rollback reflection workflow",
        )
    ]


def test_reflection_invalid_mode_returns_422(monkeypatch: pytest.MonkeyPatch) -> None:
    headers = {"X-MCP-API-Key": "reflection-secret"}
    monkeypatch.setenv("MCP_API_KEY", "reflection-secret")

    async def _service(**kwargs):
        _ = kwargs
        raise ValueError("unsupported reflection workflow mode")

    monkeypatch.setattr(maintenance_api, "_REFLECTION_WORKFLOW_SERVICE", _service)

    with _build_client(raise_server_exceptions=False) as client:
        response = client.post(
            "/maintenance/learn/reflection",
            headers=headers,
            json={
                "mode": "bogus",
                "source": "session_summary",
                "reason": "invalid mode",
                "session_id": "session-reflect",
            },
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "reflection_workflow_invalid_mode"
    assert detail["reason"] == "unsupported_reflection_mode"
    assert detail["allowed_modes"] == ["prepare", "execute", "rollback"]


def test_reflection_prepare_requires_session_id(monkeypatch: pytest.MonkeyPatch) -> None:
    headers = {"X-MCP-API-Key": "reflection-secret"}
    monkeypatch.setenv("MCP_API_KEY", "reflection-secret")

    async def _service(**kwargs):
        raise AssertionError("service should not be called without session_id")

    monkeypatch.setattr(maintenance_api, "_REFLECTION_WORKFLOW_SERVICE", _service)

    with _build_client(raise_server_exceptions=False) as client:
        response = client.post(
            "/maintenance/learn/reflection",
            headers=headers,
            json={
                "mode": "prepare",
                "source": "session_summary",
                "reason": "missing session id",
            },
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "reflection_workflow_invalid_request"
    assert detail["reason"] == "session_id_required"
    assert detail["mode"] == "prepare"


def test_reflection_rollback_requires_job_id(monkeypatch: pytest.MonkeyPatch) -> None:
    headers = {"X-MCP-API-Key": "reflection-secret"}
    monkeypatch.setenv("MCP_API_KEY", "reflection-secret")

    async def _service(**kwargs):
        raise AssertionError("service should not be called without job_id")

    monkeypatch.setattr(maintenance_api, "_REFLECTION_WORKFLOW_SERVICE", _service)

    with _build_client(raise_server_exceptions=False) as client:
        response = client.post(
            "/maintenance/learn/reflection",
            headers=headers,
            json={
                "mode": "rollback",
                "reason": "missing job id",
            },
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "reflection_workflow_invalid_request"
    assert detail["reason"] == "job_id_required"
    assert detail["mode"] == "rollback"


def test_reflection_mode_rollback_delegates_to_learn_job_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = {"X-MCP-API-Key": "reflection-secret"}
    monkeypatch.setenv("MCP_API_KEY", "reflection-secret")

    calls: list[dict[str, str | None]] = []

    async def _service(**kwargs):
        calls.append(
            {
                "mode": str(kwargs.get("mode")),
                "job_id": str(kwargs.get("job_id")),
                "reason": str(kwargs.get("reason")),
                "session_id": str(kwargs.get("session_id") or ""),
            }
        )
        handler = kwargs["rollback_handler"]
        return await handler(
            job_id=str(kwargs.get("job_id") or ""),
            reason_text=str(kwargs.get("reason") or ""),
            session_id=str(kwargs.get("session_id") or "") or None,
            actor_id=None,
        )

    monkeypatch.setattr(maintenance_api, "_REFLECTION_WORKFLOW_SERVICE", _service)
    monkeypatch.setattr(
        maintenance_api,
        "_rollback_job",
        lambda job_id, payload, prefer_learn, allow_fallback, not_found_error: asyncio.sleep(
            0,
            result={
                "ok": True,
                "status": "rolled_back",
                "job_id": job_id,
                "job_type": "learn",
                "reason": payload.reason,
                "prefer_learn": prefer_learn,
                "allow_fallback": allow_fallback,
                "not_found_error": not_found_error,
            },
        ),
    )

    with _build_client() as client:
        response = client.post(
            "/maintenance/learn/reflection",
            headers=headers,
            json={
                "mode": "rollback",
                "reason": "rollback reflection workflow",
                "job_id": "reflect-job-execute",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "status": "rolled_back",
        "job_id": "reflect-job-execute",
        "job_type": "learn",
        "reason": "rollback reflection workflow",
        "prefer_learn": True,
        "allow_fallback": False,
        "not_found_error": "learn_job_not_found",
    }
    assert calls == [
        {
            "mode": "rollback",
            "job_id": "reflect-job-execute",
            "reason": "rollback reflection workflow",
            "session_id": "",
        }
    ]


def test_learn_trigger_execute_routes_through_write_lane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = {"X-MCP-API-Key": "reflection-secret"}
    lane_calls: list[tuple[str | None, str]] = []
    monkeypatch.setenv("MCP_API_KEY", "reflection-secret")
    monkeypatch.setattr(maintenance_api, "_LEARN_JOBS", {})

    async def _run_write_lane(operation, task, *, session_id=None):
        lane_calls.append((session_id, operation))
        return await task()

    async def _service(**kwargs):
        _ = kwargs
        return {
            "ok": True,
            "accepted": True,
            "executed": True,
            "reason": "executed",
            "batch_id": "learn-job-execute",
            "source_hash": "hash-123",
            "target_parent_uri": "notes://corrections/learn-session-1",
            "created_memory": {
                "id": 11,
                "uri": "notes://corrections/learn-session-1/learn-11",
                "path": "corrections/learn-session-1/learn-11",
            },
            "created_namespace_memories": [],
        }

    monkeypatch.setattr(maintenance_api, "_run_write_lane", _run_write_lane)
    monkeypatch.setattr(maintenance_api, "_EXPLICIT_LEARN_SERVICE", _service)

    with _build_client() as client:
        response = client.post(
            "/maintenance/learn/trigger",
            headers=headers,
            json={
                "content": "explicit correction from reviewer",
                "source": "manual_review",
                "reason": "fix factual drift",
                "session_id": "learn-session-1",
                "actor_id": "actor-a",
                "domain": "notes",
                "path_prefix": "corrections",
                "execute": True,
            },
        )

    assert response.status_code == 200
    assert lane_calls == [("learn-session-1", "maintenance.learn.trigger.execute")]


def test_reflection_execute_write_lane_timeout_returns_503_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = {"X-MCP-API-Key": "reflection-secret"}
    monkeypatch.setenv("MCP_API_KEY", "reflection-secret")
    monkeypatch.setattr(maintenance_api, "_LEARN_JOBS", {})

    async def _service(**kwargs):
        _ = kwargs
        raise RuntimeError("write_lane_timeout")

    monkeypatch.setattr(maintenance_api, "_REFLECTION_WORKFLOW_SERVICE", _service)

    with _build_client(raise_server_exceptions=False) as client:
        response = client.post(
            "/maintenance/learn/reflection",
            headers=headers,
            json={
                "mode": "execute",
                "source": "session_summary",
                "reason": "execute reflection workflow",
                "session_id": "session-reflect",
            },
        )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["error"] == "reflection_workflow_rejected"
    assert detail["reason"] == "write_lane_timeout"
    assert isinstance(detail["job_id"], str) and detail["job_id"]
    assert detail["job"]["status"] == "failed"


@pytest.mark.parametrize(
    ("path", "payload", "message"),
    [
        (
            "/maintenance/learn/trigger",
            {
                "content": "explicit correction from reviewer",
                "source": "manual_review",
                "reason": "fix factual drift",
                "session_id": " bad-session",
                "actor_id": "actor-a",
                "domain": "notes",
                "path_prefix": "corrections",
                "execute": False,
            },
            "must not contain whitespace",
        ),
        (
            "/maintenance/learn/reflection",
            {
                "mode": "prepare",
                "source": "session_summary",
                "reason": "prepare reflection workflow",
                "session_id": "bad\u200bsession",
            },
            "invisible or control characters",
        ),
    ],
)
def test_maintenance_learn_endpoints_reject_invalid_session_ids(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    payload: dict[str, object],
    message: str,
) -> None:
    headers = {"X-MCP-API-Key": "reflection-secret"}
    monkeypatch.setenv("MCP_API_KEY", "reflection-secret")

    with _build_client(raise_server_exceptions=False) as client:
        response = client.post(path, headers=headers, json=payload)

    assert response.status_code == 422
    assert message in response.text
