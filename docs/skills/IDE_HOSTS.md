# Memory Palace IDE Hosts

这份文档专门给这类宿主看：

- `Cursor`
- `Windsurf`
- `VSCode-host`
- `Antigravity`

它们和 `Claude / Codex / OpenCode / Gemini` 的关键区别不是品牌，而是**接入表面**：

- 没有稳定公开的模型 API 可给外部 CLI 直接复用
- 更适合把 `Memory Palace` 投影为：
  - repo-local 规则文件
  - 本地 MCP 配置片段
  - 少量宿主特化兼容层

所以在 `Memory-Palace` 里，IDE hosts 的主路径不再是 hidden `SKILL.md` mirrors，而是：

1. `AGENTS.md`
2. MCP config snippet
3. 宿主特化的可选兼容层

## 检索档位推荐（2026-04 公开复核）

- IDE hosts 的默认交互档仍然是 `Profile B`，因为它更适合编辑器内的低延迟 recall。
- `Profile C` / `Profile D` 只作为显式深检索档提供，不应被文档描述成默认档位。
- 这轮复核没有改变 IDE hosts 的接入路径：仍然是 `AGENTS.md + MCP snippet`，不是 hidden mirror 直连。
- 三端 launcher 选择也没有变化：
  - 原生 Windows：`backend/mcp_wrapper.py`
  - macOS / Linux：`scripts/run_memory_palace_mcp_stdio.sh`

---

## 核心口径

### 1. canonical skill 仍然存在

真正的 canonical source 仍然是：

```text
docs/skills/memory-palace/
```

它继续服务于：

- `Claude / Codex / OpenCode / Gemini` 这些 CLI client
- 仓内 skill 设计与 reference 的真源维护

### 2. IDE hosts 不直接吃 hidden skill mirrors

对 IDE hosts 来说，`Memory Palace` 这套 “skill” 应该这样插入：

- **主入口**：仓库根的 `AGENTS.md`
- **执行入口**：本地 MCP 配置
  - 原生 Windows 默认走 `python backend/mcp_wrapper.py`
  - macOS / Linux 默认走 `bash scripts/run_memory_palace_mcp_stdio.sh`
- **可选兼容层**：某些宿主需要额外 workflow / wrapper

也就是说：

- `AGENTS.md` 是 IDE hosts 的 repo-local 规则投影
- `mcpServers.memory-palace` 是 IDE hosts 的工具接入投影
- `docs/skills/memory-palace/` 继续是这些投影背后的 canonical source
- 如果这个 repo-local `stdio` 入口要正常工作，本地 `.env` 里的 `DATABASE_URL` 也必须是宿主机可访问的路径；`/app/...` 或 `/data/...` 这类容器路径会被 wrapper 直接拒绝
- 如果某个宿主只是把运行时 `DATABASE_URL` 传成空字符串，但仓库 `.env` 里本来就有有效值，wrapper 仍会继续读当前仓库 `.env`
- 但如果本地 `.env` 自己就写成了 `DATABASE_URL=` 空值，wrapper 现在会直接停下并提示你先把本机配置改对

---

## 每个 IDE Host 怎么看

### Cursor

- 主要依赖 repo-local `AGENTS.md`
- MCP 通过宿主自己的本地 stdio MCP 配置接入
- 不把 `.cursor/skills/memory-palace/` 当成默认主路径

### Windsurf

- 口径和 `Cursor` 一样
- 前提是宿主支持本地 stdio MCP 和 workspace/project rules

### VSCode-host

- 这里指“带 agent / MCP 能力的 VS Code 扩展宿主”
- 不假设 `VS Code` 本体就有统一的技能系统
- 只要扩展支持：
  - 本地 stdio MCP
  - repo-local project rules
  就沿用同一条 `AGENTS.md + MCP snippet` 路径

### Antigravity

- 本质上也归入 `IDE Host`
- 仍然通过同一条 MCP 路径接 Memory Palace
- 但有一个宿主特化差异：
  - **优先读取 `AGENTS.md`**
  - **兼容旧 `GEMINI.md`**
- 同时保留一个可选 workflow projection：

```text
docs/skills/memory-palace/variants/antigravity/global_workflows/memory-palace.md
```

这只是宿主特化的附加层，不改变它属于 `IDE Host` 的本质。

---

## 配置怎么生成

不要手抄。

直接运行：

```bash
python scripts/render_ide_host_config.py --host cursor
python scripts/render_ide_host_config.py --host windsurf
python scripts/render_ide_host_config.py --host vscode-host
python scripts/render_ide_host_config.py --host antigravity
```

这里的规范参数名统一写成 `vscode-host`，和正文里的 `VSCode-host` 对齐。脚本仍兼容历史别名 `--host vscode`，但文档不再把两种写法混着用。

默认会输出一份 repo-local MCP JSON 片段：

- 原生 Windows：默认指向 `python + backend/mcp_wrapper.py`
- macOS / Linux：默认指向 `bash + scripts/run_memory_palace_mcp_stdio.sh`

两条路径都要求当前 checkout 下的 `backend/.venv` 已经可用。

如果你显式要求 `python-wrapper`，但当前 checkout 还没准备好 `backend/.venv`，`render_ide_host_config.py` 现在会直接报错，不再偷偷回退到系统 Python。

在 Windows 上，这条默认值通常已经是 `python-wrapper`。如果你在 macOS / Linux 上遇到 `stdin/stdout` / CRLF 兼容问题，再切到 wrapper 版本：

```bash
python scripts/render_ide_host_config.py --host antigravity --launcher python-wrapper
```

这时脚本会输出：

```text
backend/mcp_wrapper.py
```

对应的配置片段，并提示你如果用了 venv 管理解释器，应该把 `python` 换成实际解释器路径。

---

## 统一验证口径

IDE hosts 不再承诺仓内“一键 live smoke”。

更适合的验证层级是：

1. **静态契约检查**
   - `AGENTS.md` 存在
   - wrapper / workflow / canonical source 存在
   - MCP 命令确实指向当前仓库，而且 launcher / args 组合本身是可执行的那一组，而不是“配置里刚好提到了 wrapper 路径”

2. **宿主连接检查**
   - IDE 能看到 `memory-palace` MCP server
   - IDE 能列出 Memory Palace 工具

3. **手工 smoke checklist**
   - `read_memory("system://boot")`
   - 创建一条 `notes://ide_smoke_*`
   - 再试一次重复创建，确认 guard 阻断

### 当前这轮实测边界

- 当前公开仓口径只承诺：`AGENTS.md + MCP snippet + launcher` 这条静态接入链是对齐的。
- `Cursor / Windsurf / VSCode-host / Antigravity` 仍然要在目标宿主里各做一次手工 smoke，才能把结论升级成“该宿主 live 可用”。
- 如果某个宿主当前只拿到了 `PARTIAL`，优先把它理解成：
  - 宿主内登录 / 鉴权 / runtime 前提还没补齐，或
  - 当前机器只做了静态契约检查，还没做宿主内 live 复核。

---

## 为什么这么收口

这条思路和 `Dataojitori/nocturne_memory` 更一致：

- 它按客户端类型给出 MCP 配方
- `Antigravity` 只保留必要的 wrapper 兼容层
- 没有把这些 IDE 宿主都做成统一的一键安装 + live smoke 体系

`Memory-Palace` 和它的区别在于：

- `Memory-Palace` 仍然保留 canonical skill bundle
- 但对 IDE hosts，这个 bundle 应该通过 `AGENTS.md + MCP snippet` 投影出去
- 而不是继续强行把它们当成和 CLI clients 一样的 hidden skill mirror 消费者
