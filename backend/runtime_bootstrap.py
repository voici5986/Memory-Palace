from __future__ import annotations

import os
import sqlite3
import stat
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

from db import get_sqlite_client
from runtime_state import runtime_state


_LEGACY_REQUIRED_TABLE_NAMES: tuple[str, ...] = ("memories",)


def _extract_sqlite_file_path(database_url: Optional[str]) -> Optional[Path]:
    """Extract a local sqlite file path from a sqlite+aiosqlite URL."""
    if not database_url:
        return None
    prefix = "sqlite+aiosqlite:///"
    if not database_url.startswith(prefix):
        return None
    raw_path = database_url[len(prefix):]
    raw_path = raw_path.split("?", 1)[0].split("#", 1)[0]
    raw_path = unquote(raw_path)
    if not raw_path:
        return None
    if raw_path == ":memory:" or raw_path.startswith("file::memory:"):
        return None
    if raw_path.startswith("/") or (
        len(raw_path) >= 3 and raw_path[1] == ":" and raw_path[2] == "/"
    ):
        return Path(raw_path)
    return Path(raw_path)


def _is_regular_file_no_symlink(path: Path) -> bool:
    try:
        file_mode = path.stat(follow_symlinks=False).st_mode
    except OSError:
        return False
    return stat.S_ISREG(file_mode)


def _sqlite_quick_check_ok(conn: sqlite3.Connection) -> bool:
    try:
        rows = conn.execute("PRAGMA quick_check(1)").fetchall()
    except sqlite3.Error:
        return False
    if len(rows) != 1 or not rows[0]:
        return False
    return str(rows[0][0]).strip().lower() == "ok"


def _sqlite_has_required_legacy_tables(conn: sqlite3.Connection) -> bool:
    placeholders = ",".join("?" for _ in _LEGACY_REQUIRED_TABLE_NAMES)
    if not placeholders:
        return True
    try:
        rows = conn.execute(
            f"""
            SELECT name
            FROM sqlite_master
            WHERE type='table'
              AND name IN ({placeholders})
            LIMIT 1
            """,
            tuple(_LEGACY_REQUIRED_TABLE_NAMES),
        ).fetchall()
    except sqlite3.Error:
        return False
    return bool(rows)


def try_restore_legacy_sqlite_file(database_url: Optional[str]) -> None:
    """
    Restore legacy sqlite filenames into the current target path during upgrades.
    """
    target_path = _extract_sqlite_file_path(database_url)
    if not target_path or target_path.exists():
        return
    target_dir = target_path.parent
    if not target_dir.exists():
        return

    legacy_candidates = (
        "agent_memory.db",
        "nocturne_memory.db",
        "nocturne.db",
    )
    for legacy_name in legacy_candidates:
        legacy_path = target_dir / legacy_name
        if not legacy_path.exists():
            continue

        if not _is_regular_file_no_symlink(legacy_path):
            print(
                f"[compat] Skipped legacy database file {legacy_path}: "
                "not a regular file"
            )
            continue

        target_dir.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(f"file:{legacy_path}?mode=ro", uri=True) as source_conn:
                if not _sqlite_quick_check_ok(source_conn):
                    print(
                        f"[compat] Skipped legacy database file {legacy_path}: "
                        "sqlite quick_check failed"
                    )
                    continue
                if not _sqlite_has_required_legacy_tables(source_conn):
                    print(
                        f"[compat] Skipped legacy database file {legacy_path}: "
                        "missing expected legacy tables"
                    )
                    continue
                with sqlite3.connect(target_path) as target_conn:
                    source_conn.backup(target_conn)
        except sqlite3.Error as exc:
            print(
                f"[compat] Skipped legacy database file {legacy_path}: "
                f"sqlite error: {exc}"
            )
            if target_path.exists():
                try:
                    target_path.unlink()
                except OSError:
                    pass
            continue

        print(
            f"[compat] Restored legacy database file from {legacy_path} "
            f"to {target_path}"
        )
        return


def _try_restore_legacy_sqlite_file(database_url: Optional[str]) -> None:
    try_restore_legacy_sqlite_file(database_url)


async def initialize_backend_runtime(*, ensure_runtime_started: bool = True) -> None:
    """
    Keep API, stdio MCP, and standalone SSE startup paths aligned.
    """
    try_restore_legacy_sqlite_file(os.getenv("DATABASE_URL"))
    sqlite_client = get_sqlite_client()
    await sqlite_client.init_db()
    if ensure_runtime_started:
        await runtime_state.ensure_started(get_sqlite_client)
