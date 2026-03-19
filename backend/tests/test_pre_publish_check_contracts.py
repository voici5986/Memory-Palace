from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_pre_publish_check_uses_cross_platform_python_scans_and_env_globs() -> None:
    script_text = (PROJECT_ROOT / "scripts" / "pre_publish_check.sh").read_text(
        encoding="utf-8"
    )

    assert 'resolve_python_cmd()' in script_text
    assert 'resolve_python_project_root()' in script_text
    assert 'build_personal_path_scan_regex()' in script_text
    assert '".env.*"' in script_text
    assert '".playwright-cli"' in script_text
    assert 'python3 python' in script_text
    assert 'C:/Users/' in script_text
    assert 'cygpath -w "${PROJECT_ROOT}"' in script_text
    assert '"/windowsapps/"' in script_text
    assert 'MSYS2_ARG_CONV_EXCL="*"' in script_text
    assert 'xargs -0 rg -l -n --no-messages' not in script_text
    assert "rg -n '^[A-Z0-9_]*API_KEY=.+$' .env.example" not in script_text


def test_apply_profile_shell_accepts_crlf_windows_placeholder_lines() -> None:
    script_text = (PROJECT_ROOT / "scripts" / "apply_profile.sh").read_text(
        encoding="utf-8"
    )

    assert r"agent_memory\\.db\r?$" in script_text
