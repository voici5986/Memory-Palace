"""
Snapshot Manager for Selective Rollback

This module implements a snapshot system that allows the human to review and
selectively roll back the AI's database operations.

Design Principles:
1. Snapshots are taken BEFORE the first modification to a resource in a session
2. Multiple modifications to the same resource in one session share ONE snapshot
3. Rollback creates a NEW version with snapshot content (preserves version chain)
4. Session-based organization for easy cleanup

    Storage Structure:
    snapshots/
    └── {session_id}/
        ├── manifest.json          # Session metadata and resource index
        └── resources/
            └── {safe_resource_id}.json
"""

import json
import hashlib
import os
import shutil
import stat
import tempfile
import time
import ctypes
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
from urllib.parse import unquote


# Default snapshot directory (relative to workspace root)
DEFAULT_SNAPSHOT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "snapshots"
)

_SQLITE_URL_PREFIXES = ("sqlite+aiosqlite:///", "sqlite:///")
_SESSION_LOCK_STALE_SECONDS = 1.0
_SESSION_LOCK_WAIT_SECONDS = 5.0
_SESSION_LOCK_POLL_INTERVAL_SECONDS = 0.05


def _resolve_current_database_scope() -> Dict[str, str]:
    """
    Build a stable scope identifier for the current database target.

    Review snapshots live under a repo-level directory, so switching
    DATABASE_URL inside the same checkout can otherwise expose unrelated
    rollback sessions from another SQLite file.
    """
    raw_url = str(os.getenv("DATABASE_URL") or "").strip()
    normalized = raw_url or "database_url:missing"
    label = normalized

    for prefix in _SQLITE_URL_PREFIXES:
        if not raw_url.startswith(prefix):
            continue
        raw_path = raw_url[len(prefix) :].split("?", 1)[0].split("#", 1)[0]
        raw_path = unquote(raw_path)
        if raw_path and raw_path not in {":memory:"} and not raw_path.startswith("file::memory:"):
            resolved_path = Path(raw_path).expanduser().resolve(strict=False)
            normalized = f"sqlite:{resolved_path.as_posix()}"
            label = resolved_path.name or resolved_path.as_posix()
        else:
            normalized = f"sqlite:{raw_path or ':memory:'}"
            label = raw_path or ":memory:"
        break

    fingerprint = hashlib.sha256(
        normalized.encode("utf-8", errors="ignore")
    ).hexdigest()
    return {
        "database_fingerprint": fingerprint,
        "database_label": label,
    }


def _handle_remove_readonly(func, path, exc_info):
    """Make read-only files writable before retrying removal."""
    exc_type, exc_value, _ = exc_info
    if issubclass(exc_type, PermissionError):
        try:
            os.chmod(path, stat.S_IWRITE)
        except OSError:
            pass
        func(path)
    else:
        raise exc_value


def _force_remove(path: str):
    """Delete files or directories regardless of read-only attributes."""
    if not os.path.exists(path):
        return
    if os.path.isdir(path):
        shutil.rmtree(path, onerror=_handle_remove_readonly)
    else:
        try:
            os.remove(path)
        except PermissionError:
            os.chmod(path, stat.S_IWRITE)
            os.remove(path)
        except FileNotFoundError:
            pass


def _write_json_atomic(path: str, payload: Dict[str, Any]) -> None:
    """Write JSON through a temp file and atomically replace the target."""
    parent_dir = os.path.dirname(path)
    if parent_dir:
        Path(parent_dir).mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{Path(path).name}.",
        suffix=".tmp",
        dir=parent_dir or None,
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            _force_remove(tmp_path)


class SnapshotManager:
    """
    Manages snapshots for selective rollback functionality.
    
    Each session (typically one agent task/conversation) has its own snapshot space.
    Within a session, each resource gets at most ONE snapshot - the state before
    the first modification.
    """
    
    def __init__(self, snapshot_dir: Optional[str] = None):
        self.snapshot_dir = snapshot_dir or DEFAULT_SNAPSHOT_DIR
        self._ensure_dir_exists(self.snapshot_dir)

    @staticmethod
    def _validate_session_id(session_id: str) -> str:
        """Validate session_id to prevent path traversal and invalid paths."""
        value = str(session_id or "").strip()
        if not value:
            raise ValueError("session_id must not be empty")
        if value in {".", ".."}:
            raise ValueError("session_id contains invalid path segment")
        if "/" in value or "\\" in value or "\x00" in value:
            raise ValueError("session_id contains invalid characters")
        return value
    
    @staticmethod
    def _ensure_dir_exists(path: str):
        """Create directory if it doesn't exist."""
        Path(path).mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def _sanitize_resource_id(resource_id: str) -> str:
        """
        Convert a resource_id to a safe filename.
        
        Resource IDs like URIs "core://path/to/memory" need sanitization.
        We use a deterministic hash suffix for uniqueness to prevent collisions
        (e.g. "core://a/b" vs "core://a_b") while keeping readability.
        """
        # Calculate hash of the ORIGINAL resource_id for uniqueness
        # This prevents "core://a/b" and "core://a_b" from colliding regardless of sanitization
        id_hash = hashlib.md5(resource_id.encode()).hexdigest()[:8]

        # Replace problematic characters
        # 1. Handle protocol separator specifically for better readability
        safe_id = resource_id.replace("://", "__")
        
        # 2. Replace remaining colons, slashes, and backslashes
        safe_id = safe_id.replace(":", "_").replace("/", "_").replace("\\", "_")
        
        # 3. Replace relation arrow
        safe_id = safe_id.replace(">", "_to_")
        
        # Truncate if too long (keeping enough distinct chars + hash)
        # Windows max path is ~260 chars. We leave plenty of buffer.
        if len(safe_id) > 100:
            safe_id = safe_id[:100]
        
        # Always append hash to guarantee uniqueness
        return f"{safe_id}_{id_hash}"
    
    def _get_session_dir(self, session_id: str) -> str:
        """Get the directory path for a session."""
        safe_session_id = self._validate_session_id(session_id)
        return os.path.join(self.snapshot_dir, safe_session_id)
    
    def _get_resources_dir(self, session_id: str) -> str:
        """Get the resources subdirectory for a session."""
        return os.path.join(self._get_session_dir(session_id), "resources")
    
    def _get_manifest_path(self, session_id: str) -> str:
        """Get the manifest file path for a session."""
        return os.path.join(self._get_session_dir(session_id), "manifest.json")
    
    def _get_snapshot_path(self, session_id: str, resource_id: str) -> str:
        """Get the snapshot file path for a specific resource."""
        safe_id = self._sanitize_resource_id(resource_id)
        return os.path.join(self._get_resources_dir(session_id), f"{safe_id}.json")

    def _get_session_lock_dir(self, session_id: str) -> str:
        """Store per-session write locks outside the session tree."""
        safe_session_id = self._validate_session_id(session_id)
        return os.path.join(self.snapshot_dir, ".locks", f"{safe_session_id}.lockdir")

    @staticmethod
    def _pid_is_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        if os.name == "nt":
            process_query_limited_information = 0x1000
            error_access_denied = 5
            still_active = 259
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            handle = kernel32.OpenProcess(
                process_query_limited_information, False, pid
            )
            if not handle:
                return ctypes.get_last_error() == error_access_denied
            try:
                exit_code = ctypes.c_ulong()
                if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)) == 0:
                    return True
                return int(exit_code.value) == still_active
            finally:
                kernel32.CloseHandle(handle)
        try:
            os.kill(pid, 0)
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    @contextmanager
    def _session_write_lock(self, session_id: str):
        """Serialize write paths for one session across processes."""
        self._ensure_dir_exists(os.path.join(self.snapshot_dir, ".locks"))
        lock_dir = self._get_session_lock_dir(session_id)
        owner_file = os.path.join(lock_dir, "owner_pid")
        deadline = time.monotonic() + _SESSION_LOCK_WAIT_SECONDS

        while True:
            try:
                os.mkdir(lock_dir)
                with open(owner_file, "w", encoding="utf-8") as handle:
                    handle.write(f"{os.getpid()}\n")
                break
            except FileExistsError:
                owner_pid = ""
                try:
                    with open(owner_file, "r", encoding="utf-8") as handle:
                        owner_pid = handle.read().strip()
                except FileNotFoundError:
                    owner_pid = ""

                should_reclaim = False
                if owner_pid:
                    try:
                        should_reclaim = not self._pid_is_alive(int(owner_pid))
                    except ValueError:
                        should_reclaim = True
                else:
                    try:
                        should_reclaim = (
                            time.time() - os.path.getmtime(lock_dir)
                        ) >= _SESSION_LOCK_STALE_SECONDS
                    except OSError:
                        should_reclaim = True

                if should_reclaim:
                    _force_remove(lock_dir)
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Timed out waiting for snapshot session lock: {session_id}"
                    )
                time.sleep(_SESSION_LOCK_POLL_INTERVAL_SECONDS)

        try:
            yield
        finally:
            _force_remove(lock_dir)
    
    def _load_manifest(self, session_id: str) -> Dict[str, Any]:
        """Load or create session manifest."""
        manifest_path = self._get_manifest_path(session_id)
        
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        scope = _resolve_current_database_scope()
        return {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "database_fingerprint": scope["database_fingerprint"],
            "database_label": scope["database_label"],
            "resources": {}  # resource_id -> metadata
        }

    @staticmethod
    def _manifest_matches_current_database(manifest: Dict[str, Any]) -> bool:
        current_scope = _resolve_current_database_scope()
        manifest_fingerprint = str(manifest.get("database_fingerprint") or "").strip()
        current_fingerprint = str(current_scope.get("database_fingerprint") or "").strip()
        if not current_fingerprint:
            return True
        if not manifest_fingerprint:
            # Hide legacy unscoped sessions by default. They are not safe to
            # expose after switching DATABASE_URL within the same checkout.
            return False
        return manifest_fingerprint == current_fingerprint
    
    def _save_manifest(self, session_id: str, manifest: Dict[str, Any]):
        """Save session manifest."""
        self._ensure_dir_exists(self._get_session_dir(session_id))
        manifest_path = self._get_manifest_path(session_id)
        scope = _resolve_current_database_scope()
        manifest.setdefault("database_fingerprint", scope["database_fingerprint"])
        manifest.setdefault("database_label", scope["database_label"])

        _write_json_atomic(manifest_path, manifest)

    def _clear_session_unlocked(
        self, session_id: str, manifest: Optional[Dict[str, Any]] = None
    ) -> int:
        """Delete one session tree while the caller already owns the write lock."""
        session_dir = self._get_session_dir(session_id)
        if not os.path.exists(session_dir):
            return 0
        payload = manifest if manifest is not None else self._load_manifest(session_id)
        count = len(payload.get("resources", {}))
        _force_remove(session_dir)
        return count
    
    def has_snapshot(self, session_id: str, resource_id: str) -> bool:
        """Check if a snapshot exists for this resource in this session."""
        # Check manifest first (handles legacy snapshots with different filename formats)
        manifest = self._load_manifest(session_id)
        if resource_id in manifest.get("resources", {}):
            return True
        
        # Fallback to file existence check
        snapshot_path = self._get_snapshot_path(session_id, resource_id)
        return os.path.exists(snapshot_path)
    
    def find_memory_snapshot_by_uri(self, session_id: str, uri: str) -> Optional[str]:
        """
        Find an existing memory content snapshot for a given URI.
        
        When a memory is updated multiple times in one session, each update
        creates a new memory_id (version chain: id=1 → id=5 → id=12 → ...).
        The snapshot resource_id is "memory:{id}", so a naive has_snapshot()
        check on the new id misses the existing snapshot for the old id.
        
        This method scans the manifest for any "memory" type snapshot whose
        stored URI matches the given one, ensuring only ONE content snapshot
        per URI per session regardless of how many updates occur.
        
        Args:
            session_id: Session identifier
            uri: The memory URI (e.g. "core://foo/bar")
            
        Returns:
            The resource_id of the existing snapshot (e.g. "memory:1"),
            or None if no matching snapshot exists.
        """
        manifest = self._load_manifest(session_id)
        for resource_id, meta in manifest.get("resources", {}).items():
            if (meta.get("resource_type") == "memory"
                    and meta.get("uri") == uri):
                return resource_id
        return None
    
    def create_snapshot(
        self,
        session_id: str,
        resource_id: str,
        resource_type: str,
        snapshot_data: Dict[str, Any],
        force: bool = False
    ) -> bool:
        """
        Create a snapshot for a resource.
        
        IMPORTANT: This should be called BEFORE any modification.
        If a snapshot already exists for this resource in this session,
        this call is a no-op (returns False) unless force=True.
        
        Args:
            session_id: Unique session identifier
            resource_id: Resource identifier (e.g., memory URI)
            resource_type: Resource type (e.g., 'memory')
            snapshot_data: The complete resource state to snapshot
            force: If True, overwrite any existing snapshot for this resource.
                   Used by delete operations to ensure the final snapshot
                   reflects the delete rather than an earlier modify.
            
        Returns:
            True if snapshot was created, False if it already existed (and force=False)
        """
        with self._session_write_lock(session_id):
            manifest = self._load_manifest(session_id)
            snapshot_path = self._get_snapshot_path(session_id, resource_id)
            if not force and (
                resource_id in manifest.get("resources", {}) or os.path.exists(snapshot_path)
            ):
                return False
            if (
                not force
                and resource_type == "memory"
                and isinstance(snapshot_data.get("uri"), str)
            ):
                for existing_id, meta in manifest.get("resources", {}).items():
                    if (
                        existing_id != resource_id
                        and meta.get("resource_type") == "memory"
                        and meta.get("uri") == snapshot_data.get("uri")
                    ):
                        return False

            self._ensure_dir_exists(self._get_resources_dir(session_id))
            snapshot = {
                "resource_id": resource_id,
                "resource_type": resource_type,
                "snapshot_time": datetime.now().isoformat(),
                "data": snapshot_data,
            }
            _write_json_atomic(snapshot_path, snapshot)

            manifest["resources"][resource_id] = {
                "resource_type": resource_type,
                "snapshot_time": snapshot["snapshot_time"],
                "operation_type": snapshot_data.get("operation_type", "modify"),
                "file": os.path.basename(snapshot_path),
                "uri": snapshot_data.get("uri"),
            }
            self._save_manifest(session_id, manifest)
            return True
    
    def get_snapshot(self, session_id: str, resource_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a snapshot for a resource.
        
        Returns:
            The snapshot data, or None if not found
        """
        # First, check manifest for the actual filename (handles legacy snapshots)
        manifest = self._load_manifest(session_id)
        if not self._manifest_matches_current_database(manifest):
            return None
        resource_meta = manifest.get("resources", {}).get(resource_id)
        
        if resource_meta and resource_meta.get("file"):
            # Use the filename recorded in manifest
            snapshot_path = os.path.join(
                self._get_resources_dir(session_id), 
                resource_meta["file"]
            )
        else:
            # Fallback to computed path (for forward compatibility)
            snapshot_path = self._get_snapshot_path(session_id, resource_id)
        
        if not os.path.exists(snapshot_path):
            return None
        
        with open(snapshot_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all sessions with snapshots.
        
        Returns:
            List of session metadata (id, created_at, resource_count)
        """
        sessions = []
        
        if not os.path.exists(self.snapshot_dir):
            return sessions
        
        for session_id in os.listdir(self.snapshot_dir):
            if session_id.startswith("."):
                continue
            session_dir = self._get_session_dir(session_id)
            if os.path.isdir(session_dir):
                manifest = self._load_manifest(session_id)
                if not self._manifest_matches_current_database(manifest):
                    continue
                resource_count = len(manifest.get("resources", {}))
                
                # Auto-cleanup empty sessions
                if resource_count == 0:
                    self.clear_session(session_id)
                    continue

                sessions.append({
                    "session_id": session_id,
                    "created_at": manifest.get("created_at"),
                    "resource_count": resource_count
                })
        
        # Sort by creation time (newest first)
        sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return sessions
    
    def list_snapshots(self, session_id: str) -> List[Dict[str, Any]]:
        """
        List all snapshots in a session.
        
        Returns:
            List of snapshot metadata (resource_id, resource_type, snapshot_time, operation_type)
        """
        manifest = self._load_manifest(session_id)
        if not self._manifest_matches_current_database(manifest):
            return []
        snapshots = []
        
        for resource_id, meta in manifest.get("resources", {}).items():
            snapshots.append({
                "resource_id": resource_id,
                "resource_type": meta.get("resource_type"),
                "snapshot_time": meta.get("snapshot_time"),
                "operation_type": meta.get("operation_type", "modify"),
                "uri": meta.get("uri")  # Display URI
            })
        
        return snapshots
    
    def delete_snapshot(self, session_id: str, resource_id: str) -> bool:
        """
        Delete a specific snapshot.
        
        Returns:
            True if deleted, False if not found
        """
        with self._session_write_lock(session_id):
            manifest = self._load_manifest(session_id)
            resource_meta = manifest.get("resources", {}).get(resource_id)

            if resource_meta and resource_meta.get("file"):
                snapshot_path = os.path.join(
                    self._get_resources_dir(session_id),
                    resource_meta["file"],
                )
            else:
                snapshot_path = self._get_snapshot_path(session_id, resource_id)

            if not os.path.exists(snapshot_path):
                return False

            _force_remove(snapshot_path)

            if resource_id in manifest.get("resources", {}):
                del manifest["resources"][resource_id]
                if not manifest["resources"]:
                    self._clear_session_unlocked(session_id, manifest)
                else:
                    self._save_manifest(session_id, manifest)

            return True
    
    def clear_session(self, session_id: str) -> int:
        """
        Delete all snapshots in a session.
        
        Returns:
            Number of snapshots deleted
        """
        with self._session_write_lock(session_id):
            return self._clear_session_unlocked(session_id)


# Global singleton
_snapshot_manager: Optional[SnapshotManager] = None


def get_snapshot_manager() -> SnapshotManager:
    """Get the global SnapshotManager instance."""
    global _snapshot_manager
    if _snapshot_manager is None:
        _snapshot_manager = SnapshotManager()
    return _snapshot_manager
