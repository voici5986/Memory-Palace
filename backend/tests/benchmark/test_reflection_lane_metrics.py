import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pytest

import runtime_state as runtime_state_module
from runtime_state import ReflectionLaneCoordinator


BENCHMARK_DIR = Path(__file__).resolve().parent
if str(BENCHMARK_DIR) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_DIR))


REFLECTION_LANE_JSON_ARTIFACT = BENCHMARK_DIR / "reflection_lane_metrics.json"


def _write_artifact(payload: Dict[str, Any]) -> None:
    REFLECTION_LANE_JSON_ARTIFACT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_reflection_lane_metrics_threshold_and_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNTIME_REFLECTION_LANE_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_REFLECTION_GLOBAL_CONCURRENCY", "1")
    monkeypatch.setenv("RUNTIME_REFLECTION_ACQUIRE_TIMEOUT_SECONDS", "0.001")
    real_wait_for = runtime_state_module.asyncio.wait_for
    call_count = 0

    async def _fake_wait_for(awaitable, timeout):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            if asyncio.iscoroutine(awaitable):
                awaitable.close()
            raise asyncio.TimeoutError()
        return await real_wait_for(awaitable, timeout)

    monkeypatch.setattr(runtime_state_module.asyncio, "wait_for", _fake_wait_for)
    lane = ReflectionLaneCoordinator()

    await lane.run_reflection(
        operation="reflection_success",
        task=lambda: asyncio.sleep(0.001, result="ok"),
    )
    timeout_error = ""
    try:
        await lane.run_reflection(
            operation="reflection_timeout",
            task=lambda: asyncio.sleep(0.01, result="late"),
        )
    except RuntimeError as exc:
        timeout_error = str(exc)

    status = await lane.status()
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "tasks_total": status.get("tasks_total", 0),
        "tasks_failed": status.get("tasks_failed", 0),
        "wait_ms_p95": status.get("wait_ms_p95", 0),
        "duration_ms_p95": status.get("duration_ms_p95", 0),
        "last_error": status.get("last_error"),
        "timeout_degrade_correct": timeout_error == "reflection_lane_timeout",
        "gate_pass": timeout_error == "reflection_lane_timeout"
        and int(status.get("tasks_total", 0)) >= 2,
    }
    _write_artifact(payload)

    assert "tasks_total" in status
    assert "wait_ms_p95" in status
    assert payload["gate_pass"] is True
    assert REFLECTION_LANE_JSON_ARTIFACT.exists()
