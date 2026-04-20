import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pytest

from runtime_state import ReflectionLaneCoordinator


BENCHMARK_DIR = Path(__file__).resolve().parent
if str(BENCHMARK_DIR) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_DIR))

from helpers.common import (
    BENCHMARK_ARTIFACT_DIR,
    benchmark_artifact_path,
    load_thresholds_v1,
)


REFLECTION_LANE_JSON_ARTIFACT = benchmark_artifact_path("reflection_lane_metrics.json")


def _write_artifact(payload: Dict[str, Any]) -> None:
    REFLECTION_LANE_JSON_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
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
    monkeypatch.setenv("RUNTIME_REFLECTION_ACQUIRE_TIMEOUT_SECONDS", "0.1")

    lane = ReflectionLaneCoordinator()
    started = asyncio.Event()
    release = asyncio.Event()

    async def _hold_lane() -> str:
        started.set()
        await release.wait()
        return "ok"

    first_task = asyncio.create_task(
        lane.run_reflection(
            operation="reflection_success",
            task=_hold_lane,
        )
    )
    await started.wait()

    timeout_error = ""
    try:
        await lane.run_reflection(
            operation="reflection_timeout",
            task=lambda: asyncio.sleep(0, result="late"),
        )
    except RuntimeError as exc:
        timeout_error = str(exc)
    finally:
        release.set()
        await first_task

    status = await lane.status()
    thresholds = load_thresholds_v1()["reflection_lane"]
    payload = {
        "schema_version": "v1",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "tasks_total": status.get("tasks_total", 0),
        "tasks_failed": status.get("tasks_failed", 0),
        "wait_ms_p95": status.get("wait_ms_p95", 0),
        "duration_ms_p95": status.get("duration_ms_p95", 0),
        "last_error": status.get("last_error"),
        "timeout_degrade_correct": timeout_error == "reflection_lane_timeout",
        "gate_pass": timeout_error == "reflection_lane_timeout"
        and int(status.get("tasks_total", 0))
        >= int(thresholds["tasks_total_gte"]),
    }
    _write_artifact(payload)

    assert "tasks_total" in status
    assert "wait_ms_p95" in status
    assert payload["gate_pass"] is True
    assert payload["schema_version"] == "v1"
    assert int(payload["timeout_degrade_correct"]) == int(
        thresholds["timeout_degrade_correct_eq"]
    )
    assert REFLECTION_LANE_JSON_ARTIFACT.parent == BENCHMARK_ARTIFACT_DIR
    assert REFLECTION_LANE_JSON_ARTIFACT.parent != BENCHMARK_DIR
    assert REFLECTION_LANE_JSON_ARTIFACT.exists()
