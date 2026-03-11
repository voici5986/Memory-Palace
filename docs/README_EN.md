# Memory Palace Documentation Center

> **Memory Palace** is a long-term memory system designed for AI coding assistants. Through MCP (Model Context Protocol), it provides a unified path for memory read/write, retrieval, review, and maintenance for Codex / Claude Code / Gemini CLI / OpenCode; for IDE hosts such as `Cursor / Windsurf / VSCode-host / Antigravity`, it is recommended to start with `docs/skills/IDE_HOSTS_EN.md`.
>
> License: MIT
>
> This section prioritizes the instructions that **users will actually need**.
>
> If you need additional verification of skill smoke tests or the real MCP call chain, you can run `python scripts/evaluate_memory_palace_skill.py` or `cd backend && python ../scripts/evaluate_memory_palace_mcp_e2e.py`. They will generate local summaries under `docs/skills/`, but those reports are not the primary entry documents.
>
> The frontend currently defaults to English; the language button in the upper-right corner lets you switch between English and Chinese with one click, and the browser will remember your choice.

![System Architecture Diagram](images/系统架构图.png)

---

## 📖 Getting Started

| Document | Description |
|---|---|
| [GETTING_STARTED_EN.md](GETTING_STARTED_EN.md) | Get local development, GHCR image pull, and Docker running in 5 minutes, with example MCP client configurations |
| [DASHBOARD_GUIDE_EN.md](DASHBOARD_GUIDE_EN.md) | Explains every Dashboard button, field, and typical operation flow page by page |
| [skills/GETTING_STARTED_EN.md](skills/GETTING_STARTED_EN.md) | Connect the CLI-client skill + MCP path to the current repository for the first time |
| [TROUBLESHOOTING_EN.md](TROUBLESHOOTING_EN.md) | Troubleshooting for common issues such as startup failures, port conflicts, authentication failures, and search degradation |
| [SECURITY_AND_PRIVACY_EN.md](SECURITY_AND_PRIVACY_EN.md) | API Key secure configuration, privacy protection, and pre-sharing self-checks |

## 🔧 Core Documents

| Document | Description |
|---|---|
| [TECHNICAL_OVERVIEW_EN.md](TECHNICAL_OVERVIEW_EN.md) | Overview of the implementation structure and tech stack for the backend, frontend, MCP, and Docker |
| [TOOLS_EN.md](TOOLS_EN.md) | Inputs, outputs, return conventions, and degradation semantics of the 9 MCP tools |
| [DEPLOYMENT_PROFILES_EN.md](DEPLOYMENT_PROFILES_EN.md) | Configuration templates for the four A/B/C/D tiers, parameter tuning, and deployment methods |
| [GHCR_ACCEPTANCE_CHECKLIST_EN.md](GHCR_ACCEPTANCE_CHECKLIST_EN.md) | Minimal post-pull user acceptance checklist for GHCR images |
| [skills/SKILLS_QUICKSTART_EN.md](skills/SKILLS_QUICKSTART_EN.md) | Understand in one page how the CLI-client skill path is triggered, how MCP is configured, and how acceptance is verified |
| [changelog/dashboard_i18n_2026-03-09_EN.md](changelog/dashboard_i18n_2026-03-09_EN.md) | Summary of the dashboard's default English setting, Chinese/English switching, screenshots, and verification |
| [changelog/ghcr_release_2026-03-11_EN.md](changelog/ghcr_release_2026-03-11_EN.md) | GHCR prebuilt image release notes and scope boundaries |

## 🧩 Skills and Clients

| Document | Description |
|---|---|
| [skills/MEMORY_PALACE_SKILLS_EN.md](skills/MEMORY_PALACE_SKILLS_EN.md) | Canonical `memory-palace` skill design, installation, and multi-CLI orchestration strategy |
| [skills/CLI_COMPATIBILITY_GUIDE_EN.md](skills/CLI_COMPATIBILITY_GUIDE_EN.md) | Recommended installation paths, verification methods, and known boundaries for each CLI |
| [skills/IDE_HOSTS_EN.md](skills/IDE_HOSTS_EN.md) | How IDE hosts such as Cursor / Windsurf / VSCode-host / Antigravity should connect to this repository |

> If you only want to get the service running first, start with the **GHCR prebuilt image** path in `GETTING_STARTED_EN.md`.
>
> If you also want to wire `Claude / Codex / Gemini / OpenCode / IDE hosts` into this repository, continue with the docs under `docs/skills/`. Docker starts the service side; it does not automatically rewrite the local skill / MCP configuration on your machine.

## 📊 Evaluation and Quality

| Document | Description |
|---|---|
| [EVALUATION_EN.md](EVALUATION_EN.md) | Public benchmark methodology, summary of key A/B/C/D metrics, and reproduction commands |
