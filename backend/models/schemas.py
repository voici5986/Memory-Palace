from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class DiffRequest(BaseModel):
    """Request payload for text diff comparison."""

    text_a: str = Field(..., description="Original text")
    text_b: str = Field(..., description="Updated text")


class DiffResponse(BaseModel):
    """Response payload for text diff comparison."""

    diff_html: str = Field(..., description="HTML-formatted diff")
    diff_unified: str = Field(..., description="Unified diff")
    summary: str = Field(..., description="Change summary")


# Review / rollback models.

class SessionInfo(BaseModel):
    """Review session metadata."""

    session_id: str
    created_at: Optional[str] = None
    resource_count: int


class SnapshotInfo(BaseModel):
    """Snapshot metadata."""

    resource_id: str
    resource_type: str  # "path" or "memory"
    snapshot_time: str
    operation_type: Optional[str] = "modify"
    uri: Optional[str] = None  # Display URI when resource_id uses the internal memory:{id} form.


class SnapshotDetail(BaseModel):
    """Detailed snapshot payload."""

    resource_id: str
    resource_type: str
    snapshot_time: str
    data: Dict[str, Any]


class ResourceDiff(BaseModel):
    """Diff between a snapshot and the current resource state."""

    resource_id: str
    resource_type: str
    snapshot_time: str
    snapshot_data: Dict[str, Any]  # Full state captured in the snapshot.
    current_data: Dict[str, Any]   # Current full state.
    diff_unified: str
    diff_summary: str
    has_changes: bool


class RollbackRequest(BaseModel):
    """Request payload for snapshot rollback."""

    task_description: Optional[str] = Field(
        "Rollback to snapshot by human",
        description="Task description recorded in version history",
    )


class RollbackResponse(BaseModel):
    """Rollback result payload."""

    resource_id: str
    resource_type: str
    success: bool
    message: str
    new_version: Optional[int] = None
