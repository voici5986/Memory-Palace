import importlib.util
import json
import sys
from pathlib import Path


def _load_skill_eval_module():
    project_root = Path(__file__).resolve().parents[2]
    script_path = project_root / "scripts" / "evaluate_memory_palace_skill.py"
    spec = importlib.util.spec_from_file_location("evaluate_memory_palace_skill", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_install_skill_module():
    project_root = Path(__file__).resolve().parents[2]
    script_path = project_root / "scripts" / "install_skill.py"
    spec = importlib.util.spec_from_file_location("install_skill", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_check_gate_syntax_skips_when_workspace_gate_missing(monkeypatch, tmp_path):
    module = _load_skill_eval_module()
    repo_root = tmp_path / "Memory-Palace"
    repo_root.mkdir()
    monkeypatch.setattr(module, "REPO_ROOT", repo_root)

    result = module.check_gate_syntax()

    assert result.status == "SKIP"
    assert "run_post_change_checks.sh" in result.summary
    assert "缺失" in result.summary


def test_check_gate_syntax_accepts_parent_workspace_gate(monkeypatch, tmp_path):
    module = _load_skill_eval_module()
    repo_root = tmp_path / "Memory-Palace"
    repo_root.mkdir()
    workspace_gate = tmp_path / "new" / "run_post_change_checks.sh"
    workspace_gate.parent.mkdir()
    workspace_gate.write_text("#!/usr/bin/env bash\nset -euo pipefail\necho ok\n", encoding="utf-8")

    monkeypatch.setattr(module, "REPO_ROOT", repo_root)

    result = module.check_gate_syntax()

    assert result.status == "PASS"
    assert "语法通过" in result.summary


def test_install_skill_reports_invalid_json_with_actionable_message(tmp_path):
    module = _load_install_skill_module()
    broken = tmp_path / "settings.json"
    broken.write_text('{"mcpServers": ', encoding="utf-8")

    try:
        module.read_json_file(broken)
        raise AssertionError("expected SystemExit for invalid JSON")
    except SystemExit as exc:
        message = str(exc)

    assert str(broken) in message
    assert "Invalid JSON" in message
    assert "line" in message
    assert "column" in message


def test_install_skill_write_json_file_creates_backup_before_overwrite(tmp_path):
    module = _load_install_skill_module()
    config_path = tmp_path / "settings.json"
    original_payload = {"mcpServers": {"old": {"command": "bash"}}}
    config_path.write_text(json.dumps(original_payload), encoding="utf-8")

    module.write_json_file(
        config_path,
        {"mcpServers": {"memory-palace": {"command": "bash"}}},
        dry_run=False,
    )

    backup_path = config_path.with_name("settings.json.bak")
    assert backup_path.is_file()
    assert json.loads(backup_path.read_text(encoding="utf-8")) == original_payload


def test_install_skill_write_text_file_creates_backup_before_overwrite(tmp_path):
    module = _load_install_skill_module()
    config_path = tmp_path / "config.toml"
    config_path.write_text('[mcp_servers.old]\ncommand = "bash"\n', encoding="utf-8")

    module.write_text_file(
        config_path,
        '[mcp_servers.memory-palace]\ncommand = "bash"\n',
        dry_run=False,
    )

    backup_path = config_path.with_name("config.toml.bak")
    assert backup_path.is_file()
    assert '[mcp_servers.old]' in backup_path.read_text(encoding="utf-8")
