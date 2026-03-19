#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


IDE_HOSTS = ("cursor", "windsurf", "vscode", "antigravity")
LAUNCHERS = ("auto", "bash", "python-wrapper")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render a repo-local MCP config snippet for IDE-like hosts that do not "
            "consume Memory Palace hidden skill mirrors as their primary integration path."
        ),
    )
    parser.add_argument(
        "--host",
        required=True,
        choices=IDE_HOSTS,
        help="Target IDE host.",
    )
    parser.add_argument(
        "--launcher",
        choices=LAUNCHERS,
        default="auto",
        help=(
            "Launcher style. 'auto' picks 'python-wrapper' on Windows and 'bash' elsewhere. "
            "'bash' uses scripts/run_memory_palace_mcp_stdio.sh. "
            "'python-wrapper' emits backend/mcp_wrapper.py and is mainly for CRLF/stdin quirks."
        ),
    )
    return parser.parse_args()


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def repo_wrapper_absolute() -> Path:
    return project_root() / "scripts" / "run_memory_palace_mcp_stdio.sh"


def python_wrapper_absolute() -> Path:
    return project_root() / "backend" / "mcp_wrapper.py"


def backend_venv_python_absolute() -> Path:
    if os.name == "nt":
        return project_root() / "backend" / ".venv" / "Scripts" / "python.exe"
    return project_root() / "backend" / ".venv" / "bin" / "python"


def antigravity_workflow_absolute() -> Path:
    return (
        project_root()
        / "docs"
        / "skills"
        / "memory-palace"
        / "variants"
        / "antigravity"
        / "global_workflows"
        / "memory-palace.md"
    )


def resolve_launcher(launcher: str) -> str:
    if launcher == "auto":
        return "python-wrapper" if os.name == "nt" else "bash"
    return launcher


def build_mcp_config(launcher: str) -> dict[str, object]:
    resolved = resolve_launcher(launcher)
    if resolved == "python-wrapper":
        python_command = backend_venv_python_absolute()
        command = str(python_command) if python_command.is_file() else (sys.executable or "python")
        return {
            "mcpServers": {
                "memory-palace": {
                    "command": command,
                    "args": [str(python_wrapper_absolute())],
                }
            }
        }
    return {
        "mcpServers": {
            "memory-palace": {
                "command": "bash",
                "args": [str(repo_wrapper_absolute())],
            }
        }
    }


def host_notes(host: str, launcher: str) -> list[str]:
    resolved = resolve_launcher(launcher)
    notes = [
        "IDE hosts should project Memory Palace via repo-local AGENTS.md instead of hidden SKILL.md mirrors.",
        "Paste the rendered MCP snippet into the host's MCP/local stdio settings surface for this repository.",
        "The wrapper reuses the repository .env / DATABASE_URL when present, so Dashboard/API/MCP stay on the same database by default.",
    ]
    if host in {"cursor", "windsurf", "vscode"}:
        notes.append(
            "Use this path only if the host or extension supports local stdio MCP and workspace-level project rules."
        )
    if host == "antigravity":
        notes.append(
            "Antigravity should read AGENTS.md first and may fall back to GEMINI.md on older setups."
        )
        notes.append(
            "The optional Antigravity workflow projection lives at "
            + str(antigravity_workflow_absolute())
            + "."
        )
    if resolved == "python-wrapper":
        notes.append(
            "The python-wrapper launcher is mainly for native Windows shells and stdio normalization quirks; keep it aligned with the repository backend virtualenv interpreter."
        )
    return notes


def render_payload(host: str, launcher: str) -> dict[str, object]:
    resolved = resolve_launcher(launcher)
    payload: dict[str, object] = {
        "host": host,
        "category": "ide-host",
        "launcher": resolved,
        "canonical_skill_source": "docs/skills/memory-palace/",
        "skill_insertion": {
            "primary_rule_surface": str(project_root() / "AGENTS.md"),
            "hidden_skill_mirrors_required": False,
        },
        "mcp_config": build_mcp_config(resolved),
        "notes": host_notes(host, resolved),
    }
    if host == "antigravity":
        payload["skill_insertion"] = {
            "primary_rule_surface": str(project_root() / "AGENTS.md"),
            "legacy_rule_fallback": "GEMINI.md",
            "optional_workflow_projection": str(antigravity_workflow_absolute()),
            "hidden_skill_mirrors_required": False,
        }
    return payload


def main() -> int:
    args = parse_args()
    print(json.dumps(render_payload(args.host, args.launcher), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
