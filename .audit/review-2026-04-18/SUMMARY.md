# Comprehensive Code Review & Test Report

**Date**: 2026-04-18
**Scope**: Plan `docs/superpowers/plans/2026-04-17-cli-ide-memory-speed-and-reflection-upgrade.md` + 整个项目
**Reviewers**: codex (backend), gemini (frontend), 5 claude agent teams (plan/profile/mcp/docker/qa), 1 playwright UI e2e
**Mode**: READ-ONLY, no source changes
**Overall Verdict**: `FIXED-AND-REVALIDATED` (原始 2 个 P1 + 7 个 P2 已在当前工作树完成修复或收敛)

---

## Executive Summary

当前工作树已完成对应修复并重新验证：backend 全量 `930 passed / 20 skipped`，backend 非 benchmark `868 passed / 15 skipped`，frontend `154 passed`，build + typecheck OK。i18n 双语 100% 对齐（535 key each），持久化正常（key = `memory-palace.locale`）。所有本地密钥（`sk-local-*`, `10.88.1.144`, `127.0.0.1:8317/8318`）在 tracked 文件中**零命中**。

## Codex Independent Recheck (Current Worktree)

本节是对**当前脏工作树**的独立复核，不是对 `HEAD` 或原始计划文档自报状态的复述。结论基于当前工作树代码、fresh pytest/vitest/build/typecheck、最小复现脚本，以及一次真实浏览器烟测。

### Fresh verification

- 后端全量：`backend/.venv/bin/pytest backend/tests -q` → `930 passed, 20 skipped`
- 后端非 benchmark：`backend/.venv/bin/pytest backend/tests --ignore=backend/tests/benchmark -q` → `868 passed, 15 skipped`
- 前端：`cd frontend && npm test -- --run` → `154 passed`
- 前端构建：`cd frontend && npm run build` → `pass`
- 前端类型检查：`cd frontend && npm run typecheck` → `pass`
- 浏览器烟测：以当前 `.env`（`RETRIEVAL_EMBEDDING_BACKEND=hash`、`RETRIEVAL_RERANKER_ENABLED=false`）启动 repo-local backend/frontend；因 `8000` 被 Docker 占用，backend 改绑 `127.0.0.1:8009`，frontend 仍在 `5173`。UI 可用，`/docs` 默认 `404`；Setup Assistant 现已显式提供 `Profile A`，且 `Embedding 后端` 默认值是 `none`；语言切到中文后 `localStorage['memory-palace.locale']='zh-CN'`，刷新保持。

### Fix status

| Item | Current status | Notes |
|---|---|---|
| `P1-1` | **Resolved** | Reflection execute 现在创建 review snapshot，并把 rollback handle 指向 review 路径；maintenance learn rollback 也委托给 review snapshot。 |
| `P1-2` | **Resolved** | recent-read cache token 现在覆盖 direct-child fingerprint；父节点读不会再因 child create/delete/rollback 留下 900 秒陈旧文本。 |
| `P2-1` | **Resolved** | `scope_hint='fast'/'deep'` 现在先被 interaction tier 消费，不再落成 `path_prefix`。 |
| `P2-2` | **Resolved** | `/docs` 与 `/openapi.json` 默认关闭。 |
| `P2-3` | **Resolved** | Windows live MCP e2e 缺 `.venv` 时现在 fail-closed。 |
| `P2-4` | **Resolved** | 用户面文档已统一到当前真实口径：backend 非 benchmark `868/15`、frontend `154`。 |
| `P2-5` | **Not a bug** | 当前脚本/文档/测试对 `vscode` 与 `python-wrapper` 自洽；这里只剩别名未实现。 |
| `P2-6` | **Resolved** | Setup Assistant 现已显式提供 Profile A，且默认态回到文档定义的 `keyword + none`。 |
| `P2-7` | **Not a bug** | benchmark 测试文件当前存在且可运行。 |

### Historical repros

- `P1-1`：修复前 `/maintenance/learn/reflection` 返回的是 maintenance rollback handle，而不是 review rollback handle。
- `P1-2`：修复前最小 stub 复现结果为 `FIRST_HAS_CHILD2 False / SECOND_HAS_CHILD2 False / TTL_SECONDS 900.0`。
- `P2-1`：修复前最小复现返回 `{"interaction_tier":"fast","scope_strategy_applied":"path_prefix","scope_effective":{"path_prefix":"deep"}}`。
- `P2-2`：修复前 `TestClient(main.app)` 直接得到 `/docs 200`、`/openapi.json 200`。

---

## Critical (P1) — 必须修复后发布

### P1-1. Reflection workflow rollback 未复用 review/snapshot 语义

- **Task**: 5
- **Evidence**:
  - `backend/mcp_server.py:1615,1721` — execute 确实走 write lane，但返回的 rollback handle 指向 `/maintenance/import/jobs/{id}/rollback`（learn job 语义）
  - `backend/api/review.py:1126` — `rollback_resource` 的 "newer snapshot conflict" 保护**不会**覆盖 reflection 写入
  - `backend/tests/test_reflection_workflow_api.py:88` — 测试只断言了 prepared/executed，未断言 rollback 为 review 语义
  - plan Step 5 明确要求：`rollback_payload = await rollback_resource(review_id=..., resource_type="memory", ...)`
- **Impact**: 用户从 UI 回滚 reflection 执行时，走的不是 review/snapshot 统一回滚链路，绕过 newer-snapshot 冲突保护，可能造成双重回滚或数据不一致。
- **Recommended Fix（不写代码，只描述）**: 让 `run_reflection_workflow_service(mode="execute")` 在返回前持有真实 review snapshot handle；reflect rollback 必须经 `review.rollback_resource`；补 API 测试断言 review 语义。

### P1-2. Known-URI fast path 缓存未覆盖子节点 topology 变化

- **Task**: 4
- **Evidence**:
  - `backend/mcp_server.py:3269, 3387, 3962` — 缓存 key 只含父节点自身字段
  - `backend/runtime_state.py:743` — `SessionRecentReadCache` 默认 TTL 900s
  - codex 已用临时 SQLite 复现：读 `core://parent` → 创建 `core://parent/child2` → 立即再读，**FIRST_HAS_CHILD2 False / SECOND_HAS_CHILD2 False**（即第二次读仍看不到新 child）
  - `backend/tests/test_interaction_tier_fast_path.py:193` — 测试未覆盖父-子 topology 变化
- **Impact**: child create / delete / rollback 后，同 session 的 read_memory 父节点读取在 15 分钟内仍返回旧文本，严重违背 "fast path 不绕过 alias/rollback 一致性" 的 corner case 约束。
- **Recommended Fix**: 缓存 token 纳入 child topology version；或对"存在子节点的父 URI"禁用 recent-read 缓存；或在 create/delete/rollback 路径上主动失效相关祖先 URI 缓存。

---

## Warning (P2) — 建议修复

### P2-1. MCP `scope_hint=fast|deep` 兼容路径未落地

- **Task**: 1
- **Evidence**: `backend/mcp_server.py:2719, 5064`。codex 复现：`scope_hint="deep"` → 被当 `path_prefix="deep"`，最终输出 `{"scope_strategy_applied":"path_prefix"}`。
- **Fix**: 工具入口识别 `scope_hint` 中的 `fast|deep` 关键字映射到 `interaction_tier`；或直接 422 拒绝。

### P2-2. `/docs` 和 `/openapi.json` 默认公开，枚举 37 个管理接口

- **Task**: 8（security）
- **Evidence**: `backend/main.py:131, 155`。TestClient 不带 key：`/docs 200 / /openapi.json 200 / HAS_REVIEW_ROLLBACK True`，枚举含 rollback, browse, maintenance.import 等管理接口。
- **Fix**: 非 debug/非 loopback 环境默认关闭 docs/openapi，或套 MCP_API_KEY 鉴权。

### P2-3. Windows live MCP e2e 允许 fallback 到 sys.executable

- **Task**: 7
- **Evidence**: `scripts/evaluate_memory_palace_mcp_e2e.py:68` 与 `backend/mcp_wrapper.py:168` 不对齐 — 生产 wrapper 缺 `.venv` fail-closed；harness 却退回 `sys.executable`。
- **Fix**: live e2e Windows 分支应与生产 wrapper 同口径 fail-closed。

### P2-4. Task 8 文档 current truth 漂移

- **Evidence**: 修复前文档真值曾漂到 `862/153`，且部分页面仍保留旧 `857/149` 与 "not rerun" 说法。
- **Fix**: 当前工作树已统一到本轮真实结果：backend 非 benchmark `868/15`、frontend `154`。

### P2-5. `render_ide_host_config.py` host 命名与文档不符

- **Evidence**: `scripts/render_ide_host_config.py:10,11` — host 枚举为 `vscode` 而非文档期望的 `vscode-host`；launcher 只支持 `auto|bash|python-wrapper`，无 `shell-wrapper` 别名。
- **Fix**: 文档对齐或添加别名。

### P2-6. Setup Assistant UI 缺 Profile A 说明

- **Evidence**: `frontend/src/components/SetupAssistantModal.jsx:687,989` preset 按钮硬编码 `['b','c','d']`；Profile A = 表单初始态（direct/hash）。后端 `deploy/profiles/*/profile-a.env` 存在。
- **Fix**: 非 bug，但 UI 需明确标注 "A = 默认 direct/hash，无需 preset 按钮"（或在表单顶部加 "当前: Profile A" 的视觉提示）。

### P2-7. Task 6 benchmark 文件核实

- **Evidence**: Plan 要求 `backend/tests/benchmark/test_prompt_safety_contract_metrics.py`。qa agent 直接 pytest 跑了 13 pass；plan-landing agent 报 missing。可能命名偏差或路径移动。
- **Fix**: 核实该文件存在性，必要时补建或更新计划。

---

## Info — 次要建议

### Backend
- **main.py:14**: 顶层 `from shared_utils import` 绝对导入。从仓库根用 `python -m uvicorn backend.main:app` 会 `ModuleNotFoundError`，需 `PYTHONPATH=backend` 或改相对导入。
- **mcp_wrapper.py:205**: URL-encoded `%2Fapp%2Fdata%2Fdemo.db` 可能绕过 Docker-internal 路径拒绝（建议 `urllib.parse.unquote` 后再校验）。
- **mcp_server.py**: 缺 runtime stdout guard；误用 `print` 可能污染 JSON-RPC 协议（建议入口 `sys.stdout = sys.stderr` 或 CI lint）。
- **sqlite_client.py:2399**: `intent_llm_request_failed` 分支缺直接回归。
- **sqlite_client.py:5713**: `write_guard_llm` 非法 method 归一化缺直接回归。

### Frontend
- **MaintenancePage.jsx:149-166 / ObservabilityPage.jsx:304-320**: Axios 请求未用 AbortController/AbortSignal，组件卸载后 ghost 连接仍在。
- **MemoryBrowser.jsx:304-306**: `searchValue.trim().toLowerCase()` 在 filter 内循环调用，大树打字卡顿。
- **MaintenancePage.jsx:264-270**: 批量删除顺序 `await`，应 `Promise.allSettled` 或 bulk endpoint。
- **ObservabilityPage.jsx:371-413**: `runSearch` 无 disposed 检查。
- **tsconfig.typecheck.json:5**: `"strict": false`，弱化 `.d.ts` 类型约束。
- **GlassCard.jsx:20**: 硬编码 `rgba(179,133,79,0.15)` hover shadow，违背 `var(--palace-accent)` 设计 token。
- **App.jsx:328-330**: `document.title` useEffect 与 `i18n.js:114` 的 `languageChanged` 监听重复。
- **MemoryBrowser.jsx:650-652**: Delete 按钮缺 `aria-busy={deleting}`。
- **vite.config.js:8**: 硬编码代理 `http://127.0.0.1:8000`；端口占用时需手动设 `MEMORY_PALACE_API_PROXY_TARGET`。

### Docker
- **docker-compose.yml:21 / docker-compose.ghcr.yml:17-18**: backend 默认 `18000:8000` 对外暴露。若部署在公网且 MCP_API_KEY 未配置，某些非 `/health` 路径可能无鉴权。
- **Dockerfile.backend:15**: pip install 未固定 hash，供应链弱校验。
- **frontend-entrypoint.sh:8**: `FRONTEND_CSP_CONNECT_SRC` 默认 `'self'`；跨源部署需 .env.docker 显式设置。
- **compose healthcheck start_period: 10s** 对首次冷启 embedding 加载偏短，但 retries=10 × interval=10s 缓冲 ~100s，接受。

---

## 计划落地矩阵（综合 codex + agent A）

| Task | Status | 核心证据 | 关键缺口 |
|---|---|---|---|
| 1 | partial | mcp_server.py:2679 `_resolve_interaction_tier`；test_interaction_tier_fast_path.py | `scope_hint=fast\|deep` 兼容路径未实现（P2-1） |
| 2 | done | sqlite_client.py:580-602 intent_llm env；intent_llm_attempted 字段传播；test_week3_intent_query.py | 缺直接回归测试 |
| 3 | done | sqlite_client.py:5384 `_should_attempt_compact_gist_llm`；5476 `compact_gist_llm_skipped_short_summary`；多方验证 | 无 |
| 4 | partial | runtime_state.py:733 `SessionRecentReadCache`；test_interaction_tier_fast_path.py | **缓存未考虑子节点 topology（P1-2）** |
| 5 | partial | mcp_server.py run_reflection_workflow_service；import_learn_tracker 事件完整 | **rollback 绕过 review/snapshot 语义（P1-1）** |
| 6 | done/partial | test_reflection_lane_prompt_safety.py、test_reflection_lane_metrics.py | test_prompt_safety_contract_metrics.py 存在性需核实（P2-7） |
| 7 | done | install_skill.py 支持 --targets/--with-mcp/--check；mcp_wrapper.py:114 `is_docker_internal_database_url` | Windows live e2e 过宽松（P2-3） |
| 8 | partial | docs/EVALUATION.md Profile B 默认/C/D 深度；CLI_COMPATIBILITY_GUIDE.md 和 IDE_HOSTS.md 含 AGENTS.md 路径 | 文档 truth 漂移（P2-4）；/docs 公开（P2-2） |

---

## 全量测试结果

| 阶段 | 命令 | Pass | Fail | Skip | 耗时 |
|---|---|---|---|---|---|
| 后端全量 pytest | `backend/.venv/bin/pytest backend/tests -q` | **930** | 0 | 20 | 41.9s |
| 计划关键子集 (11 文件) | 精选回归 | **182** | 0 | 0 | 4.5s |
| 前端 vitest | `npm test -- --run` | **154** | 0 | 0 | 5.79s |
| 前端 build | `npm run build` | 1845 modules | - | - | 1.54s |
| 前端 typecheck | `npx tsc -p tsconfig.typecheck.json --noEmit` | 0 errors | - | - | - |
| codex 定向补跑 | 计划关键 + benchmark + install/wrapper | 319 pass, 8 skip | 0 | - | ~12s |

---

## 真机浏览器 UI e2e（Playwright）

- backend 端口 8000 被 Docker irdmi 占用，改用 8009（需 `PYTHONPATH=backend`）
- frontend dev 5173 起；代理 override `MEMORY_PALACE_API_PROXY_TARGET=http://127.0.0.1:8009`
- **i18n 切换 EN↔ZH** pass（zh 标题="记忆大厅"）
- **i18n 持久化** pass（localStorage `memory-palace.locale`，刷新保持）
- **Setup Modal** 首次自动弹出 / Profile A/B/C/D 可点 / 默认 retrieval baseline = `keyword + none` / 关闭正常
- **MaintenancePage** 不发起 SSE/EventSource，仅 401 REST 请求（无重连风暴；与设计一致，SSE 是 MCP 通道不是 dashboard 实时面）
- **/memory & /observability** 路由可达

---

## False Positive（排除）

- codex P1-3 "tracked 文件含 `:8080`" — 命中全部是 frontend 容器内部 healthcheck `127.0.0.1:8080`（docker-compose 合法引用）。用户实际关注的 `10.88.1.144:8080` reranker 端点经 Grep 交叉验证 **零命中**。
- gemini "SSE 完全缺失是 Critical" — 设计如此：SSE 是后端 MCP 通道（`backend/run_sse.py`），dashboard 使用 REST 轮询；应该降级为 Info 或从结果中剔除。
- gemini "Setup Assistant Profile A 缺失是 Critical" — 实际是 Profile A = 表单初始态（direct/hash），B/C/D = preset 按钮。降级 P2-6（仅 UI 说明不清晰）。

---

## Positive Confirmations

- interaction_tier、intent rule-first gating、compact gist gating、sqlite LIKE escape、snapshot scope isolation、Docker-internal sqlite URL rejection — 核心边界未见新回归
- reflection prepared/executed/rolled_back 已接入 `import_learn_tracker` 与 observability summary
- 跨平台 wrapper（macOS/Linux/Windows/MSYS/Cygwin/WSL）与 CRLF 跨 chunk 归一化扎实
- i18n zh-CN / en 各 535 key，**100% 对齐**
- Docker compose `config --quiet` 两套均 0 输出（合法）；GHCR workflow owner lowercase 正确
- `.env.example` 与 Profile B 差异明显（`SEARCH_DEFAULT_MODE`, `RETRIEVAL_EMBEDDING_BACKEND` 等）
- Setup API 不把 `.env.example` 当 profile applicator
- 本地敏感信息未泄漏到 tracked 文件

---

## 建议修复优先级

1. **P1-1 Reflection rollback 语义**（release blocker）
2. **P1-2 Known-URI cache 子树失效**（release blocker，已 PoC）
3. **P2-2 `/docs` 默认公开**（security 面）
4. **P2-1 `scope_hint` 兼容**（plan Task 1 契约）
5. **P2-4 Task 8 文档 truth 对齐**（release hygiene）
6. **P2-3 Windows e2e fail-closed**、**P2-5 render_ide_host_config 命名**、**P2-6 Setup A UI 标注**（次要）
7. Info 级：前端 AbortController / Memory Browser 性能 / main.py 导入 / vite proxy / strict typecheck 等可批量处理

---

## 附件

- codex 后端深度审查原文：本报告上游引用，SESSION_ID 019d9f71-70ec-7f50-a94a-a8e974b3ddf5
- gemini 前端深度审查原文：SESSION_ID 2d52c6f4-ed51-465a-ab53-db137a33d082
- Playwright e2e 截图与日志：`.audit/e2e/REPORT.md` + 7 张截图
