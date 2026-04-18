# Memory Palace 评测结果

本文档汇总 Memory Palace 各档位（A/B/C/D）的检索质量、延迟与语义质量门禁测试结果。这里保留**摘要表 + 复核说明**；公开仓库会保留 `backend/tests/benchmark/` 下的 benchmark helpers 与测试入口，机器相关的原始 benchmark 日志、一次性门禁草稿、阶段性重测记录以及部分指标 JSON 默认只在开发阶段或本地使用。

> 状态说明（2026-04）：本页保留 2026-02 的公开基线表格，同时把 2026-04-18 的当前 rerun 和本 session 的真实验证范围收口到公开口径里。当前交互默认档位、深检索档位和新的门禁项，请优先看本页第 3 节和第 4 节。

---

## 1. 数据来源

| 来源 | 说明 |
|---|---|
| 本页公开摘要表 | 面向用户保留的 A/B/C/D 关键指标和门禁结果 |
| `backend/tests/benchmark/` 下的公开 benchmark helpers 与测试用例 | 用于理解评测口径；具体指标文件通常仍以维护阶段或本地复核产物为主 |
| 维护期 benchmark 产物 | 一次性重测日志、门禁草稿和本机运行结果；默认不随用户仓分发 |
| 当前发布说明 | `docs/changelog/release_v3.7.1_2026-03-26.md` |
| 发布对比摘要 | `docs/changelog/release_summary_vs_old_project_2026-03-06.md` |

> 数据生成时间：`2026-02-19T06:55:30+00:00`（早期门禁基线）/ `2026-04-18`（本 session rerun）

---

## 1.5 这些指标到底在看什么？

先说人话：

- **HR@10**：前 10 条结果里，**有没有**把正确答案找出来。越高越好。
- **MRR**：正确答案排得**靠不靠前**。越靠前，分数越高。
- **NDCG@10**：不只看“找没找到”，还看**排序整体好不好**。越高越好。
- **Recall@10**：如果一条查询可能有多个相关结果，它看前 10 条里**覆盖了多少**。越高越好。
- **p50 / p95**：响应时间。`p50` 可以理解成“平时大多数请求有多快”，`p95` 可以理解成“慢的时候大概慢到什么程度”。
- **降级率**：系统因为外部 embedding / reranker 不可用而退回低配模式的比例。越低越好。

如果你只想快速看表，优先看这三个：

1. **HR@10**：能不能找到
2. **MRR**：找到了以后排得靠不靠前
3. **p95**：最慢那批请求慢不慢

---

## 2. 检索评测（A/B/CD 小样本门禁）

**来源**：`profile_ab_metrics.json`（`sample_size=100`，每档 3 个数据集 × 100 条查询；通常由 `backend/tests/benchmark/` 下的 benchmark helpers 在维护阶段生成）

| 档位 | 模式 | 数据集 | HR@10 | MRR | NDCG@10 | Recall@10 | p50(ms) | p95(ms) | 降级率 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| A | keyword | MS MARCO | 0.333 | 0.333 | 0.333 | 0.333 | 1.2 | 2.1 | 0.0% |
| A | keyword | BEIR NFCorpus | 0.300 | 0.300 | 0.300 | 0.300 | 1.6 | 2.6 | 0.0% |
| A | keyword | SQuAD v2 Dev | 0.150 | 0.150 | 0.150 | 0.150 | 1.2 | 3.0 | 0.0% |
| B | hybrid | MS MARCO | 0.867 | 0.658 | 0.696 | 0.850 | 3.4 | 3.7 | 0.0% |
| B | hybrid | BEIR NFCorpus | 1.000 | 0.828 | 0.850 | 0.975 | 4.1 | 4.7 | 0.0% |
| B | hybrid | SQuAD v2 Dev | 1.000 | 0.765 | 0.822 | 1.000 | 3.2 | 3.9 | 0.0% |
| CD | hybrid | （与 B 同配置基线） | 同 B | 同 B | 同 B | 同 B | 同 B | 同 B | 0.0% |

> **说明**：CD 门禁使用与 B 相同的 hash embedding 基线运行，目的是验证 hybrid 检索路径的正确性。

---

## 3. 检索评测（真实 A/B/C/D 运行）

**来源**：`profile_abcd_real_metrics.json`（`sample_size_requested=8`，2 个数据集 × 8 条查询；通常由 `backend/tests/benchmark/` 下的 benchmark helpers 在维护阶段生成）

策略：每条查询按 `first_relevant_only=true` 仅保留首个相关文档，额外灌入 `200` 条干扰文档，`candidate_multiplier=8`，随机种子 `20260219`。

| 档位 | 数据集 | HR@10 | MRR | NDCG@10 | p50(ms) | p95(ms) | Gate |
|---|---|---:|---:|---:|---:|---:|---|
| A | SQuAD v2 Dev | 0.000 | 0.000 | 0.000 | 5.179 | 7.920 | ✅ PASS |
| A | BEIR NFCorpus | 0.250 | 0.250 | 0.250 | 8.218 | 13.576 | ✅ PASS |
| B | SQuAD v2 Dev | 0.125 | 0.062 | 0.079 | 33.801 | 52.227 | ✅ PASS |
| B | BEIR NFCorpus | 0.250 | 0.250 | 0.250 | 40.857 | 44.675 | ✅ PASS |
| C | SQuAD v2 Dev | 1.000 | 0.896 | 0.920 | 219.999 | 298.780 | ✅ PASS |
| C | BEIR NFCorpus | 0.625 | 0.531 | 0.554 | 212.338 | 259.681 | ✅ PASS |
| D | SQuAD v2 Dev | 1.000 | 0.896 | 0.920 | 2452.644 | 2764.629 | ✅ PASS |
| D | BEIR NFCorpus | 0.750 | 0.656 | 0.679 | 3155.158 | 3409.331 | ✅ PASS |

> **说明**：
>
> - `Profile B` 仍然是**默认交互档**：延迟最低，适合 CLI / IDE 日常 recall。
> - `Profile C` 是**显式深检索档**：质量明显高于 B，p95 仍在百毫秒级。
> - `Profile D` 仍然是**最高质量档**：质量最高，但 p95 已到秒级，只适合“质量优先于时延”的场景。
> - C/D 为真实外部 embedding + reranker 链路调用，延迟显著高于本地 keyword/hash 档位。
> - 这轮 C/D 指标是基于**运行时注入的、用户显式提供的 embedding 维度**得到的；公开模板现在不再发布 `4096` 这类猜测默认值。
> - 当前 real runner 还会把**查询阶段**与**建索引阶段**的降级一起记进公开门禁口径；如果 reranker 缺配置、响应无效，或索引阶段已经 fallback，这轮结果不会再被写成“干净 PASS”。
> - 这轮结果是在**当前档位的有效 embedding 维度已经对齐**的前提下得到的，不表示你可以把 B 的旧向量和 C/D 的旧向量拿来直接混用；如果切档后维度不一致，当前运行时会返回 `embedding_dim_mismatch_requires_reindex` / `vector_dim_mismatch_requires_reindex`，需要重建索引或分开数据库。
> - 所有 Phase 6 Gate 均为 PASS，表明当前公开档位在这轮复核里没有出现失效或请求失败。

### 3.1 这轮 2026-04-17 复核该怎么读

- 如果你只想要**默认推荐**：选 `Profile B`。
- 如果你明确知道自己在做**深检索 / 高质量优先**：显式切到 `Profile C` 或 `Profile D`。
- `Profile C` 和 `Profile D` 都不是默认 recall 档，它们是按需打开的深检索档。

按两个数据集做均值之后，这轮公开复核的摘要是：

| 档位 | Avg HR@10 | Avg MRR | Avg NDCG@10 | Avg Recall@10 | Avg p95(ms) |
|---|---:|---:|---:|---:|---:|
| A | 0.125 | 0.125 | 0.125 | 0.125 | 10.7 |
| B | 0.188 | 0.156 | 0.164 | 0.188 | 48.5 |
| C | 0.812 | 0.714 | 0.737 | 0.812 | 279.2 |
| D | 0.875 | 0.776 | 0.799 | 0.875 | 3087.0 |

### 3.2 2026-04-18 当前 rerun（本 session）

这轮 rerun 只覆盖 `squad_v2_dev`，参数是：

- `dataset_scope=squad_v2_dev`
- `sample_size=2`
- `extra_distractors=20`
- `candidate_multiplier=8`

它的作用很直接：确认当前代码和 `A/B/C/D` 四档 profile 还能按现在这套实现跑通，不拿它替代上面那组范围更大的公开基线。

| 档位 | 数据集 | HR@10 | NDCG@10 | p95(ms) |
|---|---|---:|---:|---:|
| A | SQuAD v2 Dev | 0.0 | — | 2.264 |
| B | SQuAD v2 Dev | 1.0 | 0.667 | 6.687 |
| C | SQuAD v2 Dev | 1.0 | 1.0 | 666.607 |
| D | SQuAD v2 Dev | 1.0 | 1.0 | 1261.532 |

这轮结果怎么读：

- `Profile B` 还是默认交互档，质量已经明显高于 A，延迟也还很低。
- `Profile C/D` 这轮质量都跑满了，但时延明显更高，属于按需打开的深检索档。
- `Profile A` 依旧只是低配兜底，不适合拿来代表语义检索质量。

## 3.5 旧版 vs 当前版本（同口径摘要）

下面这组数字来自一轮**同口径旧新对照复核**。这里保留摘要，不保留带本机路径的原始对照记录。

![旧版 vs 当前版本检索质量与延迟对比图](images/benchmark_comparison.png)

> 📈 这张图对应的是**旧版 vs 当前版本**在同口径下的对照结果。
>
> 读图时可以先看：
>
> - 左上 `HR@10`：前 10 条里有没有找到
> - 右下 `p95 latency`：慢的时候大概慢到什么程度
> - 页脚那行 `cm=8 avg`：表示新版把候选池继续放大后的上限表现

---

### 高干扰场景的核心结论

| 场景 | 指标 | 旧版 C | 新版 C | 旧版 D | 新版 D |
|---|---|---:|---:|---:|---:|
| `s8,d10` | `HR@10` | 0.875 | 0.875 | 0.875 | 0.875 |
| `s8,d200` | `HR@10` | 0.313 | 0.563 | 0.375 | 0.625 |
| `s100,d200` | `HR@10` | 0.280 | 0.580 | 0.295 | 0.615 |

### 更细一点看：MRR / NDCG@10

| 场景 | 指标 | 旧版 C | 新版 C | 旧版 D | 新版 D |
|---|---|---:|---:|---:|---:|
| `s8,d10` | `MRR / NDCG@10` | 0.783 / 0.805 | 0.783 / 0.805 | 0.825 / 0.837 | 0.825 / 0.837 |
| `s8,d200` | `MRR / NDCG@10` | 0.313 / 0.313 | 0.563 / 0.563 | 0.375 / 0.375 | 0.625 / 0.625 |
| `s100,d200` | `MRR / NDCG@10` | 0.247 / 0.255 | 0.512 / 0.529 | 0.268 / 0.275 | 0.560 / 0.573 |

### 怎么读这组数据

- `s8,d10`：低难度场景，**持平**
- `s8,d200`：干扰一多，新版提升就很明显
- `s100,d200`：样本更大、干扰更多时，新版依然明显更稳

一句话总结：

> 如果你关心的是真实复杂检索，而不是最简单的演示场景，那么当前版本相对旧版本确实更强。

### 这些参数顺手解释一下

- `s8,d10`：`s=sample_size`，`d=extra_distractors`。可以理解成“8 条样本 + 10 条干扰文档”。
- `s8,d200`：样本还是 8 条，但干扰文档拉到 200 条，更容易把真正结果淹没。
- `s100,d200`：100 条样本 + 200 条干扰文档，更接近真实复杂检索。
- `candidate_multiplier=4 / 8`：检索第一轮先放大候选池，再做后续排序。数字越大，通常**质量更有机会提升**，但**时延也更容易上去**。

### 延迟补充

| 场景 | 仓库 | C p95(ms) | D p95(ms) |
|---|---|---:|---:|
| `s8,d10` | 旧版 | 474.5 | 2103.2 |
| `s8,d10` | 新版 | 639.5 | 2088.2 |
| `s8,d200` | 旧版 | 945.8 | 2507.1 |
| `s8,d200` | 新版 | 1150.9 | 2428.8 |
| `s100,d200` | 旧版 | 1027.8 | 2796.5 |
| `s100,d200` | 新版 | 937.6 | 2772.0 |

这里也要说人话：

- 新版的主收益是**检索质量更高**
- 不是所有场景都更快
- 但在 `s100,d200` 这种更接近真实复杂检索的场景里，延迟并没有明显变坏

### 新版增强口径（补充）

在 `s100,d200` 场景下，如果把新版的 `candidate_multiplier` 从 `4` 调到 `8`，3 次重复均值为：

- C：`HR@10=0.700`、`MRR=0.607`、`NDCG@10=0.630`
- D：`HR@10=0.720`、`MRR=0.651`、`NDCG@10=0.668`

这说明新版还有进一步调优空间，但代价是更高的候选池和更高的时延。

---

## 4. 质量门禁（语义相关）

### Write Guard（写入守卫）

**来源**：`write_guard_quality_metrics.json`（通常由 benchmark helpers 在维护阶段生成）

| 指标 | 值 | 阈值 | 状态 |
|---|---:|---:|---|
| Precision | 1.000 | ≥ 0.90 | ✅ PASS |
| Recall | 1.000 | ≥ 0.85 | ✅ PASS |

- 总测试用例数：**6**（TP=4, FP=0, FN=0）
- 决策类型分布：`NOOP`×2, `UPDATE`×2, `ADD`×2
- 综合判定：**overall_pass = true**

怎么理解这组指标：

- **Precision（精确率）**：系统说“该拦 / 该改”的时候，判断有多准。越高越好。
- **Recall（召回率）**：真正该拦 / 该改的情况，它漏掉了多少。越高越好。
- 这组测试的目标不是看“文笔”，而是看 **Write Guard 会不会误拦、漏拦**。

### Intent 分类（查询意图识别）

**来源**：`intent_accuracy_metrics.json`（通常由 benchmark helpers 在维护阶段生成）

| 指标 | 值 | 阈值 | 状态 |
|---|---:|---:|---|
| Accuracy | 1.000 | ≥ 0.80 | ✅ PASS |

- 总测试用例数：**6**
- 分类方法：`keyword_scoring_v2`（纯规则，无外部模型依赖）
- 覆盖意图：`temporal`×2, `causal`×2, `exploratory`×1, `factual`×1
- 策略模板映射：
  - `temporal` → `temporal_time_filtered`
  - `causal` → `causal_wide_pool`
  - `exploratory` → `exploratory_high_recall`
  - `factual` → `factual_high_precision`

怎么理解：

- 这里测的不是“答得好不好”，而是系统能不能先判断出：这条查询更像**事实查询、探索查询、时间查询还是因果查询**。
- 判断对了，后面的检索策略才更容易选对。

### Gist 质量（上下文压缩摘要）

**来源**：`compact_context_gist_quality_metrics.json`（通常由 benchmark helpers 在维护阶段生成）

| 指标 | 值 | 阈值 | 状态 |
|---|---:|---:|---|
| ROUGE-L（均值） | 0.759 | ≥ 0.40 | ✅ PASS |

- 总测试用例数：**5**
- 各 case ROUGE-L 分布：

| Case | ROUGE-L |
|---|---:|
| gist-001 | 0.824 |
| gist-002 | 0.923 |
| gist-003 | 0.667 |
| gist-004 | 0.667 |
| gist-005 | 0.714 |

怎么理解：

- **ROUGE-L** 可以简单理解成：生成的 gist 和参考摘要在“关键内容重合度”上有多接近。
- 它不是“最终写作质量分”，而是看压缩后**有没有把关键意思留下来**。

### Prompt Safety（反射提示安全契约）

**来源**：`prompt_safety_contract_metrics.json`（通常由 benchmark helpers 在维护阶段生成）

| 指标 | 值 | 阈值 | 状态 |
|---|---:|---:|---|
| Contract pass rate | 1.000 | ≥ 1.000 | ✅ PASS |

- 关注点：system prompt 是否明确把输入当作不可信数据、是否强制 strict JSON 输出、基础 prompt payload 是否移除了控制字符。
- 这是**安全契约门禁**，不是模型能力评分；目标是保证 write guard / gist / intent 反射链路的 prompt 框架本身不退化。

### Reflection Lane（反射并发通道）

**来源**：`reflection_lane_metrics.json`（通常由 benchmark helpers 在维护阶段生成）

| Metric | Value | Threshold | Status |
|---|---:|---:|---|
| Timeout degrade correctness | 1 | = 1 | ✅ PASS |

- 关注点：反射 lane 在并发受限且获取超时时，是否仍然按预期返回 `reflection_lane_timeout` 并留下运行时指标。
- 关键观测字段包括：`tasks_total`、`tasks_failed`、`wait_ms_p95`、`duration_ms_p95`。
- 这条公开门禁覆盖的是反射的 `prepare/execute` 并发边界；真正的 rollback 路径仍以当前结果里返回的 endpoint 为准：prepare 阶段通常先给 `/maintenance/import/jobs/.../rollback`，执行后如果已经拿到 review snapshot，则会升级为 `/review/...`，同时保留 `/maintenance/learn/jobs/.../rollback` alias。

---

## 5. 如何复核当前公开口径

当前仓库里保留了 `backend/tests/benchmark/` 相关脚本和数据，但完整 benchmark 更耗时，也更偏维护 / 复核用途。

如果你只是想确认当前安装状态，建议使用下面这组最小检查：

```bash
bash scripts/pre_publish_check.sh
curl -fsS http://127.0.0.1:8000/health
```

如果你需要更深入的复现，当前仓库已经附带 `backend/tests/benchmark/` 下的 benchmark helpers 与测试用例；只有一次性维护产物和临时门禁脚本不作为公开文档主入口。

### 5.1 本 session 已实际复核到哪里

- Backend 非 benchmark 全量：`966 passed / 20 skipped`
- Frontend 全量：`165 passed`
- Frontend `typecheck` / `build`：通过
- repo-local live MCP e2e：通过
- repo-local `Profile B`：backend + frontend + 真实浏览器 setup/maintenance smoke 通过
- 本地 smoke：补跑了一条覆盖 `Profile C/D` 同类 retrieval / reranker / `write_guard` / gist 链路的验证
- Docker one-click `Profile C/D`：本轮未重跑，继续保留目标环境复核边界
- `skills+MCP` / `single-MCP`：本轮未重跑，这里不追加新结论

这里故意不把这轮结果写成“全链路全绿”。尤其是 `skills-only`，现在还只能写 PARTIAL，不能往上拔。

---

## 6. 结果解读与档位选择建议

| 档位 | 适用场景 | 优势 | 注意事项 |
|---|---|---|---|
| A | 低配环境、先跑通验证 | 延迟极低（p95 < 3ms） | 仅关键词匹配，语义召回有限 |
| B | 单机开发、日常调试、默认交互档 | 延迟最低，适合高频 recall | 使用本地 hash embedding，和 C/D 跨维度切换时不能直接复用旧向量 |
| C | 本地/私有模型服务优先的深检索 | 质量明显高于 B，延迟仍可控 | 切到 C 前要确认 embedding 维度对齐；若和旧索引维度不同，需要重建索引或分库 |
| D | API-first / 远程服务优先的质量档 | 质量最高 | 延迟最高（当前 p95 已到秒级），同样要避免和不同维度旧索引混用 |

> **上线建议**：固定一套 profile + 模型配置，长期追踪同一指标口径，避免跨档位混合比较。

---

## 7. 如何读这页评测

- 比较不同结果时，先确认 `profile`、数据集范围、样本量和模型配置一致。
- 如果 `profile c/d` 缺少可用的外部模型服务，可能出现 `embedding_request_failed` / `embedding_fallback_hash`；这代表外部链路未就绪，不等于主流程不可用。
- 如果你采用的是分别直配 `RETRIEVAL_EMBEDDING_*` 与 `RETRIEVAL_RERANKER_*` 的部署方式，也应只拿同一套最终配置做横向比较。
- 对外沟通时，优先引用本页已经整理好的摘要表和图；不要把不同口径的临时重测结果混在一起讲。
