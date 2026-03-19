# Memory Palace Skills Quick Start

> This document is specifically written for those who want to "get it running and start using it first."
>
> It doesn't dwell on abstract concepts; it answers three things: **what these skills actually are, how to configure the CLI clients, and which path IDE hosts should use.**

---

## 🚀 The Bottom Line

If you currently start the service through GHCR / Docker, split it into two cases first:

- You only want `Dashboard / API / SSE`
  - then you can stop there; skill installation is not required yet
- You also want `Claude / Codex / Gemini / OpenCode / IDE hosts` on your machine to actually trigger and call Memory Palace
  - then continue with the rest of this page

In other words:

- Docker starts the service side
- this page explains the **repo-local skill + MCP installation path**
- they are related, but not the same layer

If your current goal is only:

- no repo-local skill install
- just manually connect an MCP client to Docker's `/sse`

start with:

- `docs/GHCR_QUICKSTART_EN.md`
- `6.2 SSE mode` in `docs/GETTING_STARTED_EN.md`
- `6.3 client configuration examples` in `docs/GETTING_STARTED_EN.md`

Those sections provide the **generic SSE MCP skeleton** that is already grounded in this repository. Do not over-read it as "every client's final field names are identical."

If you do not want to manually digest this whole page first and would rather let the AI guide the process step by step, the current preferred path is:

1. Install the standalone setup skill: [`memory-palace-setup`](https://github.com/AGI-is-going-to-arrive/memory-palace-setup)
2. Then tell the AI: `Use $memory-palace-setup to install and configure Memory Palace step by step. Prefer skills + MCP over MCP-only. Start with Profile B if you want the fewest extra requirements, but recommend C/D if the environment is ready.`

If that setup skill is not installed in your client yet, you can still give the repo URL to the AI first and say:

```text
Please read the README.md and SKILL.md in this repository first, then guide me step by step to install and configure Memory Palace. Prefer skills + MCP, not MCP-only by default.
```

This repository has already organized the `memory-palace` **canonical skill**, synchronization scripts, and installation scripts. After executing the commands below, you can connect the skill + MCP main path in your **local workspace**:

| Client | Skill Auto-recognized | MCP Connection Status | What You Should Do |
|---|---|---|---|
| `Claude Code` | Available after `sync` + user-scope install | `--scope user --with-mcp` already has a scripted path; workspace entry is optional | Prefer the unified `python scripts/install_skill.py --targets claude,codex,gemini,opencode --scope user --with-mcp --force`; add workspace install only if you also want a project-level entry in this repo |
| `Gemini CLI` | Available after `sync` + user-scope install | `--scope user --with-mcp` is more reliable; workspace can generate `.gemini/settings.json`, but `live MCP` still has edge cases | Prefer the unified `python scripts/install_skill.py --targets claude,codex,gemini,opencode --scope user --with-mcp --force`; add workspace install only if you also want a project-level entry in this repo |
| `Codex CLI` | repo-local skill after sync | User-scope MCP has a scripted installation path | Preferred: `python scripts/install_skill.py --targets codex --scope user --with-mcp --force`; manual `codex mcp add` as fallback |
| `OpenCode` | repo-local skill after sync | User-scope MCP has a scripted installation path | Preferred: `python scripts/install_skill.py --targets opencode --scope user --with-mcp --force`; manual GUI registration as fallback |

In a nutshell:

- **skill** is responsible for "when to enter the Memory Palace workflow"
- **MCP** is responsible for "actually calling tools like `read_memory / search_memory / update_memory`"
- You need both for it to "truly trigger and truly work."

> Current status:
>
> - **Smoke tests** for `Claude / Codex / Gemini` all have passing results in the recent validation environment; for `Codex`, the default assumption is that `user-scope --with-mcp` has already been installed.
> - For `OpenCode`, the more accurate public wording is: the repo-local skill is in place, and `mcp list` can confirm that `memory-palace` is connected; a real `run` still depends on the current provider credentials.
> - `Gemini live` is not yet at a stage to be described as "fully passing"; more accurately: if the Gemini configuration cannot resolve the database path, it stops at `PARTIAL`.
> - `Cursor / Windsurf / VSCode-host / Antigravity` are now grouped as **IDE Hosts**; their primary path is `AGENTS.md + MCP snippet`, not hidden skill mirrors.
>
> **A prerequisite for Windows users**:
>
> - Native Windows now defaults to `python + backend/mcp_wrapper.py`.
> - `install_skill.py --with-mcp` now writes that native path for `Claude / Codex / Gemini / OpenCode` on Windows.
> - `python scripts/render_ide_host_config.py --host ...` now also defaults to `python-wrapper` on Windows.
> - If you use `Git Bash` or `WSL`, you can still keep using `bash + scripts/run_memory_palace_mcp_stdio.sh`.
> - So the real split is now: **python-wrapper for native Windows, bash wrapper for POSIX shell boundaries**.

---

## 🧠 What is the relationship between skill and MCP?

<p align="center">
  <img src="../images/skill_vs_mcp.png" width="800" alt="Skill vs MCP Principle" />
</p>

You can think of it as:

- **skill** = The "driving rules" in the driver's head.
- **MCP** = The actual car and steering wheel.

Only skill, no MCP:

- The model knows "it should use Memory Palace now."
- But when it needs to read or write memory, there are no tools to call.

Only MCP, no skill:

- The tools exist.
- But the model doesn't necessarily know when to use them, leading to missed or incorrect triggers.

Therefore, what this repository does is essentially fill in both layers.

---

## ✅ What you will usually see locally after running sync/install

The public repository only contains the canonical bundle by default. After executing the sync/install commands above, you will typically see these key entries in your local workspace:

| File | Purpose |
|---|---|
| `docs/skills/memory-palace/` | The source of truth for the canonical skill (exists in public repo) |
| `.claude/skills/memory-palace/SKILL.md` | repo-local skill mirror for Claude Code (locally generated) |
| `.codex/skills/memory-palace/SKILL.md` | repo-local skill mirror for Codex (locally generated) |
| `.opencode/skills/memory-palace/SKILL.md` | repo-local skill mirror for OpenCode (locally generated) |
| `.gemini/skills/memory-palace/SKILL.md` | repo-local skill entry for Gemini (locally generated) |
| `.gemini/settings.json` | Project-level MCP config for Gemini (generated after workspace install) |
| `.gemini/policies/memory-palace-overrides.toml` | Gemini policy override for Memory Palace (generated after install to avoid deprecated `__` MCP tool syntax warnings) |
| `.mcp.json` | Project-level MCP config for Claude Code (generated after workspace install) |

If you follow the default `--scope user --with-mcp` path in this document, you will also usually see these home-directory entries:

- `~/.claude/skills/memory-palace/`
- `~/.codex/config.toml`
- `~/.gemini/skills/memory-palace/SKILL.md`
- `~/.gemini/settings.json`
- `~/.gemini/policies/memory-palace-overrides.toml`
- `~/.config/opencode/opencode.json`

So:

- The default recommendation is to run one unified `--scope user --with-mcp` install first.
- For `Claude Code` and `Gemini CLI`, add workspace install only when you also want project-level entries in the current repo.
- The **skill** for `Codex CLI` and `OpenCode` is already in place.
- In the recent validation environment, after `--scope user --with-mcp` was installed, both `mcp_bindings` and `Codex smoke` passed.
- For `OpenCode`, it is recommended to manually confirm once with `mcp list`.

If you are integrating an IDE host, do not keep reading with a hidden-mirror mental model. Jump directly to:

- `IDE_HOSTS_EN.md`
- `python scripts/render_ide_host_config.py --host <cursor|windsurf|vscode|antigravity>`

---

## 🛠️ How to configure the four CLI clients

## 1) `Claude Code`

The more reliable default recommendation is still:

```bash
python scripts/install_skill.py --targets claude --scope user --with-mcp --force
```

If you also want the **current repository** to get an extra project-level entry, add a workspace install afterwards.

- `~/.claude/skills/memory-palace/`
- a `mcpServers.memory-palace` block for the current repo inside `~/.claude.json`

If you also add workspace install, the local workspace will additionally contain:

- `.claude/skills/memory-palace/`
- `.mcp.json`

Then, when you start `Claude Code` in this repository, it can see both:

1. The `memory-palace` skill.
2. The `memory-palace` MCP server.

Recommended check:

```bash
claude mcp list
```

If you see `memory-palace` in the project, you're basically set.

In this actual validation, `Claude Code` was already able to complete a real MCP tool call in non-interactive mode. If you get `TOOL_OK`, that path is working.

---

## 2) `Gemini CLI`

The more reliable default recommendation is still:

```bash
python scripts/install_skill.py --targets gemini --scope user --with-mcp --force
```

After that, your home directory will at least contain:

- `~/.gemini/skills/memory-palace/SKILL.md`
- `~/.gemini/settings.json`
- `~/.gemini/policies/memory-palace-overrides.toml`

If you also want the **current repository** to get an extra project-level entry, add a workspace install afterwards; then the workspace will be supplemented with:

- `.gemini/skills/memory-palace/SKILL.md`
- `.gemini/settings.json`
- `.gemini/policies/memory-palace-overrides.toml`

In the **current local workspace**, Gemini can then use the project-level entry; for cross-repo reuse, user-scope remains the more stable default.

Recommended check:

```bash
gemini skills list --all
gemini mcp list
```

If you see this prompt:

- `Policy file warning in memory-palace-overrides.toml`
- `The "__" syntax for MCP tools is strictly deprecated`

rerun the Gemini install command from this repository first. The current installer rewrites `memory-palace-overrides.toml` to Gemini's supported `mcpName = "memory-palace"` policy format.

If you see this prompt:

- `Skill conflict detected`
- `... overriding the same skill from ~/.gemini/skills/...`

This is usually not a bad thing; it means the **skill in the current workspace is overriding the older version in the user directory.**

If you see this prompt:

- `memory-palace` is `Disconnected` in `gemini mcp list`
- Or `MCP issues detected` appears in Gemini's answer

Delete the old user-level MCP entry first, then re-add the project-level one:

```bash
# native Windows
gemini mcp remove memory-palace
gemini mcp add -s project memory-palace python <repo-root>\backend\mcp_wrapper.py
```

```bash
# macOS / Linux / Git Bash / WSL
gemini mcp remove memory-palace
gemini mcp add -s project memory-palace /bin/zsh -lc 'cd <repo-root> && bash scripts/run_memory_palace_mcp_stdio.sh'
```

> Replace `<repo-root>` with your actual repository root directory.
>
> This syntax reuses the `DATABASE_URL` in the current repo's `.env`. If you have already run Dashboard / HTTP API in the same repo, do not manually write a separate `backend/memory.db`, otherwise you may end up connecting the client and the dashboard to two different databases.
>
> Do not copy the Docker `/app/data/...` path from `.env.docker` into local `.env` either. Repo-local `stdio` MCP now refuses that configuration on purpose; use a host absolute path or keep using Docker `/sse` instead.

---

## 3) `Codex CLI`

For `Codex`, consider these separately:

- **skill**: After running `sync/install`, `.codex/skills/memory-palace/` will exist locally.
- **MCP**: Preferred path is `python scripts/install_skill.py --targets codex --scope user --with-mcp --force`, which writes to the user directory `~/.codex/config.toml`; manual `codex mcp add` is only a fallback.

In plain English:

- In this repo, `Codex` knows there is a `memory-palace` skill.
- But the first time you use it on your machine, you still need to write the MCP startup command into your user-scope config.

On a new machine, do this first:

```bash
python scripts/install_skill.py --targets codex --scope user --with-mcp --force
```

Then check:

```bash
codex mcp list
```

If `python scripts/evaluate_memory_palace_skill.py` still reports:

- `mcp_bindings` failed
- or `Codex smoke` failed

do not assume the skill itself is broken first. A more common cause is that `~/.codex/config.toml` still contains an old entry, or that `user-scope MCP` was never installed. First rerun:

```bash
python scripts/install_skill.py --targets codex --scope user --with-mcp --force
```

If the scripted check still fails, or you are explicitly doing manual troubleshooting, then use:

```bash
# native Windows
codex mcp add memory-palace -- python C:\ABS\PATH\TO\REPO\backend\mcp_wrapper.py
```

```bash
# macOS / Linux / Git Bash / WSL
codex mcp add memory-palace \
  -- /bin/zsh -lc 'cd /ABS/PATH/TO/REPO && bash scripts/run_memory_palace_mcp_stdio.sh'
```

Note:

- Replace `/ABS/PATH/TO/REPO` with your actual repository path.
- Whether you use the script or the manual fallback, the resulting config ends up in `~/.codex/config.toml`.
- This is the current product behavior of `Codex CLI`, not a missing file in this repo.
- This command also reuses the current repo `.env` for `DATABASE_URL`; if that `.env` still points to Docker `/app/data/...`, local `stdio` MCP will refuse to start.
- If you rewrite the fallback command for another shell or client config, do not accidentally remove `source .venv/bin/activate`. Either activate the project's `.venv` first or use the Python directly inside `.venv`. Otherwise, the MCP process might fail to start with `No module named 'sqlalchemy'`.

---

## 4) `OpenCode`

After you execute `sync/install`, `OpenCode` will usually have:

- `.opencode/skills/memory-palace/`

In the recent validation environment, this path was confirmed at least to the point where the repo-local skill was visible and `opencode mcp list` showed `memory-palace connected`.

However, on a new machine, the safer default sequence is still to run:

```bash
python scripts/install_skill.py --targets opencode --scope user --with-mcp --force
opencode mcp list
```

If you can already see `memory-palace`, you're set.

If the scripted check still fails, or you are explicitly doing manual troubleshooting, add a new local stdio server in `OpenCode`'s own MCP management entry. That step is fallback-only. The core parameters are:

```text
# native Windows
name: memory-palace
type: local / stdio
command: python
args:
  - <repo-root>\backend\mcp_wrapper.py
```

```text
# macOS / Linux / Git Bash / WSL
name: memory-palace
type: local / stdio
command: /bin/zsh
args:
  - -lc
  - cd <repo-root> && bash scripts/run_memory_palace_mcp_stdio.sh
```

The UI entry for different versions of `OpenCode` may look different, but these are the essential items to fill in.

---

## 5) How to configure IDE hosts

These hosts are now grouped together as **IDE Hosts**:

- `Cursor`
- `Windsurf`
- `VSCode-host`
- `Antigravity`

The unified stance is simple:

- **rules entry**: `AGENTS.md`
- **MCP entry**: `python scripts/render_ide_host_config.py --host ...`
- **host differences**: add a wrapper / workflow only when needed; do not assume these IDEs should directly consume hidden `SKILL.md` mirrors

Recommended commands:

```bash
python scripts/render_ide_host_config.py --host cursor
python scripts/render_ide_host_config.py --host windsurf
python scripts/render_ide_host_config.py --host vscode
python scripts/render_ide_host_config.py --host antigravity
```

On Windows the default output is already `python-wrapper`. If a host on macOS / Linux has `stdin/stdout` or CRLF quirks, switch to:

```bash
python scripts/render_ide_host_config.py --host antigravity --launcher python-wrapper
```

One-line memory:

- CLI clients: default to hidden skill mirrors + `install_skill.py`
- IDE hosts: default to `AGENTS.md` + `render_ide_host_config.py`

---

## 🔍 How to tell if the trigger was successful

The simplest positive prompt:

```text
Read from system://boot first, then help me check for recent memories regarding deployment preferences.
```

If `memory-palace` is hit, the response or execution will usually show these signals:

- It starts with `read_memory("system://boot")`.
- It won't write blindly before checking the target.
- It will mention `search_memory(..., include_session=true)` or an equivalent recall process.

The simplest negative prompt:

```text
Rewrite the introductory paragraph of the README for me.
```

Pure document tasks like this **should not** trigger the Memory Palace workflow.

---

## 🧪 Existing validation commands in the repository

Check for drift in the skill mirror:

```bash
python scripts/sync_memory_palace_skill.py --check
```

Check the current multi-client smoke path:

```bash
python scripts/evaluate_memory_palace_skill.py
```

Check the actual MCP call chain:

```bash
cd backend && python ../scripts/evaluate_memory_palace_mcp_e2e.py
```

Both scripts will generate validation reports locally:

- `docs/skills/TRIGGER_SMOKE_REPORT.md` (Summary of local smoke tests; please check for local paths or client config traces before sharing).
- `docs/skills/MCP_LIVE_E2E_REPORT.md`

It is recommended to treat these as review artifacts on your own machine rather than primary documentation; these files are excluded by `.gitignore` by default.

A note on the experience: `evaluate_memory_palace_skill.py` runs multiple CLIs serially; it often takes a few minutes to complete. If you see no new output for a while, don't immediately assume it's stuck.
A note on side effects: This script also attempts `gemini_live` by default. If the current Gemini config can resolve the actual database path, it will perform a round of `create/update/guard` validation and may leave test memories like `notes://gemini_suite_*`. To only perform regular smoke tests, explicitly set `MEMORY_PALACE_SKIP_GEMINI_LIVE=1`.
If the report only shows `mcp_bindings` as failed, rerun the unified `user-scope` install first and then rerun smoke:

```bash
python scripts/install_skill.py --targets claude,codex,gemini,opencode --scope user --with-mcp --force
python scripts/evaluate_memory_palace_skill.py
```

Maintain the same sharing awareness for `MCP_LIVE_E2E_REPORT.md`: it uses an isolated temporary database by default and won't touch your production database, but failures may still contain traces of local logs, stderr, or temporary directories. Check the content yourself before forwarding it to others.

---

## 🙋 Common Misconceptions

### Myth 1: Seeing the skill file means it's ready to use

No.

The skill only solves "whether it should trigger."
To actually call tools, you still need the MCP server configuration.

### Myth 2: If Gemini finds the skill, it will trigger stably

Not necessarily.

Gemini can be more conservative with hidden directories sometimes, which is why this installation chain supplements your local environment with:

- `.gemini/skills/...`
- `.gemini/settings.json`
- `variants/gemini/SKILL.md`

### Myth 3: If `.codex/skills/...` exists locally, no MCP config is needed

Still not enough.

`Codex` MCP primarily looks at the user-level config `~/.codex/config.toml`.

### Myth 4: IDE hosts should start from hidden skill mirrors

No.

For `Cursor / Windsurf / VSCode-host / Antigravity`, the current primary path is:

- repo-root `AGENTS.md`
- `python scripts/render_ide_host_config.py --host ...`

`Antigravity` only keeps one extra host-specific difference:

- a workflow can still be projected into `.agent/workflows/...` or `~/.gemini/antigravity/global_workflows/...`
- rule discovery should prefer `AGENTS.md`, while keeping `GEMINI.md` as a legacy fallback

But that does not change the fact that it belongs to the IDE-host path.

---

## 📚 What to read next

If you've got it running, follow this order:

1. `MEMORY_PALACE_SKILLS_EN.md` —— Design principles, Claude spec alignment, maintenance boundaries.
2. `CLI_COMPATIBILITY_GUIDE_EN.md` —— Unified compatibility guidance for CLI clients and IDE hosts.
3. `IDE_HOSTS_EN.md` —— The primary path for Cursor / Windsurf / VSCode-host / Antigravity.
4. `docs/skills/memory-palace/SKILL.md` —— The actual skill body intended for the model.

If you just want to verify if it's currently working, focus on these 3 commands:

```bash
python scripts/sync_memory_palace_skill.py --check
python scripts/evaluate_memory_palace_skill.py
cd backend && python ../scripts/evaluate_memory_palace_mcp_e2e.py
```
