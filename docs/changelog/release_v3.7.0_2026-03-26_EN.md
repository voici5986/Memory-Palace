# Memory Palace v3.7.0 Release Notes (2026-03-26)

This note records only what was **actually changed and re-verified** in the
current repository. It does not turn host-specific caveats into blanket
guarantees.

---

## 1. One-Sentence Conclusion

`v3.7.0` is a tightening release: stricter fail-closed input validation,
clearer Dashboard auth behavior under configured API base URLs, and a repaired
repo-local skill bundle sync path.

---

## 2. What Actually Changed

- `session_id` validation is now truly fail-closed for leading/trailing
  whitespace and control-style characters. The same rule is reused by the
  Review API instead of drifting from the snapshot layer.
- The public `priority` contract is now consistent across MCP and SQLite. The
  MCP tool layer no longer coerces `True`, `False`, or `1.9` into integers.
- The Dashboard now keeps attaching the saved browser auth key when protected
  requests are resolved through the configured `VITE_API_BASE_URL`, including
  non-root-path and cross-origin API deployments. It still does **not** send
  that key to unrelated third-party absolute URLs.
- Repo-local skill mirrors are back in sync with the canonical
  `memory-palace` bundle, so `python scripts/sync_memory_palace_skill.py --check`
  returns `PASS` again.

---

## 3. What Was Re-verified For This Release

- Backend test suite: `785 passed, 18 skipped`
- Frontend test suite: `114 passed`
- Frontend production build: passed
- Live stdio MCP e2e: passed
- Repo-local skill sync check: passed
- macOS local smoke:
  - isolated backend + SSE + Vite path verified
  - Dashboard `Memory / Review / Maintenance / Observability` pages loaded
  - language toggle and browser persistence rechecked
- Linux Docker smoke:
  - `docker_one_click.sh --profile b` rechecked
  - Dashboard root page reachable
  - backend health reachable
  - `/sse` reachable as `text/event-stream`
- D-style retrieval chain smoke:
  - verified against real OpenAI-compatible embedding / reranker / intent-LLM
    services
  - observability search returned `degraded=false`
  - `intent_llm_applied=true` on the verified path

---

## 4. What This Release Still Does Not Claim

- Native Windows host end-to-end verification is still **not** claimed here.
  Windows should still be rechecked in the target environment.
- Host-specific skill smoke items such as `Codex`, `OpenCode`, `Gemini live`,
  `Cursor`, or `agent` may still be `PARTIAL` depending on local login state,
  installed runtimes, or tool startup conditions. Those are no longer canonical
  bundle drift issues, but they are still environment-sensitive.
- This release note does not claim that every A/B/C/D startup combination was
  re-run from scratch in every environment. The concrete rechecks listed above
  are the only ones claimed.

---

## 5. Practical User-Facing Summary

If you are a normal user, the main effects of `v3.7.0` are simple:

- obviously malformed `session_id` inputs are rejected earlier and more
  consistently
- malformed `priority` values no longer slip through the MCP tool layer
- Dashboard auth behaves more predictably when the API lives under a custom
  base URL
- the repo-local skill sync path is cleaner again

If you are validating a release, keep the wording conservative:

> `v3.7.0` re-verifies the main backend/frontend paths, repairs strict
> validation around `session_id` and `priority`, restores repo-local skill sync
> consistency, and keeps explicit caveats for native Windows and host-specific
> skill smoke environments.

