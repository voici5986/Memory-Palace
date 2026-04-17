import asyncio

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

        rollback = client.post(
            "/maintenance/learn/jobs/reflect-job-execute/rollback",
            headers=headers,
            json={"reason": "rollback reflection workflow"},
        )

    assert rollback.status_code == 200
    assert rollback.json()["status"] == "rolled_back"
    assert client_stub.deleted_memory_ids == [7]
    summary = asyncio.run(maintenance_api.runtime_state.import_learn_tracker.summary())
    assert summary["operation_decision_breakdown"]["reflection_workflow|rolled_back"] == 1


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
