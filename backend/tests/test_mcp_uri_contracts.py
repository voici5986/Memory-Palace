from pathlib import Path
import json

import pytest

import mcp_server
from db.sqlite_client import SQLiteClient


def _sqlite_url(db_path: Path) -> str:
    return f"sqlite+aiosqlite:///{db_path}"


def test_parse_uri_rejects_windows_drive_paths() -> None:
    with pytest.raises(ValueError, match="Filesystem paths like 'C:/...' are not valid memory URIs"):
        mcp_server.parse_uri("C:/Users/test/memory.txt")


@pytest.mark.parametrize(
    "uri",
    [
        "core://bad\x00node",
        "core://bad\x1fnode",
        "core://bad\ud800node",
        "core://bad\u200bnode",
        "core://bad%00node",
        "C%3A/Users/test/memory.txt",
    ],
)
def test_parse_uri_rejects_control_surrogate_and_invisible_characters(uri: str) -> None:
    with pytest.raises(
        ValueError,
        match="control|surrogate|invisible|format|Filesystem paths like 'C:/...'",
    ):
        mcp_server.parse_uri(uri)


def test_parse_uri_keeps_legacy_bare_paths_for_non_windows_inputs() -> None:
    assert mcp_server.parse_uri("memory-palace") == ("core", "memory-palace")


@pytest.mark.parametrize(
    ("uri", "expected"),
    [
        ("core://foo%20bar", ("core", "foo%20bar")),
        ("core://chapter_1%2Fscene_2", ("core", "chapter_1%2Fscene_2")),
    ],
)
def test_parse_uri_preserves_literal_percent_sequences(
    uri: str,
    expected: tuple[str, str],
) -> None:
    assert mcp_server.parse_uri(uri) == expected


@pytest.mark.asyncio
async def test_read_memory_accepts_percent_encoded_uri_for_space_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = SQLiteClient(_sqlite_url(tmp_path / "uri-contract-space-read.db"))
    await client.init_db()
    await client.create_memory(
        parent_path="",
        content="space path content",
        priority=1,
        title="foo bar",
        domain="core",
    )

    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: client)

    rendered = await mcp_server.read_memory("core://foo%20bar")

    await client.close()
    assert "MEMORY: core://foo bar" in rendered
    assert "space path content" in rendered


@pytest.mark.asyncio
async def test_read_memory_keeps_literal_percent_paths_addressable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = SQLiteClient(_sqlite_url(tmp_path / "uri-contract-literal-percent.db"))
    await client.init_db()
    await client.create_memory(
        parent_path="",
        content="literal percent content",
        priority=1,
        title="foo%20bar",
        domain="core",
    )

    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: client)

    rendered = await mcp_server.read_memory("core://foo%20bar")

    await client.close()
    assert "MEMORY: core://foo%20bar" in rendered
    assert "literal percent content" in rendered


@pytest.mark.asyncio
async def test_read_memory_accepts_percent_encoded_slashes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = SQLiteClient(_sqlite_url(tmp_path / "uri-contract-encoded-slash.db"))
    await client.init_db()
    await client.create_memory(
        parent_path="",
        content="chapter root",
        priority=1,
        title="chapter_1",
        domain="core",
    )
    await client.create_memory(
        parent_path="chapter_1",
        content="scene content",
        priority=1,
        title="scene_2",
        domain="core",
    )

    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: client)

    rendered = await mcp_server.read_memory("core://chapter_1%2Fscene_2")

    await client.close()
    assert "MEMORY: core://chapter_1/scene_2" in rendered
    assert "scene content" in rendered


@pytest.mark.asyncio
async def test_delete_memory_accepts_percent_encoded_uri_for_space_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = SQLiteClient(_sqlite_url(tmp_path / "uri-contract-space-delete.db"))
    await client.init_db()
    await client.create_memory(
        parent_path="",
        content="delete target",
        priority=1,
        title="foo bar",
        domain="core",
    )

    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: client)

    result = await mcp_server.delete_memory("core://foo%20bar")
    deleted = await client.get_memory_by_path("foo bar", "core")

    await client.close()
    assert "Success: Memory 'core://foo bar' deleted." in result
    assert deleted is None


@pytest.mark.asyncio
async def test_create_memory_accepts_percent_encoded_parent_uri(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = SQLiteClient(_sqlite_url(tmp_path / "uri-contract-space-parent.db"))
    await client.init_db()
    await client.create_memory(
        parent_path="",
        content="parent content",
        priority=1,
        title="foo bar",
        domain="core",
    )

    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: client)

    result = await mcp_server.create_memory(
        "core://foo%20bar",
        "child content",
        priority=1,
        title="child",
    )
    child = await client.get_memory_by_path("foo bar/child", "core")

    await client.close()
    assert json.loads(result)["created"] is True
    assert child is not None
