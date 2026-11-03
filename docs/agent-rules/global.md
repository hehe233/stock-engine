# 全局开发与执行规则

适用于整个 Stock Engine。功能入口见[源码导航](../architecture/source-map.md)，专项约束从 [AGENTS.md](../../AGENTS.md) 按任务进入。

## 范围与事实

- 修改前定位实现、调用方、配置和对应测试；说明可观察的完成标准。既有用户修改保留在原位，避免顺手重构无关模块。
- 依赖安装使用 `pnpm` / `uv`，版本以锁文件为准。仅在任务需要时调整依赖、构建配置、数据库或协议，并同步调用方、迁移与文档。
- API Key、应用访问密钥、个人持仓和本地数据库不写入文档或测试夹具；读取配置优先查看 `.env.example`，排障输出使用脱敏字段。
- 提交、推送、外部发布和破坏性清理按用户授权执行。普通可逆编辑在既有授权内推进，不设置额外的逐文件审批。

## 文件编辑

- PowerShell 读取文本显式使用 `Get-Content -Encoding UTF8`；搜索优先 `rg`。源码和文档使用 UTF-8，中文直接写字符。
- 编辑优先使用 `apply_patch` 工具；避免经过多层 shell 拼接中文、多行代码和内嵌引号。遇到参数损坏先修正调用方式，再重试。
- 遵循当前 `.prettierrc.json` 与文件格式，不复制参考项目的 CRLF 配置。只格式化本次改动的文件，避免整仓换行和样式变更。
- 根目录 `pnpm format` 会写入整个扫描范围；局部任务使用 `pnpm exec prettier --check <文件...>`，需修复时对同一文件列表使用 `--write`。
- 有 Git 元数据时检查 `git diff --check`、`git diff` 和 `git status --short`；无 Git 元数据时核对实际修改清单、内容、格式与链接，并说明无法提供 Git 差异校验。
- 临时产物集中在 `.runtime/`，只清理本次创建且已核实不再使用的文件。持久数据库、检查点和量化产物是用户数据。

## 验证矩阵

选择能发现本次行为回归的最小验证集；跨行修改合并对应检查。失败先区分本次回归、既有问题与环境问题，修复后重跑失败项和受影响项。

| 改动范围                      | 默认验证                                                                                 | 扩大条件                                                     |
| ----------------------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| 仅文档                        | 格式、相对链接、源码事实；有 Git 时检查差异                                              | 新增可执行示例需核对命令与前置条件；有副作用时在隔离环境验证 |
| TS/TSX 逻辑、请求、页面       | 根目录 `pnpm typecheck`，对改动文件 ESLint，相关浏览器行为                               | 共享状态或路由变化扩大受影响页面；构建配置变化运行构建       |
| CSS、组件、外壳               | 桌面/窄屏布局、键盘、加载/空/错误状态；含 TSX 时加类型与 ESLint                          | 共享主题/外壳扩大到调用页面；流式页检查订阅稳定性            |
| Python API、service、provider | 在 `apps/api` 运行相关 `uv run pytest` 与 `uv run ruff check <文件...>`                  | 跨领域契约、认证或事务变化扩大相关测试                       |
| ORM、迁移、模型配置           | 相关数据库/配置/迁移测试，临时数据库升级与旧数据保留                                     | 涉及 PostgreSQL 时另做该数据库验证，SQLite 通过不代表它通过  |
| 图、任务、SSE                 | `test_p1.py`、`test_agent_stream.py` 中相关测试；模型协议变化加 `test_model_protocol.py` | 前端消费变化加 `agent-stream.spec.ts`，覆盖恢复与终止        |
| 数据、训练、回测              | `test_p2.py` / `test_quant.py` 中相关行为测试                                            | UI/导入/产物链路变化加 `p2.spec.ts` / `quant.spec.ts`        |
| 启停、构建、部署配置          | 对应脚本、日志、实际退出码、端口与产物                                                   | 部署变化核对 `/api` 代理、SSE 缓冲和 SPA fallback            |

局部命令示例（在项目根目录；文件选择随任务调整）：

```powershell
pnpm exec prettier --check AGENTS.md docs/README.md
pnpm --filter @stock-engine/web exec eslint src/pages/Jobs/index.tsx
pnpm --filter @stock-engine/web exec playwright test e2e/agent-stream.spec.ts
```

后端命令示例（工作目录 `apps/api`）：

```powershell
uv run pytest tests/test_agent_stream.py tests/test_p1.py -q
uv run ruff check app/agents tests/test_agent_stream.py
```

浏览器测试前按[启动说明](../../README.md)使用隔离演示服务；Playwright 配置不会自动启动服务。切换前记录原运行模式和进程归属，避免覆盖正在使用的环境。模型协议测试优先使用已有 mock，不因验证普通改动自动调用付费模型或公开采集。

新增测试验证业务结果、契约或故障恢复；纯文档和简单样式调整不为实现细节补测试。全量门禁按影响选择根目录 `pnpm typecheck`、`pnpm lint`、构建脚本、`pnpm test:e2e`，以及 `apps/api` 下的 `uv run pytest -q`、`uv run ruff check .`。

## Windows Shell 与进程卫生

1. 开始运行服务前记录会话开始时间、现有进程清单和端口占用。正常启动、停止与构建分别使用 `scripts/start-dev.ps1`、`scripts/stop-dev.ps1`、`scripts/build-web.ps1`。
2. 长驻 dev/watch 和构建必须脱离工具 shell：使用 `Start-Process -WindowStyle Hidden`，分别重定向 stdout/stderr，并记录 PID 与启动时间。避免 `cmd /c ... 2>&1` 把子进程长期挂在工具 stdout 上。
3. 构建脚本返回仅代表启动成功；读取 `.runtime/build.exit-code`，退出码为 `0` 才算构建通过，`running` 表示未结束。对应日志为 `build.stdout.log` / `build.stderr.log`，PID 记录为 `build-process.json`。
4. 命令卡住时先查 `D:/Codex/.codex/.sandbox/sandbox.<date>.log` 中的 `setup refresh had errors` 或 `os error 32`。核实是否为旧 `node_repl.exe`、`node.exe`、`cmd.exe` / `pwsh.exe` 及其后代占用 runtime；确认原因前不连续重试命令。
5. 收尾检查早于会话开始的进程，结合启动时间、命令行、父子关系和 PID 清单确认残留归属。只终止已确认的残留与本次需要回收的进程树；活跃客户端、其他项目或用户要求保留的服务不能仅因“启动较早”被终止。
6. 用 `netstat -ano` 核对 8000 / 8001 及本项目 5173。应释放的是本次停止的服务端口；其他项目的占用如实记录，不抢占端口。本项目 `stop-dev.ps1` 校验 PID 启动时间后清理登记的进程树。
7. 同一项目避免同时运行多个 Codex 客户端。清理 `C:/Users/<user>/AppData/Local/OpenAI/Codex/runtimes/cua_node/` 中旧版本前确认无进程占用，并核实完整目标路径；按目录年龄不能判断可删除。

本节把用户提供的 Windows 沙箱经验用于进程诊断；沙箱失败原因应以本次日志为证据。纯文档任务无需为了“验收”启动或重启服务。
