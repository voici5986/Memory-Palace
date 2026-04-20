import pytest

import mcp_server


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
    ],
)
def test_parse_uri_rejects_control_surrogate_and_invisible_characters(uri: str) -> None:
    with pytest.raises(ValueError, match="control|surrogate|invisible|format"):
        mcp_server.parse_uri(uri)


def test_parse_uri_keeps_legacy_bare_paths_for_non_windows_inputs() -> None:
    assert mcp_server.parse_uri("memory-palace") == ("core", "memory-palace")
