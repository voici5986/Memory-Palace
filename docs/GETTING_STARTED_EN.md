# Memory Palace Quick Start

This guide helps you set up the Memory Palace local development environment or Docker deployment in 5 minutes.

> **Memory Palace** is a long-term memory system designed for AI Agents. It provides 9 tools via the [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) protocol, enabling persistent memory capabilities for clients such as Claude Code, Codex, Gemini CLI, and OpenCode. If you are integrating an IDE host such as `Cursor / Windsurf / VSCode-host / Antigravity`, start with `docs/skills/IDE_HOSTS_EN.md`.
>
> **If what you are trying to fix right now is the CLI-side skill + MCP installation path, stop following this page** and go directly to `docs/skills/GETTING_STARTED_EN.md`.

---

## 1. Requirements

| Dependency | Minimum Version | Check Command |
|---|---|---|
| Python | `3.10+` | `python --version` |
| Node.js | `20.19+` (or `>=22.12`) | `node --version` |
| npm | `9+` | `npm --version` |
| Docker (Optional) | `20+` | `docker --version` |
| Docker Compose (Optional) | `2.0+` | `docker compose version` |

> **Tip**: macOS users are recommended to use [Homebrew](https://brew.sh) to install Python and Node.js. Windows users should download installers from official sites or use [Scoop](https://scoop.sh). If your machine exposes Python as `python3` instead of `python`, replace `python` with `python3` in the commands below.

---

## 2. Repository Structure at a Glance

```
memory-palace/
├── backend/              # FastAPI + SQLite backend
│   ├── main.py           # Application entry (FastAPI instance, /health endpoint)
│   ├── mcp_server.py     # Implementation of 9 MCP tools (FastMCP)
│   ├── runtime_state.py  # Write Lane, Index Worker, session cache
│   ├── run_sse.py        # MCP SSE transport layer (Starlette + API Key auth)
│   ├── mcp_wrapper.py    # MCP wrapper
│   ├── requirements.txt  # Python dependency list
│   ├── requirements-dev.txt # Backend test dependencies
│   ├── db/               # Database Schema, search engine
│   ├── api/              # HTTP routes
│   │   ├── browse.py     # Memory tree browsing (GET /browse/node)
│   │   ├── review.py     # Review interfaces (/review/*)
│   │   ├── maintenance.py# Maintenance interfaces (/maintenance/*)
│   │   └── setup.py      # First-run setup assistant APIs (/setup/*)
├── frontend/             # React + Vite + Tailwind Dashboard
│   ├── package.json      # Version 1.0.1
│   └── vite.config.js    # Dev server port 5173, proxies to backend 8000
├── deploy/               # Docker and Profile configurations
│   ├── docker/           # Dockerfile.backend / Dockerfile.frontend
│   └── profiles/         # macOS / Windows / Docker profile templates
├── scripts/              # Operation scripts
│   ├── apply_profile.sh  # Profile application script (macOS/Linux)
│   ├── apply_profile.ps1 # Profile application script (Windows)
│   ├── docker_one_click.sh   # Docker one-click deployment (macOS/Linux)
│   ├── docker_one_click.ps1  # Docker one-click deployment (Windows)
├── docs/                 # Project documentation
├── .env.example          # Configuration template (includes all available items)
├── docker-compose.yml    # Compose orchestration file
└── LICENSE               # Open source license
```

---

<p align="center">
  <img src="images/onboarding_flow.png" width="900" alt="Memory Palace Quick Start Flowchart" />
</p>

> 📌 This diagram is only to help you quickly remember the sequence.
>
> The actual commands in the text take precedence:
>
> - Backend defaults to `uvicorn` running at `127.0.0.1:8000`
> - Frontend dev server defaults to `5173`
> - Docker default entries are `http://127.0.0.1:3000` (Dashboard) and `http://127.0.0.1:3000/sse` (SSE)

## 3. Local Development (Recommended First Path)

### Step 1: Prepare Configuration Files

```bash
cp .env.example .env
```

> The file copied here is the **more conservative `.env.example` minimal template**. It is sufficient to complete the local startup, but **does not mean Profile B has been applied**.
>
> If you want to use the default values defined in the repository for Profile B (e.g., local hash Embedding), please prioritize using the Profile scripts below; if you continue to manually modify `.env.example`, that's fine too—just understand it as "supplementing configuration as needed from a minimal template."

> **Important**: After copying, please check `DATABASE_URL` in `.env` and change the path to your actual path. Absolute paths are highly recommended for shared environments or near-production scenarios. For example:
>
> ```
> DATABASE_URL=sqlite+aiosqlite:////absolute/path/to/memory_palace/demo.db
> ```
>
> The slash count is platform-specific: absolute paths on `macOS / Linux` are usually `sqlite+aiosqlite:////...`, while `Windows` drive-letter paths are usually `sqlite+aiosqlite:///C:/...`. If you edit `.env` manually, do not mix these two forms.
>
> Another very common misconfiguration: do not copy the Docker / GHCR value `sqlite+aiosqlite:////app/data/...`, or any other container-only sqlite path such as `/data/...`, into a local `.env`. `/app/...` and `/data/...` are container-internal paths, not the database file on your host machine; the repo-local `stdio` wrapper now refuses this configuration explicitly. For local `stdio`, use a host absolute path instead. If you actually want to reuse the Docker-side data and service, connect to the Docker-exposed `/sse` endpoint instead.

You can also use the Profile script to quickly generate an `.env` with default configurations:

```bash
# macOS / Linux —— Parameters: Platform Profile [Target File]
# Current script accepted template values are macos|linux|windows|docker; `linux` maps internally to the same local template as `macos`.
bash scripts/apply_profile.sh macos b

# Windows PowerShell
.\scripts\apply_profile.ps1 -Platform windows -Profile b
```

> `deploy/profiles/*/profile-*.env` files are input templates for the scripts, not the final `.env` files we recommend you copy directly. For the user path, keep using `apply_profile.sh/.ps1`; it is the safer path because it also fills paths automatically and deduplicates repeated keys.

> The `apply_profile` script copies `.env.example` to a generated env file and then appends the override configuration for the corresponding Profile. Local shell runs (`macos` / `linux`) and native Windows still default to `.env`; if you run the `docker` variant without an explicit target, it now defaults to `.env.docker`. On the shell path, `apply_profile.sh` also automatically rewrites the common local `DATABASE_URL` placeholder, including `/Users/...` and `/home/...`. On macOS / Linux, `apply_profile.sh` now also creates a `*.bak` backup before overwriting an existing target file.
>
> `apply_profile.sh/.ps1` currently deduplicates environment keys after generation; however, running it again in the target environment is still recommended for native Windows / native `pwsh`.
>
> If you only want to preview the generated output first, on macOS / Linux you can run `bash scripts/apply_profile.sh --dry-run ...`. That path prints the final env content without writing the target file.
>
> The PowerShell version now exposes the same preview/help path as well:
>
> ```powershell
> .\scripts\apply_profile.ps1 -DryRun -Platform windows -Profile b -Target .env.generated
> .\scripts\apply_profile.ps1 -Help
> ```
>
> Local `profile c/d` now also keeps `RUNTIME_AUTO_FLUSH_ENABLED=true` by default, so unless you override it yourself, the generated `.env` keeps the same auto-flush default as A/B.
>
> If you are running `apply_profile.ps1` from PowerShell on Linux / WSL, `-Platform linux` is now accepted as well; it maps to the same local template family as `macos`. On native Windows, keep using `-Platform windows`.
>
> In addition, `profile c/d` now fail-closed at the script stage when endpoint/key/model placeholders are still unresolved. If values such as `PORT`, `replace-with-your-key`, or `your-embedding-model-id` are still present, the script stops immediately instead of carrying an obviously broken config into later startup steps.
>
> `DATABASE_URL` now follows the same guard. The common local placeholder path is rewritten automatically for the current checkout; if the generated result still contains placeholder segments such as `<...>` or `__REPLACE_ME__`, the script/backend stop early instead of continuing with a broken sqlite path.
>
> Note: **The profile-b `.env` generated locally for macOS / Windows will not automatically fill in `MCP_API_KEY`**. If you are about to open the Dashboard, or directly call `/browse` / `/review` / `/maintenance`, `/sse`, or `/messages`, please supplement `MCP_API_KEY` yourself, or set `MCP_API_KEY_ALLOW_INSECURE_LOCAL=true` for local loopback debugging only. Only the `docker` platform profile script will automatically generate a local key if the key is empty.
>
> In addition, the backend itself now fail-closes when the **active** remote retrieval configuration still contains placeholder values. If you bypass `apply_profile.*`, copy a `profile c/d` template by hand, and leave values such as `host.docker.internal:PORT`, `replace-with-your-key`, `your-embedding-model-id`, or `your-reranker-model-id` in place, startup stops immediately instead of continuing with an obviously invalid embedding / reranker config.
>
> One easy mistake to avoid: do not copy the `DATABASE_URL` from `.env.docker`, or any container-only sqlite path such as `/app/data/...` or `/data/...`, into your local `.env`. Those paths only exist inside the container; local `stdio` MCP on the host will fail with them.

#### Key Configuration Items

The following are the most commonly used configuration items in `.env` (for more items, please see the comments in `.env.example`):

| Config Item | Description | Template Example Value |
|---|---|---|
| `DATABASE_URL` | SQLite database path (**Absolute path recommended**) | `sqlite+aiosqlite:////absolute/path/to/memory_palace/demo.db` |
| `SEARCH_DEFAULT_MODE` | Search mode: `keyword` / `semantic` / `hybrid` | `keyword` |
| `RETRIEVAL_EMBEDDING_BACKEND` | Embedding backend: `none` / `hash` / `router` / `api` / `openai` | `none` |
| `RETRIEVAL_EMBEDDING_MODEL` | Embedding model name | `your-embedding-model-id` |
| `RETRIEVAL_RERANKER_ENABLED` | Whether to enable Reranker | `false` |
| `RETRIEVAL_RERANKER_API_BASE` | Reranker API address | Empty |
| `RETRIEVAL_RERANKER_API_KEY` | Reranker API key | Empty |
| `RETRIEVAL_RERANKER_MODEL` | Reranker model name | `your-reranker-model-id` |
| `RETRIEVAL_REMOTE_TIMEOUT_SEC` | Timeout for remote embedding / reranker / LLM requests (seconds) | `8` |
| `INTENT_LLM_ENABLED` | Experimental intent LLM toggle | `false` |
| `RETRIEVAL_MMR_ENABLED` | Deduplication / diversity re-ranking under hybrid search | `false` |
| `RETRIEVAL_SQLITE_VEC_ENABLED` | sqlite-vec rollout toggle | `false` |
| `MCP_API_KEY` | Authentication key for HTTP/SSE interfaces | Empty (see Auth section below) |
| `MCP_API_KEY_ALLOW_INSECURE_LOCAL` | Allow access without Key during local debugging (only for loopback requests) | `false` |
| `CORS_ALLOW_ORIGINS` | List of allowed origins for cross-domain access (leave empty for local default) | Empty |
| `VALID_DOMAINS` | Allowed writable memory URI domains (`system://` is built-in read-only) | `core,writer,game,notes` |

> Profile B uses local hash Embedding by default and does not enable Reranker; it remains the **default starting profile**.
>
> If you have prepared model services, **it is highly recommended to upgrade to Profile C as soon as possible**: it requires you to fill in the Embedding / Reranker chain in `.env`; if you also want to enable LLM-assisted write guard / gist / intent routing, continue filling in `WRITE_GUARD_LLM_*`, `COMPACT_GIST_LLM_*`, and optional `INTENT_LLM_*`. See [DEPLOYMENT_PROFILES_EN.md](DEPLOYMENT_PROFILES_EN.md) for details.
>
> The table above shows template example values from `.env.example`; if certain retrieval environment variables are completely missing at runtime, the backend will use its own fallback values (e.g., `hash` / `hash-v1` / `64`).
>
> Configuration semantics: `RETRIEVAL_EMBEDDING_BACKEND` only affects Embedding. Reranker does not have a `RETRIEVAL_RERANKER_BACKEND` toggle; it prioritizes reading `RETRIEVAL_RERANKER_*`, falling back to `ROUTER_*` (and finally to `OPENAI_*` base/key) if missing.
>
> For repo-local `stdio` / `python-wrapper`, `RETRIEVAL_REMOTE_TIMEOUT_SEC` is now also reused from the current repository `.env`; if you leave it unset, the repo-local default remains `8` seconds.
>
> More advanced options (such as `INTENT_LLM_*`, `RETRIEVAL_MMR_*`, `RETRIEVAL_SQLITE_VEC_*`, `CORS_ALLOW_*`, runtime observability/sleep consolidation toggles) are documented in `.env.example` and default to conservative values, not affecting the minimal startup path.
>
> Recommended defaults (usually fine to copy):
> - `INTENT_LLM_ENABLED=false`: Use built-in keyword rules first to reduce external dependencies.
> - `RETRIEVAL_MMR_ENABLED=false`: Check raw hybrid results first, only enable if "first few results are too similar."
> - `RETRIEVAL_SQLITE_VEC_ENABLED=false`: Keep the legacy path for normal deployments.
> - `CORS_ALLOW_ORIGINS=`: Leave empty for local dev; specify domains only when opening to browser cross-domain access.
>
> The model names above are just placeholder examples, not hard project dependencies. Memory Palace is not bound to a specific provider or model family; please change them to actual available embedding / reranker / chat model IDs from your own OpenAI-compatible services.
>
> If you later use `profile c/d`, whether you stop at `apply_profile.sh/.ps1` or continue into `docker_one_click.sh/.ps1`, those placeholder model IDs / endpoints / keys are all treated as unresolved placeholders. The scripts fail-closed until you replace them with real values.
>
> If you are about to open the Dashboard locally, or directly use `curl` to call `/browse` / `/review` / `/maintenance`, it is suggested to add one of the following auth configurations to `.env`:
>
> - `MCP_API_KEY=change-this-local-key`
> - `MCP_API_KEY_ALLOW_INSECURE_LOCAL=true` (Only recommended for loopback debugging on your own machine)

### Step 2: Start Backend

```bash
cd backend
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
# .\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

> If you also plan to run backend tests afterwards, add:
>
> ```bash
> pip install -r requirements-dev.txt
> ```

Expected output:

```
Memory API starting...
SQLite database initialized.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

> The backend completes initialization via the `lifespan` context manager in `main.py`, including SQLite database creation and starting runtime states (Write Lane, Index Worker).
>
> The `uvicorn main:app --host 127.0.0.1 ...` command above is the recommended **local development** form.
>
> If you instead run `python main.py`, the current default is still loopback: `127.0.0.1:8000`. If you actually want LAN / remote direct access, bind it explicitly with `uvicorn main:app --host 0.0.0.0 --port 8000` (or your own listening address) and only do that after your `MCP_API_KEY`, firewall rules, reverse proxy, and equivalent network-side protections are already in place.

### Step 3: Start Frontend

```bash
cd frontend
npm install
npm run dev
```

> Frontend i18n dependencies are already included in `frontend/package.json` and `frontend/package-lock.json`. A normal `npm install` is sufficient; you don't need to install `i18next`, `react-i18next`, or `i18next-browser-languagedetector` separately.

Expected output:

```
VITE v7.x.x  ready in xxx ms
➜  Local:   http://127.0.0.1:5173/
```

Open your browser and visit `http://127.0.0.1:5173` to see the Memory Palace Dashboard.

If you wish to view the Dashboard buttons, fields, and typical operation flows page by page, please see:

- `docs/DASHBOARD_GUIDE_EN.md`

> If you see `Set API key` in the top right corner when starting manually, this is normal: the page is open, but protected interfaces like `/browse/*`, `/review/*`, and `/maintenance/*` are not yet authorized. Clicking this button now opens the **first-run setup assistant**, which can either save the Dashboard key in the current browser session or, when you are running against a non-Docker local checkout, write the common runtime fields into `.env`. The assistant also has its own language toggle in the upper right corner, so you do not need to close it first just to switch to Chinese. Section 5 will explain local validation.
>
> Small UI detail rechecked against the current code path: if the assistant shows interpolated labels that contain characters like `&` or `<...>`, they now render as normal text instead of showing HTML entities literally.

> If you configured `MCP_API_KEY`, click `Set API key` in the top right and enter the same key in the assistant. If you only want the Dashboard to authenticate first, prefer the browser-only save path.
> If you enabled `MCP_API_KEY_ALLOW_INSECURE_LOCAL=true`, direct requests from the local loopback address can access these protected data interfaces.

> If you choose **Save dashboard key only**, that key is stored in the current browser session (`sessionStorage`) until you clear it manually or that browser session ends. The assistant's `Profile C/D` presets now follow the documented `router + reranker` path; if your local router is not ready yet, switch the retrieval fields manually to direct API mode for debugging.

> The assistant does not pretend that Docker env / proxy changes are hot-reloaded. If you change embedding / reranker / write-guard / intent settings, you still need to restart the affected `backend` / `sse` services afterwards. For Docker, continue using the profile scripts and container restart path.

> The frontend restores the stored language first. If there is no stored choice yet, common Chinese browser locales (`zh`, `zh-TW`, `zh-HK`, and similar `zh-*`) are normalized to `zh-CN`; other first-visit cases fall back to English. If you want to switch manually, use the language button in the top right, and the browser will remember your choice.

> The frontend dev server proxies `/api` to `MEMORY_PALACE_API_PROXY_TARGET` (default: `http://127.0.0.1:8000`) via `vite.config.js`.
>
> If you also want to verify same-origin SSE from the **local Vite dev entry**, start `run_sse.py` separately first and additionally set:
>
> ```bash
> MEMORY_PALACE_SSE_PROXY_TARGET=http://127.0.0.1:8010
> ```
>
> With that in place, `/sse`, `/messages`, and `/sse/messages` are also proxied to the local SSE process, so you do not need to hand-wire CORS just for local debugging.
>
> If you are doing a **non-root-path deployment** (for example the frontend lives under `/memory-palace/` and the backend API is exposed as `/memory-palace/api`), the frontend build can also set `VITE_API_BASE_URL`. By default it still uses `/api`, which remains the better fit for local Vite proxying and the repository-shipped Docker path.

<p align="center">
  <img src="images/setup-assistant-en.png" width="900" alt="Memory Palace first-run setup assistant (English mode)" />
</p>

<p align="center">
  <img src="images/memory-palace-memory-page.png" width="900" alt="Memory Palace interface example (English mode)" />
</p>

---

## 4. Docker Deployment

### 4.1 Pull Prebuilt GHCR Images (Fastest for Users)

If your local build environment keeps failing, use the prebuilt GHCR images first. This path is for **starting the service quickly**, not for rebuilding images locally.

```bash
cd <project-root>
cp .env.example .env.docker
bash scripts/apply_profile.sh docker b .env.docker

docker compose -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.ghcr.yml up -d
```

```powershell
cd <project-root>
Copy-Item .env.example .env.docker
.\scripts\apply_profile.ps1 -Platform docker -Profile b -Target .env.docker

docker compose -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.ghcr.yml up -d
```

Default access addresses:

| Service | Address |
|---|---|
| Frontend | `http://localhost:3000` |
| Backend API | `http://localhost:18000` |
| SSE | `http://localhost:3000/sse` |

What this path does and does not do:

- It avoids **local image build**, but still assumes you have this repository checkout so you can use `docker-compose.ghcr.yml`, `.env.example`, and the profile scripts.
- It solves **Dashboard / API / SSE startup** only.
- It does **not** automatically configure local `skills / MCP / IDE host` entries on your machine.
- If you want the current repo's repo-local skill + MCP install path, keep this checkout and continue with `docs/skills/GETTING_STARTED_EN.md`.
- If you do not want the repo-local install path, any client that supports remote SSE MCP can still be configured manually to connect to `http://localhost:3000/sse` with the matching auth header / API key. For this GHCR path, `<YOUR_MCP_API_KEY>` normally means the `MCP_API_KEY` written into the `.env.docker` you just generated.
- Unlike `docker_one_click.sh/.ps1`, this GHCR compose path does **not** auto-adjust ports. If `3000` / `18000` are occupied, set `MEMORY_PALACE_FRONTEND_PORT` / `MEMORY_PALACE_BACKEND_PORT` explicitly before `docker compose up`.
- If the container still needs to reach a **model service running on your host machine**, do not write `127.0.0.1` as the host-side address from inside the container. For the container, `127.0.0.1` points back to the container itself, not your host. Prefer `host.docker.internal` (or your actual reachable host address). The compose files now add `host.docker.internal:host-gateway`, so this path also works on modern Linux Docker.
- Do **not** assume the repo-local stdio wrapper reuses container data automatically. `scripts/run_memory_palace_mcp_stdio.sh` needs a host-side local repository `.env` and the local `backend/.venv`; it does not reuse container data from `/app/data`.
- If you later switch back to a local `stdio` client, your local `.env` must contain a host-accessible absolute path. If `.env` is missing while `.env.docker` exists, or if `.env` / an explicit `DATABASE_URL` still points to `/app/...` or `/data/...`, the wrapper refuses to start and tells you to use a host path or Docker `/sse` instead.

Stop services:

```bash
docker compose -f docker-compose.ghcr.yml down --remove-orphans
```

### 4.2 Docker One-Click Deployment

```bash
# macOS / Linux
bash scripts/docker_one_click.sh --profile b

# Windows PowerShell
.\scripts\docker_one_click.ps1 -Profile b

# If you need to inject the runtime API address/key from the current process into the Docker env file for this run (e.g., profile c/d)
# The injection toggle must be explicitly enabled (default is off):
bash scripts/docker_one_click.sh --profile c --allow-runtime-env-injection
# or
.\scripts\docker_one_click.ps1 -Profile c -AllowRuntimeEnvInjection
```

> If you enable this kind of local joint debugging injection under `profile c/d`, the script will switch this run to an explicit API mode and additionally force `RETRIEVAL_EMBEDDING_BACKEND=api`. The current injection path also carries explicit `RETRIEVAL_EMBEDDING_*` (including `RETRIEVAL_EMBEDDING_DIM`), `RETRIEVAL_RERANKER_*`, and optional `INTENT_LLM_*` / `WRITE_GUARD_LLM_*` / `COMPACT_GIST_LLM_*` values. When `RETRIEVAL_EMBEDDING_API_*` / `RETRIEVAL_RERANKER_API_*` are not explicitly provided, it will prioritize reusing `ROUTER_API_BASE/ROUTER_API_KEY` from the current process as a fallback; if you also set `INTENT_LLM_*`, this chain will also be injected. This mode is more suitable for local troubleshooting and is not equivalent to verifying the final release `router` template.
>
> If you only want a fast smoke check first, hit the real `/embeddings` and `/rerank` endpoints with the same model and key you plan to use. That is usually quicker than starting from a full backend run.
>
> Note that `--runtime-env-mode` / `--runtime-env-file` are **not** arguments of `docker_one_click.sh/.ps1`. If you pass them directly to the one-click script, the command fails with `Unknown argument`. For public-repo `profile c/d` local debugging, keep using the explicit injection switches shown above. If you also need a stricter release-style verification, switch back to the actual `.env` / router configuration you plan to deploy and re-run that validation path separately.

> `docker_one_click.sh/.ps1` defaults to generating an independent temporary Docker env file for **each run**, passed to `docker compose` via `MEMORY_PALACE_DOCKER_ENV_FILE`; it only reuses a specific file if that environment variable is explicitly set, rather than sharing a fixed `.env.docker`.
>
> Concurrent deployments under the same checkout will be serialized by a deployment lock; if another one-click deployment is already executing, subsequent processes will exit immediately with a prompt to retry later.
>
> The local build path now also uses checkout-scoped stable image names. In practice, once this checkout has completed one successful build, `--no-build` can keep reusing those images even if you change `COMPOSE_PROJECT_NAME`; you only need `--build` again on the first run or after deleting the local images.
>
> If `MCP_API_KEY` in the Docker env file is empty, `apply_profile.*` will automatically generate a local key. The Docker frontend will automatically include this key in its proxy layer, so **when starting via the recommended one-click script path**, protected requests usually already work; however, the page may still keep showing `Set API key`, because the browser page itself does not know the proxy-held key. Treat that as expected unless protected data also starts failing with `401` or empty states. Even then, the first-run setup assistant stays in guidance mode for Docker instead of pretending it can persist container env changes.
>
> Currently, Docker Compose first waits for the `backend` `/health` check to pass, and the one-click script then adds one extra frontend-proxied `/sse` reachability check before treating the frontend as truly ready. In practice, when the container first shows `running`, the page may still take a few more seconds to become truly available, which is normal.
>
> The backend container-side check is no longer “HTTP 200 from `/health` is enough”. It also runs `deploy/docker/backend-healthcheck.py`, which requires the payload to report `status == "ok"`. If detailed `/health` is already degraded, Docker keeps the backend unhealthy; when the request fails, the JSON is invalid, or the status is not `ok`, the script now prints one short failure reason first, which makes container-side diagnosis less guessy.
>
> If your environment starts slowly, you can also tune that probe timeout through `MEMORY_PALACE_BACKEND_HEALTHCHECK_TIMEOUT_SEC`; the helper currently defaults to `5` seconds.
>
> Keep the WAL safety boundary in mind as well: the repository defaults only treat **Docker named volume + WAL** as a supported path. If you replace backend `/app/data` with a bind mount to NFS/CIFS/SMB or another network filesystem, explicitly switch back to `MEMORY_PALACE_DOCKER_WAL_ENABLED=false` and `MEMORY_PALACE_DOCKER_JOURNAL_MODE=delete`. `docker_one_click.sh/.ps1` now performs that preflight check before `docker compose up` and aborts on the risky combination; manual `docker compose up` / `docker compose -f docker-compose.ghcr.yml up` does not do that validation for you.
>
> The Docker frontend also serves `/index.html` with `Cache-Control: no-store, no-cache, must-revalidate` to reduce the chance that a browser keeps an old entry page after a frontend update. If you still see an obviously old page right after upgrading the image, first confirm the new container is actually running, then refresh the page once. Only continue checking cache behavior if you also put your own reverse proxy or corporate cache in front of it.
>
> Docker also persists two runtime data paths by default: the database volume is isolated per compose project as `<compose-project>_data` (container path `/app/data`), and the Review snapshots volume is isolated as `<compose-project>_snapshots` (container path `/app/snapshots`). If you intentionally want to reuse an old shared volume, set `MEMORY_PALACE_DATA_VOLUME` / `MEMORY_PALACE_SNAPSHOTS_VOLUME` explicitly. If you execute `docker compose down -v` or manually delete these volumes, both parts are cleared together.
>
> **C/D Local Joint Debugging Suggestions**:
>
> - If your local machine's `router` hasn't connected embedding / reranker / llm yet, you can first directly configure `RETRIEVAL_EMBEDDING_*`, `RETRIEVAL_RERANKER_*`, `WRITE_GUARD_LLM_*` / `COMPACT_GIST_LLM_*` separately.
> - This makes it easier to determine which specific chain is unreachable, avoiding misjudging "one model not configured correctly" as the entire system being down.
> - Whether you finally adopt the `router` solution or direct configuration for `RETRIEVAL_EMBEDDING_*` / `RETRIEVAL_RERANKER_*`, it is recommended to run the startup and health checks again according to the **final actual deployment configuration**.

> The script automatically performs the following steps:
>
> 1. Calls the Profile script to generate the Docker env file for this run (defaults to a temporary file; reuses the specified path if `MEMORY_PALACE_DOCKER_ENV_FILE` is set).
> 2. Defaults to not reading current process environment variables to override template strategy keys (avoiding implicit profile changes); injects API address/key/model fields and explicit retrieval parameters such as `RETRIEVAL_EMBEDDING_DIM` only when the injection toggle is explicitly enabled.
> 3. Detects port conflicts and automatically finds available ports.
> 4. Parses and injects Docker persistent volumes: by default the script isolates them per compose project (`<compose-project>_data` for the database and `<compose-project>_snapshots` for Review snapshots); it only reuses an old volume when `MEMORY_PALACE_DATA_VOLUME` / `MEMORY_PALACE_SNAPSHOTS_VOLUME` is explicitly set.
> 5. Fails fast before startup if backend `/app/data` has been changed to a bind mount on NFS/CIFS/SMB or another network filesystem while WAL would still be enabled.
> 6. Locks concurrent deployments for the same checkout to avoid multiple `docker_one_click` instances overwriting each other.
> 7. Builds and starts containers via `docker compose`.

Default access addresses:

| Service | Address |
|---|---|
| Frontend | `http://localhost:3000` |
| Backend API | `http://localhost:18000` |
| SSE | `http://localhost:3000/sse` |
| Health Check | `http://localhost:18000/health` |
| API Docs (Swagger) | `http://localhost:18000/docs` |

> **Port Mapping Explanation** (from `docker-compose.yml`):
>
> - The frontend container internally runs on port `8080`, mapped externally to `3000` (can be overridden by the `MEMORY_PALACE_FRONTEND_PORT` environment variable).
> - The backend container internally runs on port `8000`, mapped externally to `18000` (can be overridden by the `MEMORY_PALACE_BACKEND_PORT` environment variable).
> - Docker by default persists the database volume (`/app/data`) and review snapshot volume (`/app/snapshots`).

Stop services:

```bash
COMPOSE_PROJECT_NAME=<compose project printed in console> docker compose -f docker-compose.yml down --remove-orphans
```

> The `down --remove-orphans` command above will not delete data volumes; the database and review snapshots will only be cleared if you explicitly use `docker compose ... down -v` or manually delete the corresponding volumes.

> If you need to verify Windows paths, it is recommended to run startup and smoke tests directly in the target Windows environment.

### 4.3 Backup Current Database

Before performing batch tests, migration verification, or wide-range configuration switching, it is recommended to make a consistent SQLite backup:

```bash
# macOS / Linux
bash scripts/backup_memory.sh

# Specify env / output directory
bash scripts/backup_memory.sh --env-file .env --output-dir backups

# Keep only the latest 10 backups
bash scripts/backup_memory.sh --env-file .env --output-dir backups --keep 10
```

```powershell
# Windows PowerShell
.\scripts\backup_memory.ps1

# Keep only the latest 10 backups
.\scripts\backup_memory.ps1 -EnvFile .env -OutputDir backups -Keep 10
```

> Backup files are written to `backups/` by default. If you are preparing to share the repository or package it for delivery, you usually don't need to include them.
>
> Both backup scripts read `DATABASE_URL` from the selected env file, strip optional query / fragment suffixes such as `?mode=...` or `#...`, and then back up the resolved SQLite file. On native Windows, prefer `backup_memory.ps1`; on `Git Bash` / `WSL`, `backup_memory.sh` is fine. Both scripts now add `busy_timeout`, copy in small page batches, and remove a partial backup file if the run fails halfway, so a failed backup does not leave behind a misleading artifact. Backup filenames now use UTC timestamps so mixed host/container runs sort more consistently. They also keep the latest `20` backups by default; use `--keep <count>` / `-Keep <count>` to change that, or pass `0` to disable rotation.
>
> If you only want to see the usage first, run `bash scripts/backup_memory.sh --help` or `.\scripts\backup_memory.ps1 -?`. On native Windows, the PowerShell script now checks the repo `backend/.venv` first and then falls back to common launchers such as `python3` / `py`, so a normal local repo setup usually does not need a special PATH tweak before backup.

### 4.4 Files Typically Not Needed for Submission

The repository has already placed typical local artifacts into `<repo-root>/.gitignore`:

- Environment and secret files: `.env`, `.env.*` (keep `.env.example`)
- Runtime databases: `*.db`, `*.sqlite`, `*.sqlite3`
- Database lock files: `*.init.lock`, `*.migrate.lock`
- Local tool configurations: `.mcp.json`, `.mcp.json.bak`, `.claude/`, `.codex/`, `.cursor/`, `.opencode/`, `.gemini/`, `.agent/`, `.playwright-cli/`
- Local cache and temporary directories: `.tmp/`, `.pytest_cache/`, `backend/.pytest_cache/`
- Frontend local artifacts: `frontend/node_modules/`, `frontend/dist/`
- Logs and snapshots: `*.log`, `snapshots/`, `backups/`
- Temporary test drafts: `frontend/src/*.tmp.test.jsx`
- Internal maintenance documents: `docs/improvement/`, `backend/docs/benchmark_*.md`
- One-time comparison summaries: `docs/evaluation_old_vs_new_*.md`
- Local validation reports: `docs/skills/TRIGGER_SMOKE_REPORT.md`, `docs/skills/MCP_LIVE_E2E_REPORT.md`

If you are preparing to share the project, package it for delivery, or just want to perform an environment self-check, it is recommended to execute:

```bash
bash scripts/pre_publish_check.sh
```

It checks for common local sensitive artifacts, tool configs, local validation reports, personal paths, and `.env.example` placeholders, helping you quickly confirm if the repository is suitable for direct delivery. If it only finds these local files exist, it will usually give a `WARN` to remind you to confirm them yourself before sharing.

If you additionally run these validation scripts:

```bash
python scripts/evaluate_memory_palace_skill.py
cd backend && python ../scripts/evaluate_memory_palace_mcp_e2e.py
```

The scripts default to generating summaries in `<repo-root>/docs/skills/TRIGGER_SMOKE_REPORT.md` and `<repo-root>/docs/skills/MCP_LIVE_E2E_REPORT.md` respectively. These two results are mainly for local review and are not the primary instruction documents. `evaluate_memory_palace_skill.py` now returns a non-zero exit code whenever any check is `FAIL`; `SKIP` / `PARTIAL` / `MANUAL` do not fail the process by themselves, and the current default Gemini smoke model is `gemini-3-flash-preview`. If you only want to override that model locally for one run, set `MEMORY_PALACE_GEMINI_TEST_MODEL`; if you also need a separate fallback model, add `MEMORY_PALACE_GEMINI_FALLBACK_MODEL`. If `codex exec` does not emit structured output before the smoke timeout, the `codex` item is now reported as `PARTIAL` instead of stalling the whole run.
If you need isolated output during parallel review or CI, set `MEMORY_PALACE_SKILL_REPORT_PATH` / `MEMORY_PALACE_MCP_E2E_REPORT_PATH` first.
If you just cloned the GitHub repository, it is normal if you don't see these two files yet; they are local artifacts generated after running the scripts.

---

## 5. Initial Validation

> The checks here focus on "getting the system running"; if you need additional local Markdown validation summaries, run the validation scripts mentioned above.

### 5.1 Health Check

```bash
# Local Development
curl -fsS http://127.0.0.1:8000/health

# Docker Deployment
curl -fsS http://localhost:18000/health
```

Expected return (from the `/health` endpoint in `main.py`):

```json
{
  "status": "ok",
  "timestamp": "2026-02-19T08:00:00Z",
  "index": {
    "index_available": true,
    "degraded": false
  },
  "runtime": {
    "write_lanes": { ... },
    "index_worker": { ... }
  }
}
```

> This detailed payload with `index` / `runtime` is returned by default only for local loopback requests, or for requests carrying a valid `MCP_API_KEY`. Unauthenticated remote `/health` probes intentionally receive only a shallow payload such as `status` and `timestamp`.
>
> `status` as `"ok"` indicates the system is normal; if the index is unavailable or an error occurs, `status` will become `"degraded"`. For these **detailed health checks** on loopback or authenticated requests, the endpoint now also returns HTTP `503` whenever it is degraded, so Docker health checks and operators can treat it as not ready. Unauthenticated remote shallow health checks still stay on HTTP `200`.

### 5.2 Browsing Memory Tree

```bash
curl -fsS "http://127.0.0.1:8000/browse/node?domain=core&path=" \
  -H "X-MCP-API-Key: <YOUR_MCP_API_KEY>"
```

> This endpoint comes from `api/browse.py`'s `GET /browse/node` and is used to view the memory node tree under a specific domain. The `domain` parameter corresponds to the domains configured in `VALID_DOMAINS` in `.env`.
>
> - If you configured `MCP_API_KEY`, please include the `X-MCP-API-Key` as shown above.
> - If you enabled `MCP_API_KEY_ALLOW_INSECURE_LOCAL=true` and the request comes from the local loopback address (and has no forwarded headers), you can omit the authentication header.

### 5.3 Viewing API Docs

Visit `http://127.0.0.1:8000/docs` in your browser to open the Swagger documentation automatically generated by FastAPI, where you can view all HTTP endpoint parameters and return formats.

---

## 6. MCP Access

Memory Palace provides **9 tools** via the [MCP protocol](https://modelcontextprotocol.io/) (defined in `mcp_server.py`):

| Tool Name | Purpose |
|---|---|
| `read_memory` | Read memory (supports special URIs like `system://boot`, `system://index`) |
| `create_memory` | Create a new memory node (explicitly filling `title` is recommended) |
| `update_memory` | Update existing memory (priority use of diff patch) |
| `delete_memory` | Delete a memory node |
| `add_alias` | Add an alias for a memory node |
| `search_memory` | Search memory (keyword / semantic / hybrid modes) |
| `compact_context` | Compact context (cleanup old session logs) |
| `rebuild_index` | Rebuild search index |
| `index_status` | View index status |

### 6.1 stdio Mode (Recommended for Local Use)

```bash
cd backend
python mcp_server.py

# If you are starting in a new terminal or client configuration, this one is more stable
./.venv/bin/python mcp_server.py   # Windows PowerShell: .\.venv\Scripts\python.exe mcp_server.py
```

> In `stdio` mode, MCP tools communicate directly through the process's standard input/output, **bypassing the HTTP/SSE authentication layer**. `MCP_API_KEY` is not required.
>
> The `python mcp_server.py` here assumes you are still using the **`backend/.venv` created and populated with dependencies in Step 2**. If you switch to a new terminal or are configuring local MCP in a client, prioritize using the project's own `.venv` interpreter. Otherwise, errors like `ModuleNotFoundError: No module named 'sqlalchemy'` will occur before the MCP process truly starts.
>
> If you are wiring MCP in a client configuration, choose the repo-local wrapper by platform:
>
> - native Windows: `python backend/mcp_wrapper.py`
> - macOS / Linux / Git Bash / WSL: `bash scripts/run_memory_palace_mcp_stdio.sh`
>
> These repo-local wrappers keep the same boundary conditions: they depend on the local `backend/.venv`, reuse the current repository `.env` / `DATABASE_URL` first, and also keep using `RETRIEVAL_REMOTE_TIMEOUT_SEC` from that same `.env` when it is set; if you leave it unset, the repo-local default remains `8` seconds. They only fall back to the repo's default SQLite path when neither a local `.env` nor `.env.docker` exists. If the repository only has `.env.docker`, or if a local `.env` / explicit `DATABASE_URL` still points at a Docker-internal path such as `sqlite+aiosqlite:////app/data/memory_palace.db` or a `/data/...` variant, they refuse to start on purpose. In a Docker-only setup, prefer the exposed `/sse` endpoint instead.
>
> On the shell-wrapper path, `run_memory_palace_mcp_stdio.sh` also exports `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1` before it starts Python. In plain language: a non-UTF-8 locale is less likely to break local stdio traffic.

### 6.2 SSE Mode

```bash
cd backend
HOST=127.0.0.1 PORT=8010 python run_sse.py
```

```powershell
cd backend
$env:HOST = "127.0.0.1"
$env:PORT = "8010"
python run_sse.py
```

> `python run_sse.py` first tries loopback `127.0.0.1:8000`; if local `8000` is already occupied by the main backend, it automatically falls back to `127.0.0.1:8010`. You can still override both `HOST` and `PORT` explicitly. SSE mode remains protected by `MCP_API_KEY`.
>
> The same SSE process also provides a lightweight `/health` endpoint, mainly for standalone local debugging; the truly open streaming entry point for MCP clients remains `/sse`.
>
> The command above deliberately binds to `127.0.0.1`, which is more suitable for local machine debugging. If you truly need to allow access from other machines, change `HOST` to `0.0.0.0` (or your actual listening address). This will allow remote clients to connect to the listening address, but API Key, reverse proxy, firewall, and transport layer security will still need to be completed by you.
>
> If you use Docker one-click deployment or the GHCR compose path, SSE is no longer served by an independent `sse` container. It is mounted directly inside the `backend` process and then exposed at `http://127.0.0.1:3000/sse` through the frontend proxy. In practice, the Docker topology is now `backend + frontend`, while the public `/sse`, `/messages`, and `/sse/messages` endpoints stay the same.
>
> For containerized Profile C / D setups, the compose files also add `host.docker.internal:host-gateway`, so `host.docker.internal` is the preferred way to reach a model service running on your host machine, including modern Linux Docker.
>
> Treat that Docker frontend port as a trusted admin surface, not as public end-user auth. Anyone who can directly reach `3000` can use the Dashboard and its proxied protected routes, so add your own VPN, reverse-proxy auth, or network ACL before exposing it outside a trusted network.
>
> The `HOST=127.0.0.1 PORT=8010` example above is for **local loopback**. Only if you indeed want to open it to remote clients should you change it to `HOST=0.0.0.0` (or the target binding address) and complete the network-side security controls yourself.
>
> If you connect to `/sse` once with `curl` or a script, then disconnect and separately send the same `session_id` to `/messages`, seeing a `404` / `410` is normal: it indicates the previous SSE session has closed. The correct normal chain should be "keep the `/sse` connection alive first, and then have the client continue sending requests to `/messages`."

### 6.2.1 Multi-client concurrency (optional, but recommended)

If multiple CLI / IDE hosts will point to the **same SQLite file**, add this block to `.env`:

```env
RUNTIME_WRITE_WAL_ENABLED=true
RUNTIME_WRITE_JOURNAL_MODE=wal
RUNTIME_WRITE_WAL_SYNCHRONOUS=normal
RUNTIME_WRITE_BUSY_TIMEOUT_MS=5000
```

In plain language:

- each stdio MCP client is usually a separate Python process
- different processes do not share the same in-process write lock
- WAL plus a larger `busy_timeout` reduces `database is locked` failures when several clients write at the same time

One more note about the current default path:

- if you use the repository-shipped Docker / GHCR compose path, compose already forces the journal mode to `wal`
- the `.env` block above is mainly for **repo-local stdio / manually started multi-process local paths**

### 6.3 Client Configuration Examples

**stdio Mode**

Native Windows (preferred there):

```json
{
  "mcpServers": {
    "memory-palace": {
      "command": "python",
      "args": ["/ABS/PATH/TO/REPO/backend/mcp_wrapper.py"]
    }
  }
}
```

macOS / Linux / Git Bash / WSL:

```json
{
  "mcpServers": {
    "memory-palace": {
      "command": "bash",
      "args": ["/ABS/PATH/TO/REPO/scripts/run_memory_palace_mcp_stdio.sh"]
    }
  }
}
```

> If you haven't created `backend/.venv` yet, go back to **Step 2** to complete the virtual environment and dependency installation.
>
> In a native Windows environment, prefer `python + backend/mcp_wrapper.py` directly. Only keep `bash + run_memory_palace_mcp_stdio.sh` when you already have Git Bash / WSL available and want to stay on the shell-wrapper path.
>
> If a Windows-style host still ends up launching `backend/mcp_wrapper.py` from `Git Bash / MSYS / Cygwin`, the wrapper now also prefers `.venv/Scripts/python.exe` first. This is only a fallback guard; it does not change the recommended path above.

**SSE Mode**:

```json
{
  "mcpServers": {
    "memory-palace": {
      "url": "http://127.0.0.1:8010/sse"
    }
  }
}
```

> ⚠️ Replace `127.0.0.1:8010` here with the actual host and port you used when starting `run_sse.py`.
>
> ⚠️ SSE is still protected by `MCP_API_KEY`. Most clients also need to configure request headers or a Bearer Token; please refer to the client's own MCP documentation for specific field names.
>
> ⚠️ `HOST=0.0.0.0` only means "allow remote connection to this listening address," not "allow unauthenticated access."

### 6.3.1 What is currently safe to document

If your goal is to connect a client manually to Docker's exposed `/sse`, the current public guidance should be split into two groups:

| Client | Current public stance | Recommended path |
|---|---|---|
| `Claude Code` | Official CLI already exposes a remote SSE option | Safe to document directly below |
| `Gemini CLI` | Official CLI already exposes a remote SSE option | Safe to document directly below |
| `Codex CLI` | Current official evidence is remote `--url` for streamable HTTP | For this repository today, prefer the repo-local stdio path |
| `OpenCode` | Current official evidence is the generic `remote + url` structure | For this repository today, prefer the repo-local path unless you are comfortable mapping the generic remote config yourself |

In other words:

- if you want to connect a client manually to `http://localhost:3000/sse`
- the **publicly supported direct path today is Claude Code and Gemini CLI first**
- for `Codex` / `OpenCode`, this repository should not yet describe `/sse` as a fully validated copy-paste path

For the Docker / GHCR paths in Section 4, read `<YOUR_MCP_API_KEY>` from the `MCP_API_KEY` value in the `.env.docker` file you just generated.

### 6.3.2 Claude Code manual `/sse` connection

```bash
claude mcp add \
  --transport sse \
  --scope project \
  --header "X-MCP-API-Key: <YOUR_MCP_API_KEY>" \
  memory-palace \
  http://127.0.0.1:3000/sse
```

Check:

```bash
claude mcp list
```

Notes:

- Claude Code officially supports `stdio`, `sse`, and `http`
- if Memory Palace later exposes a clearer HTTP / streamable HTTP MCP entry, prefer `http`
- for the current public repository, the remote entry users can connect to directly is `/sse`
- treat `/sse` as the canonical public URL; `/sse/` is now only a compatibility spelling and is forwarded to the same backend SSE path
- for the GHCR / Docker path above, `<YOUR_MCP_API_KEY>` normally comes from `.env.docker`, not from a repo-local stdio wrapper

### 6.3.3 Gemini CLI manual `/sse` connection

```bash
gemini mcp add \
  --transport sse \
  --scope project \
  --header "X-MCP-API-Key: <YOUR_MCP_API_KEY>" \
  memory-palace \
  http://127.0.0.1:3000/sse
```

Check:

```bash
gemini mcp list
```

If you prefer editing `settings.json` directly, the minimal public skeleton we can safely confirm is:

```json
{
  "mcpServers": {
    "memory-palace": {
      "url": "http://127.0.0.1:3000/sse",
      "headers": {
        "X-MCP-API-Key": "<YOUR_MCP_API_KEY>"
      }
    }
  }
}
```

For the GHCR / Docker path above, `<YOUR_MCP_API_KEY>` normally comes from the `MCP_API_KEY` in `.env.docker`.

### 6.3.4 Why there is no direct `/sse` copy-paste block for `Codex / OpenCode` here

This does **not** mean they can never support remote MCP. It means the current public evidence is still narrower than what would be needed for this repository to claim that `/sse` is already a fully validated copy-paste path:

- `Codex CLI` currently documents `codex mcp add <name> --url <URL>` for remote MCP / streamable HTTP
- `OpenCode` currently documents the generic `type = remote` / `url` structure
- but the public remote endpoint exposed and validated by this repository today is `/sse`

So, to avoid misleading users:

- `Codex / OpenCode` should still prefer the repo-local installation path today
- once we complete a dedicated validation path for `Memory Palace /sse`, that client-specific remote example can be promoted into public copy-paste docs

---

## 7. HTTP/SSE Interface Authentication

Some HTTP interfaces of Memory Palace are protected by `MCP_API_KEY`, adopting a **fail-closed** strategy (defaults to `401` if Key is not configured).

### Protected Interfaces

| Route Prefix | Description | Auth Method |
|---|---|---|
| `/maintenance/*` | Maintenance interfaces (orphan node cleanup, etc.) | `require_maintenance_api_key` |
| `/review/*` | Review interfaces (content audit process) | `require_maintenance_api_key` |
| `/browse/*` (GET/POST/PUT/DELETE) | Memory tree read/write operations | `require_maintenance_api_key` |
| `/sse` and `/messages` in `run_sse.py` | MCP SSE transport channel and message entry | `apply_mcp_api_key_middleware` |

### Authentication Methods

The backend supports two types of Headers for passing the API Key (defined in `api/maintenance.py` and `run_sse.py`):

```bash
# Method 1: Custom Header
curl -fsS http://127.0.0.1:8000/maintenance/orphans \
  -H "X-MCP-API-Key: <YOUR_MCP_API_KEY>"

# Method 2: Bearer Token
curl -fsS http://127.0.0.1:8000/maintenance/orphans \
  -H "Authorization: Bearer <YOUR_MCP_API_KEY>"
```

### Frontend Auth Configuration

If the frontend also needs to access protected interfaces, runtime configuration can be injected in **local debugging or your own controlled private deployment environment** (frontend `src/lib/api.js` will read `window.__MEMORY_PALACE_RUNTIME__`):

```html
<script>
  window.__MEMORY_PALACE_RUNTIME__ = {
    maintenanceApiKey: "<YOUR_MCP_API_KEY>",
    maintenanceApiKeyMode: "header"
  };
</script>
```

> Do not write the real `MCP_API_KEY` into any public pages, shared static resources, or HTML delivered to end users. This global object can be read directly in the browser.

> This configuration is mainly for the scenario of **manually starting front and back ends locally**.
>
> Docker one-click deployment by default does not require writing the key into the page: the frontend container will automatically forward the same `MCP_API_KEY` to `/api/*`, `/sse`, and `/messages` at the proxy layer.

### Skipping Auth for Local Debugging

If you don't want to configure an API Key during local development, set the following in `.env`:

```env
MCP_API_KEY_ALLOW_INSECURE_LOCAL=true
```

> This option only applies to **direct requests** from `127.0.0.1` / `::1` / `localhost`; if the request has forwarded headers, it will still be rejected. It only affects HTTP/SSE interfaces and **does not affect** stdio mode (stdio does not go through the auth layer).

---

## 8. Common FAQ

| Issue | Cause and Solution |
|---|---|
| `ModuleNotFoundError` when starting backend | Most common cause is not using `backend/.venv` or not installing dependencies in that environment. Execute `source .venv/bin/activate && pip install -r requirements.txt` first; if it's local stdio MCP, prioritize using `./.venv/bin/python mcp_server.py` (Windows: `.\.venv\Scripts\python.exe mcp_server.py`). |
| `DATABASE_URL` error | Absolute paths are recommended, and it must have the `sqlite+aiosqlite:///` prefix. Example: `sqlite+aiosqlite:////absolute/path/to/memory_palace.db`. |
| Local stdio MCP in a client fails with `startup failed`, `initialize response`, or a similar startup interruption | Check whether `.env` or an explicit `DATABASE_URL` points to `/app/...` or `/data/...`. That is a Docker container path; `scripts/run_memory_palace_mcp_stdio.sh` now refuses to start with it on purpose. Use a host-accessible absolute path instead, or keep using Docker `/sse`. |
| Frontend accessing API returns `502` or `Network Error` | Confirm the backend has started and is running on port `8000`. Check if the proxy target in `vite.config.js` matches the backend port. |
| Protected interface returns `401` | Local manual startup: configure `MCP_API_KEY` or set `MCP_API_KEY_ALLOW_INSECURE_LOCAL=true`; Docker: confirm if using the Docker env file generated by `apply_profile.*` / `docker_one_click.*`. |
| SSE `/messages` returns `429` or `413` | `429` means one SSE session is posting too many messages in a short window; check for duplicate retries or retry loops first. `413` means one request body exceeds `SSE_MESSAGE_MAX_BODY_BYTES`, so reduce the payload size or raise the backend limit intentionally. |
| Docker startup port conflict | `docker_one_click.sh` automatically finds idle ports by default. You can also specify manually via `--frontend-port` / `--backend-port`. |

For more troubleshooting, please refer to [TROUBLESHOOTING_EN.md](TROUBLESHOOTING_EN.md).

---

## 9. Further Reading

| Document | Content |
|---|---|
| [DEPLOYMENT_PROFILES_EN.md](DEPLOYMENT_PROFILES_EN.md) | Detailed parameter explanation and selection guide for deployment profiles (A/B/C/D). |
| [TOOLS_EN.md](TOOLS_EN.md) | Complete semantics, parameters, and return formats for the 9 MCP tools. |
| [TECHNICAL_OVERVIEW_EN.md](TECHNICAL_OVERVIEW_EN.md) | System architecture, data flow, and technical details. |
| [TROUBLESHOOTING_EN.md](TROUBLESHOOTING_EN.md) | Common issue troubleshooting and diagnosis. |
| [SECURITY_AND_PRIVACY_EN.md](SECURITY_AND_PRIVACY_EN.md) | Security model and privacy design. |
