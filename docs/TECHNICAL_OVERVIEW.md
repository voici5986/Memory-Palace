# Memory Palace 技术总览

本文档面向需要了解系统内部实现或进行二次开发的技术用户，涵盖后端、前端、MCP 工具层、运行时与部署架构。

---

## 1. 技术栈

| 层 | 技术 | 版本要求 | 作用 |
|---|---|---|---|
| Backend | FastAPI + SQLAlchemy + SQLite | FastAPI ≥0.109 · SQLAlchemy ≥2.0 · aiosqlite ≥0.19 | 记忆读写、检索、审查、维护 |
| MCP | `mcp.server.fastmcp` | mcp ≥0.1 | 为 Codex / Claude Code / Gemini CLI / OpenCode 暴露统一工具面；对 `Cursor / Windsurf / VSCode-host / Antigravity` 这类 IDE 宿主，推荐通过 repo-local `AGENTS.md` 与 MCP 配置片段接入 |
| Frontend | React + Vite + TailwindCSS + Framer Motion | React ≥18.2 · Vite ≥7.3 · TailwindCSS ≥3.3 · Framer Motion ≥12.34 | 可视化管理 Dashboard |
| Runtime | 内置队列与 worker | — | 写入串行化、索引重建、vitality 衰减、sleep consolidation |
| Deployment | Docker Compose + profile 脚本 | Docker ≥20 · Compose ≥2.0（手动运行仓库 compose 文件时建议使用较新的 `docker compose` plugin） | A/B/C/D 档位快速部署 |

核心依赖详见 `backend/requirements.txt` 和 `frontend/package.json`。

补充边界：仓库自带 compose 文件在卷名默认值上使用了嵌套 `${...:-...}`。对较旧 Compose 实现，这更像“解析兼容性”问题，而不是后端启动失败。遇到这种情况，优先改走 `docker_one_click.sh/.ps1`，或在手动启动前显式设置 `MEMORY_PALACE_DATA_VOLUME`、`MEMORY_PALACE_SNAPSHOTS_VOLUME`、`COMPOSE_PROJECT_NAME`。

---

## 2. 后端结构

```
backend/
├── main.py               # FastAPI 入口，注册路由，生命周期管理
├── mcp_server.py          # 9 个 MCP 工具实现
├── runtime_state.py       # 写入 lane、索引 worker、vitality 衰减、cleanup review 管理
├── run_sse.py             # SSE 传输层，支持 API Key 鉴权门控
├── mcp_wrapper.py         # MCP 启动封装
├── api/
│   ├── __init__.py        # 路由导出
│   ├── browse.py          # 记忆浏览与写入接口（prefix: /browse）
│   ├── review.py          # 审查、回滚与集成接口（prefix: /review）
│   ├── maintenance.py     # 维护、观测与 vitality 清理接口（prefix: /maintenance）
│   ├── setup.py           # 首启配置与本地 .env 写入接口（prefix: /setup）
│   └── utils.py           # Diff 计算工具（优先 diff-match-patch，缺失时回退到 difflib.HtmlDiff）
├── db/
│   ├── __init__.py        # 客户端工厂（get_sqlite_client / close_sqlite_client）
│   ├── sqlite_client.py   # 核心数据库层（CRUD、检索、write_guard、gist、vitality、embedding、rerank）
│   ├── snapshot.py        # 快照管理器（按 session 记录写操作的前置状态、串行化同一 session 的快照写入，并做保守的 session 级 retention/GC：按 age/count 清理旧 session、保护当前 session、对拿不到锁的旧 session 先跳过；Review 可见会话仍按当前数据库过滤）
│   ├── migration_runner.py# 自动数据库迁移执行器
│   └── migrations/        # SQL 迁移脚本目录
├── models/
│   ├── __init__.py        # 模型导出
│   └── schemas.py         # Pydantic 数据模型定义
```

> 补充说明：部署、profile 应用、分享前自检等脚本位于仓库根目录的 `scripts/`，不在 `backend/` 子目录里。

### 核心模块说明

- **`main.py`**：FastAPI 应用入口，负责生命周期管理（数据库初始化、legacy 数据库文件兼容恢复、退出前 best-effort drain pending auto-flush summary）、CORS 配置、路由注册（`review`、`browse`、`maintenance`、`setup`）和健康检查。当前 `/health` 对本机 loopback 或带有效 `MCP_API_KEY` 的请求会返回索引状态、write lane 与 index worker 的详细运行时信息；未鉴权的远端探活只返回浅健康结果，避免把内部状态直接暴露出去。如果这类详细健康检查已经进入降级态，HTTP 状态码也会直接变成 `503`，方便 Docker healthcheck 和运维探活按“未就绪”处理。默认 CORS origin 收敛为本地常用列表（`localhost/127.0.0.1` 的 `5173/3000`）；显式配置 wildcard（`*`）时会自动禁用 credentials；legacy sqlite 恢复前会执行 regular-file + quick_check + 核心表存在校验，并在解析 SQLite URL 时剥离 query / fragment，跳过 `:memory:` / `file::memory:` 这类非文件目标。启动阶段在 `load_dotenv(..., override=False)` 之前，还会先记下当时进程里原本就存在的 env key，给 setup 模块后续判断“这是不是进程显式覆盖”用。
- **`mcp_server.py`**：实现 9 个 MCP 工具，包括 URI 解析（`domain://path` 格式）、快照管理、write guard 决策、会话缓存、异步索引入队等核心逻辑。同时提供系统 URI（`system://boot`、`system://index`、`system://index-lite`、`system://audit`、`system://recent`）资源。当前公开支持的 MCP 入口是 `stdio` 和 SSE：`stdio` 直接连工具进程；远程访问则通过 `/sse + /messages` 这条 SSE 链路，并继续受 API Key 与网络侧安全控制约束。`search_memory` 现在还会把极端 `candidate_multiplier` 再压回一个硬上限，并通过 metadata 暴露实际生效的 `candidate_limit_applied`；在 session-first 合并之后，最终返回结果也会再按对外暴露的 `score` 做一次稳定排序，避免出现“顺序和分数字段不一致”的返回契约；如果调用方只关心结果本身，也可以传 `verbose=false` 省掉高噪音调试字段。最终结果回包前的 path 状态复核，现在也会优先走批量查询，减少结果较多时逐条回查 SQLite 的额外开销；如果复核 lookup 自己出错，当前实现会直接丢掉这条结果，并在回包里带上降级信号，而不是继续 fail-open 把可能过期的结果照常返回。`fast` interaction tier 传下去的 candidate cap 现在也会继续压住 `temporal/causal` 这类 intent widening，不会到了 SQLite 层又被悄悄抬高。`create_memory` 在 write guard 临时异常或降级导致 fail-closed 时，当前返回里也会明确标出 `retryable` / `retry_hint`，避免调用方把“临时不可用”误读成“永远不能创建”。`compact_context` / auto-flush 这条摘要落盘路径现在还会额外走一层基于数据库文件的 session 级进程锁，避免两个本地进程同时压同一条 session 时重复写入。
- **`runtime_state.py`**：管理写入 lane（串行化写操作）、索引 worker（异步队列处理索引重建任务）、vitality 衰减调度、cleanup review 审批流程和 sleep consolidation 调度等运行时状态。当前 session-first 检索缓存与 flush tracker 都采用“**单 session 限长 + 总 session 数上限**”的进程内边界，避免长时间运行后按 session 数无限增长；session-first 命中缓存还会惰性清理过期条目，避免旧命中长期占着容量。
- **`run_sse.py`**：SSE 传输层，负责 API Key 鉴权和 `/sse`、`/messages` 两条链路的会话管理。当前实现会在客户端断开后清理 session；如果你继续拿旧的 `session_id` 往 `/messages` 发请求，服务端会明确返回 `404/410`，而不是假装 `202 Accepted`。它现在还会在受信代理链路下优先按 `X-Forwarded-For` / `X-Real-IP` 识别真实客户端地址来做 `/messages` burst limit，并默认发送 15 秒 heartbeat ping。传输层的 host/origin 校验现在默认保留本机回环 allowlist；如果你确实需要远程 hostname / origin 通过校验，可以显式补 `MCP_ALLOWED_HOSTS` / `MCP_ALLOWED_ORIGINS`，而不是依赖非回环监听地址去“自动放开”。仓库当前保留两种使用方式：本地可独立运行 `run_sse.py` 做 standalone 调试；Docker 默认路径则把同一套 SSE 入口直接挂进 `main.py` 的 backend 进程，通过前端代理暴露。
- **`setup.py`**：首启配置与本地 `.env` 写入口。当前 `/setup/status` 和 `/setup/config` 在判断 setup 管理变量时，会把“真正的进程显式覆盖”和“服务启动时只是从 `.env` 读进来的值”分开看；所以 status/save 不会再把 `.env` 启动值误判成 process override，本地保存后也能把当前进程里的 setup 管理配置刷新到新值。`/setup/status` 的可写性探测现在也是纯检查：只看状态不会为了探测先创建目标父目录。
- **`db/sqlite_client.py`**：SQLite 数据库操作层，包含记忆 CRUD、keyword/semantic/hybrid 三种检索模式、write_guard 逻辑（支持语义匹配 + 关键词匹配 + LLM 决策三级判定）、gist 生成与缓存、vitality 评分与衰减、embedding 获取（支持远程 API 和本地 hash 两种模式）、reranker 集成。数据库初始化现在还会用基于数据库文件路径的 `.init.lock` 做进程级串行化，避免 `backend` / `sse` 首次并发启动时互相抢库；`:memory:` 这类非文件目标不会生成这个锁。keyword fallback 的 `LIKE` 查询现在会转义 `%` 和 `_`，避免把通配符当普通搜索词时误扫出一大片不相关结果。
- **`db/migration_runner.py`**：负责发现和执行 SQL migration，并记录版本与 checksum。当前 checksum 归一化不仅会处理 `CRLF/LF`，也会剥离 UTF-8 BOM，所以同一份 migration 只是被 Windows/Notepad 改了文件头，不会被误判成 schema drift。

---

## 3. HTTP API 入口

先说人话：

- `/browse`：平时最常用，负责**看记忆、写记忆**
- `/review`：出了改动要复核时用，负责**看 diff、回滚、确认集成**
- `/maintenance`：系统运维入口，负责**清理、重建索引、看运行状态**

如果你只是接一个普通客户端，通常先看 `/browse` 和 `/review` 就够了。

### 浏览与写入（`/browse`）

| 方法 | 路径 | 鉴权 | 说明 |
|---|---|---|---|
| `GET` | `/browse/node` | API Key | 浏览记忆树（含子节点、面包屑、gist、别名） |
| `POST` | `/browse/node` | API Key | 创建记忆节点（含 write_guard） |
| `PUT` | `/browse/node` | API Key | 更新记忆节点（含 write_guard） |
| `DELETE` | `/browse/node` | API Key | 删除记忆路径 |

这是最像“主业务接口”的一组：

- 记忆树浏览
- 新建 / 更新 / 删除记忆
- 返回结果里会带上当前节点、子节点、面包屑、gist 等前端直接要用的数据
- 当前这组写接口也会先写 Review snapshot；在 Review 里看到的 session 名会带当前数据库作用域（例如 `dashboard-<scope>`），避免不同 SQLite 目标混到一起
- 当前 Dashboard 通过 `/browse/node` 成功写入后，也会补记 reflection workflow 需要的 session summary 输入；所以后续再走 `/maintenance/learn/reflection`，不会再因为“写入来自 Dashboard”本身卡在 `session_summary_empty`
- `POST / PUT /browse/node` 默认还会对单次 `content` 做长度校验（`BROWSE_CONTENT_MAX_CHARS`，默认 1 MiB），防止把超大正文直接塞进 Dashboard 写接口
- `POST /browse/node` 还会对生成后的路径长度做前置校验（`BROWSE_PATH_MAX_CHARS`，默认 512），如果 `parent_path + title` 太长，会在真正写入前直接返回 `422`
- 如果 write lane 长时间拿不到写槽位，`browse` / `review` / `maintenance` 这几组写接口现在都会直接返回结构化 `503`（`write_lane_timeout`），而不是只冒一个通用 `500`；MCP 写工具遇到同样情况时，也会返回可重试的结构化错误结果
- 如果 SQLite 运行时写入 pragma 因网络文件系统风险或 `journal_mode` 不可用而从 `WAL` 回退到 `DELETE`，当前实现也会明确打一条 warning，方便你把问题直接定位到部署环境，而不是继续猜业务层报错

### 审查与回滚（`/review`）

路由级 API Key 鉴权（所有端点均需要鉴权）。

当前实现补一条边界：

- snapshot 文件仍然位于仓库级 `snapshots/` 目录；
- 但会话列表、快照列表和快照读取会按**当前数据库作用域**过滤，避免你在同一 checkout 下切换 `DATABASE_URL`、临时 SQLite 文件或 Docker 数据卷后，把另一份库的 rollback 会话混进当前审查列表；
- 同一个 `session_id` 下的 snapshot 写路径现在会串行化，`manifest.json` 和单个快照 JSON 文件也会通过原子替换落盘；同一套快照目录还会做保守的 session 级 retention/GC：按 age/count 清理旧 session、保护当前 session、对拿不到锁的旧 session 先跳过；所以多个本地进程共用同一个 checkout 时，活跃 session 不会为了抢锁被误删，快照元数据也更不容易丢条目或出现半写入 JSON；
- 如果 `manifest.json` 损坏，后端现在会优先使用 session 侧记录的数据库作用域去重建；只有在能保住原始作用域时才会把重建结果写回。拿不到可靠作用域时，这条会话会先保持隐藏，也不会被一次只读的会话列表请求自动删掉；
- 没有数据库作用域标记的 legacy snapshot 会话，默认不会继续暴露在当前 Review 列表里；当前实现还会对这类“被隐藏的老会话”补一条一次性 warning，避免升级后看起来像快照凭空消失。
- 如果同一个 URI 已经在另一条 Review session 里留下了更晚的**内容快照**，旧快照的 rollback 现在会在真正写入前再检查一次；发现内容已经变新，就会直接返回 `409`，避免把较新的内容改动默默回滚掉。
- metadata-only rollback 现在也会在真正写入前按当前 path 状态 fail-close：如果 path 中途已经不存在，会直接返回 `404`；如果当前 path 指向或 metadata 已经先变了，会返回 `409`，不再默默覆盖较新的状态，也不会再冒一个笼统的 `500`。
- 对 `create` 型 rollback，如果目标下面有很多后代节点，当前实现会把“删后代路径 + 清孤儿 memory + 删当前节点”收敛到一次 write-lane 执行里，减少大树回滚时反复进 lane 的开销。

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/review/sessions` | 列出审查会话 |
| `GET` | `/review/sessions/{session_id}/snapshots` | 查看会话快照列表 |
| `GET` | `/review/sessions/{session_id}/snapshots/{resource_id}` | 查看快照详情 |
| `GET` | `/review/sessions/{session_id}/diff/{resource_id}` | 查看版本 diff |
| `POST` | `/review/sessions/{session_id}/rollback/{resource_id}` | 执行回滚 |
| `DELETE` | `/review/sessions/{session_id}/snapshots/{resource_id}` | 确认集成（删除快照） |
| `DELETE` | `/review/sessions/{session_id}` | 清除整个 session 的快照 |
| `GET` | `/review/deprecated` | 列出所有 deprecated 记忆 |
| `DELETE` | `/review/memories/{memory_id}` | 永久删除已审查的记忆 |
| `POST` | `/review/diff` | 通用文本 diff 计算 |

这组接口更像“变更复核区”：

- 先看 session
- 再看 snapshot / diff
- 最后决定是 rollback 还是 integrate
- `POST /review/diff` 更像通用文本对比 helper：它会返回 `diff_html`、`diff_unified` 和一条简短的英文 `summary`；如果环境里缺少 `diff_match_patch`，HTML diff 会自动退回到 `difflib.HtmlDiff`

### 维护与观测（`/maintenance`）

路由级 API Key 鉴权（所有端点均需要鉴权）。

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/maintenance/orphans` | 查看孤儿记忆（deprecated 或无路径指向） |
| `GET` | `/maintenance/orphans/{memory_id}` | 查看孤儿记忆详情 |
| `DELETE` | `/maintenance/orphans/{memory_id}` | 永久删除孤儿记忆（如果某条 deprecated 最终目标仍被更旧版本引用，会先拒绝删除，直到前面的旧链路先清掉） |
| `POST` | `/maintenance/import/prepare` | 准备外部导入任务（生成可执行计划） |
| `POST` | `/maintenance/import/execute` | 执行外部导入任务 |
| `GET` | `/maintenance/import/jobs/{job_id}` | 查看导入任务状态 |
| `POST` | `/maintenance/import/jobs/{job_id}/rollback` | 回滚导入任务 |
| `POST` | `/maintenance/learn/trigger` | 触发显式学习任务 |
| `POST` | `/maintenance/learn/reflection` | 触发 reflection workflow（`prepare/execute`；`execute` 会进入 write lane、登记 learn job，并为新建 path 写 review snapshot） |
| `GET` | `/maintenance/learn/jobs/{job_id}` | 查看显式学习任务状态 |
| `POST` | `/maintenance/learn/jobs/{job_id}/rollback` | 回滚显式学习任务（reflection execute 会委托给对应的 review snapshot rollback） |
| `POST` | `/maintenance/vitality/decay` | 触发 vitality 衰减 |
| `POST` | `/maintenance/vitality/candidates/query` | 查询清理候选记忆（支持 `domain` / `path_prefix` 过滤） |
| `POST` | `/maintenance/vitality/cleanup/prepare` | 准备清理审批（生成 review_id + token） |
| `POST` | `/maintenance/vitality/cleanup/confirm` | 确认并执行清理（需 review_id + token + 确认短语） |
| `GET` | `/maintenance/index/worker` | 查看索引 worker 状态 |
| `GET` | `/maintenance/index/job/{job_id}` | 查看索引任务详情 |
| `POST` | `/maintenance/index/job/{job_id}/cancel` | 取消索引任务 |
| `POST` | `/maintenance/index/job/{job_id}/retry` | 重试索引任务 |
| `POST` | `/maintenance/index/rebuild` | 触发全量索引重建 |
| `POST` | `/maintenance/index/reindex/{memory_id}` | 单条索引重建 |
| `POST` | `/maintenance/index/sleep-consolidation` | 触发 sleep consolidation |
| `POST` | `/maintenance/observability/search` | 观测搜索（含检索统计） |
| `GET` | `/maintenance/observability/summary` | 观测概览 |

这组接口比较多，但可以简单分成 5 类：

1. **导入 / 学习任务**：`import/*`、`learn/*`
2. **孤儿记忆清理**：`orphans*`
3. **活力治理**：`vitality/*`
4. **索引任务**：`index/*`
5. **运行态观测**：`observability/*`

和这轮 reflection 修复直接相关的边界也补一句：

- `POST /maintenance/learn/reflection` 的 `prepare` 仍然只是准备态；真正会落库的 `execute` 现在会进入同一条 write lane，和其他写操作保持一致的串行化语义
- reflection execute 成功后，当前 learn job 会同时带上对应的 review snapshot 信息；`/maintenance/learn/jobs/{job_id}/rollback` 这条维护接口现在会继续委托给 review rollback，而不是绕开 review 语义自己删数据
- 如果同一个 `session_id`、`source`、`reason`、`content` 被并发 `prepare`，现在会复用同一个 prepared review，而不是为同一批内容生成多个 review ID
- `/maintenance/observability/summary` 里的 `reflection_workflow` 统计现在会合并持久化 summary，重启后 summary 计数口径稳定；这里说的是 summary 稳定，不是把所有明细事件都永久保留下来
- 如果调用方显式传了空白或只含空格的 `session_id`，reflection workflow 现在会直接按 `session_id_invalid` fail-closed；只有真的没传 `session_id` 时，才会回退到 ambient session

当前后端默认不会公开 `http://127.0.0.1:8000/docs`；直接访问一般会得到 `404`。接口说明优先看这里、[TOOLS.md](TOOLS.md) 和 `backend/tests/` 里的接口测试。

---

## 4. MCP 工具实现

实现文件：`backend/mcp_server.py`

| 工具 | 类型 | 说明 |
|---|---|---|
| `read_memory` | 读取 | 读取记忆内容，支持整段与分片（chunk_id / range / max_chars），支持系统 URI（`system://boot`、`system://index`、`system://index-lite`、`system://audit`、`system://recent`） |
| `create_memory` | 写入 | 创建新记忆节点（含 write_guard，进入 write lane 串行化；建议显式填写 `title`） |
| `update_memory` | 写入 | 更新已有记忆（优先用 `old_string/new_string` 做精确替换；`append` 只用于真实尾追加，含 write_guard） |
| `delete_memory` | 写入 | 删除记忆路径（进入 write lane 串行化） |
| `add_alias` | 写入 | 为同一记忆添加别名路径（可跨 domain） |
| `search_memory` | 检索 | 统一检索入口（keyword/semantic/hybrid），支持意图分类与策略模板 |
| `compact_context` | 治理 | 将当前会话上下文压缩为长期记忆摘要（进入 write lane 串行化） |
| `rebuild_index` | 维护 | 全量或单条索引重建，支持同步等待与 sleep consolidation |
| `index_status` | 维护 | 查询索引可用性、运行时状态与配置开关 |

工具返回约定与降级语义详见：[TOOLS.md](TOOLS.md)

---

## 5. 前端结构

```
frontend/src/
├── App.jsx                                    # 路由与页面骨架
├── main.jsx                                   # React 入口
├── RootErrorBoundary.jsx                      # 根级 render 崩溃兜底页
├── i18n.js                                    # react-i18next 初始化、默认语言与持久化
├── index.css                                  # 全局样式（TailwindCSS）
├── locales/
│   ├── en.js                                  # 英文文案
│   └── zh-CN.js                               # 中文文案
├── features/
│   ├── memory/MemoryBrowser.jsx               # 树形浏览、编辑、gist 视图
│   ├── review/ReviewPage.jsx                  # diff、rollback、integrate
│   ├── maintenance/MaintenancePage.jsx        # vitality 清理与维护任务
│   └── observability/ObservabilityPage.jsx    # 检索统计与任务可观测
├── components/
│   ├── DiffViewer.jsx                         # Diff 可视化
│   ├── FluidBackground.jsx                    # 流体动画背景
│   ├── GlassCard.jsx                          # 毛玻璃卡片
│   └── SnapshotList.jsx                       # 快照列表
├── lib/
│   ├── api.js                                 # 统一 API 客户端与运行时鉴权注入
│   ├── format.js                              # 跟随当前语言的日期/数字格式化
│   ├── api.test.js                            # API 客户端单元测试
│   └── api.contract.test.js                   # API 鉴权契约测试
└── test/                                      # 前端测试目录
```

### Dashboard 四大功能模块

| 模块 | 路由 | 功能 |
|---|---|---|
| Memory Browser | `/memory` | 按域（domain）树形浏览、内联编辑、查看 gist 摘要、别名管理 |
| Review | `/review` | 查看写入快照 diff、支持 rollback 回滚和 integrate 确认、清理 deprecated 记忆 |
| Maintenance | `/maintenance` | 查看 vitality 评分、清理孤儿记忆、触发索引重建、管理清理审批流程，支持 `domain` / `path_prefix` 过滤 |
| Observability | `/observability` | 检索日志与统计、任务执行记录、索引 worker 状态、系统状态概览，支持 `scope_hint` 与更细的运行时快照 |

补充说明：

- 当前版本的前端会先恢复浏览器里已保存的语言；如果没有保存值，常见中文浏览器语言（`zh`、`zh-TW`、`zh-HK` 和其他 `zh-*`）会统一归并到 `zh-CN`，其他首次访问场景则回退到英文。React 挂载前还会先把 `<html lang>` 和 `document.title` 同步到这次启动实际要用的语言，减少刷新后先闪回旧标题或旧语言的情况。应用壳层右上角同时提供语言切换入口与统一鉴权入口
- React 根节点现在还会先包一层 `RootErrorBoundary`。说人话就是：如果某个组件在 render 阶段直接崩掉，Dashboard 会先退回一个最小兜底页，而不是把整个 SPA 直接卸掉又不给解释。
- 语言切换支持英文 / 中文一键切换，结果会保存在浏览器 `localStorage` 的 `memory-palace.locale`
- 常见静态文案、日期/数字格式，以及前端侧的常见错误映射会跟随当前语言切换
- 如果还没配置鉴权，页面外壳仍会打开，但受保护的数据请求会先显示授权提示、空态或 `401`
- 按推荐的一键 Docker 路径启动时，受保护请求通常已经能直接使用：前端代理会在服务端自动转发同一把 `MCP_API_KEY`；但页面右上角仍可能继续显示 `设置 API 密钥`（英文模式下会显示 `Set API key`），因为浏览器页面本身并不知道代理层的真实 key。只有当受保护数据也一起 `401` 或空态时，才需要继续排查 env / 代理配置
- 如果服务端 Dashboard 鉴权已经生效，尤其是标准 Docker proxy-held key 路径，首启配置向导现在不会只因为浏览器本地还没保存 key 就自己误弹
- 浏览器里保存的 Dashboard 鉴权现在走当前浏览器会话的 `sessionStorage`；若检测到旧版 `localStorage` 值，前端仍只会做一次迁移，但只会在确认 `localStorage` 里还是那份旧值时才删除它，避免多标签页同时迁移时误删新值。通过 Setup Assistant 保存本地 `.env` 时，如果表单里带了当前 key，前端也会把这把 key 一并落到浏览器会话；如果这次保存把 key 清空，旧的浏览器侧保存值也会一起清掉
- Setup Assistant 现在在 `Profile B/C/D`、以及 `hash / api / router` 这些切换之间，会把当前已经隐藏的旧字段一起清掉，减少把上一档残留的 router/API 值继续带进本次保存的情况；切到远端 embedding backend 时，保存还会一起写正确的 `RETRIEVAL_EMBEDDING_DIM`，并且 `/setup/config` 已支持 `openai` embedding backend
- Setup Assistant 现在也会把 `Profile A` 直接显示出来；它对应的还是默认 `keyword + none` 基线，不是新增的一条独立高阶配置档
- Setup Assistant 现在一打开就会优先把焦点放到 Dashboard API key 输入框；`Escape` 可以直接关闭，`Tab/Shift+Tab` 会在弹窗内部循环，不会把键盘焦点甩到弹窗外面
- `Maintenance` 页的 vitality cleanup confirm 现在不是“失败就一律把 prepared review 清空”；像 `401`、超时、网络错误这类更像临时失败的情况，会保留当前 prepared review，方便修完鉴权或网络后直接重试
- Memory 页的“离开未保存编辑”和“删除路径”现在都走 fail-closed 确认逻辑；如果宿主环境不支持原生 `confirm()`，动作会被直接拦下，并给出页内错误提示，而不是静默继续

---

## 6. 前端鉴权注入模型

前端不会从 `VITE_*` 构建变量读取维护密钥，采用运行时注入方式：

```html
<script>
  window.__MEMORY_PALACE_RUNTIME__ = {
    maintenanceApiKey: "<YOUR_MCP_API_KEY>",
    maintenanceApiKeyMode: "header"
  };
</script>
```

`maintenanceApiKeyMode` 支持：`header`（发送 `X-MCP-API-Key` 头）或 `bearer`（发送 `Authorization: Bearer` 头）。

> 兼容性：运行时对象也兼容旧字段名 `window.__MCP_RUNTIME_CONFIG__`。
>
> 代码参考：`frontend/src/lib/api.js` 中的 `readWindowRuntimeMaintenanceAuth()` 与 `getMaintenanceAuthState()`。
>
> 说人话就是：默认情况下，前端优先读运行时注入的 key；如果没有，再读当前浏览器会话里的已保存 key。只有一个额外例外：如果你刚在 Setup Assistant 里手动保存了一把浏览器侧 Dashboard key，前端会明确让这把新 key 在当前会话里优先于 runtime key。旧版遗留在 `localStorage` 里的 Dashboard key 只会做一次迁移；只有在那份旧值没有被别的标签页改写时，当前标签页才会把它删掉。
>
> 说人话就是：前端把鉴权做成了“运行时再决定”，所以你可以在页面顶部直接补 key，也可以由部署脚本在页面加载前注入。
>
> 如果这把鉴权已经在服务端代理层生效，前端现在也不会只因为浏览器本地没有保存 Dashboard key 就自己弹出首启向导。
>
> 还有一个当前代码已经补齐的小细节：如果你把 `maintenanceApiKeyMode` 从 `header` 切到 `bearer`（或反过来），请求拦截器会先删掉旧的相反 header，再按当前模式补新的那一个，避免同一个请求同时带两套鉴权头。
>
> 再补一个当前代码已经对齐的小边界：如果你给前端显式配置了 `VITE_API_BASE_URL`，无论它是同源下的带前缀路径，还是你自己的跨源 API 地址，前端现在都会按这个 API base 去识别 `/browse`、`/review`、`/maintenance`、`/setup` 这些受保护请求，并继续附加浏览器里保存的 Dashboard key；但它仍然不会把这把 key 发到无关第三方绝对 URL。
>
> `run_memory_palace_mcp_stdio.sh` 这层 wrapper 的额外价值不是“修复本来就会读错库的 mcp_server.py”，而是给 CLI/本地配置一个更稳的默认入口：优先复用仓库 `.env` / `DATABASE_URL`；如果 `.env` 里已经设置了 `RETRIEVAL_REMOTE_TIMEOUT_SEC`，它也会继续复用这个值；只有在仓库里既没有本地 `.env`、也没有 `.env.docker` 时，才回退到仓库里的默认 SQLite 路径。如果只存在 `.env.docker`，wrapper 会明确拒绝回退到 `demo.db`，避免把本地 stdio 和 Docker 容器数据混在一起；如果 `.env` 或显式 `DATABASE_URL` 在把常见斜杠和大小写变体归一化后，仍写成 `/app/...` 或 `/data/...` 这类容器路径（例如 `sqlite+aiosqlite://///app/data/...` 或大写 `/APP/...` 变体），它也会直接拒绝启动。对 shell wrapper 这条路径，它还会在启动 Python 前先导出 `PYTHONIOENCODING=utf-8` 和 `PYTHONUTF8=1`，减少非 UTF-8 locale 下的本地 stdio 编码问题；同时也会合并已有的 `NO_PROXY` / `no_proxy` 并补上 `localhost`、`127.0.0.1`、`::1`、`host.docker.internal`，让 repo-local stdio 更不容易被宿主机代理误伤本机模型调用。

> Docker 一键部署走的是第三种方式：不把 key 注入页面，而是在前端代理层自动转发。

---

## 7. 数据与任务流

### 写入路径

1. `create_memory` / `update_memory` 进入 **write lane**（串行化写操作；遇到短暂 SQLite 锁冲突时会先做一次小范围重试）。
2. 写前执行 **write_guard** 判定（核心决策：`ADD` / `UPDATE` / `NOOP` / `DELETE`；`BYPASS` 为上层 metadata-only 更新时的流程标记）。
   - write_guard 支持三级判定链：语义匹配 → 关键词匹配 → LLM 决策（可选）。
3. 生成 **snapshot** 与版本变更（按 `path` 和 `memory` 两维度分别记录；MCP 工具写入和 Dashboard `/browse/node` 写入都遵循这套语义；同一 session 的快照写入现在通过文件锁串行化）。
   - 对 Dashboard `/browse/node` 来说，成功写入后现在还会补上 reflection workflow 可复用的 session summary 输入。
   - 每次 snapshot 成功写入后，后端现在还会按 age/count 做保守的 session 级 retention；当前 session 会被保护，拿不到锁的旧 session 会先跳过。
4. 入队 **索引任务**（队列满会返回 `index_dropped` / `queue_full`；真正写库的索引任务也会经过同一条 write lane，而不是直接和前台写入抢同一个 SQLite 文件）。

### 检索路径

1. **`preprocess_query`** 对查询文本进行预处理（标准化空白、分词、多语言/URI 保留）。
2. **`classify_intent`** 默认按 4 种核心意图路由；无显著关键词信号时默认 `factual`（模板 `factual_high_precision`），当信号冲突或低信号混合时回退 `unknown`（模板 `default`）：
   - `factual` → 策略模板 `factual_high_precision`（高精度匹配）
   - `exploratory` → 策略模板 `exploratory_high_recall`（高召回探索）
   - `temporal` → 策略模板 `temporal_time_filtered`（时间过滤）
   - `causal` → 策略模板 `causal_wide_pool`（因果推理，宽候选池）
   - `unknown` → 策略模板 `default`（冲突或低信号混合时保守回退）
   - 一个容易误解的边界是：`why ... after/before ...` 不会因为出现 `after/before` 就自动掉到 `unknown`；如果这些词只是描述触发事件，规则仍优先保留 `causal`。只有像 `when`、`timeline`、`yesterday` 这类更强的时间锚点一起出现时，才继续按混合低信号查询保守回退。
3. 执行 **keyword / semantic / hybrid** 检索。
4. 可选 **reranker** 重排序（通过远程 API 调用）。
5. 支持额外的查询侧约束，例如 `scope_hint`、`domain`、`path_prefix`、`max_priority`。
6. 返回 `results` 与 `degrade_reasons`。

> 当前向量维度检查会跟着这次查询真正命中的 scope 走，而不是对全库做一遍全局判定；所以无关 domain 里的旧向量不会再把当前作用域的语义检索误降级。若当前作用域内确实存在维度不一致，`degrade_reasons` 会明确提示需要 reindex。

> 兼容性补一句：`scope_hint=fast|deep` 现在会先按旧调用方的习惯被当成 interaction tier 快捷值处理，而不是被当成 path scope。新调用方如果就是想切快/深档，优先直接传 `interaction_tier`。

> 意图分类使用 `keyword_scoring_v2` 方法实现（`db/sqlite_client.py` `classify_intent` 方法），通过关键词匹配评分与排名进行意图推断，无需外部模型调用。当前规则已经区分“弱时间连接词”和“强时间锚点”：前者不会轻易压过明显的因果意图，后者仍会触发保守回退。
>
> **配置策略说明**：
> - 本项目支持两种思路：`1)` 分别直配 embedding / reranker / llm；`2)` 通过 `router` 统一代理这些能力。
> - `INTENT_LLM_ENABLED` 默认关闭；开启后会优先尝试 LLM 意图分类，失败则回退到现有关键词规则。
> - `RETRIEVAL_MMR_ENABLED` 默认关闭；只有 `hybrid` 检索下才会做去重 / 多样性重排。
> - `RETRIEVAL_SQLITE_VEC_ENABLED` 默认关闭；当前仍保留 legacy 向量路径为默认实现，sqlite-vec 走受控 rollout。
> - 本地开发默认更推荐前者，因为三条链路的故障通常彼此独立，分别配置更容易确认是哪一个模型、哪个端点或哪组密钥出了问题。
> - `router` 更适合作为生产 / 客户环境的统一入口：便于集中做鉴权、限流、审计、模型切换与 fallback 编排。

![记忆写入与审查时序图](images/记忆写入与审查时序图.png)

---

## 8. 部署口径

| 场景 | 宿主机端口 | 容器内部端口 | 说明 |
|---|---|---|---|
| 本地开发 | Backend `8000` · Frontend `5173` | — | 直接启动 |
| Docker 默认 | Backend `18000` · Frontend `3000` · SSE `3000/sse` | Backend `8000`（同时承载 REST + SSE） · Frontend `8080` | 端口可通过环境变量覆盖 |

Docker 端口环境变量：

- Backend：`MEMORY_PALACE_BACKEND_PORT`（回退到 `NOCTURNE_BACKEND_PORT`，默认 `18000`）
- Frontend：`MEMORY_PALACE_FRONTEND_PORT`（回退到 `NOCTURNE_FRONTEND_PORT`，默认 `3000`）

补充一句：

- 把 SSE 监听地址改成 `0.0.0.0`（或其他非 loopback 地址）只表示远程客户端可以连到这个监听地址，不表示可以跳过 `MCP_API_KEY`、反向代理、防火墙或 TLS 等安全控制。

相关文件：

- Compose 文件：`docker-compose.yml`（frontend healthcheck 在探测 `127.0.0.1:8080` 前会先显式 unset `http_proxy/https_proxy/all_proxy/no_proxy` 这一组环境变量，避免容器继承宿主代理后把本机探活误导到代理链路）
- 镜像定义：`deploy/docker/Dockerfile.backend`（基于 `python:3.11-slim`）、`deploy/docker/Dockerfile.frontend`（构建阶段 `node:22-alpine`，运行阶段 `nginxinc/nginx-unprivileged:1.27-alpine`）
- Backend 健康检查脚本：`deploy/docker/backend-healthcheck.py`（容器内对 `/health` 做二次检查，要求返回 payload 的 `status == "ok"`；默认超时 `5` 秒，可通过 `MEMORY_PALACE_BACKEND_HEALTHCHECK_TIMEOUT_SEC` 调整）
- Nginx 配置模板：`deploy/docker/nginx.conf.template`（仅对受保护的 Dashboard API 路径和 `/sse` / `/messages` 注入 `X-MCP-API-Key`，并对 `/index.html` 返回 no-store/no-cache/must-revalidate，减少前端更新后继续命中旧入口页面；前端入口脚本会先对代理持有的 key 做一次特殊字符转义，并拒绝剩余 ASCII 控制字符，再生成最终 Nginx 配置）
- 入口脚本：`deploy/docker/backend-entrypoint.sh`、`deploy/docker/frontend-entrypoint.sh`（后端入口脚本在 root 场景下如果找不到 `gosu` 会直接 fail-closed）
- 备份脚本：`scripts/backup_memory.sh`、`scripts/backup_memory.ps1`（默认保留最近 `20` 份备份，可通过 `--keep` / `-Keep` 调整；备份文件名统一使用 UTC 时间戳，方便宿主机和容器环境混用时按时间排序）
- 分享前检查：`scripts/pre_publish_check.sh`

当前 validate 链路已经把 frontend `npm run typecheck` 纳入和 `npm test` / build 同级的检查；本 session 实测 backend `943 passed, 20 skipped`、frontend `159 passed`，前端 typecheck 和 build 通过。repo-local `Profile B` 这轮还实际跑了 backend + frontend + 真实浏览器 setup/maintenance smoke；另外也补跑了一条覆盖 `Profile C/D` 同类 retrieval / reranker / `write_guard` / gist 链路的本地 smoke。Docker one-click 的 `Profile C/D` 和原生 Windows / Linux 宿主 runtime 这轮没有重跑，所以这里继续保留目标环境复核边界。

---

## 9. 安全默认值

- `/maintenance/*`、`/review/*` 所有端点均需 API Key 鉴权。
- `/browse` 读写操作（GET/POST/PUT/DELETE）均通过端点级 `Depends(require_maintenance_api_key)` 门控。
- 公开 HTTP 端点包括 `/`、`/health`，以及 FastAPI 默认文档端点；其中 `/health` 公开的是浅健康结果，详细 runtime/index 仍只对本机 loopback 或带有效 key 的请求开放。其余 Browse / Review / Maintenance 与 SSE 通道遵循同一鉴权逻辑。
- `MCP_API_KEY` 为空时默认 **fail-closed**（拒绝请求）。
- 仅在 `MCP_API_KEY_ALLOW_INSECURE_LOCAL=true` **且** loopback 请求（`127.0.0.1` / `::1` / `localhost`）时可本地放行，且仅限直连 loopback 且无 forwarding headers 的请求。
- `/setup/config` 这条本地 `.env` 写入路径同样按 fail-closed 处理：它只会写当前项目里的 `.env*` 文件，仍然只允许直连 loopback 请求；如果后端已经带着 `MCP_API_KEY` 在跑，那么即使是这条 loopback 写入路径，也还要带上同一把有效 key。
- Docker 容器默认以非 root 用户运行：
  - Backend：自定义用户 `app`（UID `10001`，GID `10001`）
  - Frontend：使用 `nginx-unprivileged` 官方非 root 镜像

详细策略：[SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md)
