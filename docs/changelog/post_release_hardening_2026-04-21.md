# Memory Palace 修复后收口说明（2026-04-21）

这份说明只记录**这次 session 里已经真实修改、已经真实复验**的内容，不把目标环境差异写成统一保证。

---

## 1. 一句话结论

这轮属于发布后的收口加固：公开 MCP 契约更严格，`add_alias` 不再留下半成功状态，检索对不安全 FTS 查询改成单次安全回退，snapshot 对缺失/损坏 manifest 的恢复也更稳。

---

## 2. 这次实际改了什么

- MCP 入口层现在会直接拒绝带控制字符、不可见格式字符或 surrogate 的 URI，不再把这类输入继续放进底层写链路。
- `search_memory.query` 现在在 MCP 入口层限制为 `8000` 字符；`create_memory.content` 与 `update_memory.old_string/new_string/append` 现在限制为 `100000` 字符。超长 payload 会在真正进 DB 前直接拒绝。
- `add_alias` 如果已经写入 alias path，但后续 snapshot 补记失败，当前实现会把这条 alias path 一起补偿回滚，避免出现“工具报错但 alias 已经半成功落库”的状态。
- keyword 检索现在会先判断 query 是否适合走 FTS。像 `AND / OR / NOT / NEAR` 这类保留词，或 wildcard 很重的输入，不会再直接改变匹配语义；当前实现会按这次请求回退到安全路径。
- snapshot 恢复现在不只覆盖“manifest 损坏”，也覆盖“manifest 缺失但 resources 还在”的情况；前提仍然是能保住原始数据库作用域。
- `read_memory` 的 recent-read fast path 现在会先查一层更轻量的最近状态，再决定要不要跳过第二次完整读取，减少热路径上的重复 DB 命中。
- Maintenance 的 observability search 请求现在也同步加上了 query 长度上限，避免公开 HTTP 面和 MCP 面在这条约束上继续漂移。

---

## 3. 这次实际复验了什么

- 后端全量：`1111 passed, 22 skipped`
- 前端全量：`194 passed`
- 前端 `typecheck`：通过
- 前端 `build`：通过
- repo-local live MCP e2e：通过（`docs/skills/MCP_LIVE_E2E_REPORT.md` 全 `PASS`）
- repo-local macOS `Profile B` 真实浏览器 smoke：通过
- repo-local skill smoke：
  - `structure`、`description_contract`、`mirrors`、`sync_check`、`mcp_bindings`、`claude`、`opencode` 为 `PASS`
  - `codex`、`gemini`、`cursor`、`agent`、`antigravity` 为 `PARTIAL`
  - `gemini_live` 为 `SKIP`
- 小样本 real A/B/C/D 复核：
  - 数据集：`BEIR NFCorpus`
  - 参数：`sample_size=5`、`extra_distractors=20`、`candidate_multiplier=8`
  - 结果：`Profile D` 的 Phase 6 Gate 继续 `PASS`

---

## 4. 这次没有写成“已全面重新验证”的内容

- 这轮没有把公开 benchmark 大表整体重算一遍；评测页保留原来的公开基线表，只额外补记这次 session 的小样本 real A/B/C/D 复核。
- 这轮也没有把 Docker one-click `Profile C/D`、native Windows、native Linux 宿主 runtime 写成“重新全量覆盖验证”；这些路径仍然保留目标环境复核边界。
- `codex`、`gemini`、`cursor`、`agent`、`antigravity` 这组宿主相关项仍然受本机登录状态、CLI 输出形态和宿主环境是否完整影响，所以继续按 `PARTIAL` / `SKIP` 口径保守表述。

---

## 5. 对用户最直接的影响

如果你只关心这轮收口之后“到底更稳了什么”，可以简单理解成：

- 公开 MCP 工具现在更早拒绝明显不合法的 URI 和超长输入
- `add_alias` 不会再留下“报错了但 alias 已经写进去”的半成功状态
- 普通文本里的 FTS 保留词和 wildcard 不再悄悄改掉检索语义
- Review snapshot 在 manifest 缺失时也更有机会安全恢复

如果你要对外写一句摘要，建议用保守口径：

> 这轮 follow-up 收紧了公开 MCP 输入契约，修掉了 `add_alias` 的半成功窗口，把不安全 FTS 查询改成单次安全回退，并补做了后端、前端、repo-local MCP、skill smoke 与小样本 real A/B/C/D 复核；目标环境相关路径仍继续保留边界说明。
