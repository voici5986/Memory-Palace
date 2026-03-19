import json
import threading
from pathlib import Path

import db.snapshot as snapshot_module
from db.snapshot import SnapshotManager


def _sqlite_url(db_path: Path) -> str:
    return f"sqlite+aiosqlite:///{db_path}"


def test_snapshot_manager_filters_sessions_by_current_database_scope(
    monkeypatch,
    tmp_path: Path,
) -> None:
    manager = SnapshotManager(str(tmp_path / "snapshots"))
    db_a = tmp_path / "scope-a.db"
    db_b = tmp_path / "scope-b.db"

    monkeypatch.setenv("DATABASE_URL", _sqlite_url(db_a))
    created = manager.create_snapshot(
        "session-a",
        "notes://alpha",
        "path",
        {
            "uri": "notes://alpha",
            "operation_type": "create",
        },
    )
    assert created is True

    manifest_a = json.loads(
        (tmp_path / "snapshots" / "session-a" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest_a["database_label"] == "scope-a.db"
    assert manager.list_sessions()[0]["session_id"] == "session-a"

    monkeypatch.setenv("DATABASE_URL", _sqlite_url(db_b))
    created = manager.create_snapshot(
        "session-b",
        "notes://beta",
        "path",
        {
            "uri": "notes://beta",
            "operation_type": "create",
        },
    )
    assert created is True

    sessions = manager.list_sessions()
    assert [item["session_id"] for item in sessions] == ["session-b"]
    assert manager.list_snapshots("session-a") == []
    assert manager.get_snapshot("session-a", "notes://alpha") is None


def test_snapshot_manager_hides_legacy_unscoped_sessions_when_database_scope_is_set(
    monkeypatch,
    tmp_path: Path,
) -> None:
    snapshot_dir = tmp_path / "snapshots"
    session_dir = snapshot_dir / "legacy-session"
    resources_dir = session_dir / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)

    (resources_dir / "legacy.json").write_text(
        json.dumps(
            {
                "resource_id": "notes://legacy",
                "resource_type": "path",
                "snapshot_time": "2026-03-11T00:00:00",
                "data": {
                    "uri": "notes://legacy",
                    "operation_type": "create",
                },
            }
        ),
        encoding="utf-8",
    )
    (session_dir / "manifest.json").write_text(
        json.dumps(
            {
                "session_id": "legacy-session",
                "created_at": "2026-03-11T00:00:00",
                "resources": {
                    "notes://legacy": {
                        "resource_type": "path",
                        "snapshot_time": "2026-03-11T00:00:00",
                        "operation_type": "create",
                        "file": "legacy.json",
                        "uri": "notes://legacy",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("DATABASE_URL", _sqlite_url(tmp_path / "active.db"))
    manager = SnapshotManager(str(snapshot_dir))

    assert manager.list_sessions() == []
    assert manager.list_snapshots("legacy-session") == []
    assert manager.get_snapshot("legacy-session", "notes://legacy") is None


def test_snapshot_manager_serializes_same_session_manifest_updates(
    monkeypatch,
    tmp_path: Path,
) -> None:
    manager = SnapshotManager(str(tmp_path / "snapshots"))
    session_id = "shared-session"
    first_save_started = threading.Event()
    release_first_save = threading.Event()
    second_save_started = threading.Event()
    save_call_count = 0
    save_call_guard = threading.Lock()
    original_save_manifest = manager._save_manifest
    failures: list[Exception] = []
    results: dict[str, bool] = {}

    def delayed_save_manifest(target_session_id: str, manifest: dict[str, object]) -> None:
        nonlocal save_call_count
        with save_call_guard:
            save_call_count += 1
            current_call = save_call_count
        if target_session_id == session_id and current_call == 1:
            first_save_started.set()
            assert release_first_save.wait(timeout=2)
        elif target_session_id == session_id and current_call == 2:
            second_save_started.set()
        original_save_manifest(target_session_id, manifest)

    def create_named_snapshot(name: str) -> None:
        try:
            results[name] = manager.create_snapshot(
                session_id,
                f"notes://{name}",
                "path",
                {
                    "uri": f"notes://{name}",
                    "operation_type": "create",
                },
            )
        except Exception as exc:  # pragma: no cover - surfaced by assertion below
            failures.append(exc)

    monkeypatch.setattr(manager, "_save_manifest", delayed_save_manifest)

    first_thread = threading.Thread(target=create_named_snapshot, args=("alpha",))
    second_thread = threading.Thread(target=create_named_snapshot, args=("beta",))

    first_thread.start()
    assert first_save_started.wait(timeout=2)

    second_thread.start()
    assert not second_save_started.wait(timeout=0.3)

    release_first_save.set()
    first_thread.join(timeout=2)
    second_thread.join(timeout=2)

    assert failures == []
    assert results == {"alpha": True, "beta": True}

    manifest = json.loads(
        (tmp_path / "snapshots" / session_id / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert set(manifest["resources"]) == {"notes://alpha", "notes://beta"}


def test_snapshot_manager_windows_pid_check_uses_win32_api(
    monkeypatch,
) -> None:
    class _FakeKernel32:
        def __init__(self) -> None:
            self.closed_handles: list[int] = []

        def OpenProcess(self, access: int, inherit: bool, pid: int) -> int:
            assert access == 0x1000
            assert inherit is False
            assert pid == 4242
            return 99

        def GetExitCodeProcess(self, handle: int, exit_code_ptr) -> int:
            assert handle == 99
            exit_code_ptr._obj.value = 259
            return 1

        def CloseHandle(self, handle: int) -> int:
            self.closed_handles.append(handle)
            return 1

    fake_kernel32 = _FakeKernel32()
    monkeypatch.setattr(snapshot_module.os, "name", "nt", raising=False)
    monkeypatch.setattr(
        snapshot_module.ctypes,
        "WinDLL",
        lambda *_args, **_kwargs: fake_kernel32,
        raising=False,
    )
    monkeypatch.setattr(
        snapshot_module.ctypes,
        "get_last_error",
        lambda: 0,
        raising=False,
    )
    monkeypatch.setattr(
        snapshot_module.os,
        "kill",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("os.kill should not be used on Windows")
        ),
        raising=False,
    )

    assert SnapshotManager._pid_is_alive(4242) is True
    assert fake_kernel32.closed_handles == [99]
