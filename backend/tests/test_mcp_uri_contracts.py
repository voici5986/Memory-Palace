import pytest

import mcp_server


def test_parse_uri_rejects_windows_drive_paths() -> None:
    with pytest.raises(ValueError, match="Filesystem paths like 'C:/...' are not valid memory URIs"):
        mcp_server.parse_uri("C:/Users/test/memory.txt")


def test_parse_uri_keeps_legacy_bare_paths_for_non_windows_inputs() -> None:
    assert mcp_server.parse_uri("memory-palace") == ("core", "memory-palace")
