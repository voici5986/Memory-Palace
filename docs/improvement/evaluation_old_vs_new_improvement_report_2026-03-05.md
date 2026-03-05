# 新仓库相对旧仓库评测提升报告（2026-03-05）

## 1. 一句话结论

在同口径对比下，**新仓库在高难场景（高干扰、小样本和大样本）检索质量显著提升**；在低难场景（`s8,d10`）质量持平。  
因此可得出结论：**当前新仓修改后项目整体检索能力优于旧仓修改前项目**，尤其体现在真实复杂检索场景。

---

## 2. 测试目标

本次测试要回答一个问题：

- 新仓库（`/Users/yangjunjie/Desktop/clawanti/Memory-Palace`）相比旧仓库（`/Users/yangjunjie/Desktop/clawmemo/nocturne_memory`）是否有实质提升？

重点关注指标：

- `HR@10`
- `MRR`
- `NDCG@10`
- 参考延迟：`p95(ms)`

---

## 3. 测试口径与公平性说明

### 3.1 公平对齐口径（主结论依据）

旧仓真实 A/B/C/D runner 固定使用：

- `max_results=10`
- `candidate_multiplier=4`（旧仓代码固定值）

因此为了公平比较，主对比采用：

- `sample_size`、`extra_distractors` 完全一致
- 新仓使用 `candidate_multiplier=4` 与旧仓对齐
- 同一套外部环境变量（`/Users/yangjunjie/Desktop/clawmemo/nocturne_memory/.env`）

### 3.2 能力上限补充口径

另外补充新仓增强配置：

- `s100,d200,candidate_multiplier=8`（新仓 3 次重复，取均值）

这部分用于说明“新仓改动后可达上限”，不替代公平对齐结论。

---

## 4. 测试场景

本次覆盖三类场景：

1. `s8,d10`（低难）
2. `s8,d200`（高干扰）
3. `s100,d200`（高干扰 + 大样本）

其中 `C/D` 为核心关注档位（API embedding / reranker 路径）。

---

## 5. 结果总览（公平对齐：新旧均为 cm=4）

### 5.1 质量指标（C/D）

| 场景 | 仓库 | C: HR@10 / MRR / NDCG@10 | D: HR@10 / MRR / NDCG@10 |
|---|---|---|---|
| `s8,d10` | 旧仓 | `0.875 / 0.783 / 0.805` | `0.875 / 0.825 / 0.837` |
| `s8,d10` | 新仓 | `0.875 / 0.783 / 0.805` | `0.875 / 0.825 / 0.837` |
| `s8,d200` | 旧仓 | `0.313 / 0.313 / 0.313` | `0.375 / 0.375 / 0.375` |
| `s8,d200` | 新仓 | `0.563 / 0.563 / 0.563` | `0.625 / 0.625 / 0.625` |
| `s100,d200` | 旧仓 | `0.280 / 0.247 / 0.255` | `0.295 / 0.268 / 0.275` |
| `s100,d200` | 新仓 | `0.580 / 0.512 / 0.529` | `0.615 / 0.560 / 0.573` |

### 5.2 关键提升幅度（公平对齐）

#### `s8,d200`

- C: `HR@10 +0.250`（`0.313 -> 0.563`，约 `+80.0%`）
- D: `HR@10 +0.250`（`0.375 -> 0.625`，约 `+66.7%`）

#### `s100,d200`

- C: `HR@10 +0.300`（`0.280 -> 0.580`，约 `+107.1%`）
- D: `HR@10 +0.320`（`0.295 -> 0.615`，约 `+108.5%`）

#### `s8,d10`

- C/D 质量指标与旧仓一致（持平，无回退）

---

## 6. 延迟观察（p95，公平对齐）

| 场景 | 仓库 | C p95(ms) | D p95(ms) |
|---|---|---:|---:|
| `s8,d10` | 旧仓 | 474.5 | 2103.2 |
| `s8,d10` | 新仓 | 639.5 | 2088.2 |
| `s8,d200` | 旧仓 | 945.8 | 2507.1 |
| `s8,d200` | 新仓 | 1150.9 | 2428.8 |
| `s100,d200` | 旧仓 | 1027.8 | 2796.5 |
| `s100,d200` | 新仓 | 937.6 | 2772.0 |

解读：

- 新仓主要提升体现在质量，不是“所有场景都更低延迟”。
- `s100,d200` 下新仓 `cm=4` 的 C/D 延迟与旧仓接近或略优。

---

## 7. 新仓增强能力（cm=8，补充）

新仓 `s100,d200,cm=8` 连续 3 次均值：

- C: `HR@10=0.700, MRR=0.607, NDCG@10=0.630`
- D: `HR@10=0.720, MRR=0.651, NDCG@10=0.668`

相对新仓 `cm=4`（同场景）进一步提升明显，但 D 侧 p95 时延增加较大（质量-时延权衡）。

稳定性（3 次重复）：

- 质量方差极小（`HR@10` 近乎 0 波动）
- `phase6` 门禁均有效（`valid=true`）

---

## 8. 严谨结论

基于同口径实测结果，可给出以下结论：

1. **高难场景提升明确且幅度大**：`s8,d200` 与 `s100,d200` 均显著优于旧仓。  
2. **低难场景不夸大**：`s8,d10` 与旧仓持平，不宣称该场景有提升。  
3. **总体判断成立**：若关注真实复杂检索（更大样本、更高干扰），新仓修改后项目确实优于旧仓。  

结论置信度：

- “高难场景有显著提升”：`High`
- “所有配置全部提升”：`Low`（证据不支持，`s8,d10` 为持平）

---

## 9. 复现命令（核心）

### 9.1 旧仓（公平口径）

```bash
cd /Users/yangjunjie/Desktop/clawmemo/nocturne_memory/backend
set -a; source /Users/yangjunjie/Desktop/clawmemo/nocturne_memory/.env; set +a
python tests/benchmark/run_profile_abcd_real.py --sample-size 100 --extra-distractors 200 --output-json tests/benchmark/profile_abcd_real_metrics_s100_d200_old_r1.json
```

### 9.2 新仓（公平口径）

```bash
cd /Users/yangjunjie/Desktop/clawanti/Memory-Palace/backend
set -a; source /Users/yangjunjie/Desktop/clawmemo/nocturne_memory/.env; set +a
export BENCHMARK_PHASE6_GATE_MODE=api_tolerant
export BENCHMARK_PHASE6_INVALID_RATE_THRESHOLD=0.05
python tests/benchmark/run_profile_abcd_real.py --sample-size 100 --extra-distractors 200 --candidate-multiplier 4 --output-json tests/benchmark/profile_abcd_real_metrics_s100_d200_new_cm4_r1.json
```

### 9.3 新仓（增强口径）

```bash
cd /Users/yangjunjie/Desktop/clawanti/Memory-Palace/backend
set -a; source /Users/yangjunjie/Desktop/clawmemo/nocturne_memory/.env; set +a
export BENCHMARK_PHASE6_GATE_MODE=api_tolerant
export BENCHMARK_PHASE6_INVALID_RATE_THRESHOLD=0.05
python tests/benchmark/run_profile_abcd_real.py --sample-size 100 --extra-distractors 200 --candidate-multiplier 8 --output-json tests/benchmark/profile_abcd_real_metrics_s100_d200_cm8_r1.json
```

---

## 10. 关键证据文件

- 旧仓 `s8,d10`：[profile_abcd_real_metrics_s8_d10_old_r1.json](/Users/yangjunjie/Desktop/clawmemo/nocturne_memory/backend/tests/benchmark/profile_abcd_real_metrics_s8_d10_old_r1.json)
- 新仓 `s8,d10,cm4`：[profile_abcd_real_metrics_s8_d10_new_cm4_r1.json](/Users/yangjunjie/Desktop/clawanti/Memory-Palace/backend/tests/benchmark/profile_abcd_real_metrics_s8_d10_new_cm4_r1.json)
- 旧仓 `s8,d200`：[profile_abcd_real_metrics_s8_d200_old_r1.json](/Users/yangjunjie/Desktop/clawmemo/nocturne_memory/backend/tests/benchmark/profile_abcd_real_metrics_s8_d200_old_r1.json)
- 新仓 `s8,d200,cm4`：[profile_abcd_real_metrics_s8_d200_new_cm4_r1.json](/Users/yangjunjie/Desktop/clawanti/Memory-Palace/backend/tests/benchmark/profile_abcd_real_metrics_s8_d200_new_cm4_r1.json)
- 旧仓 `s100,d200`：[profile_abcd_real_metrics_s100_d200_old_r1.json](/Users/yangjunjie/Desktop/clawmemo/nocturne_memory/backend/tests/benchmark/profile_abcd_real_metrics_s100_d200_old_r1.json)
- 新仓 `s100,d200,cm4`：[profile_abcd_real_metrics_s100_d200_new_cm4_r1.json](/Users/yangjunjie/Desktop/clawanti/Memory-Palace/backend/tests/benchmark/profile_abcd_real_metrics_s100_d200_new_cm4_r1.json)
- 新仓 `s100,d200,cm8` 三次重复：  
  [r1](/Users/yangjunjie/Desktop/clawanti/Memory-Palace/backend/tests/benchmark/profile_abcd_real_metrics_s100_d200_cm8_r1.json)  
  [r2](/Users/yangjunjie/Desktop/clawanti/Memory-Palace/backend/tests/benchmark/profile_abcd_real_metrics_s100_d200_cm8_r2.json)  
  [r3](/Users/yangjunjie/Desktop/clawanti/Memory-Palace/backend/tests/benchmark/profile_abcd_real_metrics_s100_d200_cm8_r3.json)

