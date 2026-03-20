import os
from pathlib import Path
import shlex
import shutil
import sqlite3
import subprocess

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKUP_PS1 = PROJECT_ROOT / "scripts" / "backup_memory.ps1"
BACKUP_SH = PROJECT_ROOT / "scripts" / "backup_memory.sh"


def _create_sample_sqlite(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE sample (id INTEGER PRIMARY KEY AUTOINCREMENT, value TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO sample(value) VALUES ('ok')")
        connection.commit()


def _assert_backup_has_sample(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        row = connection.execute("SELECT value FROM sample").fetchone()
    assert row == ("ok",)


def _backup_files(output_dir: Path) -> list[Path]:
    return sorted(output_dir.glob("memory_palace_backup_*.db"))


def _git_bash_executable() -> str | None:
    candidates = [
        shutil.which("bash"),
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if not path.is_file():
            continue
        normalized = str(path).replace("\\", "/").lower()
        if normalized.endswith("/windows/system32/bash.exe"):
            continue
        return str(path)
    return None


def _pwsh_executable() -> str | None:
    candidates = [
        shutil.which("pwsh"),
        r"C:\Program Files\PowerShell\7\pwsh.exe",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_file():
            return str(path)
    return None


def test_backup_memory_ps1_accepts_database_url_suffixes(tmp_path: Path) -> None:
    pwsh_bin = _pwsh_executable()
    if not pwsh_bin:
        pytest.skip("PowerShell is not available")

    db_path = tmp_path / "memory.db"
    env_path = tmp_path / ".env"
    output_dir = tmp_path / "backups"
    _create_sample_sqlite(db_path)
    env_path.write_text(
        f"DATABASE_URL=sqlite+aiosqlite:///{db_path.as_posix()}?cache=shared#read-only\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            pwsh_bin,
            "-File",
            str(BACKUP_PS1),
            "-EnvFile",
            str(env_path),
            "-OutputDir",
            str(output_dir),
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert proc.returncode == 0, proc.stderr
    backups = _backup_files(output_dir)
    assert len(backups) == 1
    _assert_backup_has_sample(backups[0])


def test_backup_memory_ps1_help_flag_shows_usage_without_writing_files(tmp_path: Path) -> None:
    pwsh_bin = _pwsh_executable()
    if not pwsh_bin:
        pytest.skip("PowerShell is not available")

    output_dir = tmp_path / "backups"

    proc = subprocess.run(
        [
            pwsh_bin,
            "-File",
            str(BACKUP_PS1),
            "-OutputDir",
            str(output_dir),
            "-?",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert proc.returncode == 0, proc.stderr
    assert "backup_memory.ps1" in proc.stdout
    assert not output_dir.exists()


def test_backup_memory_ps1_uses_repo_venv_when_python_missing_from_path(tmp_path: Path) -> None:
    pwsh_bin = _pwsh_executable()
    if not pwsh_bin:
        pytest.skip("PowerShell is not available")

    db_path = tmp_path / "memory.db"
    env_path = tmp_path / ".env"
    output_dir = tmp_path / "backups"
    _create_sample_sqlite(db_path)
    env_path.write_text(
        f"DATABASE_URL=sqlite+aiosqlite:///{db_path.as_posix()}?mode=ro#snapshot\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(Path(pwsh_bin).parent), r"C:\Windows\System32"])

    proc = subprocess.run(
        [
            pwsh_bin,
            "-File",
            str(BACKUP_PS1),
            "-EnvFile",
            str(env_path),
            "-OutputDir",
            str(output_dir),
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )

    assert proc.returncode == 0, proc.stderr
    backups = _backup_files(output_dir)
    assert len(backups) == 1
    _assert_backup_has_sample(backups[0])


def test_backup_memory_sh_accepts_database_url_suffixes(tmp_path: Path) -> None:
    bash_bin = _git_bash_executable()
    if not bash_bin:
        pytest.skip("Git Bash is not available")

    db_path = tmp_path / "memory.db"
    env_path = tmp_path / ".env"
    output_dir = tmp_path / "backups"
    _create_sample_sqlite(db_path)
    env_path.write_text(
        f"DATABASE_URL=sqlite+aiosqlite:///{db_path.as_posix()}?mode=ro#snapshot\n",
        encoding="utf-8",
    )
    command = " ".join(
        [
            shlex.quote("scripts/backup_memory.sh"),
            "--env-file",
            shlex.quote(str(env_path).replace("\\", "/")),
            "--output-dir",
            shlex.quote(str(output_dir).replace("\\", "/")),
        ]
    )

    proc = subprocess.run(
        [
            bash_bin,
            "-lc",
            command,
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert proc.returncode == 0, proc.stderr
    backups = _backup_files(output_dir)
    assert len(backups) == 1
    _assert_backup_has_sample(backups[0])


def test_backup_memory_sh_uses_incremental_backup_and_cleans_partial_file() -> None:
    script_text = BACKUP_SH.read_text(encoding="utf-8")

    assert 'sqlite3.connect(sqlite_path, timeout=30.0)' in script_text
    assert 'source_conn.execute("PRAGMA busy_timeout = 30000")' in script_text
    assert 'target_conn.execute("PRAGMA busy_timeout = 30000")' in script_text
    assert "source_conn.backup(target_conn, pages=256, sleep=0.05)" in script_text
    assert "dest_file.unlink(missing_ok=True)" in script_text
    assert 'fail(f"SQLite backup failed: {exc}")' in script_text


def test_backup_memory_ps1_uses_incremental_backup_and_cleans_partial_file() -> None:
    script_text = BACKUP_PS1.read_text(encoding="utf-8")

    assert 'sqlite3.connect(source, timeout=30.0)' in script_text
    assert 'source_conn.execute("PRAGMA busy_timeout = 30000")' in script_text
    assert 'target_conn.execute("PRAGMA busy_timeout = 30000")' in script_text
    assert "source_conn.backup(target_conn, pages=256, sleep=0.05)" in script_text
    assert "os.remove(target)" in script_text
