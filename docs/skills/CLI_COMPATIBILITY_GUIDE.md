# Memory Palace CLI Compatibility Guide

## Summary

- `Claude Code`：完成 `sync/install` 后，可获得 **repo-local skill 自动发现** + **workspace MCP 直连**
- `Gemini CLI`：完成 `sync/install` 后，可获得 **repo-local skill 自动发现** + **workspace MCP 直连**
- `Codex CLI`：完成 `sync` 后，可获得 **repo-local skill 自动发现**；`MCP` 仍以 **user-scope 注册** 为主
- `OpenCode`：完成 `sync` 后，可获得 **repo-local skill 自动发现**；`MCP` 仍以 **user-scope 注册** 为主
- `IDE Hosts`（`Cursor / Windsurf / VSCode-host / Antigravity`）：主路径改为 **repo-local `AGENTS.md` + MCP snippet**，不再把 hidden skill mirrors 当默认入口
- 当前设计已对齐 `Anthropic skill-creator` 的核心要求：`frontmatter`、`trigger description`、`references`、`eval/smoke`

先补一句最容易误会的：

- 如果你只是通过 GHCR / Docker 把服务跑起来，`Dashboard / API / SSE` 已经可以工作
- 但这**不等于**本机上的 `Claude / Codex / Gemini / OpenCode / IDE host` 已经自动配好
- 当前这份兼容指南描述的是 **客户端接入层**

如果你不走 repo-local skill 安装链路，而是只想把客户端手工接到 Docker 的 `/sse`：

- 当前仓库已经提供了**通用 SSE MCP 骨架**
- 但不同客户端的字段名、GUI 入口、header 写法不完全一样
- 所以这份文档不会猜测各家 UI，而是把：
  - 服务端地址
  - 鉴权方式
  - 通用 JSON 结构
作为仓库文档的边界

当前仓库对“手工接远程 `/sse`”的公开口径是：

- `Claude Code`：可直接写
- `Gemini CLI`：可直接写
- `Codex CLI`：当前先保守，优先继续走 repo-local stdio 路径
- `OpenCode`：当前先保守，优先继续走 repo-local 路径

更具体的手工示例已经写到：

- `docs/GETTING_STARTED.md` 的 `6.3.1 ~ 6.3.4`

## 先分清两层

`memory-palace` 这套链路分成两层：

1. **skill 自动发现**
   - 负责让客户端知道“什么时候该进入 Memory Palace 工作流”
   - 主要由 `SKILL.md` 的 `frontmatter + description` 决定

2. **MCP 真正绑到当前仓库**
   - 负责让客户端真的调用当前仓库里的 `Memory-Palace` backend
   - 只看 skill 被发现还不够，必须确认 MCP 指向当前项目

所以判断“能不能直接用”，必须同时满足：

- skill 能被当前 CLI 发现
- MCP 确实指向当前仓库的 repo-local launcher
  - 原生 Windows：`backend/mcp_wrapper.py`
  - macOS / Linux / `Git Bash` / `WSL`：`scripts/run_memory_palace_mcp_stdio.sh`

再补一句最容易踩坑的：

- 这个 wrapper 会优先复用当前仓库 `.env` 里的 `DATABASE_URL`
- 如果某个客户端把 `DATABASE_URL` 传成空字符串，它也会按“没设置”处理，继续回退到当前仓库 `.env` 的有效值
- 如果那份 `.env` 还是 Docker 用的 `/app/...` 或 `/data/...` 容器路径，wrapper 也会直接拒绝启动
- 也就是说，只要你别手工乱改客户端命令，Dashboard / HTTP API / MCP 默认就是同一份数据库

## Current Local Baseline After Sync / Install

执行 `sync_memory_palace_skill.py` / `install_skill.py` 之后，通常会出现这些入口：

- `Claude Code`
  - `.claude/skills/memory-palace/`
  - `.mcp.json`
- `Codex CLI`
  - `.codex/skills/memory-palace/`
- `OpenCode`
  - `.opencode/skills/memory-palace/`
- `Gemini CLI`
  - `.gemini/skills/memory-palace/`
  - `.gemini/settings.json`
  - `.gemini/policies/memory-palace-overrides.toml`

对应的 canonical skill 真源是：

```text
docs/skills/memory-palace/
```

> 注意：`docs/skills/memory-palace/` 是仓库里稳定存在的公开路径；`.claude/.codex/.gemini/.opencode/...`、`.mcp.json` 等隐藏目录/配置是在安装后生成的本地产物。
>
> **Windows 前提说明**：
>
> - 当前 repo-local MCP 启动链路已经拆成两条
> - 原生 Windows 默认走 `backend/mcp_wrapper.py`
> - `install_skill.py` 现在会为 Claude / Codex / Gemini / OpenCode 在 Windows 上写入这条 native 路径
> - `Git Bash` / `WSL` 仍然有用，但只是在你明确走 POSIX `bash` wrapper 时才是前提
> - 所以原生 Windows 不要先照抄 `/bin/zsh` / `bash` 版本的示例；先看脚本实际生成的命令
> - 如果你走 `pwsh-in-docker`，`docker_one_click.ps1` 当前会在 `Get-NetTCPConnection` 不可用时自动回退到 `ss`；如果目标环境两者都没有，请显式指定端口或回到目标 Windows 主机复验
> - 这些 repo-local launcher 都会优先复用当前仓库 `.env` 的 `DATABASE_URL`，避免你在客户端侧又另外接到第二份 SQLite 库

## install_skill.py 现在负责什么

当前 `install_skill.py` 已支持两类动作：

- **装 skill**
  - 把 canonical bundle 分发到 workspace 或 user 的 skill 目录
  - 如果 target 是 `gemini`，还会同步分发 `memory-palace-overrides.toml`，避免旧 `__` MCP tool 语法告警
- **装 MCP**
  - 通过 `--with-mcp` 把对应 CLI 的 MCP 配置绑到当前仓库

同时支持：

- `--check`
  - 检查 skill 是否与 canonical 一致
  - 如果同时传了 `--with-mcp`，还会检查 MCP 绑定是否到位

再补一条很实用的边界：

- 如果你省略 `--targets`，当前默认只会安装 CLI 目标：`claude,codex,opencode`
- `gemini` 仍然推荐，但要你在命令里显式加上
- IDE 宿主兼容投影已经不在默认 target 集合里

当前还有两个和“少踩坑”直接相关的行为：

- 如果脚本要覆盖已有配置，会先在原目录留一份 `*.bak`
  - 常见文件名会长这样：`.mcp.json.bak`、`settings.json.bak`、`config.toml.bak`、`memory-palace-overrides.toml.bak`
- 如果某个 JSON 配置已经被手工改坏，脚本会直接报出坏文件路径和行列号，方便你先修文件再重跑

## 推荐命令

### 1) 先同步 repo-local mirrors

```bash
python scripts/sync_memory_palace_skill.py
python scripts/sync_memory_palace_skill.py --check
```

### 2) 打通当前仓库的 workspace 直连入口

这一步会把：

- `Claude Code` 绑定到 `.mcp.json`
- `Gemini CLI` 绑定到 `.gemini/settings.json`
- `Gemini CLI` 补齐 `.gemini/policies/memory-palace-overrides.toml`

```bash
python scripts/install_skill.py \
  --targets claude,gemini \
  --scope workspace \
  --with-mcp \
  --force
```

检查：

```bash
python scripts/install_skill.py \
  --targets claude,gemini \
  --scope workspace \
  --with-mcp \
  --check
```

如果你要补 workspace 级 MCP，`install_skill.py` 当前只会为 `Claude Code` 和 `Gemini CLI` 写稳定的 repo-local 绑定；`Codex/OpenCode` 继续走 user-scope MCP 更稳。

如果 `workspace --check` 已经通过，但 `user --check` 还在报 `SKILL FAIL / mismatch`，先优先怀疑你 home 目录里残留了旧版镜像或旧的 MCP 配置。通常直接重跑同一条 `--scope user --with-mcp --force` 就够了；脚本现在会先生成 `*.bak`，不会上来就把原文件静默覆盖掉。

说明：

- 这里的 `Codex/OpenCode` 会完成 repo-local skill mirror
- 但 `Codex/OpenCode` 的 MCP 不会在 workspace scope 下自动落项目配置
- 这是当前文档口径里的**明确边界**，不是遗漏
- 如果你是在新机器上第一次配置 `Codex/OpenCode`，优先直接跑 `python scripts/install_skill.py --targets codex,opencode --scope user --with-mcp --force`；手工 `codex mcp add` / GUI 注册更适合作为兜底排障手段

### 3) 打通 user-scope MCP 注册

这一步主要给：

- `Codex CLI`
- `OpenCode`
- 以及需要跨仓复用的 `Claude/Gemini`

```bash
python scripts/install_skill.py \
  --targets claude,codex,gemini,opencode \
  --scope user \
  --with-mcp \
  --force
```

检查：

```bash
python scripts/install_skill.py \
  --targets claude,codex,gemini,opencode \
  --scope user \
  --with-mcp \
  --check
```

## Per-CLI Strategy

### Claude Code

- 自动发现层：
  - repo-local `.claude/skills/memory-palace/`
- MCP 层：
  - workspace 走 `.mcp.json`
  - user-scope 可写入 `~/.claude.json` 当前仓库 project block

结论：

- **默认更稳的推荐是先跑 `--scope user --with-mcp`**
- 如果你还想让当前仓库额外落一个项目级入口，再补一次 workspace 安装

### Gemini CLI

- 自动发现层：
  - repo-local `.gemini/skills/memory-palace/`
- MCP 层：
  - workspace 走 `.gemini/settings.json`
  - user-scope 走 `~/.gemini/settings.json`
- policy 层：
  - workspace 走 `.gemini/policies/memory-palace-overrides.toml`
  - user-scope 走 `~/.gemini/policies/memory-palace-overrides.toml`

结论：

- **默认更稳的推荐仍是先跑 `--scope user --with-mcp`**
- 如果你还想让当前仓库额外落一个 workspace 入口，再补一次 workspace 安装
- 如果你看到 `Policy file warning in memory-palace-overrides.toml`，优先重跑同一条 `--scope user --with-mcp --force`
- 写给别人看时，建议写成“smoke 已通过，但 `gemini_live` 尚未完全通过”

### Codex CLI

- 自动发现层：
  - repo-local `.codex/skills/memory-palace/`
- MCP 层：
  - 当前以 `~/.codex/config.toml` 为主

结论：

- **不要把 Codex 说成“天然开箱即用”**
- 准确说法是：
  - skill 可 repo-local 自动发现
  - MCP 仍建议通过 `--scope user --with-mcp` 注册到当前仓库
- 最近一次验证环境里，补完 `--scope user --with-mcp` 之后，`Codex` 的 `mcp_bindings` 和 `Codex smoke` 都能通过

### OpenCode

- 自动发现层：
  - repo-local `.opencode/skills/memory-palace/`
- MCP 层：
  - 当前以 `~/.config/opencode/opencode.json` 为主

结论：

- **不要把 OpenCode 说成“天然开箱即用”**
- 准确说法是：
  - skill 可 repo-local 自动发现
  - MCP 仍建议通过 `--scope user --with-mcp` 注册到当前仓库

## IDE Hosts

`Cursor / Windsurf / VSCode-host / Antigravity` 现在统一按 **IDE Host** 处理，而不是继续假设它们都是 hidden skill mirror 的直接消费者。

统一口径：

- **技能投影入口**：repo-root `AGENTS.md`
- **执行入口**：本地 MCP 配置，指向当前仓库的 repo-local launcher
  - 原生 Windows 默认指向 `backend/mcp_wrapper.py`
  - POSIX shell 路径默认指向 `scripts/run_memory_palace_mcp_stdio.sh`
- **宿主差异**：只在必要时补一层兼容包装，而不是为每个 IDE 维护一整套 live smoke

其中：

- `Cursor / Windsurf / VSCode-host`
  - 主路径都是 `AGENTS.md + MCP snippet`
  - 前提是宿主或扩展本身支持 local stdio MCP 和 workspace/project rules
- `Antigravity`
  - 也归入 IDE Host
  - 但规则发现要写成：**优先读取 `AGENTS.md`，兼容旧 `GEMINI.md`**
  - 可额外投影一个 workflow：
    `docs/skills/memory-palace/variants/antigravity/global_workflows/memory-palace.md`

对应的配置片段建议不要手抄，直接运行：

```bash
python scripts/render_ide_host_config.py --host cursor
python scripts/render_ide_host_config.py --host windsurf
python scripts/render_ide_host_config.py --host vscode
python scripts/render_ide_host_config.py --host antigravity
```

如果某个宿主存在 `stdin/stdout` 或 CRLF 兼容问题，再切换到 wrapper 版本：

```bash
python scripts/render_ide_host_config.py --host antigravity --launcher python-wrapper
```

更多说明见：

- `IDE_HOSTS.md`

## 最小验证链

### 安装检查

```bash
python scripts/install_skill.py \
  --targets claude,gemini \
  --scope workspace \
  --with-mcp \
  --check

python scripts/install_skill.py \
  --targets claude,codex,gemini,opencode \
  --scope user \
  --with-mcp \
  --check
```

### 触发 smoke

```bash
python scripts/evaluate_memory_palace_skill.py
```

本地输出：

```text
docs/skills/TRIGGER_SMOKE_REPORT.md
```

如果刚 clone 下来的 GitHub 仓库里暂时没有这份文件，属于正常现象；这是运行后生成的本地验证摘要。
如果你准备把它转发给别人，先自己看一遍内容；这类本地报告可能会带上你机器上的路径、客户端配置路径或其他环境痕迹。`evaluate_memory_palace_skill.py` 现在只要任一检查是 `FAIL` 就会返回非零退出码；`SKIP` / `PARTIAL` / `MANUAL` 不会单独让进程失败，当前默认的 Gemini smoke 模型是 `gemini-3-flash-preview`。如果 `codex exec` 在 smoke 超时前没有产出结构化输出，`codex` 那一项会记成 `PARTIAL`，而不是把整轮卡住。
如果你在并行 review 或 CI 里不想覆盖默认文件，也可以先设置 `MEMORY_PALACE_SKILL_REPORT_PATH`，把 smoke 报告改写到别的本地路径。
另外，这条脚本默认还会尝试 `gemini_live`。如果 Gemini 当前配置能反推出真实数据库路径，它会对那份库做一轮 `create/update/guard` 验证，并可能留下 `notes://gemini_suite_*` 测试记忆；只想做普通 smoke 时，可显式设置 `MEMORY_PALACE_SKIP_GEMINI_LIVE=1`。
如果这轮 live 验证撞上共享真实数据库，或者有另一条 Gemini live 会话先改了同一条记忆，它也可能停在 `PARTIAL`；先把它理解成 live 宿主侧的验证边界，不要直接等同于主链路 skill/MCP 已坏。
如果当前机器没有 `Antigravity` 宿主 runtime，这一项更适合看成“目标宿主上的手工补验还没做”，不要先把它理解成仓库主链路失败。
如果你看到的失败项只剩 `mcp_bindings`，先不要急着怀疑仓库本身。更常见的情况是你机器上的 user-scope MCP 条目还没同步到当前 checkout；优先先重跑：

```bash
python scripts/install_skill.py --targets claude,codex,gemini,opencode --scope user --with-mcp --force
python scripts/evaluate_memory_palace_skill.py
```

### 真实 MCP e2e

```bash
cd backend
python ../scripts/evaluate_memory_palace_mcp_e2e.py
```

本地输出：

```text
docs/skills/MCP_LIVE_E2E_REPORT.md
```

这两份报告主要用来补做验证，不作为主入口文档。它们默认都是“运行后才出现”的本地产物，所以公开 GitHub 仓库里暂时没有也正常。
如果你在并行 review 或 CI 里不想覆盖默认文件，也可以先设置 `MEMORY_PALACE_MCP_E2E_REPORT_PATH`，把 e2e 报告改写到别的本地路径。
`MCP_LIVE_E2E_REPORT.md` 默认使用隔离临时库，不会碰你的正式库；但失败时仍可能把 stderr、日志或临时目录路径带进报告，转发前同样建议先自己看一遍内容。
现在这条 live e2e 会跟用户实际连接时一样，优先走 repo-local wrapper。按当前验证链路，它也会把 wrapper 行为和 `compact_context` 的 gist 持久化一起带上复核，而不只是检查工具清单。

## 正向 / 反向 prompt

正向 prompt：

```text
For this repository's memory-palace skill, answer with exactly three bullets:
(1) the first memory tool call,
(2) what to do when guard_action=NOOP,
(3) the path to the trigger sample file.
```

反向 prompt：

```text
请帮我改一下 README 开头的文案，不需要碰 Memory Palace。
```

期望：

- 正向 prompt 命中 `memory-palace`
- 反向 prompt 不应误触发 `memory-palace`

## 一句话口径

- `Claude/Gemini`：跑完 workspace 安装后即可获得 **repo-local 直连**
- `Codex/OpenCode`：跑完 sync 后即可获得 **repo-local 自动发现**，但要做到“真能用当前仓库 MCP”，仍应补 **user-scope MCP 注册**
