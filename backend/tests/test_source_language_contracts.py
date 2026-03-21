import re
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")


def _read_backend_source(relative_path: str) -> str:
    return (BACKEND_ROOT / relative_path).read_text(encoding="utf-8")


def test_selected_backend_sources_use_english_only_strings_and_docstrings() -> None:
    for relative_path in ("main.py", "api/utils.py", "mcp_server.py", "models/schemas.py"):
        source = _read_backend_source(relative_path)
        assert _CJK_PATTERN.search(source) is None, relative_path


def test_main_source_uses_logger_for_lifespan_messages() -> None:
    source = _read_backend_source("main.py")

    assert "logger = logging.getLogger(__name__)" in source
    assert "print(" not in source
    assert 'description="Persistent memory backend for AI agents."' in source


def test_review_openapi_schema_descriptions_use_english_only_text() -> None:
    from main import app

    openapi = app.openapi()
    schema_map = openapi["components"]["schemas"]

    for schema_name in (
        "DiffRequest",
        "DiffResponse",
        "SessionInfo",
        "SnapshotInfo",
        "SnapshotDetail",
        "ResourceDiff",
        "RollbackRequest",
        "RollbackResponse",
    ):
        schema = schema_map[schema_name]
        descriptions = [schema.get("description")]
        descriptions.extend(
            property_schema.get("description")
            for property_schema in schema.get("properties", {}).values()
            if property_schema.get("description")
        )
        filtered = [text for text in descriptions if isinstance(text, str) and text.strip()]

        assert filtered, schema_name
        assert all(_CJK_PATTERN.search(text) is None for text in filtered), (
            schema_name,
            filtered,
        )
