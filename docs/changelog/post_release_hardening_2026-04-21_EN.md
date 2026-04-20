# Memory Palace Post-Release Hardening Follow-up (2026-04-21)

This note records only what was **actually changed and actually re-verified**
in this session. It does not turn target-environment caveats into blanket
guarantees.

---

## 1. One-Sentence Conclusion

This round is a post-release hardening follow-up: the public MCP contract is
tighter, `add_alias` no longer leaves a half-success state behind, retrieval
now treats unsafe FTS input as a per-request safe fallback, and snapshot
recovery is stronger when a manifest is missing or damaged.

---

## 2. What Actually Changed

- The public MCP boundary now rejects URIs containing control chars, invisible
  format chars, or surrogates instead of letting them continue into the write
  chain.
- `search_memory.query` is now capped at `8000` characters at the MCP entry
  point; `create_memory.content` and
  `update_memory.old_string/new_string/append` are now capped at `100000`
  characters. Overlong payloads are rejected before DB work begins.
- If `add_alias` writes the alias path first but snapshot capture fails
  afterwards, the current implementation compensates by rolling back that alias
  path instead of leaving a “tool errored, alias still landed” half-success
  state behind.
- Keyword retrieval now checks whether a query is safe for FTS first. Reserved
  tokens such as `AND / OR / NOT / NEAR`, or wildcard-heavy inputs, no longer
  get to silently steer match semantics; the current implementation falls back
  safely for that request.
- Snapshot recovery now covers not only “damaged manifest” but also “manifest
  missing while resource files still exist,” as long as the original database
  scope can still be preserved.
- The `read_memory` recent-read fast path now consults a lighter recent-state
  check before deciding whether the second full read can be skipped, reducing
  repeated DB work on hot paths.
- The Maintenance observability search request now uses the same query length
  cap as the MCP search path, so the public HTTP surface and MCP surface no
  longer drift on that contract.

---

## 3. What Was Actually Re-verified

- Full backend suite: `1111 passed, 22 skipped`
- Full frontend suite: `194 passed`
- Frontend `typecheck`: passed
- Frontend `build`: passed
- Repo-local live MCP e2e: passed (`docs/skills/MCP_LIVE_E2E_REPORT.md` is all
  `PASS`)
- Repo-local macOS `Profile B` real-browser smoke: passed
- Repo-local skill smoke:
  - `structure`, `description_contract`, `mirrors`, `sync_check`,
    `mcp_bindings`, `claude`, and `opencode` are `PASS`
  - `codex`, `gemini`, `cursor`, `agent`, and `antigravity` remain `PARTIAL`
  - `gemini_live` remains `SKIP`
- Small real A/B/C/D rerun:
  - dataset: `BEIR NFCorpus`
  - parameters: `sample_size=5`, `extra_distractors=20`,
    `candidate_multiplier=8`
  - result: `Profile D` Phase 6 Gate stayed `PASS`

---

## 4. What This Follow-up Still Does Not Claim

- This round did **not** recalculate the public benchmark tables end to end;
  the evaluation page keeps the existing public baseline tables and only adds
  the smaller real A/B/C/D rerun note from this session.
- This round also does **not** turn Docker one-click `Profile C/D`, native
  Windows, or native Linux host-runtime paths into “freshly revalidated
  everywhere” claims; those paths still keep explicit target-environment
  boundaries.
- Host-sensitive items such as `codex`, `gemini`, `cursor`, `agent`, and
  `antigravity` still depend on local login state, CLI output shape, and host
  availability, so they continue to be described conservatively as
  `PARTIAL` / `SKIP` where appropriate.

---

## 5. Practical User-Facing Summary

If you only care about what became more reliable after this follow-up, the
simple version is:

- public MCP tools now reject obviously invalid URIs and overlong inputs earlier
- `add_alias` no longer leaves a “failed but already written” alias behind
- FTS control words and wildcard-heavy user text no longer quietly change
  retrieval semantics
- Review snapshots are more likely to recover safely when the manifest file is
  missing

If you need a conservative one-line summary for others, use something like:

> This follow-up tightens the public MCP input contract, closes the
> half-success window in `add_alias`, turns unsafe FTS queries into per-request
> safe fallback, and re-verifies backend, frontend, repo-local MCP, public
> skill smoke, and a small real A/B/C/D run; target-environment caveats remain
> explicit.
