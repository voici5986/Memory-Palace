<p align="center">
  <img src="docs/images/系统架构图.png" width="280" alt="Memory Palace Logo" />
</p>

<h1 align="center">🏛️ Memory Palace</h1>

<p align="center">
  <strong>Memory Palace provides AI agents with persistent context and seamless cross-session continuity.</strong>
</p>

<p align="center">
  <em>"Every conversation leaves a trace. Every trace becomes memory."</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License" />
  <img src="https://img.shields.io/badge/python-3.10+-3776ab.svg?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-009688.svg?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/React-18-61dafb.svg?logo=react&logoColor=black" alt="React" />
  <img src="https://img.shields.io/badge/Vite-646cff.svg?logo=vite&logoColor=white" alt="Vite" />
  <img src="https://img.shields.io/badge/SQLite-003b57.svg?logo=sqlite&logoColor=white" alt="SQLite" />
  <img src="https://img.shields.io/badge/protocol-MCP-orange.svg" alt="MCP" />
  <img src="https://img.shields.io/badge/Docker-ready-2496ed.svg?logo=docker&logoColor=white" alt="Docker" />
</p>

<p align="center">
  <a href="README_CN.md">中文</a> · <a href="docs/README_EN.md">Docs</a> · <a href="docs/GETTING_STARTED_EN.md">Quick Start</a> · <a href="docs/EVALUATION_EN.md">Benchmarks</a>
</p>

---

## 🌟 What Is Memory Palace?

**Memory Palace** provides AI agents with persistent context and seamless cross-session continuity. It gives LLMs **persistent, searchable, and auditable** historical context — so your Agent never "starts from scratch" in each conversation.

Through the unified [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) interface, Memory Palace provides integration paths for **Codex, Claude Code, Gemini CLI, and OpenCode**. For IDE-like hosts such as `Cursor / Windsurf / VSCode-host / Antigravity`, the repository now recommends a separate **AGENTS.md + MCP snippet** path instead of treating them like full CLI skill clients. For the shortest user path, use [SKILLS_QUICKSTART_EN.md](docs/skills/SKILLS_QUICKSTART_EN.md) for CLI clients and [IDE_HOSTS_EN.md](docs/skills/IDE_HOSTS_EN.md) for IDE hosts.

If you want the AI to guide installation step by step, start with the standalone setup-skill repo: [`memory-palace-setup`](https://github.com/AGI-is-going-to-arrive/memory-palace-setup). The intended stance is **skills + MCP first**, not MCP-only. A practical prompt is: `Use $memory-palace-setup to install and configure Memory Palace step by step. Prefer skills + MCP over MCP-only. Start with Profile B if you want the fewest extra requirements, but recommend C/D if the environment is ready.`

### Why Memory Palace?

| Pain Point | How Memory Palace Solves It |
|---|---|
| 🔄 Agent forgets everything after each session | **Persistent memory store** with SQLite — memories survive across sessions |
| 🔍 Hard to find relevant past context | **Hybrid retrieval** (keyword + semantic + reranker) with intent-aware search |
| 🚫 No control over what gets stored | **Write Guard** pre-checks every write; snapshots enable full rollback |
| 🧩 Different tools, different integrations | **Unified MCP protocol** — one integration for all AI clients |
| 📊 Can't observe what's happening | **Built-in dashboard** with Memory, Review, Maintenance, and Observability views |

---

## 🆕 What's New In This Release?

<p align="center">
  <img src="docs/images/memory_palace_upgrade.png" width="900" alt="Memory Palace Project Upgrade Comparison" />
</p>

- **skills + MCP now feel productized**: installation, sync, smoke, and live e2e are all part of the documented path.
- **Deployment is safer**: the Docker one-click scripts now use deployment locks, runtime env injection is opt-in, and there is a dedicated repository hygiene check before sharing or publishing your workspace.
- **Write-path recovery is tighter**: same-session snapshots now use file locks, transient SQLite lock conflicts get a small bounded retry, and background index jobs share the same write gate as foreground writes.
- **Review rollback is now more conservative**: if the same URI already has a newer content snapshot in another review session, rolling back the older snapshot now fails closed instead of silently undoing the newer change.
- **High-noise retrieval looks stronger in the current benchmark set**: compared with the old project, the C/D profiles show better recall in harder `s8,d200` and `s100,d200` style scenarios.
- **Dashboard language is now easier to control**: the frontend restores the stored language first; if there is no stored choice yet, common Chinese browser locales fall back to `zh-CN`, otherwise it falls back to English. You can still switch between English and Chinese from the top-right corner, and the browser remembers the choice.
- **Local operator paths are less brittle**: repo-local stdio wrappers now reuse `.env` `RETRIEVAL_REMOTE_TIMEOUT_SEC`, forward stdio in chunks instead of one byte at a time, export UTF-8 defaults on the shell-wrapper path, and give longer-running Dashboard observability / vitality confirmation actions a longer client-side timeout before the browser gives up.
- **A few easy-to-miss edges are tighter now**: final search-result revalidation prefers batched path checks, Windows-style hosts that accidentally run `backend/mcp_wrapper.py` from `Git Bash / MSYS / Cygwin` are more likely to pick the correct `.venv` interpreter, and the Docker frontend proxy now rejects ASCII control characters such as tabs inside the proxy-held key.
- **Public claims stay conservative**: the docs now include a native-Windows repo-local stdio path through `backend/mcp_wrapper.py`, while still asking you to re-check your own remote / GUI-host deployment environment.
- **Client boundaries are explicit**: `Claude/Codex/OpenCode/Gemini` use the documented CLI path; IDE hosts such as `Cursor / Windsurf / VSCode-host / Antigravity` use repo-local rules plus an MCP snippet; `Gemini live` and GUI-only host validation still carry explicit caveats.

---

## ✨ Key Features

### 🔒 Auditable Write Pipeline

Every memory write passes through a strict pipeline: **Write Guard pre-check → Snapshot creation → Async index rebuild**. Core Write Guard actions are `ADD`, `UPDATE`, `NOOP`, and `DELETE`; `BYPASS` is an upper-layer marker for metadata-only update flows. Each step is logged and traceable.

The same rule now applies to Dashboard tree writes as well: `POST /browse/node`, `PUT /browse/node`, and `DELETE /browse/node` also create Review snapshots before modifying data, so the Review page can see and roll them back under the current database scope.

Within the same `session_id`, snapshot writes are now serialized through a per-session file lock, and both `manifest.json` and individual snapshot JSON files are written through atomic replace. In plain terms: if multiple local processes share one repo checkout and touch the same Review session, the snapshot ledger is much less likely to lose entries or leave behind half-written JSON files.

If a Review session's `manifest.json` is damaged, the backend now only rebuilds it when it can preserve the original database scope. In plain terms: switching to another `.env`, compose project, or SQLite file no longer "claims" an old damaged session for the wrong database, and unreadable sessions stay hidden instead of being auto-deleted by a read-only session listing.

If the same URI already has a **newer content snapshot** in another Review session, rolling back the older snapshot now returns `409` instead of pretending the rollback is still safe. In plain terms: the backend now blocks the obvious "old snapshot overwrites newer content" case before it writes.

Normal backend, SSE, and repo-local stdio shutdown paths now also do a **best-effort drain** for pending `compact_context` / auto-flush summaries. In plain language: before the process exits cleanly, the system tries once to persist any pending flush summary; if that step fails, it skips it instead of forcing a risky last-minute write.

Same-session `compact_context` / auto-flush flushes now also take a database-file-backed per-session process lock. In plain language: if two local processes or workers try to compact the same session at the same time, the later one now gets `already_in_progress` instead of racing the write.

Transient SQLite lock conflicts now also get a small bounded retry, and background index jobs go through the same global write gate instead of racing the foreground path. In plain language: foreground writes and async reindex work are less likely to trip over each other under local multi-process pressure.

Dashboard / Review / Maintenance write endpoints now surface write-lane saturation as a structured `503` (`write_lane_timeout`) instead of a generic `500`. The MCP write tools also return a retryable structured error payload for the same condition.

### 🔍 Unified Retrieval Engine

Three retrieval modes — `keyword`, `semantic`, and `hybrid` — with automatic degradation. When external embedding services are unavailable, the system gracefully falls back to keyword search and reports `degrade_reasons` when degradation occurs.

Embedding-dimension mismatch checks now follow the current query scope (`domain`, `path_prefix`, and similar filters) instead of scanning unrelated vectors globally. If the vectors inside that scope really do not match the current config, `degrade_reasons` now explicitly says that a reindex is required.

`candidate_multiplier` is still only a first-round expansion hint, not an unlimited pool-size switch. The current implementation keeps a hard cap on the effective candidate pool and exposes the applied value as `candidate_limit_applied` in metadata.

The final "is this path still current?" revalidation step now also prefers batched path lookups when the backend supports them. In plain terms: larger result sets no longer need one SQLite round-trip per row just to confirm the path still exists.

### 🧠 Intent-Aware Search

The search engine routes queries with four core intent categories — **factual**, **exploratory**, **temporal**, and **causal** — and applies specialized strategy templates (`factual_high_precision`, `exploratory_high_recall`, `temporal_time_filtered`, `causal_wide_pool`); when there is no strong signal it defaults to `factual_high_precision`, and falls back to `unknown` (`default` template) only for conflicting or low-signal mixed queries.

### ♻️ Memory Governance Loop

Memories are living entities with a **vitality score** that decays over time. The governance loop includes: review & rollback, orphan cleanup, vitality decay, and sleep consolidation for automatic fragment cleanup.

### 🌐 Multi-Client MCP Integration

One protocol, many clients: the public docs focus on the most practical paths for **Claude Code / Codex / Gemini CLI / OpenCode**, and separately document **IDE hosts** such as `Cursor / Windsurf / VSCode-host / Antigravity` through repo-local project rules plus MCP snippets.

### 📦 Flexible Deployment

Four deployment profiles (A/B/C/D) from pure local to cloud-connected, with Docker support and one-click scripts. The broadest validated path today is still `macOS + Docker`; native Windows now has a repo-local stdio path through `backend/mcp_wrapper.py`, while remote and GUI-host combinations should still be re-checked in the target environment.

On the repository-shipped Docker / GHCR compose paths, compose now forces WAL by default for the repository's **named-volume** deployment path to reduce `database is locked` style write contention on the shared SQLite volume. That default is **not** meant to bless NFS/CIFS/SMB-style bind mounts for `/app/data`: if you replace the backend data volume with a network filesystem bind mount, explicitly switch back to `MEMORY_PALACE_DOCKER_WAL_ENABLED=false` plus `MEMORY_PALACE_DOCKER_JOURNAL_MODE=delete`. The repo-local `docker_one_click.sh/.ps1` path now fails fast when it detects that risky combination; manual `docker compose up` remains a bring-your-own-validation path.

### 📊 Built-in Observability Dashboard

A React-powered dashboard with four views: **Memory Browser**, **Review & Rollback**, **Maintenance**, and **Observability**.

The current frontend first restores the stored language choice. If there is no stored choice yet, common Chinese browser locales (`zh`, `zh-TW`, `zh-HK`, and similar `zh-*`) are normalized to `zh-CN`; other first-visit cases fall back to English. You can still use the top-right language button to switch between English and Chinese, and the browser remembers your choice for common UI copy, date/number formatting, and common API error hints, including structured validation errors returned by the backend.

Longer-running Observability search and vitality cleanup confirmation calls now also wait longer on the client side, so larger local datasets are less likely to show a browser timeout while the backend is still working.

When neither runtime Dashboard auth nor stored browser Dashboard auth is available, the frontend auto-opens a first-run setup assistant. It can save the Dashboard `MCP_API_KEY` in the current browser session and, when the app is running directly against a local checkout, write the common local runtime fields into `.env` without hand-editing the file. If you use the local `.env` save path and also enter a Dashboard key, the assistant still needs browser session storage for that key; if the browser blocks that storage path, the page now shows a save failure instead of pretending the whole setup succeeded. Backend-side changes still require a restart.

If you want a page-by-page walkthrough of the Dashboard, see [Dashboard User Guide (English)](docs/DASHBOARD_GUIDE_EN.md).

---

## 🏗️ System Architecture

<p align="center">
  <img src="docs/images/系统架构图.png" width="900" alt="Memory Palace Architecture" />
</p>

```
┌─────────────────────────────────────────────────────────────┐
│                    User / AI Agent                          │
│       (Codex · Claude Code · Gemini CLI · OpenCode)         │
└──────────────┬──────────────────────┬───────────────────────┘
               │                      │
    ┌──────────▼──────────┐  ┌────────▼─────────┐
    │  🖥️ React Dashboard  │  │  🔌 MCP Server    │
    │  (Memory / Review /  │  │  (9 Tools + SSE)  │
    │   Maintenance / Obs) │  │                   │
    └──────────┬──────────┘  └────────┬──────────┘
               │                      │
               └──────────┬───────────┘
                          │
                ┌─────────▼──────────┐
                │  ⚡ FastAPI Backend  │
                │  (Async IO)        │
                └───┬────────────┬───┘
                    │            │
          ┌─────────▼──┐  ┌─────▼───────────┐
          │ 🛡️ Write    │  │ 🔍 Search &      │
          │   Guard     │  │   Retrieval      │
          └─────┬──────┘  └─────┬────────────┘
                │               │
          ┌─────▼──────┐  ┌─────▼───────────┐
          │ 📝 Write    │  │ ⚙️ Index Worker  │
          │   Lane      │  │   (Async Queue)  │
          └─────┬──────┘  └─────┬────────────┘
                │               │
                └───────┬───────┘
                        │
                ┌───────▼────────┐
                │ 🗄️ SQLite DB   │
                │ (Single File)  │
                └────────────────┘
```

---

## 🛠️ Tech Stack

### Backend

| Component | Technology | Version | Purpose |
|---|---|---|---|
| Web Framework | [FastAPI](https://fastapi.tiangolo.com/) | ≥ 0.109 | Async REST API with auto-generated OpenAPI docs |
| ORM | [SQLAlchemy](https://www.sqlalchemy.org/) | ≥ 2.0 | Async ORM and query layer for SQLite; schema changes are handled by the repo migration runner |
| Database | [SQLite](https://www.sqlite.org/) + aiosqlite | ≥ 0.19 | Zero-config embedded database; single file, portable |
| MCP Protocol | `mcp (FastMCP)` | ≥ 0.1 | Exposes 9 standardized tools via stdio / SSE transport |
| HTTP Client | [httpx](https://www.python-httpx.org/) | ≥ 0.26 | Async HTTP for embedding / reranker API calls |
| Validation | [Pydantic](https://docs.pydantic.dev/) | ≥ 2.5 | Request/response validation |
| Diff Engine | `diff_match_patch` + `difflib` fallback | — | Prefer semantic HTML diff when `diff_match_patch` is installed; fall back to `difflib.HtmlDiff` table output if that optional package is missing |

### Frontend

| Component | Technology | Version | Purpose |
|---|---|---|---|
| UI Framework | [React](https://react.dev/) | 18 | Component-based dashboard UI |
| Build Tool | [Vite](https://vitejs.dev/) | 7.x | Fast HMR development and optimized production builds |
| Styling | [Tailwind CSS](https://tailwindcss.com/) | 3.x | Utility-first CSS framework |
| Animation | [Framer Motion](https://www.framer.com/motion/) | 12.x | Smooth page transitions and micro-interactions |
| Routing | React Router DOM | 6.x | Client-side routing for four dashboard views |
| API Client | [Axios](https://axios-http.com/) | 1.x | Dashboard API requests and auth header injection |
| Markdown | react-markdown + remark-gfm | — | Reserved for optional Markdown rendering workflows; the current dashboard still renders memory bodies as plain text |
| Icons | [Lucide React](https://lucide.dev/) | — | Consistent icon set across all views |

### How Each Layer Works

#### Write Pipeline (`mcp_server.py` → `runtime_state.py` → `sqlite_client.py`)

1. **Write Guard** — Every `create_memory` / `update_memory` call first passes through the Write Guard (`sqlite_client.py`). In rule-based mode, the guard evaluates in this order: **semantic matching → keyword matching → optional LLM**, and outputs core actions `ADD`, `UPDATE`, `NOOP`, or `DELETE`; `BYPASS` is marked by upper-layer flow for metadata-only updates. When `WRITE_GUARD_LLM_ENABLED=true`, an optional LLM participates via an OpenAI-compatible chat API.

2. **Snapshot** — Before any modification, the system creates snapshots for the current memory state. The MCP tool path uses the snapshot helpers in `mcp_server.py`, and Dashboard `/browse/node` writes follow the same path/content snapshot semantics under a database-scoped dashboard session. Same-session snapshot writes are serialized through a per-session file lock, and both `manifest.json` and per-resource snapshot JSON files are written via atomic replace, so local multi-process use is less likely to lose Review entries or expose half-written snapshot files. This enables full diff comparison and one-click rollback in the Review dashboard.

3. **Write Lane** — Writes enter a serialized queue (`runtime_state.py` → `WriteLanes`) with configurable concurrency (`RUNTIME_WRITE_GLOBAL_CONCURRENCY`). This prevents race conditions on the single SQLite file, and transient SQLite lock conflicts now get a small bounded retry instead of immediately surfacing as a hard failure.

4. **Index Worker** — After each write completes, an async task is enqueued for index rebuild (`IndexWorker` in `runtime_state.py`). The worker still processes index updates in FIFO order, but DB-writing jobs now also pass through the same write-lane gate, so background reindex work is less likely to contend with the foreground write path.

#### Retrieval Pipeline (`sqlite_client.py`)

1. **Query Preprocessing** — `preprocess_query()` normalizes and tokenizes the search query.
2. **Intent Classification** — `classify_intent()` uses keyword scoring (`keyword_scoring_v2`) to determine intent: four core classes (`factual`, `exploratory`, `temporal`, `causal`); it defaults to `factual` (`factual_high_precision`) when no strong keyword signal exists, and falls back to `unknown` (`default` template) for conflicting or low-signal mixed queries.
3. **Strategy Selection** — Based on intent, a strategy template is applied (e.g., `factual_high_precision` uses tighter matching; `temporal_time_filtered` adds time range constraints).
4. **Multi-Stage Retrieval** — Depending on the profile:
   - **Profile A**: Pure keyword matching via SQLite FTS
   - **Profile B**: Keyword + local hash embedding hybrid scoring
   - **Profile C/D**: Keyword + API embedding + reranker (OpenAI-compatible)
5. **Result Assembly** — Results include `degrade_reasons` when any stage fails, so the caller always knows the retrieval quality.

#### Memory Governance (`sqlite_client.py` → `runtime_state.py`)

- **Vitality Decay** — Each memory has a vitality score (max `3.0`, configurable). Scores decay exponentially with `VITALITY_DECAY_HALF_LIFE_DAYS=30`. Memories below `VITALITY_CLEANUP_THRESHOLD=0.35` for over `VITALITY_CLEANUP_INACTIVE_DAYS=14` days are flagged for cleanup.
- **Sleep Consolidation** — `rebuild_index` with consolidation merges fragmented small memories into coherent summaries.
- **Orphan Cleanup** — Periodic scans identify paths without valid memory references.

---

## 📁 Project Structure

```
memory-palace/
├── backend/
│   ├── main.py                 # FastAPI entrypoint; registers Review/Browse/Maintenance/Setup routes
│   ├── mcp_server.py           # 9 MCP tools + snapshot logic + URI parsing
│   ├── runtime_state.py        # Write Lane queue, Index Worker, vitality decay scheduler
│   ├── run_sse.py              # SSE transport layer with API Key auth gating
│   ├── requirements.txt        # Backend runtime dependencies
│   ├── requirements-dev.txt    # Backend test dependencies
│   ├── db/
│   │   └── sqlite_client.py    # Schema definition, CRUD, retrieval, Write Guard, Gist
│   ├── api/                    # REST routers: review, browse, maintenance, setup
├── frontend/
│   └── src/
│       ├── App.jsx             # Routing and page scaffold
│       ├── features/
│       │   ├── memory/         # MemoryBrowser.jsx — tree browser, editor, Gist view
│       │   ├── review/         # ReviewPage.jsx — diff comparison, rollback, integrate
│       │   ├── maintenance/    # MaintenancePage.jsx — vitality cleanup tasks
│       │   └── observability/  # ObservabilityPage.jsx — retrieval & task monitoring
│       └── lib/
│           └── api.js          # Unified API client with runtime auth injection
├── deploy/
│   ├── profiles/               # A/B/C/D profile templates for macOS/Windows/Docker
│   └── docker/                 # Dockerfile and compose helpers
├── scripts/
│   ├── apply_profile.sh        # macOS/Linux profile applicator
│   ├── apply_profile.ps1       # Windows profile applicator
│   ├── docker_one_click.sh     # macOS/Linux one-click Docker deployment
│   └── docker_one_click.ps1    # Windows one-click Docker deployment
├── docs/                       # Full documentation suite
├── .env.example                # Configuration template (with detailed comments)
├── docker-compose.yml          # Docker Compose definition
└── LICENSE                     # MIT License
```

---

## 📋 Requirements

| Component | Minimum | Recommended |
|---|---|---|
| Python | 3.10+ | 3.11+ |
| Node.js | 20.19+ (or >=22.12) | latest LTS |
| npm | 9+ | latest stable |
| Docker (optional) | 20+ | latest stable |

---

## 🚀 Quick Start

### Option 1: Pull Prebuilt Docker Images (Fastest User Path)

If your local build environment keeps failing, use the prebuilt GHCR images first. This path is for **running the service**, not for building images locally.

```bash
git clone https://github.com/AGI-is-going-to-arrive/Memory-Palace.git
cd Memory-Palace

cp .env.example .env.docker
bash scripts/apply_profile.sh docker b .env.docker

docker compose -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.ghcr.yml up -d
```

```powershell
git clone https://github.com/AGI-is-going-to-arrive/Memory-Palace.git
cd Memory-Palace

Copy-Item .env.example .env.docker
.\scripts\apply_profile.ps1 -Platform docker -Profile b -Target .env.docker

docker compose -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.ghcr.yml up -d
```

Default access addresses:

| Service | URL |
|---|---|
| Frontend Dashboard | <http://127.0.0.1:3000> |
| Backend API | <http://127.0.0.1:18000> |
| SSE | <http://127.0.0.1:3000/sse> |

Important boundaries:

- This path avoids **local image build**, but you still need the repository checkout to get `docker-compose.ghcr.yml`, `.env.example`, and the profile helpers.
- This path solves **Dashboard / API / proxied SSE endpoint startup** only.
- It does **not** automatically configure `Claude / Codex / Gemini / OpenCode / Cursor / Antigravity` on your machine.
- If you also want repo-local skill + MCP automation, keep the same checkout and continue with [docs/skills/GETTING_STARTED_EN.md](docs/skills/GETTING_STARTED_EN.md).
- If you do **not** want the repo-local install path, any MCP client that supports remote SSE can still be configured manually to connect to `http://localhost:3000/sse` with the matching API key / auth header. For this GHCR path, that key normally means the `MCP_API_KEY` written into the freshly generated `.env.docker`.
- If a Dockerized C / D setup still needs to reach a model service on your host machine, use `host.docker.internal`. The compose files now add `host.docker.internal:host-gateway`, so this path also works on modern Linux Docker instead of only Docker Desktop.
- Do **not** assume the repo-local stdio wrapper shares container data automatically. `scripts/run_memory_palace_mcp_stdio.sh` needs a host-side local repository `.env` and the local `backend/.venv`; it does not reuse container data from `/app/data`.
- If you later switch back to a local `stdio` client, your local `.env` must contain a host-accessible absolute path. If `.env` is missing while `.env.docker` exists, the wrapper refuses to fall back to `demo.db`; if `.env` or an explicit `DATABASE_URL` still points to `/app/...` or `/data/...`, it also refuses to start and tells you to use a host path or Docker `/sse` instead.
- Unlike `docker_one_click.sh/.ps1`, the GHCR compose path does **not** auto-adjust ports. If `3000` / `18000` are already occupied, set `MEMORY_PALACE_FRONTEND_PORT` / `MEMORY_PALACE_BACKEND_PORT` yourself before `docker compose up`.

Stop services:

```bash
docker compose -f docker-compose.ghcr.yml down --remove-orphans
```

### Option 2: Manual Local Setup (Recommended for Beginners)

> **💡 Tip**: The recommended starting target in this guide is still **Profile B**, so you can boot with zero external model services.
> For real day-to-day retrieval quality, **Profile C is the strongly recommended target profile** once you are ready to fill the embedding / reranker / LLM settings described in [Upgrading to Profile C/D](#-upgrading-to-profile-cd).

#### Step 1: Clone the Repository

```bash
git clone https://github.com/AGI-is-going-to-arrive/Memory-Palace.git
cd Memory-Palace
```

#### Step 2: Create Configuration File

Choose **one** of the following methods:

**Method A — Copy template and edit manually:**

```bash
cp .env.example .env
```

> This path starts from the **conservative `.env.example` template**. It is enough for a minimal local boot, but it is **not the same thing as applying Profile B**.
>
> If you want the actual Profile B defaults from this repository (for example local hash embedding), use **Method B** below. If you stay on Method A, that is fine too — just treat it as the minimal template and fill the fields you actually need.

Then open `.env` and set `DATABASE_URL` to a path on your system. An absolute path is recommended for shared or production-like environments:

```bash
# Example for macOS / Linux:
DATABASE_URL=sqlite+aiosqlite:////absolute/path/to/demo.db

# Example for Windows:
DATABASE_URL=sqlite+aiosqlite:///C:/absolute/path/to/demo.db
```

> Do not copy the Docker / GHCR value `sqlite+aiosqlite:////app/data/...`, or any other container-only sqlite path such as `/data/...`, into a local `.env`. `/app/...` and `/data/...` are container-internal paths, not real file paths on your host machine; the repo-local `stdio` wrapper now refuses this configuration explicitly. For local `stdio`, use a host absolute path instead. If you actually want the Docker-side data and service, connect to the Docker-exposed `/sse` endpoint instead.

If you want to use the Dashboard or call `/browse` / `/review` / `/maintenance` locally right away, add **one** of these lines to your `.env` before starting the backend:

```dotenv
# Option A: set a local API key (recommended)
MCP_API_KEY=change-this-local-key

# Option B: local loopback-only debugging (do not use on shared machines)
MCP_API_KEY_ALLOW_INSECURE_LOCAL=true
```

**Method B — Use the profile script (recommended):**

```bash
# macOS / Linux (use the `macos` template value here)
bash scripts/apply_profile.sh macos b

# Windows PowerShell
.\scripts\apply_profile.ps1 -Platform windows -Profile b
```

This generates a Profile B-based env file using the platform-specific template at `deploy/profiles/{macos,windows,docker}/profile-b.env`. Local shell runs (`macos` / `linux`) and native `windows` still default to `.env`; if you run the `docker` variant without an explicit target file, `apply_profile.sh/.ps1` now defaults to `.env.docker`.

Treat `deploy/profiles/*/*.env` as **Profile template inputs**, not as final `.env` files you should copy by hand. Some template values intentionally keep placeholder paths until `apply_profile.*` rewrites them for the current repository location.

For `profile c/d`, `apply_profile.sh/.ps1` now also fail-closed when the generated file still contains unresolved endpoint/key/model placeholders. In plain language: replace the example `PORT`, key, and model-id values first, then continue to Docker startup or local C/D testing.

The same guard now also applies to `DATABASE_URL` placeholder remnants. On the local shell path, `apply_profile.sh` rewrites the common checkout-specific placeholder path for you, including `/Users/...` and `/home/...`; if the generated result still leaves segments such as `<...>` or `__REPLACE_ME__` inside `DATABASE_URL`, the script/backend stop early instead of quietly carrying a broken sqlite path forward.

On macOS / Linux, `apply_profile.sh` now also backs up an existing target file to `*.bak` before overwrite. If you only want to preview the generated result first, use `bash scripts/apply_profile.sh --dry-run ...`; that prints the final env content without writing the target file. Windows PowerShell now has the same preview path via `.\scripts\apply_profile.ps1 -Platform windows -Profile b -DryRun`. If you only want the script usage first, run `.\scripts\apply_profile.ps1 -Help`.

If you previously generated `.env.docker`, do not simply rename that Docker file to `.env`. The Docker profile uses container-only paths such as `/app/data/...`; if you customized the mount to `/data/...`, that is still container-only. Local `stdio` MCP needs a host-side absolute path instead.

On **macOS / Windows local setup**, the generated file still leaves `MCP_API_KEY` empty by default. If you want the Dashboard, `/browse` / `/review` / `/maintenance`, or `/sse` / `/messages` to work immediately, add either:

- `MCP_API_KEY=change-this-local-key`
- `MCP_API_KEY_ALLOW_INSECURE_LOCAL=true` (loopback-only debugging on your own machine)

For the **docker** platform only, `apply_profile` auto-generates a local `MCP_API_KEY` when the value is empty.

#### Step 3: Start the Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# If you also plan to run backend tests afterwards
# pip install -r requirements-dev.txt

# Start the API server
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

You should see:

```
Memory API starting...
SQLite database initialized.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

> The `uvicorn main:app --host 127.0.0.1 ...` command above is the recommended **local development** form.
>
> If your machine exposes Python as `python3` instead of `python`, replace `python` with `python3` in the commands above.
>
> If you instead run `python main.py`, the current default is still loopback: `127.0.0.1:8000`. If you actually want LAN / remote direct access, bind it explicitly with `uvicorn main:app --host 0.0.0.0 --port 8000` (or your own listening address) and only do that after your `MCP_API_KEY`, firewall rules, reverse proxy, and equivalent network protections are already in place.

#### Step 4: Start the Frontend

Open a **new terminal** window:

```bash
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

You should see:

```
  VITE v7.x.x  ready

  ➜  Local:   http://localhost:5173/
```

#### Step 5: Verify Everything Works

```bash
# Check backend health
curl -s http://127.0.0.1:8000/health | python -m json.tool

# Browse memory tree
#
# Option A: if you configured `MCP_API_KEY`
curl -s "http://127.0.0.1:8000/browse/node?domain=core&path=" \
  -H "X-MCP-API-Key: <YOUR_MCP_API_KEY>" | python -m json.tool

# Option B: if you enabled `MCP_API_KEY_ALLOW_INSECURE_LOCAL=true`
curl -s "http://127.0.0.1:8000/browse/node?domain=core&path=" | python -m json.tool
```

Open your browser at **<http://localhost:5173>** — you should see the Memory Palace dashboard 🎉

> If local manual setup shows `Set API key` in the top-right corner, that is expected. The dashboard shell is up, but protected data requests (`/browse/*`, `/review/*`, `/maintenance/*`) still follow `MCP_API_KEY` / `MCP_API_KEY_ALLOW_INSECURE_LOCAL`. The separate MCP SSE endpoints (`/sse` and `/messages`) follow the same rule.
>
> If you set `MCP_API_KEY`, click `Set API key` to open the setup assistant, then either save the same key to the current browser session or, on a local non-Docker checkout, write it into `.env` together with the other common runtime fields. If you enabled `MCP_API_KEY_ALLOW_INSECURE_LOCAL=true`, direct loopback requests (`127.0.0.1` / `::1` / `localhost`, without forwarded headers) can load those protected requests without manually entering a key.
>
> If you choose **Save dashboard key only**, that key is stored in the current browser session (`sessionStorage`) until you clear it manually or that browser session ends. The setup assistant's `Profile C/D` presets now follow the documented `router + reranker` path; if your local router is not ready yet, switch the retrieval fields manually to direct API mode for debugging.
>
> If you choose **Save local `.env` settings** and also fill a Dashboard key, remember that `.env` writing and browser key storage are two separate steps. If the browser blocks local storage, the assistant now shows a save failure instead of a false success. In practice that usually means the `.env` change may already be written, but the browser-side auth is still not ready; check the top-right auth state and retry if needed.
>
> The setup assistant stays in guidance mode when the frontend is talking to Docker containers. It does not pretend that container env / proxy changes can be persisted or hot-reloaded from the browser.

#### Step 6: Connect an AI Client

Start the MCP server so AI clients can access Memory Palace:

```bash
cd backend

# stdio mode (for common stdio clients such as Claude Code / Codex / OpenCode)
python mcp_server.py

# safer in a new terminal or client config
./.venv/bin/python mcp_server.py   # Windows: .\.venv\Scripts\python.exe mcp_server.py

# SSE mode (loopback example; change HOST for remote access)
HOST=127.0.0.1 PORT=8010 python run_sse.py
```

```powershell
cd backend
$env:HOST = "127.0.0.1"
$env:PORT = "8010"
python run_sse.py
```

> Note: `stdio` connects directly to the MCP tool process and does not pass through the HTTP/SSE auth middleware, so MCP tools can still be used locally without `MCP_API_KEY`. This applies to `stdio` only — protected HTTP/SSE routes still follow the normal API key rules.
>
> The plain `python mcp_server.py` form assumes you are still using the same `backend/.venv` where you ran `pip install -r requirements.txt`. If you launch MCP from a new terminal or a client config, it is safer to point to the project venv directly. Otherwise the process can fail before startup with errors like `ModuleNotFoundError: No module named 'sqlalchemy'`.
>
> If you are wiring MCP into a client config, use the launcher that matches your local shell boundary:
>
> - native Windows: prefer `backend/mcp_wrapper.py`
> - macOS / Linux / Git Bash / WSL: prefer `scripts/run_memory_palace_mcp_stdio.sh`
>
> Both launchers use the repository `backend/.venv`, read the repository `.env` first, and only fall back to the repo's default SQLite path when neither `DATABASE_URL` nor `.env` is present. They also reuse `RETRIEVAL_REMOTE_TIMEOUT_SEC` from the repository `.env` when it is set; if you leave it unset, the repo-local default remains `8` seconds. If `.env` is missing but `.env.docker` exists, or if a local `.env` still points `DATABASE_URL` at a Docker-internal path such as `sqlite+aiosqlite:////app/data/memory_palace.db` or a `/data/...` variant, the wrapper now refuses to start on purpose because the repo-local stdio path does **not** reuse container-only sqlite paths. In a Docker-only setup, connect the client to `/sse` instead of assuming the wrapper will pick up container data. The repo-local stdio wrapper also no longer depends on `python-dotenv` alone just to read `.env`; if local startup still fails after this change, the problem is usually the `.env` content or path itself rather than that extra package being missing.
>
> On the shell-wrapper path (`macOS / Linux / Git Bash / WSL`), `run_memory_palace_mcp_stdio.sh` now also exports `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1` before it starts Python. In plain language: a non-UTF-8 locale is less likely to turn local stdio traffic into mojibake or encoding errors.
>
> On native Windows or other wrapper-heavy host paths, the repo-local stdio launcher now forwards stdin/stdout in chunks instead of byte by byte. In plain language: larger MCP responses should feel less sluggish than before, while the same CRLF cleanup rules still apply.
>
> One more detail rechecked in the current validation round: if a client or IDE host passes `DATABASE_URL` as an empty string, these wrappers still treat that as “not set” and keep reusing the repository `.env` value. They do not misclassify that case as a missing repo-local configuration just because the variable name exists.
>
> The same rule now applies when `.env` itself is wrong: if `.env` or an explicit `DATABASE_URL` still points to `/app/...` or `/data/...`, the wrapper refuses to start on purpose. That is a local path configuration error, not an MCP protocol failure.
>
> `python run_sse.py` first tries loopback `127.0.0.1:8000`; if local `8000` is already occupied by the main backend, it automatically falls back to `127.0.0.1:8010`. This `HOST=127.0.0.1` example is intentionally loopback-only. If you really need remote access, switch `HOST` to `0.0.0.0` (or your bind address). That opens the listener for remote clients, but it does **not** remove the normal safety requirements — you still need your own API key, firewall, reverse proxy, and transport security controls. If your remote hostname / origin should also pass MCP transport-security checks, add it explicitly through `MCP_ALLOWED_HOSTS` / `MCP_ALLOWED_ORIGINS` instead of assuming a non-loopback bind disables those checks.

See [Multi-Client Integration](#-multi-client-integration) for detailed client configuration.

---

### Option 3: One-Click Docker Deployment

```bash
# macOS / Linux
bash scripts/docker_one_click.sh --profile b

# Windows PowerShell
.\scripts\docker_one_click.ps1 -Profile b

# Explicitly opt in when runtime env injection is required (disabled by default)
bash scripts/docker_one_click.sh --profile c --allow-runtime-env-injection
# or
.\scripts\docker_one_click.ps1 -Profile c -AllowRuntimeEnvInjection
```

> One-click Docker deployment brings up the current two-service topology and exposes three operator endpoints:
>
> - Dashboard: `http://127.0.0.1:3000`
> - Backend API: `http://127.0.0.1:18000`
> - SSE: `http://127.0.0.1:3000/sse`
>
> If `MCP_API_KEY` is empty in the Docker env file, the profile helper generates a local key automatically. The frontend proxy uses that key on the server side, so on the recommended one-click path, **protected requests usually already work**. The page may still keep showing `Set API key`, because the browser itself does not know the proxy-held key. Treat that as expected unless protected data also starts failing with `401` or empty states.
>
> Keep using `/sse` as the canonical public URL in client configs. `/sse/` is now only kept as a compatibility spelling and is forwarded to the same backend SSE path, so new examples and operator docs should continue to point to `/sse`.
>
> Treat that Docker frontend port as a trusted operator/admin surface. Anyone who can directly reach `http://<host>:3000` can use the Dashboard and its proxied protected routes, so do not expose this port to untrusted networks as if `MCP_API_KEY` were end-user auth. Add your own VPN, reverse-proxy auth, or network ACL in front of it.
>
> WAL safety boundary: the repository defaults still assume the backend database lives on the Docker **named volume** mounted at `/app/data`. If you intentionally replace that with a bind mount to NFS/CIFS/SMB or another network filesystem, do **not** keep WAL enabled. `docker_one_click.sh/.ps1` now runs a preflight check and aborts before `docker compose up` when it sees that risky combination. If you are bypassing the one-click script and running `docker compose up` yourself, you must enforce the same rule manually.
>
> Windows check (March 19, 2026): this repo-local `docker compose -f docker-compose.yml` path was rechecked end to end on native Windows. `http://127.0.0.1:3000/sse` returned `HTTP 200`, exposed `/messages/?session_id=...`, and both `Claude` and `Gemini` completed a real `read_memory(system://boot)` call through that proxied SSE endpoint.
>
> The Docker frontend now waits for the backend `/health` check before it is treated as ready, and the one-click readiness probe also verifies that the proxied `/sse` endpoint is reachable through the frontend. The backend container-side check is no longer just “HTTP 200 from `/health` is enough”; it also requires the payload to report `status == "ok"`. If containers are already up but the page still looks unavailable, wait a few more seconds and re-check the printed URLs.
>
> The Docker frontend also serves `/index.html` with `Cache-Control: no-store, no-cache, must-revalidate` to reduce the chance that a browser keeps an old entry page after a frontend update. If you still see an obviously old page after upgrading the image, first confirm the new container is actually running, then refresh the page once. Only continue checking cache behavior if you also put your own reverse proxy or CDN in front of it.
>
> Docker also persists two runtime data paths by default: the database volume is isolated per compose project as `<compose-project>_data` (`/app/data` in the container), and the snapshots volume is isolated as `<compose-project>_snapshots` (`/app/snapshots` in the container). If you want to intentionally reuse an old shared volume, set `MEMORY_PALACE_DATA_VOLUME` / `MEMORY_PALACE_SNAPSHOTS_VOLUME` explicitly. If you run `docker compose down -v` or delete those volumes manually, both are cleared together.
>
> That isolation also affects the Review page: when you switch to another data volume or compose project, the visible rollback sessions move with that database instead of being merged across environments.

| Service | URL |
|---|---|
| Frontend Dashboard | <http://127.0.0.1:3000> |
| Backend API | <http://127.0.0.1:18000> |
| SSE | <http://127.0.0.1:3000/sse> |
| Health Check | <http://127.0.0.1:18000/health> |

> Note: these are default ports. If occupied, the one-click script auto-adjusts ports and prints the actual URLs in console output.

Stop services:

```bash
COMPOSE_PROJECT_NAME=<printed-compose-project> docker compose -f docker-compose.yml down --remove-orphans
```

---

## ⚙️ Deployment Profiles (A / B / C / D)

Memory Palace provides four deployment profiles to match your hardware and requirements:

| Profile | Retrieval Mode | Embedding | Reranker | Best For |
|---|---|---|---|---|
| **A** | `keyword` only | ❌ Off | ❌ Off | 🟢 Minimal resources, initial validation |
| **B** | `hybrid` | 📦 Local Hash | ❌ Off | 🟡 **Default starting profile** — local dev, no external services |
| **C** | `hybrid` | 🌐 Router / API | ✅ On | 🟠 **Strongly recommended** when you can provide local model endpoints |
| **D** | `hybrid` | 🌐 Router / API | ✅ On | 🔴 Remote API, production environments |

> **Note**: Profiles C and D share the same hybrid retrieval pipeline (`keyword + semantic + reranker`). In the shipped templates, the main differences are the model endpoint (local vs remote) and the default `RETRIEVAL_RERANKER_WEIGHT` (`0.30` vs `0.35`).

### 🔼 Upgrading to Profile C/D

**Profile C is the strongly recommended target profile**, but it is not zero-config.

- Keep **Profile B** as the default starting point when you want the repo to work with no extra model services.
- Move to **Profile C** when you are ready to configure the embedding and reranker endpoints yourself.
- If you also want LLM-assisted write guard / gist / intent routing, fill the matching `WRITE_GUARD_LLM_*`, `COMPACT_GIST_LLM_*`, and optional `INTENT_LLM_*` settings in the same `.env`.

Configure these parameters in your `.env` file. All endpoints support the **OpenAI-compatible API** format, including locally deployed Ollama or LM Studio:

```bash
# ── Embedding Model ──────────────────────────────────────────
RETRIEVAL_EMBEDDING_BACKEND=api
RETRIEVAL_EMBEDDING_API_BASE=http://localhost:11434/v1   # e.g., Ollama
RETRIEVAL_EMBEDDING_API_KEY=your-api-key
RETRIEVAL_EMBEDDING_MODEL=your-embedding-model-id
RETRIEVAL_EMBEDDING_DIM=1024          # Match the provider's actual vector size

# ── Reranker Model ───────────────────────────────────────────
RETRIEVAL_RERANKER_ENABLED=true
RETRIEVAL_RERANKER_API_BASE=http://localhost:11434/v1
RETRIEVAL_RERANKER_API_KEY=your-api-key
RETRIEVAL_RERANKER_MODEL=your-reranker-model-id

# ── Tuning (recommended 0.20 ~ 0.40) ────────────────────────
RETRIEVAL_RERANKER_WEIGHT=0.25
```

> Configuration semantics:
> - `RETRIEVAL_EMBEDDING_BACKEND` controls only the embedding path.
> - There is no `RETRIEVAL_RERANKER_BACKEND` switch; reranker activation is controlled by `RETRIEVAL_RERANKER_ENABLED`.
> - Reranker connection settings are resolved from `RETRIEVAL_RERANKER_API_BASE/API_KEY/MODEL` first, and fall back to `ROUTER_*` only when missing (with base/key then able to fall back to `OPENAI_*`).
> - The current runtime also sends `RETRIEVAL_EMBEDDING_DIM` as the `dimensions` field on OpenAI-compatible `/embeddings` requests; if a provider explicitly rejects that field, it automatically retries once without `dimensions`.
> - If the final embedding response still comes back with the wrong vector size, the runtime now rejects that vector immediately and falls back / degrades instead of silently writing an incompatible index entry.
>
> The model IDs above are placeholders only. Memory Palace does not require a specific provider or model family; use the exact embedding / reranker / chat model IDs exposed by your own OpenAI-compatible service.
> If you are using a local OpenAI-compatible endpoint such as Ollama, prefer the `/v1/embeddings` path as well; only set an explicit `dimensions=1024` when the model really returns 1024-dimensional vectors.
> For a quick local smoke test, it is usually faster to hit the real `/embeddings` and `/rerank` endpoints with the same model/key you plan to use before blaming the backend. The troubleshooting guide includes copyable `curl` examples.
> If you use `docker_one_click.sh/.ps1` for `profile c/d`, unresolved placeholder model IDs are treated the same as placeholder endpoint/key values: the script stops before `docker compose` until you replace them with real values.
>
> If you use `--allow-runtime-env-injection` for local `profile c/d` debugging, the script switches that run into explicit API mode, forwards explicit `RETRIEVAL_EMBEDDING_*` (including `RETRIEVAL_EMBEDDING_DIM`), `RETRIEVAL_RERANKER_ENABLED` / `RETRIEVAL_RERANKER_*`, and optional `WRITE_GUARD_LLM_*` / `COMPACT_GIST_LLM_*` / `INTENT_LLM_*` values, reuses `ROUTER_API_BASE/ROUTER_API_KEY` as the fallback source for embedding / reranker API base+key when the explicit `RETRIEVAL_*` values are not set, and falls back to `ROUTER_RERANKER_MODEL` when `RETRIEVAL_RERANKER_MODEL` is still missing.
>
> For local Docker builds, the one-click path now also uses stable checkout-scoped image names. In practice this means `--no-build` can reuse images built earlier in the same checkout even if you change `COMPOSE_PROJECT_NAME`; the only time you still need `--build` is the first run or after deleting those local images.
>
> Advanced switch guidance:
> - `INTENT_LLM_ENABLED`: experimental; keep `false` unless you are validating a stable chat model and want better intent classification on ambiguous queries
> - `RETRIEVAL_MMR_ENABLED`: keep `false` by default; turn it on only when hybrid results look too repetitive and you want more diversity in the top results
> - `CORS_ALLOW_ORIGINS`: leave empty for local development; in production, set an explicit browser allowlist instead of using `*`
> - `RETRIEVAL_SQLITE_VEC_ENABLED`: keep `false` for normal user deployments; this is still a rollout switch for sqlite-vec validation and fallback testing

### Optional: LLM-Powered Write Guard & Gist

```bash
# ── Write Guard LLM ─────────────────────────────────────────
WRITE_GUARD_LLM_ENABLED=true
WRITE_GUARD_LLM_API_BASE=http://localhost:11434/v1
WRITE_GUARD_LLM_API_KEY=your-api-key
WRITE_GUARD_LLM_MODEL=your-chat-model-id

# ── Compact Gist LLM (falls back to Write Guard if empty) ──
COMPACT_GIST_LLM_ENABLED=true
COMPACT_GIST_LLM_API_BASE=
COMPACT_GIST_LLM_API_KEY=
COMPACT_GIST_LLM_MODEL=your-chat-model-id
```

Profile templates are located at: `deploy/profiles/{macos,windows,docker}/profile-{a,b,c,d}.env`

Full parameter reference: [DEPLOYMENT_PROFILES_EN.md](docs/DEPLOYMENT_PROFILES_EN.md)

---

## 🔌 MCP Tools Reference

Memory Palace exposes **9 standardized tools** via the MCP protocol:

| Category | Tool | Description |
|---|---|---|
| **Read/Write** | `read_memory` | Read memory content (full or chunked by `RETRIEVAL_CHUNK_SIZE`) |
| | `create_memory` | Create new memory node (passes through Write Guard first; prefer giving an explicit `title`) |
| | `update_memory` | Update existing memory (prefer Patch mode; use Append only for real tail appends) |
| | `delete_memory` | Delete a memory path (returns a structured JSON string) |
| | `add_alias` | Add an alias path for a memory |
| **Retrieval** | `search_memory` | Unified search entry with `keyword` / `semantic` / `hybrid` modes |
| **Governance** | `compact_context` | Compress session context into long-term summary (Gist + Trace) |
| | `rebuild_index` | Trigger index rebuild / sleep consolidation |
| | `index_status` | Query index availability and runtime state |

### System URIs

| URI | Description |
|---|---|
| `system://boot` | Loads core memories from `CORE_MEMORY_URIS` when `system://boot` is read |
| `system://index` | Full memory index overview |
| `system://index-lite` | Gist-backed lightweight index summary |
| `system://audit` | Consolidated observability / audit summary |
| `system://recent` | Recently modified memories |
| `system://recent/N` | Last N memories |

### Starting the MCP Server

```bash
# stdio mode (for common stdio clients — Claude Code, Codex, OpenCode, etc.)
cd backend && python mcp_server.py

# safer in a new terminal or client config
cd backend && ./.venv/bin/python mcp_server.py   # Windows: cd backend && .\.venv\Scripts\python.exe mcp_server.py

# SSE mode (loopback example; change HOST for remote access)
cd backend && HOST=127.0.0.1 PORT=8010 python run_sse.py
```

> The plain `python mcp_server.py` form assumes `backend/.venv` is already active. If you are wiring up a client on a fresh terminal, use the venv's Python directly to avoid starting with the wrong interpreter.
>
> Use `HOST=0.0.0.0` only when you really need remote clients and have already added the usual network protections.

Full tool semantics: [TOOLS_EN.md](docs/TOOLS_EN.md)

---

## 🔄 Multi-Client Integration

The MCP tool layer handles **deterministic execution**; the Skills strategy layer handles **policy and timing**.

<p align="center">
  <img src="docs/images/多客户端 MCP + Skills 编排图.png" width="900" alt="Multi-Client MCP + Skills Orchestration" />
</p>

### Recommended Default Flow

```
1. 🚀 Boot    → read_memory("system://boot")               # Load core memories
2. 🔍 Recall  → search_memory(include_session=true)         # Topic recall
3. ✍️ Write   → prefer update_memory patch; create_memory if new (with title)  # Read before write
4. 📦 Compact → compact_context(force=false)                 # Session compression
5. 🔧 Recover → rebuild_index(wait=true) + index_status()   # Degradation recovery
```

### Supported Clients

| Client | Integration Method |
|---|---|
| Claude Code | User-scope install is the stable default on fresh machines; add workspace install only if you also want a project-level entry in this repo |
| Gemini CLI | User-scope install is the stable default on fresh machines; workspace install stays optional for the current repo |
| Codex CLI / OpenCode | `sync` gives repo-local skill discovery; use `--scope user --with-mcp` if you want MCP to reliably bind to this repo backend |
| Cursor / Windsurf / VSCode-host / Antigravity | Repo-local `AGENTS.md` + rendered MCP snippet |

### Install The Skill

```bash
python scripts/sync_memory_palace_skill.py
python scripts/sync_memory_palace_skill.py --check
python scripts/install_skill.py --targets claude,codex,gemini,opencode --scope user --with-mcp --force
python scripts/install_skill.py --targets claude,gemini --scope workspace --with-mcp --force
python scripts/install_skill.py --targets claude,gemini --scope workspace --with-mcp --check
```

For workspace-local MCP, the script only manages stable repo-local bindings for `Claude Code` and `Gemini CLI`. Keep `Codex/OpenCode` on the user-scope MCP path.

For IDE hosts, do not start with hidden skill mirrors. Render the repo-local MCP snippet instead:

```bash
python scripts/render_ide_host_config.py --host cursor
python scripts/render_ide_host_config.py --host windsurf
python scripts/render_ide_host_config.py --host vscode
python scripts/render_ide_host_config.py --host antigravity
```

If an IDE host has `stdin/stdout` or CRLF quirks, switch to the wrapper form:

```bash
python scripts/render_ide_host_config.py --host antigravity --launcher python-wrapper
```

Optional local verification on your own machine:

```bash
python scripts/evaluate_memory_palace_skill.py
cd backend && python ../scripts/evaluate_memory_palace_mcp_e2e.py
```

For `Gemini CLI`, `Codex CLI`, and `OpenCode`, prefer a **user-scope** MCP install on fresh machines:

```bash
python scripts/install_skill.py --targets gemini,codex,opencode --scope user --with-mcp --force
```

The two verification commands above are best treated as **extra validation**, not as the first thing every user must run.

Canonical source and the local paths that appear after you run the CLI sync/install steps:

- Canonical: `<repo-root>/docs/skills/memory-palace/`
- Claude Code: `<repo-root>/.claude/skills/memory-palace/`
- Codex CLI: `<repo-root>/.codex/skills/memory-palace/`
- OpenCode: `<repo-root>/.opencode/skills/memory-palace/`

These hidden client directories are local mirrors generated after install. A new clone normally starts with only the canonical bundle under `docs/skills/memory-palace/`.

For IDE hosts, the recommended projection is different:

- repo-local rules: `<repo-root>/AGENTS.md`
- MCP config snippet: `python scripts/render_ide_host_config.py --host <cursor|windsurf|vscode|antigravity>`
- Antigravity fallback: `backend/mcp_wrapper.py` only when the host really needs a wrapper

The canonical skill is aligned with the current code contract:

- start relevant sessions with `read_memory("system://boot")`
- prefer `search_memory(..., include_session=true)` when the URI is uncertain
- follow read-before-write discipline and inspect `guard_action` / `guard_reason`
- check `index_status()` before deciding to run `rebuild_index(wait=true)`
- when `guard_action=NOOP`, stop writing, inspect the suggested target, and only then decide whether to switch to `update_memory`
- the trigger sample set lives at `<repo-root>/docs/skills/memory-palace/references/trigger-samples.md`

If you want to re-check skill smoke or the live MCP path, run `python scripts/evaluate_memory_palace_skill.py` and `cd backend && python ../scripts/evaluate_memory_palace_mcp_e2e.py`. By default they generate local reports under `docs/skills/`; if you need isolated output during parallel review or CI, set `MEMORY_PALACE_SKILL_REPORT_PATH` / `MEMORY_PALACE_MCP_E2E_REPORT_PATH` first. `evaluate_memory_palace_skill.py` now returns a non-zero exit code whenever any check is `FAIL`; `SKIP` / `PARTIAL` / `MANUAL` do not fail the process by themselves, and the current default Gemini smoke model is `gemini-3-flash-preview`. If you only want to override that model locally for one run, set `MEMORY_PALACE_GEMINI_TEST_MODEL`; if you also need a separate fallback model, add `MEMORY_PALACE_GEMINI_FALLBACK_MODEL`. On a clean clone, "workspace mirrors not installed yet" is now reported as `PARTIAL` instead of a hard failure. If `codex exec` starts but does not emit structured output before the smoke timeout, the `codex` item also lands as `PARTIAL` instead of stalling the whole run. If the current machine simply does not have the `Antigravity` host runtime, treat the `antigravity` item as manual host-side follow-up rather than a repository-mainline failure.

The live MCP e2e script now follows the same repo-local wrapper path that users actually connect to. In the current verified path, it also covers wrapper behavior and `compact_context` gist persistence instead of only checking the bare tool inventory.

Full guides:

- [MEMORY_PALACE_SKILLS_EN.md](docs/skills/MEMORY_PALACE_SKILLS_EN.md)
- [IDE_HOSTS_EN.md](docs/skills/IDE_HOSTS_EN.md)

---

## 📊 Benchmark Results

> This section keeps the **user-facing summary tables** from the current benchmark suite.
>
> For methodology, caveats, and reproduction commands, see [EVALUATION_EN.md](docs/EVALUATION_EN.md). For the same-setup old-vs-current summary used in this release note, see [release_summary_vs_old_project_2026-03-06_EN.md](docs/changelog/release_summary_vs_old_project_2026-03-06_EN.md).
>
> The numbers below are a release summary, not a guarantee for every hardware or provider setup.

### Retrieval Quality — A/B/C/D Real Run

Source: `profile_abcd_real_metrics.json` · Sample size = 8 per dataset · 10 distractor documents · Seed = 20260219

> 📌 These numbers summarize one current release run. Hardware, provider, and model differences may change outcomes.

> 📌 How to read these metrics:
>
> - `HR@10`: did the correct result appear in the top 10?
> - `MRR`: how early did the correct result appear?
> - `NDCG@10`: how good was the overall ranking quality?
> - `p95`: how slow do the slower requests get?
>
> If you only look at one metric, start with `HR@10`.

| Profile | Dataset | HR@10 | MRR | NDCG@10 | p95 (ms) | Gate |
|---|---|---:|---:|---:|---:|---|
| A | SQuAD v2 | 0.000 | 0.000 | 0.000 | 1.78 | ✅ PASS |
| A | NFCorpus | 0.250 | 0.250 | 0.250 | 1.74 | ✅ PASS |
| B | SQuAD v2 | 0.625 | 0.302 | 0.383 | 4.92 | ✅ PASS |
| B | NFCorpus | 0.750 | 0.478 | 0.542 | 5.02 | ✅ PASS |
| **C** | **SQuAD v2** | **1.000** | **1.000** | **1.000** | 665.14 | ✅ PASS |
| C | NFCorpus | 0.750 | 0.567 | 0.611 | 454.42 | ✅ PASS |
| **D** | **SQuAD v2** | **1.000** | **1.000** | **1.000** | 2078.38 | ✅ PASS |
| D | NFCorpus | 0.750 | 0.650 | 0.673 | 2364.97 | ✅ PASS |

> 💡 In the current SQuAD v2 run, profiles C/D reach perfect recall through external Embedding (bge-m3) + Reranker (bge-reranker-v2-m3). The additional latency comes from model inference and network overhead.

### Retrieval Quality — A/B Large-Sample Gate

Source: `profile_ab_metrics.json` · Sample size = 100

| Profile | Dataset | HR@10 | MRR | NDCG@10 | p95 (ms) |
|---|---|---:|---:|---:|---:|
| A | MS MARCO | 0.333 | 0.333 | 0.333 | 2.1 |
| A | BEIR NFCorpus | 0.300 | 0.300 | 0.300 | 2.6 |
| A | SQuAD v2 | 0.150 | 0.150 | 0.150 | 3.0 |
| B | MS MARCO | 0.867 | 0.658 | 0.696 | 3.7 |
| B | BEIR NFCorpus | 1.000 | 0.828 | 0.850 | 4.7 |
| B | SQuAD v2 | 1.000 | 0.765 | 0.822 | 3.9 |

> ⚠️ The A/B/C/D numbers above are mainly here to help you understand the **profile differences** in the current benchmark set.
>
> If you want to see the **same-setup old-vs-current comparison** used in this release note, go straight to:
>
> - `docs/EVALUATION_EN.md` → `3.5 Old vs Current Version (Same-Metric Summary)`
> - `docs/changelog/release_summary_vs_old_project_2026-03-06_EN.md`

<p align="center">
  <img src="docs/images/benchmark_comparison.png" width="900" alt="Old vs Current benchmark comparison" />
</p>

> 📈 This chart shows one **old vs current** comparison snapshot under the same setup. It is not the old A/B/C/D profile baseline chart, and it should not be read as a blanket guarantee for every environment.

### Quality Gates Summary

| Gate | Metric | Result | Threshold | Status |
|---|---|---:|---:|---|
| Write Guard | Precision | 1.000 | ≥ 0.90 | ✅ PASS |
| Write Guard | Recall | 1.000 | ≥ 0.85 | ✅ PASS |
| Intent Classification | Accuracy | 1.000 | ≥ 0.80 | ✅ PASS |
| Gist Quality | ROUGE-L | 0.759 | ≥ 0.40 | ✅ PASS |
| Phase 6 Gate | Valid | true | — | ✅ PASS |

> **Write Guard**: Evaluated on 6 test cases (4 TP, 0 FP, 0 FN). Source: `write_guard_quality_metrics.json`
>
> **Intent Classification**: 6/6 correct classifications across temporal, causal, exploratory, and factual intents using `keyword_scoring_v2`. Source: `intent_accuracy_metrics.json`
>
> **Gist ROUGE-L**: Average across 5 test cases (range: 0.667 – 0.923). Source: `compact_context_gist_quality_metrics.json`
>
> In plain English:
>
> - **Write Guard** checks whether the system blocks or redirects writes correctly
> - **Intent Classification** checks whether the system understands what kind of query it is before retrieval
> - **ROUGE-L** checks whether the compressed gist still keeps the key meaning

### Benchmark Reproduction Notes

The current repository still keeps the benchmark helpers and test entries under
`backend/tests/benchmark/`, but treat them as deeper maintenance / re-check
material rather than the first step for new users.

These tables are kept as a **published summary** of project validation runs.

If you are using the user-facing repo, the practical re-check flow is:

```bash
bash scripts/pre_publish_check.sh
curl -fsS http://127.0.0.1:8000/health
```

If you are working in a full development workspace that still includes benchmark
artifacts and runners are handled there as internal validation material rather
than part of the public user package.

---

## 🖼️ Dashboard Screenshots

> 📌 These images are here to help you quickly understand the main dashboard areas.
>
> - They show the **typical post-entry dashboard state**
> - These screenshots show the common English-mode dashboard state; on a first visit without a stored choice, common Chinese browser locales now auto-map to `zh-CN`, and other cases fall back to English
> - The top bar now provides a unified auth/setup entry (`Set API key` / `Update API key` / `Clear key`; when runtime auth is injected, the page shows `Runtime key active` plus a `Setup` button)
> - If auth is not configured yet, the page shell still opens, but protected data requests show an auth hint, empty state, or `401` until credentials are available

<details>
<summary>🪄 First-Run Setup Assistant</summary>

<img src="docs/images/setup-assistant-en.png" width="900" alt="Memory Palace — First-run setup assistant (English mode)" />

Use the assistant to save the Dashboard key in the current browser session and, on a local non-Docker checkout, write the common `.env` fields without hand-editing the file. If the browser cannot persist that session-scoped key locally, the page now shows a save failure instead of a success message, so treat `.env` writing and browser auth storage as separate steps. Backend-side changes still require a restart.
</details>

<details>
<summary>📂 Memory — Tree Browser & Editor</summary>

<img src="docs/images/memory-palace-memory-page.png" width="900" alt="Memory Palace — Memory Browser Page (English mode)" />

Tree-structured memory browser with inline editor and Gist view. Navigate by domain → path hierarchy.
</details>

<details>
<summary>📋 Review — Diff & Rollback</summary>

<img src="docs/images/memory-palace-review-page.png" width="900" alt="Memory Palace — Review Page (English mode)" />

Side-by-side diff comparison of snapshots with one-click rollback and integrate actions. The current version also adds more explicit error handling and session-state behavior here. The visible Review queue is scoped to the current database target, so switching to another local `.env`, compose project, or SQLite file does not mix rollback sessions from a different database into the page.
</details>

<details>
<summary>🔧 Maintenance — Vitality Governance</summary>

<img src="docs/images/memory-palace-maintenance-page.png" width="900" alt="Memory Palace — Maintenance Page (English mode)" />

Monitor memory vitality scores, trigger cleanup tasks, and manage decay parameters. The current version also adds domain / path-prefix filters and a more explicit human-confirmation flow.
</details>

<details>
<summary>📊 Observability — Search & Task Monitoring</summary>

<img src="docs/images/memory-palace-observability-page.png" width="900" alt="Memory Palace — Observability Page (English mode)" />

Real-time search query monitoring, retrieval quality insights, and task queue status. The current version also adds `scope hint`, runtime snapshot details, and richer index-task visibility.
</details>

> 💡 For API docs, use the live `/docs` page from a running service. It stays more accurate than a static screenshot as routes continue to evolve.

---

## ⏱️ Memory Write & Review Workflow

<p align="center">
  <img src="docs/images/记忆写入与审查时序图.png" width="900" alt="Memory Write & Review Sequence Diagram" />
</p>

### Write Path

1. `create_memory` / `update_memory` enters the **Write Lane** queue
2. Pre-write **Write Guard** evaluation → core action: `ADD` / `UPDATE` / `NOOP` / `DELETE` (`BYPASS` is only used as a metadata-only flow marker)
3. **Snapshot** and version change record generation
4. Async **Index Worker** enqueue for index updates

### Retrieval Path

1. `preprocess_query` → `classify_intent` (factual / exploratory / temporal / causal; default `factual_high_precision` when no strong signal, `unknown/default` for conflicting or low-signal mixed queries)
2. Strategy template matching (e.g., `factual_high_precision`, `temporal_time_filtered`)
3. Execute `keyword` / `semantic` / `hybrid` retrieval
4. Return `results` + `degrade_reasons`

---

## 📚 Documentation

| Document | Description |
|---|---|
| [Getting Started](docs/GETTING_STARTED_EN.md) | Complete guide from zero to running |
| [Technical Overview](docs/TECHNICAL_OVERVIEW_EN.md) | Architecture design and module responsibilities |
| [Deployment Profiles](docs/DEPLOYMENT_PROFILES_EN.md) | A/B/C/D detailed configuration and tuning guide |
| [MCP Tools](docs/TOOLS_EN.md) | Full semantics and return formats for all 9 tools |
| [Evaluation](docs/EVALUATION_EN.md) | Retrieval quality, write gates, intent classification metrics |
| [Skills Guide](docs/skills/MEMORY_PALACE_SKILLS_EN.md) | Multi-client unified integration strategy |
| [Security & Privacy](docs/SECURITY_AND_PRIVACY_EN.md) | API Key authentication and security policies |
| [Troubleshooting](docs/TROUBLESHOOTING_EN.md) | Common issues and solutions |

---

## 🔐 Security & Privacy

- Only `.env.example` is committed — **real `.env` files are always gitignored**
- All API keys in documentation use placeholders only
- HTTP/SSE auth is **fail-closed** by default: protected endpoints return `401` when `MCP_API_KEY` is missing or invalid
- This gate applies only to HTTP/SSE interfaces; `stdio` mode is unaffected
- Docker one-click deployment forwards auth headers at the server-side proxy, so the browser does not receive the real `MCP_API_KEY`
- Local bypass requires explicit opt-in: `MCP_API_KEY_ALLOW_INSECURE_LOCAL=true` (loopback only)

Details: [SECURITY_AND_PRIVACY_EN.md](docs/SECURITY_AND_PRIVACY_EN.md)

---

## 🔀 Migration & Compatibility

For backward compatibility with legacy `nocturne_memory` deployments:

- Scripts still support the legacy `NOCTURNE_*` env prefix
- Docker scripts auto-detect and reuse legacy data volumes
- Backend auto-recovers from legacy SQLite filenames (`agent_memory.db`, `nocturne_memory.db`, `nocturne.db`) on startup via `_try_restore_legacy_sqlite_file()`

> The compatibility layer does not affect current Memory Palace branding or primary paths.

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=AGI-is-going-to-arrive/Memory-Palace&type=Date)](https://star-history.com/#AGI-is-going-to-arrive/Memory-Palace&Date)

---

## 📄 License

[MIT](LICENSE) — Copyright (c) 2026 agi

---

## 🙏 Acknowledgements

- The original inspiration came from the community discussion: <https://linux.do/t/topic/1616409>
- The earliest project reference came from `Dataojitori/nocturne_memory`: <https://github.com/Dataojitori/nocturne_memory>
- Memory Palace is a full rework on top of that initial idea, with a new public documentation, deployment, and verification path

---

<p align="center">
  <strong>Built with ❤️ for AI Agents that remember.</strong>
</p>

<p align="center">
  <sub>Memory Palace — because the best AI assistant never forgets.</sub>
</p>
