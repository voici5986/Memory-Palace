from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _load_harness():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "evaluate_memory_palace_mcp_e2e.py"
    spec = importlib.util.spec_from_file_location("evaluate_memory_palace_mcp_e2e", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_live_mcp_stdio_e2e_suite_passes() -> None:
    harness = _load_harness()
    results, stderr_output = harness.run_suite_sync()

    failing = [item for item in results if item.status == "FAIL"]
    assert not failing, [(item.name, item.summary, item.details) for item in failing]
    assert "bound to a different event loop" not in stderr_output


def test_repo_local_stdio_command_uses_python_wrapper_on_windows(
    monkeypatch, tmp_path: Path
) -> None:
    harness = _load_harness()
    project_root = tmp_path / "Memory-Palace"
    backend_root = project_root / "backend"

    monkeypatch.setattr(harness, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(harness, "BACKEND_ROOT", backend_root)
    monkeypatch.setattr(harness.os, "name", "nt")
    monkeypatch.setattr(harness.sys, "executable", r"C:\Python313\python.exe")

    command, args = harness._repo_local_stdio_command()

    assert command == r"C:\Python313\python.exe"
    assert args == [str(backend_root / "mcp_wrapper.py")]


def test_resolve_report_path_supports_relative_override_under_temp_root(
    monkeypatch, tmp_path: Path
) -> None:
    harness = _load_harness()
    monkeypatch.setenv("MEMORY_PALACE_MCP_E2E_REPORT_PATH", "tmp/custom-e2e-report.md")
    monkeypatch.setattr(harness, "REPORT_OVERRIDE_ROOT", tmp_path / "tmp-root")

    resolved = harness._resolve_report_path()

    assert resolved == tmp_path / "tmp-root" / "tmp" / "custom-e2e-report.md"


def test_python_wrapper_live_stdio_smoke() -> None:
    harness = _load_harness()
    backend_python = harness._resolve_backend_python()
    if backend_python is None:
        raise AssertionError("backend virtualenv python is required for python-wrapper smoke")

    results, stderr_output = harness.run_suite_sync(
        repo_local_command=(
            str(backend_python),
            [str(harness.BACKEND_ROOT / "mcp_wrapper.py")],
        )
    )

    failing = [item for item in results if item.status == "FAIL"]
    assert not failing, [(item.name, item.summary, item.details) for item in failing]
    assert "tool_inventory" in {item.name for item in results}
    assert "bound to a different event loop" not in stderr_output
