# Memory Palace Trigger Smoke Report

## Summary

| Check | Status | Summary |
|---|---|---|
| `structure` | `PASS` | canonical bundle 结构与 YAML 通过 |
| `mirrors` | `PASS` | workspace mirrors match canonical bundle and Gemini variant |
| `sync_check` | `PASS` | All memory-palace skill mirrors are in sync. |
| `gate_syntax` | `PASS` | run_post_change_checks.sh 语法通过 |
| `mcp_bindings` | `PASS` | Claude/Codex/Gemini/OpenCode 的 memory-palace MCP 都已绑定到当前项目 |
| `claude` | `PASS` | Claude smoke 通过 |
| `codex` | `PASS` | Codex smoke 通过 |
| `opencode` | `PASS` | OpenCode smoke 通过 |
| `gemini` | `PASS` | Gemini smoke 通过 |
| `gemini_live` | `FAIL` | Gemini live MCP 链路未完全通过 |
| `cursor` | `PARTIAL` | Cursor runtime 存在，但当前机器缺少登录/鉴权 |
| `agent` | `PARTIAL` | agent 仅完成 mirror 结构校验 |
| `antigravity` | `PARTIAL` | Antigravity app-bundled CLI 已发现，global_workflow 已安装；仍需 GUI 手工 smoke |

## Details

### structure

- Status: `PASS`
- Summary: canonical bundle 结构与 YAML 通过

### mirrors

- Status: `PASS`
- Summary: workspace mirrors match canonical bundle and Gemini variant

### sync_check

- Status: `PASS`
- Summary: All memory-palace skill mirrors are in sync.

### gate_syntax

- Status: `PASS`
- Summary: run_post_change_checks.sh 语法通过

### mcp_bindings

- Status: `PASS`
- Summary: Claude/Codex/Gemini/OpenCode 的 memory-palace MCP 都已绑定到当前项目

```text
PASS claude: MCP 已绑定到当前项目 backend/memory.db（/Users/yangjunjie/.claude.json）

PASS codex: MCP 已绑定到当前项目 backend/memory.db（/Users/yangjunjie/.codex/config.toml）

PASS gemini: MCP 已绑定到当前项目 backend/memory.db（/Users/yangjunjie/.gemini/settings.json）

PASS opencode: MCP 已绑定到当前项目 backend/memory.db（/Users/yangjunjie/.config/opencode/opencode.json）
```

### claude

- Status: `PASS`
- Summary: Claude smoke 通过

```text
Based on the Memory-Palace skill documentation:

- **First memory tool call**: `read_memory("system://boot")` before any real Memory Palace operation in a session
- **When guard_action is NOOP**: Stop the write immediately, inspect `guard_target_uri` / `guard_target_id`, and read the suggested target before deciding whether anything should change
- **Canonical trigger sample path**: `Memory-Palace/docs/skills/memory-palace/references/trigger-samples.md`
```

### codex

- Status: `PASS`
- Summary: Codex smoke 通过

```text
{"first_move": "`read_memory(\"system://boot\")`", "noop_handling": "当 `guard_action=NOOP` 时，停止写入，检查 `guard_target_uri` / `guard_target_id`，先读取建议目标，再决定是更新还是保持不变。", "trigger_samples_path": "`Memory-Palace/docs/skills/memory-palace/references/trigger-samples.md`"}
```

### opencode

- Status: `PASS`
- Summary: OpenCode smoke 通过

```text
- **First move:** call `read_memory("system://boot")` before any real Memory Palace operation in a session.
- **If `guard_action=NOOP`:** stop the write, inspect `guard_target_uri` / `guard_target_id`, then `read_memory` on the suggested target before deciding any change.
- **Trigger sample file:** `Memory-Palace/docs/skills/memory-palace/references/trigger-samples.md`.

[0m
> Sisyphus (Ultraworker) · gpt-5.3-codex
[0m
[0m→ [0mSkill "memory-palace"
```

### gemini

- Status: `PASS`
- Summary: Gemini smoke 通过

```text
[model=gemini-3-flash-preview]
I will read the project documentation and activate the `memory-palace` skill to provide the specific information requested.

I will activate the `memory-palace` skill to access the specific procedural guidance and repository-local facts required to answer the user's request.

I will verify the existence of the canonical repo-visible path for the trigger sample set as specified in the `memory-palace` skill instructions.

Based on the `memory-palace` skill documentation and the repository structure, here is the requested information:

*   The first memory tool call required by the skill is `read_memory("system://boot")`.
*   If `guard_action` is `NOOP`, the agent must stop the write, inspect the `guard_target_uri` or `guard_target_id`, read the suggested target, and then decide whether to update or leave it unchanged.
*   The canonical repo-visible path for the trigger sample set is `Memory-Palace/docs/skills/memory-palace/references/trigger-samples.md`.

Loaded cached credentials.
Server 'chrome-devtools' supports tool updates. Listening for changes...
Server 'grok-search' supports tool updates. Listening for changes...
Skill conflict detected: "memory-palace" from "/Users/yangjunjie/Desktop/clawanti/.gemini/skills/memory-palace/SKILL.md" is overriding the same skill from "/Users/yangjunjie/.gemini/skills/memory-palace/SKILL.md".Error recording tool call interactions: request to https://cloudcode-pa.googleapis.com/v1internal:recordCodeAssistMetrics failed, reason: Client network socket disconnected before secure TLS connection was established
```

### gemini_live

- Status: `FAIL`
- Summary: Gemini live MCP 链路未完全通过

```text
db_path=//Users/yangjunjie/Desktop/clawanti/Memory-Palace/backend/memory.db
create_model=gemini-3-flash-preview
create_timed_out=False
create_stdout=
create_verified=missing
update_model=gemini-3.1-pro-preview
update_timed_out=False
update_stdout=SUCCESS notes://gemini_suite_1772869612
update_verified={"domain": "notes", "path": "gemini_suite_1772869612", "priority": 0, "disclosure": null, "memory_id": 48, "content": "Unique token gemini_suite_1772869612_nonce. This note records one preference only: user prefers concise answers. Updated once.", "deprecated": 0, "created_at": "2026-03-07 07:49:45.071926"}
guard_model=gemini-3-flash-preview
guard_timed_out=False
guard_stdout=BLOCKED notes://gemini_suite_1772869612
guard_duplicate_created=False
guard_create_output={"ok": false, "message": "Skipped: write_guard blocked create_memory (action=NOOP, method=embedding). suggested_target=notes://gemini_suite_1772866234", "created": false, "reason": "write_guard_blocked", "uri": "notes://gemini_suite_1772866234", "guard_action": "NOOP", "guard_reason": "semantic similarity 1.000 >= 0.920", "guard_method": "embedding", "guard_target_id": 48, "guard_target_uri": "notes://gemini_suite_1772866234"}
guard_target_uri=notes://gemini_suite_1772866234
guard_user_visible_block=True
guard_followup=True
guard_resolved_to_existing_target=False
```

### cursor

- Status: `PARTIAL`
- Summary: Cursor runtime 存在，但当前机器缺少登录/鉴权

```text
Error: Authentication required. Please run 'agent login' first, or set CURSOR_API_KEY environment variable.
```

### agent

- Status: `PARTIAL`
- Summary: agent 仅完成 mirror 结构校验

```text
/Users/yangjunjie/Desktop/clawanti/.agent/skills/memory-palace
```

### antigravity

- Status: `PARTIAL`
- Summary: Antigravity app-bundled CLI 已发现，global_workflow 已安装；仍需 GUI 手工 smoke

```text
/Applications/Antigravity.app/Contents/Resources/app/bin/antigravity
/Users/yangjunjie/.gemini/antigravity/global_workflows/memory-palace.md
```

