import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _extract_section_numbers(path: Path, *, chapter: str) -> list[str]:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^### ({re.escape(chapter)}\.\d+)\b", re.MULTILINE)
    return pattern.findall(text)


def test_getting_started_section_four_numbers_are_unique_and_ordered() -> None:
    assert _extract_section_numbers(
        PROJECT_ROOT / "docs" / "GETTING_STARTED.md",
        chapter="4",
    ) == ["4.1", "4.2", "4.3", "4.4"]
    assert _extract_section_numbers(
        PROJECT_ROOT / "docs" / "GETTING_STARTED_EN.md",
        chapter="4",
    ) == ["4.1", "4.2", "4.3", "4.4"]


def test_getting_started_notes_macos_and_windows_database_autofill() -> None:
    zh_text = (PROJECT_ROOT / "docs" / "GETTING_STARTED.md").read_text(encoding="utf-8")
    en_text = (PROJECT_ROOT / "docs" / "GETTING_STARTED_EN.md").read_text(
        encoding="utf-8"
    )

    assert "macOS / Windows 本地模板都会自动检测并填充 `DATABASE_URL`" in zh_text
    assert "For local macOS / Windows templates, it also automatically detects and fills in `DATABASE_URL`" in en_text


def test_readme_benchmark_reproduction_note_matches_repo_layout() -> None:
    readme_en = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    readme_zh = (PROJECT_ROOT / "README_CN.md").read_text(encoding="utf-8")

    assert "`backend/tests/benchmark/`" in readme_en
    assert "`backend/tests/benchmark/`" in readme_zh


def test_skill_install_docs_use_user_scope_as_the_default_recommendation() -> None:
    readme_en = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    readme_zh = (PROJECT_ROOT / "README_CN.md").read_text(encoding="utf-8")
    cli_guide_en = (
        PROJECT_ROOT / "docs" / "skills" / "CLI_COMPATIBILITY_GUIDE_EN.md"
    ).read_text(encoding="utf-8")
    cli_guide_zh = (
        PROJECT_ROOT / "docs" / "skills" / "CLI_COMPATIBILITY_GUIDE.md"
    ).read_text(encoding="utf-8")

    assert "User-scope install is the stable default on fresh machines" in readme_en
    assert "新机器上更稳的默认方案是 `user` 级安装" in readme_zh
    assert "The more stable default is still to start with `--scope user --with-mcp`." in cli_guide_en
    assert "默认更稳的推荐是先跑 `--scope user --with-mcp`" in cli_guide_zh
