# Memory Palace v3.7.0 发布说明（2026-03-26）

这份说明只记录**当前仓库里已经真实修改、已经真实复验**的内容，不把宿主环境差异写成统一保证。

---

## 1. 一句话结论

`v3.7.0` 是一轮“收口型”发布：把 fail-close 输入校验收紧，把 Dashboard 在自定义 API base URL 下的鉴权行为讲清楚，也把 repo-local skill bundle 的同步链路重新修正了。

---

## 2. 这次实际改了什么

- `session_id` 现在真正按 fail-close 处理前后空白和控制类字符。Review API 也统一复用了同一套规则，不再和 snapshot 层漂移。
- 公开 `priority` 契约现在和 SQLite 层一致了。MCP 工具入口不再把 `True`、`False`、`1.9` 这类值静默吞成整数。
- 当前端通过 `VITE_API_BASE_URL` 指向自定义 API 地址时，Dashboard 现在也会继续把浏览器里保存的鉴权 key 附加到受保护请求上。这包括非根路径部署，也包括显式跨源的 API 部署；但它仍然**不会**把 key 发到无关第三方绝对 URL。
- repo-local skill mirrors 已重新和 canonical `memory-palace` bundle 对齐，所以 `python scripts/sync_memory_palace_skill.py --check` 现在又回到了 `PASS`。

---

## 3. 这次实际复验了什么

- 后端测试：`785 passed, 18 skipped`
- 前端测试：`114 passed`
- 前端生产构建：通过
- live stdio MCP e2e：通过
- repo-local skill sync check：通过
- macOS 本机 smoke：
  - 独立 backend + SSE + Vite 路径已复验
  - Dashboard 的 `Memory / Review / Maintenance / Observability` 四页已复验
  - 语言切换与浏览器持久化已复验
- Linux Docker smoke：
  - 已复验 `docker_one_click.sh --profile b`
  - Dashboard 根页面可访问
  - backend health 可访问
  - `/sse` 可访问，返回 `text/event-stream`
- D 风格检索链路 smoke：
  - 已对真实 OpenAI-compatible embedding / reranker / intent-LLM 服务复验
  - observability search 返回 `degraded=false`
  - 已验证路径上 `intent_llm_applied=true`

---

## 4. 这次没有写成“已完全通过”的内容

- 这次**没有**把 native Windows 主机的端到端终验写成已完成。Windows 仍建议在目标环境补验。
- `Codex`、`OpenCode`、`Gemini live`、`Cursor`、`agent` 这类宿主相关 skill smoke，当前仍可能因为本机登录状态、宿主 runtime 或工具启动条件而显示 `PARTIAL`。这些问题已经不再是 canonical bundle 漂移，但仍然带有环境依赖。
- 这次也没有声称“所有 A/B/C/D 启动组合都在所有环境里从头重跑过”。公开口径只覆盖上面已经列出的那些实际复验项。

---

## 5. 对普通用户最直接的影响

如果你只关心“升级之后到底更稳了什么”，可以简单理解成：

- 明显不合法的 `session_id` 现在会更早、更一致地被拒绝
- 不合法的 `priority` 不会再从 MCP 工具入口漏过去
- 当 API 部署在自定义 base URL 下时，Dashboard 鉴权行为更符合直觉
- repo-local skill 同步链路重新回到了可复核状态

如果你要对外写发布摘要，建议保持保守口径：

> `v3.7.0` 重新复验了主后端/前端链路，修紧了 `session_id` 与 `priority` 的严格校验，恢复了 repo-local skill sync 一致性，同时继续保留 native Windows 和宿主侧 skill smoke 的目标环境边界说明。

