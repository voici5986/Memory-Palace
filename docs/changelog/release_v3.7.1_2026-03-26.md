# Memory Palace v3.7.1 发布说明（2026-03-26）

这份说明只记录**当前仓库里已经真实修改、已经真实复验**的内容，不把宿主环境差异写成统一保证。

---

## 1. 一句话结论

`v3.7.1` 是一轮偏“收口 + 运维边界修正”的发布：路径删除更接近原子，回滚 metadata 不再误伤 alias，Windows 脚本边界更稳，repo-local skill evaluator 也更像环境检查而不是误报仓库失败。

---

## 2. 这次实际改了什么

- `delete_memory` 现在会把当前 path 状态读取、删除前 snapshot 取值、以及 path 删除都放进同一条 SQLite 写事务里。说人话就是：多个本地进程共用同一个 SQLite 文件时，别的进程更不容易在“删的是什么”和“实际删掉了什么”之间插队。
- `rollback_to_memory(..., restore_path_metadata=True)` 现在只恢复当前选中 path 的 metadata。alias 自己的 `priority` / `disclosure` 不会再被主路径的 snapshot metadata 一起覆盖掉。
- provider-chain 的 embedding cache 现在也更会复用 fallback/provider 的缓存结果了。对 fail-open 远端链路来说，前一次 provider 失败后，后续请求不再总是把后面的 fallback provider 全部重新打一遍。
- Review session 列表现在会跳过非法的 legacy session 目录名，而不是让这些旧目录直接把 session 列表打挂。
- `add_alias` 现在也会在 MCP 入口层统一执行 `priority` 严格校验，所以 bool / float 这类值不会再从这条公开工具路径漏过去。
- `apply_profile.sh` 现在能正确处理从 PowerShell / WSL / Git Bash 传进来的 Windows 绝对目标路径，包括那种分隔符已经被 shell 吞坏的常见形态，不会再往仓库根目录里落一个坏文件名。
- `docker_one_click.ps1` 现在会用 UTF-8 without BOM 回写生成出来的 Docker env 文件。说人话就是：原生 Windows PowerShell 不会再沿着这条路径把 Docker Compose 要读的 env 文件写成 UTF-16。
- `evaluate_memory_palace_skill.py` 现在能更正确地解析常见 dotenv 风格的 `DATABASE_URL`，包括带引号、`export DATABASE_URL=...` 和尾部注释。它现在也会把 user-scope 绑定漂移、Gemini 登录/鉴权提示这类机器环境问题记成 `PARTIAL`，并把 `gemini_live` 保持为显式 opt-in。

---

## 3. 这次实际复验了什么

- 后端测试：`797 passed, 20 skipped`
- 前端测试：`119 passed`
- 前端生产构建：通过
- live stdio MCP e2e：通过
- repo-local skill sync check：通过
- repo-local skill evaluator：
  - 当前机器上已重新确认退出码为成功
  - user-scope 漂移、Gemini 登录、宿主 runtime 缺失这类环境问题，会保留为 `PARTIAL` / `MANUAL`，不再把整份 repo 校验误报成失败
- native macOS 本机验证：
  - repo-local backend + standalone SSE + Vite 路径已复验
  - Memory / Review / Maintenance / Observability 四页已在真实浏览器中复验
  - 中英文切换与持久化已复验
  - repo-local browse 创建、Review 交互、Observability 诊断搜索已复验
- native Windows 本机 smoke：
  - 已在发布标签上完成后续真实宿主复验
  - 宿主机启动与主功能路径已复验
- Docker 路径验证：
  - Profile B one-click 路径已复验
  - Profile C / D 的 runtime injection 检索链路已结合真实 embedding / reranker / LLM 服务复验
  - 已复验 Dashboard 根页面、backend health、带鉴权的 browse、以及 `/sse` 可达

---

## 4. 这次没有写成“已完全通过”的内容

- `Gemini CLI`、`Cursor`、`agent`、`Antigravity` 这类项，仍可能因为本机登录状态、宿主 runtime 是否安装、或目标机器可用性而落在 `PARTIAL` / `MANUAL`。
- 这次也没有声称“所有 A/B/C/D 启动组合都在所有环境里从头重跑过”。公开口径只覆盖上面已经列出的实际复验项。
- 第三方 provider 的可用性仍依赖目标环境本身的网络可达性，以及 embedding / reranker / LLM 服务配置。

---

## 5. 对普通用户最直接的影响

如果你只关心“升级之后到底更稳了什么”，可以简单理解成：

- 共用本地 SQLite 时，路径删除更不容易撞上竞态
- 回滚单一路径时，不会再把 alias 自己的 metadata 一起抹平
- Windows 的 shell / PowerShell 运维脚本边界更稳了
- repo-local skill 验证更不容易因为机器本地登录或 user-scope 漂移而误报仓库失败

如果你要对外写发布摘要，建议保持保守口径：

> `v3.7.1` 收紧了本地 delete-path 原子性，保住了 alias 自身的 rollback metadata，修稳了 Windows 运维脚本边界，并完成了原生 macOS / Windows 宿主上的主链路复验；宿主侧 skill 环境与第三方 provider 可用性仍继续保留明确边界说明。
