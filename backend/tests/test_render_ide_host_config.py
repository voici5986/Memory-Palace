from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    project_root = Path(__file__).resolve().parents[2]
    script_path = project_root / "scripts" / "render_ide_host_config.py"
    spec = importlib.util.spec_from_file_location("render_ide_host_config", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_render_payload_for_cursor_uses_repo_agents_and_bash_wrapper(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    project_root = tmp_path / "Memory-Palace"

    monkeypatch.setattr(module, "project_root", lambda: project_root)

    payload = module.render_payload("cursor", "bash")

    assert payload["host"] == "cursor"
    assert payload["canonical_skill_source"] == "docs/skills/memory-palace/"
    assert payload["skill_insertion"]["primary_rule_surface"] == str(project_root / "AGENTS.md")
    assert payload["skill_insertion"]["hidden_skill_mirrors_required"] is False
    assert payload["mcp_config"]["mcpServers"]["memory-palace"]["command"] == "bash"
    assert payload["mcp_config"]["mcpServers"]["memory-palace"]["args"] == [
        str(project_root / "scripts" / "run_memory_palace_mcp_stdio.sh")
    ]


def test_render_payload_for_antigravity_keeps_rule_fallback_and_workflow_projection(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    project_root = tmp_path / "Memory-Palace"

    monkeypatch.setattr(module, "project_root", lambda: project_root)

    payload = module.render_payload("antigravity", "bash")

    assert payload["skill_insertion"]["primary_rule_surface"] == str(project_root / "AGENTS.md")
    assert payload["skill_insertion"]["legacy_rule_fallback"] == "GEMINI.md"
    assert payload["skill_insertion"]["optional_workflow_projection"] == str(
        project_root
        / "docs"
        / "skills"
        / "memory-palace"
        / "variants"
        / "antigravity"
        / "global_workflows"
        / "memory-palace.md"
    )
    assert any("AGENTS.md first" in note for note in payload["notes"])


def test_render_payload_with_python_wrapper_uses_mcp_wrapper_path(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    project_root = tmp_path / "Memory-Palace"
    if module.os.name == "nt":
        venv_python = project_root / "backend" / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = project_root / "backend" / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    venv_python.write_text("", encoding="utf-8")

    monkeypatch.setattr(module, "project_root", lambda: project_root)

    payload = module.render_payload("vscode", "python-wrapper")

    assert payload["mcp_config"]["mcpServers"]["memory-palace"]["command"] == str(venv_python)
    assert payload["mcp_config"]["mcpServers"]["memory-palace"]["args"] == [
        str(project_root / "backend" / "mcp_wrapper.py")
    ]
    assert any("backend virtualenv interpreter" in note for note in payload["notes"])


def test_render_payload_auto_uses_python_wrapper_on_windows(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    project_root = tmp_path / "Memory-Palace"
    venv_python = project_root / "backend" / ".venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    venv_python.write_text("", encoding="utf-8")

    monkeypatch.setattr(module, "project_root", lambda: project_root)
    monkeypatch.setattr(module.os, "name", "nt")

    payload = module.render_payload("cursor", "auto")

    assert payload["launcher"] == "python-wrapper"
    assert payload["mcp_config"]["mcpServers"]["memory-palace"]["command"] == str(venv_python)
    assert payload["mcp_config"]["mcpServers"]["memory-palace"]["args"] == [
        str(project_root / "backend" / "mcp_wrapper.py")
    ]


def test_render_payload_supports_windsurf_python_wrapper(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    project_root = tmp_path / "Memory-Palace"
    venv_python = project_root / "backend" / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    venv_python.write_text("", encoding="utf-8")

    monkeypatch.setattr(module, "project_root", lambda: project_root)

    payload = module.render_payload("windsurf", "python-wrapper")

    assert payload["launcher"] == "python-wrapper"
    assert "mcpServers" in payload["mcp_config"]
    assert payload["mcp_config"]["mcpServers"]["memory-palace"]["args"] == [
        str(project_root / "backend" / "mcp_wrapper.py")
    ]
