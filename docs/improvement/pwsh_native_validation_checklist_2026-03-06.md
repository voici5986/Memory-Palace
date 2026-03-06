# PowerShell / Windows 专项验证清单（2026-03-06）

## 1. 目标

本清单用于在 **原生 Windows / 原生 `pwsh`** 环境中补齐专项验证，重点确认：

- `scripts/apply_profile.ps1` 不再生成重复 env key
- `scripts/docker_one_click.ps1` 在 `b/c/d` 档位的参数处理与 Docker 链路稳定
- `pwsh-in-docker` 等效 smoke 已通过后，原生 `pwsh` 口径也可复现

---

## 2. 前置条件

- 已安装 `pwsh`
- 已安装 `Docker Desktop`
- 当前仓库位于本机可写目录
- 如需本地 `c/d` 联调，准备可用的 runtime env 文件：
  - `/Users/yangjunjie/Desktop/clawmemo/nocturne_memory/.env`（本仓当前验证口径）
  - 或你自己机器上的等价 `.env`

---

## 3. 核心验证命令

### 3.1 `apply_profile.ps1` 重复键验证

```powershell
cd <repo>/Memory-Palace
pwsh -NoLogo -NoProfile -File .\scripts\apply_profile.ps1 -Platform windows -Profile c -Target "$env:TEMP\mp-win-c.env"
```

```powershell
Get-Content "$env:TEMP\mp-win-c.env" |
  Where-Object { $_ -match '^[A-Z0-9_]+=' } |
  ForEach-Object { ($_ -split '=', 2)[0] } |
  Group-Object |
  Where-Object { $_.Count -gt 1 }
```

**预期结果**

- 命令成功退出
- 重复键检查无输出
- `DATABASE_URL`、`RETRIEVAL_EMBEDDING_BACKEND`、`RETRIEVAL_RERANKER_ENABLED`、`SEARCH_DEFAULT_MODE` 仅保留 1 份最终值

### 3.2 `docker_one_click.ps1` 档位 B 烟测

```powershell
cd <repo>/Memory-Palace
pwsh -NoLogo -NoProfile -File .\scripts\docker_one_click.ps1 -Profile b -NoBuild
```

**预期结果**

- `.env.docker` 成功生成
- `docker compose` 成功启动前后端
- `http://localhost:3000/` 可访问
- `http://localhost:18000/health` 返回 `200`

### 3.3 档位 C 本地 file-mode 联调

```powershell
cd <repo-root>
bash new/run_post_change_checks.sh --with-docker --docker-profile c --skip-sse --runtime-env-mode file --runtime-env-file /Users/yangjunjie/Desktop/clawmemo/nocturne_memory/.env --allow-runtime-env-debug
```

**预期结果**

- `deployment.docker.smoke` 为 `PASS`
- `observability.search probe` 中 `degraded=False`
- `.env.docker` 中实际写入 embedding / reranker / LLM 字段

### 3.4 档位 D 本地注入口径联调

```powershell
cd <repo-root>
bash new/run_post_change_checks.sh --with-docker --docker-profile d --skip-sse --runtime-env-mode none --allow-runtime-env-injection --runtime-env-file /Users/yangjunjie/Desktop/clawmemo/nocturne_memory/.env
```

**预期结果**

- `deployment.docker.smoke` 为 `PASS`
- `deployment.windows_equivalent_pwsh_docker` 为 `PASS`
- `profile_d.assertions_passed=true`

---

## 4. 失败时优先排查

### 4.1 `apply_profile.ps1` 仍有重复键

- 先检查 `scripts/apply_profile.ps1` 是否包含 `Dedupe-EnvKeys`
- 再检查目标文件是否被手工二次 append

### 4.2 `docker_one_click.ps1` 失败

- 检查 Docker daemon 是否可用
- 检查端口 `3000/18000` 是否被占用
- 检查 `ComposeArgs` 参数是否完整传递

### 4.3 `c/d` 出现 placeholder / fail-closed

- 检查 runtime env 文件是否真的包含：
  - `ROUTER_API_BASE`
  - `ROUTER_API_KEY`
  - `RETRIEVAL_EMBEDDING_*`
  - `RETRIEVAL_RERANKER_*`
  - `WRITE_GUARD_LLM_*`
  - `COMPACT_GIST_LLM_*`
- 检查 `.env.docker` 是否仍残留 `https://<your-router-host>/v1` / `replace-with-your-key`

### 4.4 `pwsh-in-docker` / helper 失败

- 检查 `chat_probe_assertion.passed`
- 检查 `profile_c.assertions_passed` 与 `profile_d.assertions_passed`
- 若只有 helper chat probe 失败，但 `profile_c/profile_d assertions_passed=true`，优先看 helper 网络/端口，不要直接判定主链路回归

---

## 5. 本轮已知通过锚点

- `new/release_gate_log.md`
  - `20260306T021644Z-pid69739-r7682`：`profile a`
  - `20260306T022819Z-pid90525-r24653`：`profile b`
  - `20260306T022618Z-pid84541-r26048`：`profile c`
  - `20260306T021208Z-pid59119-r21971`：`profile d` 注入口径
- `new/verification_log.md`
  - `deployment.windows_equivalent_pwsh_docker - PASS`
  - `deployment.docker.smoke - PASS`

