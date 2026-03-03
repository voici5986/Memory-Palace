# 当前代码改进对照说明（相对 docs 根目录旧口径）

> 目的：用简单、可核对的话说明“现在代码到底比原有项目多了什么”。  
> 说明：这里只写**已落地实现**，不写规划项。

---

## 1. 对比范围

本次对比基线是 `Memory-Palace/docs` 根目录（不含子目录）的旧说明文档：

- `README.md`
- `GETTING_STARTED.md`
- `TECHNICAL_OVERVIEW.md`
- `TOOLS.md`
- `DEPLOYMENT_PROFILES.md`
- `SECURITY_AND_PRIVACY.md`
- `TROUBLESHOOTING.md`
- `EVALUATION.md`

---

## 2. 一句话总结

当前代码已经从“可用的记忆服务”升级为“更稳定、更可审计、可灰度发布”的长期记忆系统：  
在**持久化、检索质量、审计治理、部署门禁、跨平台联调**五个方面都有实质增强。

---

## 3. 已落地改进清单（按读者最关心的维度）

| 维度 | 现在代码的真实改进 | 关键实现锚点 |
|---|---|---|
| 数据可靠性 | 增加了自动迁移与并发迁移锁，降低“版本升级后库结构不一致”的风险。 | `backend/db/migration_runner.py`、`backend/db/migrations/0001_add_vitality_and_support_tables.sql` |
| 启动兼容性 | 启动时可自动识别历史数据库文件名，减少升级后“找不到数据”的概率。 | `backend/main.py` |
| 写入安全（核心） | 写入前统一经过 `write_guard`，按“语义/关键词/可选 LLM”决策，异常路径按 fail-closed 处理。 | `backend/db/sqlite_client.py`、`backend/mcp_server.py`、`backend/api/browse.py` |
| 读写边界更清晰 | 修复了读接口潜在副作用风险，`GET /browse/node` 走无副作用读取口径。 | `backend/api/browse.py`、`backend/tests/test_browse_read_side_effects.py` |
| 检索更“懂问题” | 增加 query 预处理、意图分类和策略模板；支持 `scope_hint`，减少“查得多但不准”。 | `backend/db/sqlite_client.py`、`backend/mcp_server.py`、`backend/api/maintenance.py` |
| 长上下文治理 | `compact_context` + `gist` 链路完善，摘要写入可追踪、可降级、可审计。 | `backend/mcp_server.py`（`generate_gist`/`compact_context`）、`backend/db/sqlite_client.py` |
| 系统级可读性 | 新增 `system://audit` 与 `system://index-lite`，对系统状态和轻量索引更友好。 | `backend/mcp_server.py` |
| 生命周期治理 | 增加 vitality 衰减、候选查询、prepare/confirm 审批式清理，减少误删。 | `backend/runtime_state.py`、`backend/api/maintenance.py` |
| 任务治理 | 索引任务支持状态查询、取消、重试，队列状态更可观测。 | `backend/api/maintenance.py`（`/index/job/{job_id}/retry` 等） |
| 高风险能力改成“默认保守” | 外部导入、自动学习、provider 链、sqlite-vec、WAL 等都走默认关闭 + 分阶段门禁。 | `docs/improvement/implementation_plan.md`、`docs/improvement/hold_items_next_step_plan.md` |
| 部署与联调更稳 | `run_post_change_checks.sh` 增加 `runtime-env-mode`、profile 门禁、docker smoke；避免假绿。 | `new/run_post_change_checks.sh` |
| 跨平台一致性 | macOS/Linux 与 Windows 一键脚本都支持受控 runtime 注入，减少“同配置不同结果”。 | `scripts/docker_one_click.sh`、`scripts/docker_one_click.ps1` |
| C/D 本地联调效率 | 当本机 router 没有 embedding/reranker 时，可显式注入外部 `.env`，并同步 LLM（`gpt-5.2`）键。 | `new/run_post_change_checks.sh`、`docs/DEPLOYMENT_PROFILES.md` |
| 测试与质量门禁 | 已形成 small/profile/full 三层检查思路，并沉淀 benchmark 与回归产物。 | `new/verification_log.md`、`backend/tests/benchmark/`、`.github/workflows/` |

---

## 4. 当前版本“没有放开”的边界（避免误解）

以下能力并非“已全面上线默认开启”，而是**受控推进**：

1. `#5` 外部导入：默认关闭，先满足鉴权/白名单/审计/回滚。
2. `#6` 自动学习触发器：仅允许显式触发，不允许隐式自动写入。
3. `#11` Embedding provider 链：默认关闭，先保兼容再谈切换。
4. `#12` sqlite-vec：已做验证与修复，但仍按 `HOLD` 管理（默认不强开）。
5. `#13` WAL 写优化：先看一致性指标，再决定灰度放量。
6. `#7` MMR 与 `#14` intent LLM：目前仍按实验开关管理，未作为默认行为强推。

参考：`docs/improvement/implementation_plan.md`、`docs/improvement/hold_items_next_step_plan.md`

---

## 5. 是否偏离项目初衷

结论：**没有偏离，反而更贴近初衷**。  
项目初衷是“给 AI Agent 提供持久化、可检索、可审计的长期记忆能力”。  
当前改进重点正是：

1. 持久化更稳（迁移、兼容、回滚）。
2. 检索更准（意图路由、scope、重排链路治理）。
3. 审计更清楚（audit URI、observability、任务与写入留痕）。
4. 发布更安全（默认保守、分层门禁、跨平台一致脚本）。

这四点都在增强“长期记忆操作系统”能力，而不是转向另一个产品方向。
