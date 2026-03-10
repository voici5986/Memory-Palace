#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


IDE_HOSTS = ("cursor", "windsurf", "vscode", "antigravity")
LAUNCHERS = ("bash", "python-wrapper")


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
        default="bash",
        help=(
            "Launcher style. 'bash' uses scripts/run_memory_palace_mcp_stdio.sh. "
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


def build_mcp_config(launcher: str) -> dict[str, object]:
    if launcher == "python-wrapper":
        return {
            "mcpServers": {
                "memory-palace": {
                    "command": "python",
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
    if launcher == "python-wrapper":
        notes.append(
            "The python-wrapper launcher is mainly for stdin/stdout normalization quirks; if you use a virtualenv-managed interpreter, replace 'python' with the appropriate executable."
        )
    return notes


def render_payload(host: str, launcher: str) -> dict[str, object]:
    payload: dict[str, object] = {
        "host": host,
        "category": "ide-host",
        "canonical_skill_source": "docs/skills/memory-palace/",
        "skill_insertion": {
            "primary_rule_surface": str(project_root() / "AGENTS.md"),
            "hidden_skill_mirrors_required": False,
        },
        "mcp_config": build_mcp_config(launcher),
        "notes": host_notes(host, launcher),
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
