import asyncio
import sqlite3

import pytest

from runtime_state import WriteLaneCoordinator


@pytest.mark.asyncio
async def test_write_lane_status_includes_new_metrics_fields_with_defaults() -> None:
    coordinator = WriteLaneCoordinator()

    status = await coordinator.status()

    assert status["global_concurrency"] >= 1
    assert status["global_active"] == 0
    assert status["global_waiting"] == 0
    assert status["session_waiting_count"] == 0
    assert status["session_waiting_sessions"] == 0
    assert status["max_session_waiting"] == 0
    assert status["wait_warn_ms"] >= 1
    assert status["writes_total"] == 0
    assert status["writes_failed"] == 0
    assert status["writes_success"] == 0
    assert status["failure_rate"] == 0.0
    assert status["session_wait_ms_p95"] == 0
    assert status["global_wait_ms_p95"] == 0
    assert status["duration_ms_p95"] == 0
    assert status["last_error"] is None


@pytest.mark.asyncio
async def test_write_lane_metrics_track_outcomes_and_latency_percentiles() -> None:
    coordinator = WriteLaneCoordinator()

    async def _hold(started: asyncio.Event) -> str:
        started.set()
        await asyncio.sleep(0.03)
        return "hold_done"

    async def _ok(value: str) -> str:
        return value

    global_started = asyncio.Event()
    global_first = asyncio.create_task(
        coordinator.run_write(
            session_id="global-first",
            operation="create_memory",
            task=lambda: _hold(global_started),
        )
    )
    await global_started.wait()
    global_second = await coordinator.run_write(
        session_id="global-second",
        operation="create_memory",
        task=lambda: _ok("global_waited"),
    )
    assert global_second == "global_waited"
    assert await global_first == "hold_done"

    session_started = asyncio.Event()
    session_first = asyncio.create_task(
        coordinator.run_write(
            session_id="shared-session",
            operation="update_memory",
            task=lambda: _hold(session_started),
        )
    )
    await session_started.wait()
    session_second = await coordinator.run_write(
        session_id="shared-session",
        operation="update_memory",
        task=lambda: _ok("session_waited"),
    )
    assert session_second == "session_waited"
    assert await session_first == "hold_done"

    async def _fail() -> str:
        raise RuntimeError("write_failed_for_test")

    with pytest.raises(RuntimeError, match="write_failed_for_test"):
        await coordinator.run_write(
            session_id="failure-session",
            operation="delete_memory",
            task=_fail,
        )

    status = await coordinator.status()

    assert status["writes_total"] == 5
    assert status["writes_success"] == 4
    assert status["writes_failed"] == 1
    assert status["failure_rate"] == pytest.approx(0.2)
    assert status["session_wait_ms_p95"] > 0
    assert status["global_wait_ms_p95"] > 0
    assert status["duration_ms_p95"] > 0
    assert status["last_error"] == "write_failed_for_test"
    assert coordinator._session_locks == {}
    assert coordinator._session_waiting == {}


@pytest.mark.asyncio
async def test_write_lane_metrics_count_cancelled_global_wait_as_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNTIME_WRITE_GLOBAL_CONCURRENCY", "1")
    coordinator = WriteLaneCoordinator()
    release_holder = asyncio.Event()

    async def _hold_global_slot() -> str:
        await release_holder.wait()
        return "holder_done"

    async def _quick_success() -> str:
        return "quick_done"

    holder = asyncio.create_task(
        coordinator.run_write(
            session_id="holder",
            operation="create_memory",
            task=_hold_global_slot,
        )
    )

    for _ in range(100):
        if (await coordinator.status())["global_active"] == 1:
            break
        await asyncio.sleep(0.001)
    else:
        pytest.fail("holder did not acquire global write slot in time")

    waiter = asyncio.create_task(
        coordinator.run_write(
            session_id="waiter",
            operation="update_memory",
            task=_quick_success,
        )
    )

    for _ in range(100):
        if (await coordinator.status())["global_waiting"] >= 1:
            break
        await asyncio.sleep(0.001)
    else:
        pytest.fail("waiter did not enter global waiting state in time")

    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter

    release_holder.set()
    assert await holder == "holder_done"

    post_result = await asyncio.wait_for(
        coordinator.run_write(
            session_id="post-cancel",
            operation="delete_memory",
            task=_quick_success,
        ),
        timeout=0.2,
    )
    assert post_result == "quick_done"

    status = await coordinator.status()

    assert status["global_waiting"] == 0
    assert status["global_active"] == 0
    assert status["writes_total"] == 3
    assert status["writes_success"] == 2
    assert status["writes_failed"] == 1
    assert status["failure_rate"] == pytest.approx(1 / 3)
    assert status["last_error"] == "cancelled"
    assert coordinator._session_locks == {}
    assert coordinator._session_waiting == {}


@pytest.mark.asyncio
async def test_write_lane_metrics_survive_second_cancellation_during_recording(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNTIME_WRITE_GLOBAL_CONCURRENCY", "1")
    coordinator = WriteLaneCoordinator()
    release_holder = asyncio.Event()
    metrics_started = asyncio.Event()
    original_record = coordinator._record_write_metrics

    async def _slow_record_write_metrics(**kwargs):
        metrics_started.set()
        await asyncio.sleep(0.05)
        await original_record(**kwargs)

    monkeypatch.setattr(coordinator, "_record_write_metrics", _slow_record_write_metrics)

    async def _hold_global_slot() -> str:
        await release_holder.wait()
        return "holder_done"

    async def _quick_success() -> str:
        return "quick_done"

    holder = asyncio.create_task(
        coordinator.run_write(
            session_id="holder",
            operation="create_memory",
            task=_hold_global_slot,
        )
    )

    for _ in range(100):
        if (await coordinator.status())["global_active"] == 1:
            break
        await asyncio.sleep(0.001)
    else:
        pytest.fail("holder did not acquire global write slot in time")

    waiter = asyncio.create_task(
        coordinator.run_write(
            session_id="waiter",
            operation="update_memory",
            task=_quick_success,
        )
    )

    for _ in range(100):
        if (await coordinator.status())["global_waiting"] >= 1:
            break
        await asyncio.sleep(0.001)
    else:
        pytest.fail("waiter did not enter global waiting state in time")

    waiter.cancel()
    await metrics_started.wait()
    with pytest.raises(asyncio.CancelledError):
        await waiter

    release_holder.set()
    assert await holder == "holder_done"

    for _ in range(100):
        status = await coordinator.status()
        if status["writes_failed"] == 1:
            break
        await asyncio.sleep(0.005)
    else:
        pytest.fail("cancelled write metrics were lost")

    assert status["writes_total"] == 2
    assert status["writes_success"] == 1
    assert status["writes_failed"] == 1
    assert status["last_error"] == "cancelled"


@pytest.mark.asyncio
async def test_write_lane_times_out_when_global_slot_is_held_too_long(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNTIME_WRITE_GLOBAL_CONCURRENCY", "1")
    monkeypatch.setenv("RUNTIME_WRITE_GLOBAL_ACQUIRE_TIMEOUT_SECONDS", "0.01")
    coordinator = WriteLaneCoordinator()
    release_holder = asyncio.Event()

    async def _hold_global_slot() -> str:
        await release_holder.wait()
        return "holder_done"

    async def _quick_success() -> str:
        return "quick_done"

    holder = asyncio.create_task(
        coordinator.run_write(
            session_id="holder-timeout",
            operation="create_memory",
            task=_hold_global_slot,
        )
    )

    for _ in range(100):
        if (await coordinator.status())["global_active"] == 1:
            break
        await asyncio.sleep(0.001)
    else:
        pytest.fail("holder did not acquire global write slot in time")

    with pytest.raises(RuntimeError, match="write_lane_timeout"):
        await coordinator.run_write(
            session_id="timed-out",
            operation="update_memory",
            task=_quick_success,
        )

    release_holder.set()
    assert await holder == "holder_done"

    status = await coordinator.status()

    assert status["global_waiting"] == 0
    assert status["global_active"] == 0
    assert status["writes_total"] == 2
    assert status["writes_success"] == 1
    assert status["writes_failed"] == 1
    assert status["last_error"] == "write_lane_timeout"


@pytest.mark.asyncio
async def test_write_lane_releases_idle_session_locks_after_write_completion() -> None:
    coordinator = WriteLaneCoordinator()

    async def _ok() -> str:
        return "ok"

    assert await coordinator.run_write(
        session_id="session-a",
        operation="create_memory",
        task=_ok,
    ) == "ok"
    assert await coordinator.run_write(
        session_id="session-b",
        operation="update_memory",
        task=_ok,
    ) == "ok"

    assert coordinator._session_waiting == {}
    assert coordinator._session_locks == {}


@pytest.mark.asyncio
async def test_write_lane_retries_transient_sqlite_lock_errors() -> None:
    coordinator = WriteLaneCoordinator()
    attempts = 0

    async def _flaky() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise sqlite3.OperationalError("database is locked")
        return "ok"

    assert await coordinator.run_write(
        session_id="retry-session",
        operation="update_memory",
        task=_flaky,
    ) == "ok"

    status = await coordinator.status()
    assert attempts == 2
    assert status["writes_total"] == 1
    assert status["writes_success"] == 1
    assert status["writes_failed"] == 0


@pytest.mark.asyncio
async def test_write_lane_reclaims_idle_session_lock_entries() -> None:
    coordinator = WriteLaneCoordinator()

    async def _ok() -> str:
        return "done"

    for idx in range(20):
        result = await coordinator.run_write(
            session_id=f"session-{idx}",
            operation="update_memory",
            task=_ok,
        )
        assert result == "done"

    assert coordinator._session_locks == {}
    assert coordinator._session_waiting == {}
