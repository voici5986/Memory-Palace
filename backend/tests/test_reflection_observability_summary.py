import json
from typing import Any, Dict

import pytest

import mcp_server
from api import maintenance as maintenance_api


class _ObservabilityClient:
    def __init__(self, persisted_summary: Dict[str, Any] | None = None) -> None:
        self._persisted_summary = persisted_summary

    async def get_index_status(self) -> Dict[str, Any]:
        return {"degraded": False, "index_available": True}

    async def get_gist_stats(self) -> Dict[str, Any]:
        return {"degraded": False, "total_rows": 0, "active_coverage": 0.0}

    async def get_vitality_stats(self) -> Dict[str, Any]:
        return {"degraded": False, "total_memories": 0, "low_vitality_count": 0}

    async def get_runtime_meta(self, key: str) -> str | None:
        if key != mcp_server.IMPORT_LEARN_AUDIT_META_KEY:
            return None
        if self._persisted_summary is None:
            return None
        return json.dumps(self._persisted_summary, ensure_ascii=False)


async def _noop_async(*_: Any, **__: Any) -> None:
    return None


async def _lane_status_ok() -> Dict[str, Any]:
    return {
        "global_concurrency": 1,
        "global_active": 0,
        "global_waiting": 0,
        "session_waiting_count": 0,
        "session_waiting_sessions": 0,
        "max_session_waiting": 0,
        "wait_warn_ms": 2000,
    }


async def _worker_status_ok() -> Dict[str, Any]:
    return {"enabled": True, "running": False, "recent_jobs": [], "stats": {}}


async def _simple_summary_ok() -> Dict[str, Any]:
    return {"degraded": False}


async def _sm_lite_ok() -> Dict[str, Any]:
    return {
        "degraded": False,
        "session_cache": {},
        "flush_tracker": {},
        "promotion": {},
    }


def _patch_summary_dependencies(
    monkeypatch: pytest.MonkeyPatch, client: _ObservabilityClient
) -> None:
    monkeypatch.setattr(maintenance_api, "get_sqlite_client", lambda: client)
    monkeypatch.setattr(maintenance_api.runtime_state, "ensure_started", _noop_async)
    monkeypatch.setattr(maintenance_api, "_ensure_search_events_loaded", _noop_async)
    monkeypatch.setattr(
        maintenance_api.runtime_state.index_worker, "status", _worker_status_ok
    )
    monkeypatch.setattr(
        maintenance_api.runtime_state.write_lanes, "status", _lane_status_ok
    )
    monkeypatch.setattr(
        maintenance_api.runtime_state.reflection_lanes, "status", _lane_status_ok
    )
    monkeypatch.setattr(
        maintenance_api.runtime_state.vitality_decay, "status", _simple_summary_ok
    )
    monkeypatch.setattr(
        maintenance_api.runtime_state.cleanup_reviews, "summary", _simple_summary_ok
    )
    monkeypatch.setattr(
        maintenance_api.runtime_state.sleep_consolidation, "status", _simple_summary_ok
    )
    monkeypatch.setattr(
        maintenance_api.runtime_state.guard_tracker, "summary", _simple_summary_ok
    )
    monkeypatch.setattr(maintenance_api, "_build_sm_lite_stats", _sm_lite_ok)


@pytest.mark.asyncio
async def test_reflection_workflow_counts_are_exposed_from_runtime_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_summary = {
        "window_size": 300,
        "total_events": 3,
        "event_type_breakdown": {"learn": 3},
        "operation_breakdown": {"reflection_workflow": 3},
        "decision_breakdown": {"accepted": 1, "executed": 1, "rolled_back": 1},
        "operation_decision_breakdown": {
            "reflection_workflow|accepted": 1,
            "reflection_workflow|executed": 1,
            "reflection_workflow|rolled_back": 1,
        },
        "rejected_events": 0,
        "rollback_events": 1,
        "top_reasons": [],
        "last_event_at": "2026-04-17T10:00:00Z",
        "recent_events": [],
    }
    _patch_summary_dependencies(monkeypatch, _ObservabilityClient())
    monkeypatch.setattr(
        maintenance_api.runtime_state.import_learn_tracker,
        "summary",
        lambda: _return_async(runtime_summary),
    )

    summary = await maintenance_api.get_observability_summary()

    assert summary["reflection_workflow"] == {
        "prepared": 1,
        "executed": 1,
        "rolled_back": 1,
    }


@pytest.mark.asyncio
async def test_reflection_workflow_counts_recover_from_persisted_summary_when_runtime_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_summary = {
        "window_size": 300,
        "total_events": 0,
        "event_type_breakdown": {},
        "operation_breakdown": {},
        "decision_breakdown": {},
        "operation_decision_breakdown": {},
        "rejected_events": 0,
        "rollback_events": 0,
        "top_reasons": [],
        "last_event_at": None,
        "recent_events": [],
    }
    persisted_summary = {
        "window_size": 300,
        "total_events": 4,
        "event_type_breakdown": {"learn": 4},
        "operation_breakdown": {"reflection_workflow": 4},
        "decision_breakdown": {"accepted": 2, "executed": 1, "rolled_back": 1},
        "operation_decision_breakdown": {
            "reflection_workflow|accepted": 2,
            "reflection_workflow|executed": 1,
            "reflection_workflow|rolled_back": 1,
        },
        "rejected_events": 0,
        "rollback_events": 1,
        "top_reasons": [{"reason": "prepared", "count": 2}],
        "last_event_at": "2026-04-17T10:05:00Z",
        "recent_events": [],
    }
    _patch_summary_dependencies(monkeypatch, _ObservabilityClient(persisted_summary))
    monkeypatch.setattr(
        maintenance_api.runtime_state.import_learn_tracker,
        "summary",
        lambda: _return_async(runtime_summary),
    )

    summary = await maintenance_api.get_observability_summary()

    assert summary["reflection_workflow"] == {
        "prepared": 2,
        "executed": 1,
        "rolled_back": 1,
    }


async def _return_async(payload: Dict[str, Any]) -> Dict[str, Any]:
    return payload
