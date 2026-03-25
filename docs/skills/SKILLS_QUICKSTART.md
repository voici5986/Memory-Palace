# Memory Palace Skills 快速上手

> 这份文档专门写给“先跑通、先用起来”的人。
>
> 不讲一大堆抽象概念，就回答三件事：**这套 skills 到底是什么、CLI 客户端怎么配、IDE 宿主走哪条路。**

---

## 🚀 先说结论

如果你现在是通过 GHCR / Docker 把服务跑起来，先分成两种情况：

- 只想用 `Dashboard / API / SSE`
  - 到这里就够了，不一定要继续做 skill 安装
- 还想让 `Claude / Codex / Gemini / OpenCode / IDE host` 在你本机上真正触发并调用 Memory Palace
  - 再继续按下面这份做

也就是说：

- Docker 负责跑服务
- 这份文档负责讲 **repo-local skill + MCP 安装路径**
- 两者不是同一层能力

如果你现在的目标只是：

- 不装 repo-local skill
- 只把某个 MCP 客户端手工接到 Docker 的 `/sse`

先走：

- `docs/GHCR_QUICKSTART.md`
- `docs/GETTING_STARTED.md` 的 `6.2 SSE 模式`
- `docs/GETTING_STARTED.md` 的 `6.3 客户端配置示例`

那里给的是当前仓库已经验证过的**通用 SSE MCP 骨架**。不要把它误读成“每个客户端的最终字段名都完全一样”。

如果你不想先手动消化这整页，而是希望 **AI 直接一步一步带你装**，当前更推荐这样走：

1. 先安装独立的 setup skill：[`memory-palace-setup`](https://github.com/AGI-is-going-to-arrive/memory-palace-setup)
2. 再直接对 AI 说：`使用 $memory-palace-setup 帮我一步步安装配置 Memory Palace，优先走 skills + MCP，不要只给 MCP-only。默认先按 Profile B 起步，但如果环境允许，请主动推荐我升级到 C/D。`

如果你还没把这个 setup skill 装进客户端，也可以先把仓库地址发给 AI，然后说：

```text
请先阅读这个仓库的 README.md 和 SKILL.md，再按它的规则一步步引导我安装配置 Memory Palace。优先走 skills + MCP，不要默认走 MCP-only。
```

当前这个仓库已经把 `memory-palace` 的 **canonical skill**、同步脚本和安装脚本整理好了。按下面命令执行后，你可以在**自己的本地工作区**把 skill + MCP 主链路接起来：

| 客户端 | skill 自动识别 | MCP 连接现状 | 你该怎么做 |
|---|---|---|---|
| `Claude Code` | 执行 `sync` + user-scope 安装后即可 | `--scope user --with-mcp` 已有脚本化安装路径；workspace 入口可选 | 首选统一跑 `python scripts/install_skill.py --targets claude,codex,gemini,opencode --scope user --with-mcp --force`；只在想补当前仓库项目级入口时再加 workspace 安装 |
| `Gemini CLI` | 执行 `sync` + user-scope 安装后即可 | `--scope user --with-mcp` 更稳；workspace 可生成 `.gemini/settings.json`，但 `live MCP` 仍有个别场景待补验 | 首选统一跑 `python scripts/install_skill.py --targets claude,codex,gemini,opencode --scope user --with-mcp --force`；需要当前仓库项目级入口时再补 workspace 安装 |
| `Codex CLI` | sync 后有 repo-local skill | user-scope MCP 已有脚本化安装路径 | 首选 `python scripts/install_skill.py --targets codex --scope user --with-mcp --force`，手工 `codex mcp add` 只当 fallback |
| `OpenCode` | sync 后有 repo-local skill | user-scope MCP 已有脚本化安装路径 | 首选 `python scripts/install_skill.py --targets opencode --scope user --with-mcp --force`，手工 GUI 注册只当 fallback |

一句话理解：

- **skill** 负责“什么时候该进入 Memory Palace 工作流”
- **MCP** 负责“真正去调用 `read_memory / search_memory / update_memory` 这些工具”
- 两个都到位，才叫“真的能自动触发并且真的能干活”

> 当前公开口径：
>
> - `Claude / Codex / Gemini` 的 **smoke** 在最近一次验证环境里都已有通过结果；其中 `Codex` 默认前提是先补好 `user-scope --with-mcp`
> - `OpenCode` 当前更准确的说法是：repo-local skill 已就位，`mcp list` 可以确认 `memory-palace` 已连接；真实 `run` 仍取决于当前 provider 凭证
> - 当前验证环境里，隔离用户目录下的 `install_skill.py --scope user --with-mcp --check` 已对 `Claude / Codex / Gemini / OpenCode` 全部通过；同一套隔离 user-scope 也通过了 skills-only 的 `--check`
> - `MCP-only` 的 live e2e 当前也是 pass；仓库里的 repo-local MCP 验证结果来自真实运行，而不只是静态配置检查
> - `Gemini live` 还没到可以写成“完全通过”的程度；当前更准确的说法是：如果 Gemini 配置无法反推出数据库路径，或者共享真实数据库先被另一条 Gemini live 会话改动了，它会停在 `PARTIAL`
> - `Cursor / Windsurf / VSCode-host / Antigravity` 现在统一归到 **IDE Hosts**；它们的主路径是 `AGENTS.md + MCP snippet`，不是 hidden skill mirrors
>
> **Windows 用户先看这个前提**：
>
> - 原生 Windows 现在默认走 `python + backend/mcp_wrapper.py`
> - `install_skill.py --with-mcp` 在 Windows 上会为 `Claude / Codex / Gemini / OpenCode` 生成这条 native 路径
> - `python scripts/render_ide_host_config.py --host ...` 在 Windows 上默认也会输出 `python-wrapper`
> - profile/apply 脚本的 PowerShell-in-Docker 等效路径也已经重新复验过，但 native Windows 主机本身仍建议按目标环境再复核一次
> - 如果你是 `Git Bash` 或 `WSL` 用户，仍然可以继续使用 `bash + scripts/run_memory_palace_mcp_stdio.sh`
> - 所以现在要区分的是：**native Windows 用 python-wrapper，POSIX shell 边界用 bash wrapper**

---

## 🧠 skill 和 MCP 到底啥关系

<p align="center">
  <img src="../images/skill_vs_mcp.png" width="800" alt="Skill vs MCP 工作原理" />
</p>

可以把它理解成：

- **skill** = 司机脑子里的“出车规则”
- **MCP** = 真正的车和方向盘

只有 skill，没有 MCP：

- 模型知道“这时候应该用 Memory Palace”
- 但真到要读写记忆时，没工具可调

只有 MCP，没有 skill：

- 工具明明存在
- 但模型不一定知道什么时候该用，容易漏触发、误触发

所以当前仓库做的事情，本质上就是把这两层一起补齐。

---

## ✅ 运行同步 / 安装后，本地通常会看到什么

公开仓库默认只带 canonical bundle。你执行上面的同步 / 安装命令后，本地工作区通常会看到这些关键入口：

| 文件 | 作用 |
|---|---|
| `docs/skills/memory-palace/` | canonical skill 真源（公开仓库默认存在） |
| `.claude/skills/memory-palace/SKILL.md` | Claude Code 的 repo-local skill 镜像（本地生成） |
| `.codex/skills/memory-palace/SKILL.md` | Codex 的 repo-local skill 镜像（本地生成） |
| `.opencode/skills/memory-palace/SKILL.md` | OpenCode 的 repo-local skill 镜像（本地生成） |
| `.gemini/skills/memory-palace/SKILL.md` | Gemini 的 repo-local skill 入口（本地生成） |
| `.gemini/settings.json` | Gemini 的项目级 MCP 配置（workspace 安装后生成） |
| `.gemini/policies/memory-palace-overrides.toml` | Gemini 的 Memory Palace policy 覆盖文件（安装后生成，用来避免旧 `__` MCP tool 语法告警） |
| `.mcp.json` | Claude Code 的项目级 MCP 配置（workspace 安装后生成） |

按本文默认推荐的 `--scope user --with-mcp` 路线，本机 home 目录里通常还会出现：

- `~/.claude/skills/memory-palace/`
- `~/.codex/config.toml`
- `~/.gemini/skills/memory-palace/SKILL.md`
- `~/.gemini/settings.json`
- `~/.gemini/policies/memory-palace-overrides.toml`
- `~/.config/opencode/opencode.json`

所以：

- 默认推荐先跑一遍统一的 `--scope user --with-mcp`
- `Claude Code`、`Gemini CLI` 如果还想补当前仓库项目级入口，再额外执行 workspace 安装
- `Codex CLI` 和 `OpenCode` 的 **skill** 已经就位
- 最近验证环境里，补完 `--scope user --with-mcp` 之后，`Codex` 的 `mcp_bindings` 和 `Codex smoke` 都能通过
- `OpenCode` 建议先手动确认一次 `mcp list`

如果你接的是 IDE 宿主，请不要继续按 hidden skill mirrors 的心智往下读，直接切到：

- `IDE_HOSTS.md`
- `python scripts/render_ide_host_config.py --host <cursor|windsurf|vscode|antigravity>`

---

## 🛠️ 四个 CLI 客户端怎么配

## 1) `Claude Code`

默认更稳的推荐还是先跑：

```bash
python scripts/install_skill.py --targets claude --scope user --with-mcp --force
```

如果你还想让**当前仓库**额外落一个项目级入口，再补一次 workspace 安装。

- `~/.claude/skills/memory-palace/`
- `~/.claude.json` 里当前仓库的 `mcpServers.memory-palace`

如果你又补了 workspace 安装，本地工作区里还会有：

- `.claude/skills/memory-palace/`
- `.mcp.json`

这样在这个仓库里启动 `Claude Code`，它就能同时看得到：

1. `memory-palace` skill
2. `memory-palace` MCP server

推荐检查：

```bash
claude mcp list
```

如果你看到项目里有 `memory-palace`，基本就对了。

这次真实验证里，`Claude Code` 已经能在非交互模式下直接完成真实 MCP 工具调用；如果你看到 `TOOL_OK`，说明这条链路已经通了。

---

## 2) `Gemini CLI`

默认更稳的推荐还是先跑：

```bash
python scripts/install_skill.py --targets gemini --scope user --with-mcp --force
```

补完之后，home 目录里至少会有：

- `~/.gemini/skills/memory-palace/SKILL.md`
- `~/.gemini/settings.json`
- `~/.gemini/policies/memory-palace-overrides.toml`

如果你还想让**当前仓库**额外落一个项目级入口，再补一次 workspace 安装；那时工作区里会补齐：

- `.gemini/skills/memory-palace/SKILL.md`
- `.gemini/settings.json`
- `.gemini/policies/memory-palace-overrides.toml`

所以在**当前工作区本地**里，Gemini 可以走项目级入口；而跨仓复用时，默认还是 user-scope 更稳。

推荐检查：

```bash
gemini skills list --all
gemini mcp list
```

如果你看到这种提示：

- `Policy file warning in memory-palace-overrides.toml`
- `The "__" syntax for MCP tools is strictly deprecated`

优先重新执行一遍当前仓库里的 Gemini 安装命令；新版安装脚本会把 `memory-palace-overrides.toml` 改写成 Gemini 当前认可的 `mcpName = "memory-palace"` 规则格式。

如果你看到这种提示：

- `Skill conflict detected`
- `... overriding the same skill from ~/.gemini/skills/...`

这通常不是坏事，表示**当前工作区里的 skill 正在覆盖用户目录里的旧版本**。

如果你看到这种提示：

- `gemini mcp list` 里 `memory-palace` 是 `Disconnected`
- 或 Gemini 回答里出现 `MCP issues detected`

先把旧的用户级 MCP 条目删掉，再重新加项目级这一条：

```bash
# native Windows
gemini mcp remove memory-palace
gemini mcp add -s project memory-palace python <repo-root>\backend\mcp_wrapper.py
```

```bash
# macOS / Linux / Git Bash / WSL
gemini mcp remove memory-palace
gemini mcp add -s project memory-palace /bin/zsh -lc 'cd <repo-root> && bash scripts/run_memory_palace_mcp_stdio.sh'
```

> 把上面的 `<repo-root>` 替换成你的实际仓库根目录。
>
> 这条写法会复用当前仓库 `.env` 里的 `DATABASE_URL`。如果你前面已经让 Dashboard / HTTP API 跑在同一个仓库里，就不要再另外手写一条 `backend/memory.db`，否则很容易把客户端和页面接到两份不同的库上。
>
> 也别把 `.env.docker` 里的 `/app/data/...` 容器路径，或者你自己改成 `/data/...` 的同类路径，原样抄进本地 `.env`。repo-local `stdio` MCP 现在会直接拒绝这种配置；要么改成宿主机绝对路径，要么继续走 Docker `/sse`。

---

## 3) `Codex CLI`

`Codex` 这边要分开看：

- **skill**：执行 `sync/install` 后，本地会有 `.codex/skills/memory-palace/`
- **MCP**：首选 `python scripts/install_skill.py --targets codex --scope user --with-mcp --force` 写入用户目录 `~/.codex/config.toml`；手工 `codex mcp add` 只作为 fallback

说人话就是：

- 在这个仓库里，`Codex` 已经知道有 `memory-palace` 这套 skill
- 但你第一次在自己的机器上用时，仍要把 MCP 启动命令写进自己的用户级配置

第一次在新机器上，优先执行：

```bash
python scripts/install_skill.py --targets codex --scope user --with-mcp --force
```

然后检查：

```bash
codex mcp list
```

如果 `python scripts/evaluate_memory_palace_skill.py` 里还是报：

- `mcp_bindings` 失败
- 或 `Codex smoke` 失败

先不要直接怀疑 skill 本身。更常见的情况是你机器上的 `~/.codex/config.toml` 还残留旧条目，或者没先补 `user-scope MCP`。优先重跑：

```bash
python scripts/install_skill.py --targets codex --scope user --with-mcp --force
```

如果脚本检查仍失败，或者你就是要手工排障，再用：

```bash
# native Windows
codex mcp add memory-palace -- python C:\ABS\PATH\TO\REPO\backend\mcp_wrapper.py
```

```bash
# macOS / Linux / Git Bash / WSL
codex mcp add memory-palace \
  -- /bin/zsh -lc 'cd /ABS/PATH/TO/REPO && bash scripts/run_memory_palace_mcp_stdio.sh'
```

注意：

- 把上面的 `/ABS/PATH/TO/REPO` 换成你的真实仓库路径
- 无论走脚本还是手工 fallback，最终都会写到 `~/.codex/config.toml`
- 这是 `Codex CLI` 当前的产品行为，不是本仓库少了文件
- 这条命令最终也会复用当前仓库 `.env` 里的 `DATABASE_URL`；如果那份 `.env` 还是 Docker 用的 `/app/data/...`，或者其他 `/data/...` 这类容器路径，本机 `stdio` MCP 会直接拒绝启动
- 如果你把 fallback 命令改写成别的 shell / 客户端配置，别把 `source .venv/bin/activate` 随手删掉；要么先激活项目自己的 `.venv`，要么直接改成 `.venv` 里的 Python。否则 MCP 进程可能会在启动前就因为解释器不对而报 `No module named 'sqlalchemy'`

---

## 4) `OpenCode`

`OpenCode` 这边在你执行 `sync/install` 后，本地通常会有：

- `.opencode/skills/memory-palace/`

并且最近验证环境里，至少已经确认到 repo-local skill 可见，`opencode mcp list` 也能看到 `memory-palace connected`。

但如果你换一台新机器，更稳妥的默认顺序仍然是先跑：

```bash
python scripts/install_skill.py --targets opencode --scope user --with-mcp --force
opencode mcp list
```

如果已经能看到 `memory-palace`，那就不用折腾。

如果脚本检查仍失败，或者你就是要手工排障，再在 `OpenCode` 自己的 MCP 管理入口里新增一个本地 stdio server，核心参数就是：

```text
# native Windows
name: memory-palace
type: local / stdio
command: python
args:
  - <repo-root>\backend\mcp_wrapper.py
```

```text
# macOS / Linux / Git Bash / WSL
name: memory-palace
type: local / stdio
command: /bin/zsh
args:
  - -lc
  - cd <repo-root> && bash scripts/run_memory_palace_mcp_stdio.sh
```

不同版本的 `OpenCode` 交互入口可能长得不一样，但要填的本质就是这几项。

---

## 5) IDE 宿主怎么配

这类宿主现在统一按 **IDE Host** 处理：

- `Cursor`
- `Windsurf`
- `VSCode-host`
- `Antigravity`

统一口径很简单：

- **规则入口**：`AGENTS.md`
- **MCP 入口**：`python scripts/render_ide_host_config.py --host ...`
- **宿主差异**：只在必要时补 wrapper / workflow，不再假设这些 IDE 会直接吃 hidden `SKILL.md` mirrors

推荐命令：

```bash
python scripts/render_ide_host_config.py --host cursor
python scripts/render_ide_host_config.py --host windsurf
python scripts/render_ide_host_config.py --host vscode
python scripts/render_ide_host_config.py --host antigravity
```

在 Windows 上，默认输出已经是 `python-wrapper`。如果你在 macOS / Linux 上遇到 `stdin/stdout` 或 CRLF 兼容问题，再改用：

```bash
python scripts/render_ide_host_config.py --host antigravity --launcher python-wrapper
```

一句话记忆：

- CLI 客户端：优先看 hidden skill mirrors + `install_skill.py`
- IDE 宿主：优先看 `AGENTS.md` + `render_ide_host_config.py`

---

## 🔍 怎么判断“真的触发成功了”

最简单的正向问题：

```text
先从 system://boot 读一下，再帮我查最近关于部署偏好的记忆。
```

如果命中了 `memory-palace`，回答或执行里通常会体现这些信号：

- 先走 `read_memory("system://boot")`
- 不会直接瞎写
- 会提到 `search_memory(..., include_session=true)` 或等价 recall 流程

最简单的反向问题：

```text
给我重写 README 的开头介绍。
```

这类纯文档任务**不应该**误触发 Memory Palace 工作流。

---

## 🧪 仓库里已经有的验证命令

先看 skill 镜像有没有漂移：

```bash
python scripts/sync_memory_palace_skill.py --check
```

再看当前这套多客户端 smoke：

```bash
python scripts/evaluate_memory_palace_skill.py
```

再看真实 MCP 调用链：

```bash
cd backend && python ../scripts/evaluate_memory_palace_mcp_e2e.py
```

这两条脚本都会在本地生成验证报告：

- `docs/skills/TRIGGER_SMOKE_REPORT.md`（本地 smoke 摘要，分享前请自己检查是否包含本机路径或客户端配置痕迹）
- `docs/skills/MCP_LIVE_E2E_REPORT.md`

默认建议把它们当成你自己机器上的复核产物，不把它们当成主入口文档；这两份文件默认也被 `.gitignore` 排除，所以公开 GitHub 仓库里通常不会带上。`evaluate_memory_palace_skill.py` 现在只要任一检查是 `FAIL` 就会返回非零退出码；`SKIP` / `PARTIAL` / `MANUAL` 不会单独让进程失败，当前默认的 Gemini smoke 模型是 `gemini-3-flash-preview`。
如果你在并行 review 或 CI 里想隔离输出，可以先设置 `MEMORY_PALACE_SKILL_REPORT_PATH` / `MEMORY_PALACE_MCP_E2E_REPORT_PATH`，把报告改写到别的本地路径。

补一句体验口径：`evaluate_memory_palace_skill.py` 会串行调多个 CLI，完整跑完往往要几分钟；如果你机器上这几种客户端都装了，看到它跑一阵子没新输出，先别急着判定为卡死。当前 `codex` 这一项如果只是 `codex exec` 在 smoke 超时前没产出结构化输出，会直接记成 `PARTIAL`，而不是把整轮卡死。
再补一句副作用口径：这条脚本默认还会尝试 `gemini_live`。如果 Gemini 当前配置能反推出真实数据库路径，它会做一轮 `create/update/guard` 验证，并可能留下 `notes://gemini_suite_*` 这类测试记忆；只想做普通 smoke 时，可显式设置 `MEMORY_PALACE_SKIP_GEMINI_LIVE=1`。
如果当前机器根本没有 `Antigravity` 宿主 runtime，`evaluate_memory_palace_skill.py` 里的 Antigravity 项更适合看成“待目标宿主手工补验”，不要先把它理解成仓库主链路坏了。
如果这条报告里只有 `mcp_bindings` 失败，优先先重跑一次统一的 `user-scope` 安装，再重新执行 smoke：

```bash
python scripts/install_skill.py --targets claude,codex,gemini,opencode --scope user --with-mcp --force
python scripts/evaluate_memory_palace_skill.py
```

对 `MCP_LIVE_E2E_REPORT.md` 也要保持同样的分享意识：它默认使用隔离临时库，不会碰你的正式库，但失败时仍可能带上本地日志、stderr 或临时目录痕迹。准备转发给别人前，先自己看一遍内容。

---

## 🙋 常见误区

### 误区 1：看到 skill 文件就等于能用了

不是。

skill 只解决“该不该触发”。
真正要调工具，还得有 MCP server 配置。

### 误区 2：Gemini 发现了 skill，就一定能稳定触发

也不是。

Gemini 对隐藏目录有时更保守，所以这套安装链才会在你本地同时补：

- `.gemini/skills/...`
- `.gemini/settings.json`
- `variants/gemini/SKILL.md`

### 误区 3：本地已经有 `.codex/skills/...`，就不用配 MCP

还是不够。

`Codex` 的 MCP 目前主要看用户级配置 `~/.codex/config.toml`。

### 误区 4：IDE 宿主也应该先去找 hidden skill mirrors

不是。

对 `Cursor / Windsurf / VSCode-host / Antigravity` 这类 IDE 宿主，当前推荐主路径是：

- 仓库根的 `AGENTS.md`
- `python scripts/render_ide_host_config.py --host ...`

`Antigravity` 只是额外保留了一个宿主特化差异：

- workflow 可投影到 `.agent/workflows/...` 或 `~/.gemini/antigravity/global_workflows/...`
- 规则发现优先读 `AGENTS.md`，兼容旧 `GEMINI.md`

但这不改变它属于 IDE 宿主这件事。

---

## 📚 继续往下看什么

如果你已经能跑起来，下一步按这个顺序读：

1. `MEMORY_PALACE_SKILLS.md` —— 设计原则、Claude 规范对齐、维护边界
2. `CLI_COMPATIBILITY_GUIDE.md` —— CLI 客户端与 IDE 宿主的统一兼容口径
3. `IDE_HOSTS.md` —— Cursor / Windsurf / VSCode-host / Antigravity 的主接法
4. `docs/skills/memory-palace/SKILL.md` —— 真正给模型看的 skill 本体

如果你只想先验证现在是不是通的，就盯住这 3 条命令：

```bash
python scripts/sync_memory_palace_skill.py --check
python scripts/evaluate_memory_palace_skill.py
cd backend && python ../scripts/evaluate_memory_palace_mcp_e2e.py
```
