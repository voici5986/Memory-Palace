# 发布说明 / 变更摘要（相对旧项目）

> 对比对象：
>
> - 旧项目：`/Users/yangjunjie/Desktop/old/Memory-Palace`
> - 当前项目：`/Users/yangjunjie/Desktop/clawanti/Memory-Palace`
>
> 说明：
>
> - 本文同时参考**旧项目文档**、**当前项目真实代码**、**当前项目真实测试结果**。
> - 这里只写**已落地、已验证**的内容；不把规划项写成已上线能力。
> - Windows 口径当前仅完成 `pwsh-in-docker` 等效验证，**未完成原生 Windows / native `pwsh` 终验**。

---

## 1. 一句话结论

当前版本相对旧项目，已经从“可用的长期记忆服务”升级为“**检索质量更强、运行时治理更完整、部署门禁更严格、文档与验证链更可审计**”的版本。

如果只看**真实代码 + 真实验证**，本轮升级主线已经**基本完成**；如果要求“所有平台原生最终签收”，则仍差 **原生 Windows / native `pwsh`** 这一项。

---

## 2. 本次发布最重要的结论

### 2.1 与旧项目相比，确定增强的地方

1. **高干扰检索质量显著提升**
   - 旧新同口径对比显示：
     - `s8,d200`：C/D 的 `HR@10` 从 `0.313/0.375` 提升到 `0.563/0.625`
     - `s100,d200`：C/D 的 `HR@10` 从 `0.280/0.295` 提升到 `0.580/0.615`
   - 低难场景 `s8,d10` 持平，没有夸大。
   - 证据：`Memory-Palace/docs/improvement/evaluation_old_vs_new_improvement_report_2026-03-05.md`

2. **部署链路比旧项目更安全、更可并发**
   - `docker compose` 不再只依赖固定 `.env.docker`，而是接通独立 `MEMORY_PALACE_DOCKER_ENV_FILE`
   - `docker_one_click` shell / PowerShell 都增加了 checkout 级部署锁，减少同仓并发时 profile 串写、串配的风险
   - 证据：`Memory-Palace/docker-compose.yml`、`Memory-Palace/scripts/docker_one_click.sh`、`Memory-Palace/scripts/docker_one_click.ps1`

3. **验证门禁明显更成熟**
   - `new/run_post_change_checks.sh` 已形成按 profile、按 runtime mode、按 Docker 实际 smoke 的门禁链
   - 增加了：
     - `review_snapshot_chain_contract`
     - `docs.skills_mcp_contract`
     - `deployment.windows_equivalent_pwsh_docker`
     - root-shell guard / workspace lock
   - 证据：`new/run_post_change_checks.sh`

4. **`pwsh` 等效 Windows 链路更稳**
   - `run_pwsh_docker_real_test.sh` 现在使用 per-run 临时结果文件
   - 明确透传 `PWSH_RUN_TOKEN`
   - 结果复制到目标输出后会清理临时 JSON
   - 对当前 `arm64` 主机，不再把不可执行环境误记成 `FAIL`
   - 证据：`new/run_pwsh_docker_real_test.sh`

5. **Benchmark / 回归链路比旧项目更可并发**
   - profile real runner 默认生成唯一 `run-*` workdir
   - 避免多次 benchmark 共用一个缓存目录产生互踩
   - 证据：`Memory-Palace/backend/tests/benchmark/helpers/profile_abcd_real_runner.py`

6. **错误语义更适合前后端协作**
   - `/review` 相关接口的 `500` 已统一为结构化 `internal_error` payload
   - 避免直接把 Python 内部异常细节暴露到前端或调用方
   - 证据：`Memory-Palace/backend/api/review.py`

---

## 3. 旧项目文档 vs 当前真实代码：主要差异

### 3.1 旧项目文档能表达的能力，当前项目基本都还在

- FastAPI + SQLite 后端主架构仍在
- 前端 Dashboard 仍在，且页面能力更完整
- Docker 部署、A/B/C/D profiles、MCP 工具主链路仍在
- 旧项目的长期记忆定位没有改变

### 3.2 当前项目相对旧项目，多出来的“已落地能力”

1. **更强的评测与对比文档**
   - 新增旧新对比、重基线评估、扩展消融、HOLD 路线、实施基线等文档
   - 典型文件：
     - `Memory-Palace/docs/improvement/implementation_plan.md`
     - `Memory-Palace/docs/improvement/evaluation_rebaseline_assessment_2026-03-04.md`
     - `Memory-Palace/docs/improvement/evaluation_ablation_results_2026-03-04.md`
     - `Memory-Palace/docs/improvement/evaluation_old_vs_new_improvement_report_2026-03-05.md`

2. **更完整的工作区级工程记录**
   - 新增 `llmdoc/`，把“代码现状、验证锚点、部署事实、产物说明”集中管理
   - 典型文件：
     - `llmdoc/index.md`
     - `llmdoc/reference/phase-status.md`
     - `llmdoc/overview/new-artifacts.md`

3. **快照与技能文档沉淀**
   - 新项目已有 `snapshots/` 实际产物
   - `docs/skills/` 已提供策略层文档
   - 典型文件：
     - `Memory-Palace/snapshots/.../manifest.json`
     - `Memory-Palace/docs/skills/MEMORY_PALACE_SKILLS.md`

4. **测试面明显扩展**
   - 新增了 hold contract、review rollback、profile real runner、benchmark CI isolation、pwsh helper 契约等测试
   - 典型文件：
     - `Memory-Palace/backend/tests/test_phase_d_hold_contracts.py`
     - `Memory-Palace/backend/tests/test_review_rollback.py`
     - `Memory-Palace/backend/tests/benchmark/test_profile_abcd_real_runner.py`
     - `Memory-Palace/backend/tests/benchmark/test_phase7_ci_isolation_contract.py`

---

## 4. 当前版本的真实验证结果

### 4.1 全量 / 主套件

- 后端全量：`410 passed`
- Benchmark 套件：`56 passed`
- 前端测试：`54 passed`
- 前端构建：`PASS`
- 发布前检查：`PASS`

### 4.2 Docker / Profile

- `profile a`：真实 Docker 门禁通过
- `profile b`：真实 Docker 门禁通过
- `profile c`：
  - `file-mode + /Users/yangjunjie/Desktop/clawmemo/nocturne_memory/.env` 通过
  - `runtime-env-mode none` 继续按预期 `fail-closed`
- `profile d`：
  - `file-mode + /Users/yangjunjie/Desktop/clawmemo/nocturne_memory/.env` 通过
  - `runtime-env-mode none` 继续按预期 `fail-closed`

### 4.3 Windows 口径

- 已完成：`pwsh-in-docker` 等效验证
- 未完成：原生 Windows / native `pwsh` 最终签收

---

## 5. 当前版本的边界（避免误解）

以下内容不应在发布说明里写成“已全面完成所有平台最终签收”：

1. **原生 Windows**
   - 当前没有在原生 Windows / native `pwsh` 上复跑
   - 所以只能说“已完成 Docker 等效 Windows 验证”

2. **绝对无隐性 bug**
   - 本轮已经完成当前可执行范围内的全面回归
   - 但工程上不能诚实承诺“绝对没有任何隐性 bug”

3. **所有 HOLD 项已经上线**
   - 不能这样写
   - 仍应保持“有些能力是受控推进 / 默认保守 / 默认关闭”的口径

---

## 6. 对外建议表述

建议使用下面这段表述：

> 当前版本已完成一轮以真实代码、真实门禁和真实 benchmark 为基础的升级收口。  
> 相对旧项目，检索质量、部署隔离、门禁验证、`pwsh` 等效 Windows 链路和 benchmark 并发稳定性均有实质提升。  
> 当前已完成 macOS + Docker + `pwsh-in-docker` 等效 Windows 验证；原生 Windows / native `pwsh` 终验尚未执行，因此该部分仍保留为外部环境补充项。

不建议使用下面这类表述：

- “已经完成所有平台原生最终签收”
- “已经证明没有任何隐性 bug”
- “所有规划项都已经上线”

---

## 7. 关键实现锚点

- 部署 env 参数化：`Memory-Palace/docker-compose.yml`
- Shell 部署锁：`Memory-Palace/scripts/docker_one_click.sh`
- PowerShell 部署锁：`Memory-Palace/scripts/docker_one_click.ps1`
- 验证门禁主脚本：`new/run_post_change_checks.sh`
- `pwsh` 等效 helper：`new/run_pwsh_docker_real_test.sh`
- benchmark 唯一 workdir：`Memory-Palace/backend/tests/benchmark/helpers/profile_abcd_real_runner.py`
- review 结构化 500：`Memory-Palace/backend/api/review.py`
- 旧新评测报告：`Memory-Palace/docs/improvement/evaluation_old_vs_new_improvement_report_2026-03-05.md`
- 工程事实索引：`llmdoc/reference/phase-status.md`

