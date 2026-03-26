# Memory Palace v3.7.1 Release Notes (2026-03-26)

This note records only what was **actually changed and re-verified** in the
current repository. It does not turn host-specific caveats into blanket
guarantees.

---

## 1. One-Sentence Conclusion

`v3.7.1` is a tightening and operator-safety release: path deletion is more
atomic, rollback metadata restore is less lossy, Windows script boundaries are
safer, and the repo-local skill evaluator now behaves more like an environment
check than a false repo failure.

---

## 2. What Actually Changed

- `delete_memory` now keeps the current-path read, delete snapshot capture, and
  path removal inside one SQLite write transaction. In plain language: another
  local process sharing the same SQLite file is less likely to swap the path
  occupant between "what was deleted" and "what was actually removed".
- `rollback_to_memory(..., restore_path_metadata=True)` now restores metadata
  only for the selected path. Alias-specific `priority` / `disclosure` values
  are no longer overwritten by the primary path's snapshot metadata.
- Provider-chain embedding cache reuse is tighter now. In fail-open remote
  chains, later requests can reuse cached provider results after an earlier
  remote failure instead of always re-hitting every fallback provider.
- Review session listing now skips invalid legacy session directory names
  instead of letting those names break session listing.
- `add_alias` now enforces the same public `priority` contract as
  `create_memory` / `update_memory`, so bool/float-style values are rejected
  at the MCP boundary too.
- `apply_profile.sh` now normalizes Windows absolute target paths passed from
  PowerShell / WSL / Git Bash on a native Windows checkout, including the
  common separator-mangled form, instead of dropping a broken filename into the
  repository root.
- `docker_one_click.ps1` now preserves UTF-8 without BOM when it rewrites the
  generated Docker env file. In plain language: native Windows PowerShell no
  longer risks feeding Docker Compose a UTF-16 env file through that path.
- `evaluate_memory_palace_skill.py` now parses normal dotenv-style
  `DATABASE_URL` values more correctly, including quoted values, `export
  DATABASE_URL=...`, and trailing comments. The same script now treats
  user-scope binding drift and Gemini login/auth prompts as environment
  `PARTIAL`s, and keeps `gemini_live` as an explicit opt-in path.

---

## 3. What Was Re-verified For This Release

- Backend test suite: `797 passed, 20 skipped`
- Frontend test suite: `119 passed`
- Frontend production build: passed
- Live stdio MCP e2e: passed
- Repo-local skill sync check: passed
- Repo-local skill evaluator:
  - exit code rechecked as success on the current machine
  - environment-sensitive items such as user-scope drift, Gemini login, or
    missing host runtimes remain `PARTIAL` / `MANUAL` instead of turning the
    whole repo check into a false failure
- Native macOS local validation:
  - repo-local backend + standalone SSE + Vite path rechecked
  - Memory / Review / Maintenance / Observability pages rechecked in a real browser
  - English/Chinese toggle and persistence rechecked
  - repo-local browse create flow, Review integration flow, and Observability
    diagnostic search rechecked
- Native Windows local smoke:
  - follow-up real-host validation confirmed on the released tag
  - host-side startup and the main functional path were rechecked
- Docker validation:
  - Profile B one-click path rechecked
  - Profile C / D runtime-injection retrieval paths rechecked against real
    embedding / reranker / LLM services
  - Dashboard root, backend health, authenticated browse, and `/sse` were
    reachable on the verified paths

---

## 4. What This Release Still Does Not Claim

- `Gemini CLI`, `Cursor`, `agent`, or `Antigravity` items can still be
  `PARTIAL` / `MANUAL` depending on local login state, installed host runtimes,
  or target-machine availability.
- This release note does not claim that every A/B/C/D startup combination was
  re-run from scratch in every environment. The concrete rechecks listed above
  are the only ones claimed.
- Third-party provider availability still depends on the target environment,
  network reachability, and the configured embedding / reranker / LLM services.

---

## 5. Practical User-Facing Summary

If you are a normal user, the main effects of `v3.7.1` are simple:

- deleting a path is less racy on a shared local SQLite file
- rolling back one path no longer wipes alias-specific metadata
- Windows shell / PowerShell deployment helpers are less brittle
- repo-local skill validation is less likely to fail for machine-local auth or
  config drift that is not a repository bug

If you are writing a release summary for others, keep the wording conservative:

> `v3.7.1` tightens local delete-path atomicity, preserves alias-specific
> rollback metadata, hardens Windows operator script boundaries, re-verifies
> the main backend/frontend paths on real macOS and Windows hosts, and keeps
> explicit caveats for host-specific skill environments and third-party
> provider availability.
