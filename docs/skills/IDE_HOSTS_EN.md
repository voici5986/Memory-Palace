# Memory Palace IDE Hosts

This page is for IDE-like hosts:

- `Cursor`
- `Windsurf`
- `VSCode-host`
- `Antigravity`

Their main difference from `Claude / Codex / OpenCode / Gemini` is not branding, but **integration surface**:

- they do not expose a stable public model API for external CLIs to reuse
- the right way to project Memory Palace into them is:
  - repo-local rules
  - local MCP config snippets
  - a small host-specific compatibility layer when needed

So in `Memory-Palace`, the primary IDE-host path is no longer hidden `SKILL.md` mirrors. It is:

1. `AGENTS.md`
2. an MCP config snippet
3. an optional host-specific compatibility layer

## Retrieval Tier Recommendation (2026-04 Public Verification)

- The default interaction tier for IDE hosts is still `Profile B`, because it
  fits low-latency editor recall better.
- `Profile C` / `Profile D` are available only as explicit deep-retrieval
  tiers and should not be described as default tiers.
- This verification round did not change the IDE-host integration path: it is
  still `AGENTS.md + MCP snippet`, not hidden-mirror direct consumption.
- The launcher split is also unchanged:
  - native Windows: `backend/mcp_wrapper.py`
  - macOS / Linux: `scripts/run_memory_palace_mcp_stdio.sh`

## Reflection And C/D Config Boundary

- On the IDE-host side, the public `reflection workflow` wording also follows
  `prepare -> execute -> rollback`; rollback should use the review/maintenance
  endpoint returned by the current result instead of relying on implicit host
  state.
- When IDE hosts move to `Profile C/D`, `RETRIEVAL_EMBEDDING_DIM` must still be
  filled by the user with the provider's real vector dimension; the public
  templates no longer guess `4096` or `1024`.
- This verification round did not change the IDE-host main path: it is still
  `AGENTS.md + MCP snippet + user-supplied runtime config`.

---

## Core Positioning

### 1. The canonical skill still exists

The canonical source remains:

```text
docs/skills/memory-palace/
```

It still serves:

- CLI clients such as `Claude / Codex / OpenCode / Gemini`
- the repository's source of truth for skill design and references

### 2. IDE hosts should not rely on hidden skill mirrors as the primary path

For IDE hosts, Memory Palace should be inserted through:

- **primary entry**: repo-root `AGENTS.md`
- **execution entry**: a local MCP config
  - native Windows defaults to `python backend/mcp_wrapper.py`
  - macOS / Linux defaults to `bash scripts/run_memory_palace_mcp_stdio.sh`
- **optional compatibility layer**: workflow / wrapper for specific hosts

That means:

- `AGENTS.md` is the rule projection for IDE hosts
- `mcpServers.memory-palace` is the tool projection for IDE hosts
- `docs/skills/memory-palace/` remains the canonical source behind both projections
- if a host only passes runtime `DATABASE_URL` as an empty string while the repository `.env` still has a valid value, the wrapper continues to read the current repository `.env`
- but if the local `.env` itself exists and leaves `DATABASE_URL=` empty, the wrapper now stops immediately and tells you to fix the local config first

### 3. Local prerequisites for the default IDE-host path

The default IDE-host path in this repository is split by host environment:

- native Windows: `python` -> `backend/mcp_wrapper.py`
- macOS / Linux / `Git Bash` / `WSL`: `bash` -> `scripts/run_memory_palace_mcp_stdio.sh`
- local repository `backend/.venv`
- local repository `.env`

Treat these as one bundle:

- the generated IDE-host snippet assumes the host can run the matching wrapper for its own environment
- the wrapper assumes the local `backend/.venv` already exists and has the backend dependencies installed
- the wrapper reads the local repository `.env` first to decide `DATABASE_URL`
- if `.env` is missing while `.env.docker` exists, or if `.env` still points `DATABASE_URL` at Docker `/app/data/...` or a `/data/...` variant, it refuses to start, because the repo-local stdio wrapper does **not** reuse container-only sqlite paths
- if local `.env` or an explicit `DATABASE_URL` still points to `/app/...` or `/data/...`, the wrapper also refuses to start, because those paths only exist inside the container

So if you only have the Docker / GHCR service side running and do not have a prepared local checkout runtime, do **not** use the stdio wrapper as your first IDE-host path. Point the host at the exposed `/sse` endpoint instead.

---

## Per-host view

### Cursor

- primarily consumes repo-local `AGENTS.md`
- connects through the host's local stdio MCP settings surface
- should not treat `.cursor/skills/memory-palace/` as the default primary path

### Windsurf

- same positioning as `Cursor`
- only valid when the host supports local stdio MCP and workspace/project rules

### VSCode-host

- means a VS Code extension host with agent / MCP capabilities
- does not assume VS Code itself has a first-class skill system
- if the extension supports:
  - local stdio MCP
  - repo-local project rules
  then it can reuse the same `AGENTS.md + MCP snippet` path

### Antigravity

- still belongs to the `IDE Host` category
- uses the same MCP path as the other IDE hosts
- but keeps one host-specific difference:
  - **prefer `AGENTS.md`**
  - **accept legacy `GEMINI.md`**
- it also keeps an optional workflow projection:

```text
docs/skills/memory-palace/variants/antigravity/global_workflows/memory-palace.md
```

That is an extra host-specific layer, not a different integration category.

---

## How to generate config

Do not hand-write it.

Use:

```bash
python scripts/render_ide_host_config.py --host cursor
python scripts/render_ide_host_config.py --host windsurf
python scripts/render_ide_host_config.py --host vscode-host
python scripts/render_ide_host_config.py --host antigravity
```

Use `vscode-host` as the canonical CLI flag so it matches the documented `VSCode-host` label. The script still accepts the legacy `--host vscode` alias for compatibility.

By default, this renders a repo-local MCP JSON snippet:

- native Windows: `python + backend/mcp_wrapper.py`
- macOS / Linux: `bash + scripts/run_memory_palace_mcp_stdio.sh`

That default path assumes the same bundle above is already true:

- the repository-local `backend/.venv` is ready
- the repository-local `.env` exists when you want to reuse a specific SQLite file
- and, for the bash path, the host can launch `bash`

On Windows the default output is already `python-wrapper`. If a host on macOS / Linux has `stdin/stdout` or CRLF quirks, switch to the wrapper form:

```bash
python scripts/render_ide_host_config.py --host antigravity --launcher python-wrapper
```

This renders a config snippet pointing to:

```text
backend/mcp_wrapper.py
```

and reminds you to replace `python` with the actual interpreter when your environment is managed by a virtualenv.

If you explicitly request `python-wrapper` but the current checkout does not have a ready `backend/.venv`, `render_ide_host_config.py` now stops with an explicit error instead of silently falling back to some unrelated system Python.

---

## Unified validation stance

IDE hosts should no longer be presented as repository-level “one-click live smoke” targets.

The safer layered approach is:

1. **static contract checks**
   - `AGENTS.md` exists
   - wrapper / workflow / canonical source exists
   - the MCP command really points at this checkout, and the launcher / args pair is the executable wrapper pair rather than just a config string that happens to mention the wrapper path

2. **host connection checks**
   - the IDE can see the `memory-palace` MCP server
   - the IDE can list Memory Palace tools

3. **manual smoke checklist**
   - `read_memory("system://boot")`
   - create one `notes://ide_smoke_*`
   - try the duplicate write path and confirm guard blocks it

### Current verified boundary

- The public repository only promises that the static integration chain
  `AGENTS.md + MCP snippet + launcher` is aligned.
- `Cursor / Windsurf / VSCode-host / Antigravity` still need one host-side
  manual smoke each before the claim can be upgraded to "live-ready on that
  host."
- If a host is currently only `PARTIAL`, read it as:
  - the host-side login / auth / runtime prerequisite is still missing, or
  - this machine only completed static contract checks, not host-side live
    verification yet.

---

## Why this matches the reference project

This is closer to the approach used by `Dataojitori/nocturne_memory`:

- it documents client-specific MCP recipes
- `Antigravity` only keeps the minimum wrapper compatibility layer
- it does not try to turn every IDE host into a unified one-click install + live smoke target

`Memory-Palace` differs in one important way:

- it still keeps a canonical skill bundle
- but for IDE hosts, that bundle should be projected through `AGENTS.md + MCP snippet`
- instead of forcing those hosts to behave like full hidden-skill-mirror consumers
