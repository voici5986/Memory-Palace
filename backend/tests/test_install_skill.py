import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_install_skill_module():
    project_root = Path(__file__).resolve().parents[2]
    script_path = project_root / "scripts" / "install_skill.py"
    spec = importlib.util.spec_from_file_location("install_skill", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_read_json_file_reports_invalid_json_path(tmp_path: Path) -> None:
    module = _load_install_skill_module()
    config_path = tmp_path / "settings.json"
    config_path.write_text("{ invalid json", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        module.read_json_file(config_path)

    message = str(excinfo.value)
    assert "Invalid JSON" in message
    assert str(config_path) in message
    assert "Fix or remove the file and retry" in message


def test_read_json_file_rejects_non_object_roots(tmp_path: Path) -> None:
    module = _load_install_skill_module()
    config_path = tmp_path / "settings.json"
    config_path.write_text("[]", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        module.read_json_file(config_path)

    assert "expected an object" in str(excinfo.value)


def test_write_json_file_creates_backup_before_overwrite(tmp_path: Path) -> None:
    module = _load_install_skill_module()
    config_path = tmp_path / "settings.json"
    config_path.write_text(json.dumps({"old": True}), encoding="utf-8")

    module.write_json_file(config_path, {"new": True}, dry_run=False)

    backup_path = tmp_path / "settings.json.bak"
    assert backup_path.is_file()
    assert json.loads(backup_path.read_text(encoding="utf-8")) == {"old": True}
    assert json.loads(config_path.read_text(encoding="utf-8")) == {"new": True}
