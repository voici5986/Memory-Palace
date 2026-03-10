# Memory Palace Skills Docs

This directory describes the skills / MCP orchestration setup for Memory Palace.

If this is your first time looking here, it is recommended to read in this order:

1. **Get it running first**
   - `GETTING_STARTED_EN.md`
2. **Quickly understand how to connect it in the current repository**
   - `SKILLS_QUICKSTART_EN.md`
3. **Then read the full design**
   - `MEMORY_PALACE_SKILLS_EN.md`
4. **If you are integrating an IDE host**
   - `IDE_HOSTS_EN.md`

---

## What these files are each for

- `GETTING_STARTED_EN.md`
  - For people connecting it for the first time
  - Mainly answers “what to do first, and how to check whether it is connected correctly”
- `SKILLS_QUICKSTART_EN.md`
  - For people who want to quickly understand the relationship between skill + MCP
  - Mainly answers “which clients can be used in what way right now, and where the boundaries still are”
- `MEMORY_PALACE_SKILLS_EN.md`
  - For people who want to see the full design
  - Mainly explains the canonical bundle, variants, and workflow boundaries
- `CLI_COMPATIBILITY_GUIDE_EN.md`
  - For multi-CLI integration scenarios
  - Mainly focuses on the differences among Claude / Gemini / Codex / OpenCode
- `IDE_HOSTS_EN.md`
  - For IDE-like hosts such as Cursor / Windsurf / VSCode-host / Antigravity
  - Focuses on the `AGENTS.md + MCP snippet` projection path instead of hidden skill mirrors

---

## Local validation reports

- `TRIGGER_SMOKE_REPORT.md`
  - Generated after running `python scripts/evaluate_memory_palace_skill.py`
- `MCP_LIVE_E2E_REPORT.md`
  - Generated after running `cd backend && python ../scripts/evaluate_memory_palace_mcp_e2e.py`

They are mainly used to help you re-check the connection results in the current environment, and they are not the primary entry documents.
If you do not temporarily see these two files in a freshly cloned GitHub repository, that is normal; run the commands above first and then check again.
If you plan to forward them to someone else, read through the contents yourself first; this kind of local report may include paths on your machine or traces of client configuration.

---

## Where is the canonical bundle

The real canonical bundle is here:

- `docs/skills/memory-palace/`

What is inside:

- `SKILL.md`
- `references/`
- `variants/`
- `agents/openai.yaml`

A one-sentence way to understand it:

> The public documents are responsible for telling users how to use it, while the canonical bundle is responsible for defining what this skill actually is.

One more repository-level note:

> `Memory-Palace/AGENTS.md` is now shipped as a repo-local rule entry as well, so clients such as Antigravity that support `AGENTS.md` can read the repository constraints directly. Older setups can still fall back to the legacy `GEMINI.md` convention.

One more unified repository stance:

> IDE hosts such as `Cursor / Windsurf / VSCode-host / Antigravity` should no longer treat hidden skill mirrors as the default integration path. They should consume the repository through `AGENTS.md + python scripts/render_ide_host_config.py ...`, which projects the same skills + MCP capability surface into IDE hosts.
