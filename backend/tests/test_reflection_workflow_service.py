import pytest

import mcp_server
from runtime_state import ImportLearnAuditTracker


class _FakeFlushTracker:
    def __init__(self, summary: str) -> None:
        self.summary = summary

    async def build_summary(self, *, session_id: str | None, limit: int = 12) -> str:
        _ = session_id
        _ = limit
        return self.summary


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
