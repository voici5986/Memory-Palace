# Memory Palace CLI Compatibility Guide

## Summary

- `Claude Code`：完成 `sync/install` 后，可获得 **repo-local skill 自动发现** + **workspace MCP 直连**
- `Gemini CLI`：完成 `sync/install` 后，可获得 **repo-local skill 自动发现** + **workspace MCP 直连**
- `Codex CLI`：完成 `sync` 后，可获得 **repo-local skill 自动发现**；`MCP` 仍以 **user-scope 注册** 为主
- `OpenCode`：完成 `sync` 后，可获得 **repo-local skill 自动发现**；`MCP` 仍以 **user-scope 注册** 为主
- `Cursor` / `.agent`：当前仍以 mirror 结构兼容为主，未提升为统一直连入口
- 当前设计已对齐 `Anthropic skill-creator` 的核心要求：`frontmatter`、`trigger description`、`references`、`eval/smoke`

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
- MCP 确实指向当前仓库的 `scripts/run_memory_palace_mcp_stdio.sh`

再补一句最容易踩坑的：

- 这个 wrapper 会优先复用当前仓库 `.env` 里的 `DATABASE_URL`
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

对应的 canonical skill 真源是：

```text
docs/skills/memory-palace/
```

> 注意：`docs/skills/memory-palace/` 是仓库里稳定存在的公开路径；`.claude/.codex/.gemini/.opencode/...`、`.mcp.json` 等隐藏目录/配置是在安装后生成的本地产物。
>
> **Windows 前提说明**：
>
> - 当前 repo-local MCP wrapper 实际是 `scripts/run_memory_palace_mcp_stdio.sh`
> - `install_skill.py` 为 Claude / Codex / Gemini / OpenCode 生成的本地 MCP 配置也都调用 `bash` 风格命令
> - 所以原生 Windows 如果没有 **Git Bash** 或 **WSL**，不要直接照抄 `/bin/zsh` / `bash` 版本的示例
> - 当前更稳妥的口径是：在 Git Bash / WSL 中接这条本地 stdio 链，或使用 Docker / `pwsh-in-docker` 做等效验证
> - 这条 wrapper 还会优先复用当前仓库 `.env` 的 `DATABASE_URL`，避免你在客户端侧又另外接到第二份 SQLite 库

## install_skill.py 现在负责什么

当前 `install_skill.py` 已支持两类动作：

- **装 skill**
  - 把 canonical bundle 分发到 workspace 或 user 的 skill 目录
- **装 MCP**
  - 通过 `--with-mcp` 把对应 CLI 的 MCP 配置绑到当前仓库

同时支持：

- `--check`
  - 检查 skill 是否与 canonical 一致
  - 如果同时传了 `--with-mcp`，还会检查 MCP 绑定是否到位

当前还有两个和“少踩坑”直接相关的行为：

- 如果脚本要覆盖已有配置，会先在原目录留一份 `*.bak`
  - 常见文件名会长这样：`.mcp.json.bak`、`settings.json.bak`、`config.toml.bak`
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

```bash
python scripts/install_skill.py \
  --targets claude,codex,gemini,opencode \
  --scope workspace \
  --with-mcp \
  --force
```

检查：

```bash
python scripts/install_skill.py \
  --targets claude,codex,gemini,opencode \
  --scope workspace \
  --with-mcp \
  --check
```

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

- **先跑一次 workspace 安装，再打开当前仓库即可直接用**
- 如果要带去别的仓库，再补 `--scope user --with-mcp`

### Gemini CLI

- 自动发现层：
  - repo-local `.gemini/skills/memory-palace/`
- MCP 层：
  - workspace 走 `.gemini/settings.json`
  - user-scope 走 `~/.gemini/settings.json`

结论：

- **跑完 workspace 安装后，workspace 入口就位**
- 若你想更稳，或准备跨仓复用，仍推荐再补一次 `--scope user --with-mcp`
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

### Cursor / `.agent`

- 目前仍以 mirror 分发与结构兼容为主
- 未纳入当前这轮统一的 workspace/user MCP 自动注册链

## 最小验证链

### 安装检查

```bash
python scripts/install_skill.py \
  --targets claude,codex,gemini,opencode \
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
如果你准备把它转发给别人，先自己看一遍内容；这类本地报告可能会带上你机器上的路径、客户端配置路径或其他环境痕迹。
另外，这条脚本默认还会尝试 `gemini_live`。如果 Gemini 当前配置能反推出真实数据库路径，它会对那份库做一轮 `create/update/guard` 验证，并可能留下 `notes://gemini_suite_*` 测试记忆；只想做普通 smoke 时，可显式设置 `MEMORY_PALACE_SKIP_GEMINI_LIVE=1`。

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
`MCP_LIVE_E2E_REPORT.md` 默认使用隔离临时库，不会碰你的正式库；但失败时仍可能把 stderr、日志或临时目录路径带进报告，转发前同样建议先自己看一遍内容。

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
