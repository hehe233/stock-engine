# Stock Engine

文档入口：[分类总索引](docs/README.md) · [Agent 规范](AGENTS.md) · [前端提示词](docs/agent-rules/frontend/prompts.md) · [后端提示词](docs/agent-rules/backend/prompts.md)

面向前端开发者的 A 股研究 Agent 学习项目。P3 研究验证版在行情与 LangGraph 任务闭环上，加入 Parquet 数据版本、LightGBM 滚动校准和受成交约束的回测实验。

默认尝试采集 A 股、ETF 和指数的免费公开行情；独立保留离线演示模式。模型支持多套可管理的 OpenAI 兼容 API 和手动选择的 Ollama 备选。**五分钟刷新不等于交易所级实时；规则热度分不是妖股概率。** P2 已提供连板梯队、行业聚合、龙虎榜席位、资金流向、公告、持仓和历史窗口统计；P3 新增概率校准与保守成交模拟，结果只对应所选数据范围。

## 技术栈

界面采用固定侧栏与独立滚动工作区：侧栏支持收起、拖拽和宽度记忆，手机端切换为导航抽屉；Agent 分析保留完整过程，生成报告在可调整宽度的抽屉中展示。主题、动效与组件约定见 [界面框架](docs/modules/ui-workspace.md)。

- 前端：React 19、TypeScript、Vite、Ant Design 6、TanStack Query、React Router。
- 后端：Python 3.12、FastAPI、Pydantic、LangGraph、LangChain 模型适配。
- 数据：SQLAlchemy 2、Alembic；本地 SQLite，可切换 PostgreSQL 17。
- 调度：独立 worker，每 300 秒尝试采集；SQLAlchemy 任务表、执行租约、独立检查点、SSE 进度。
- 验证：pytest、Ruff、ESLint、TypeScript、Playwright。
- 量化实验：LightGBM、scikit-learn、Parquet/PyArrow、DuckDB；模型文本与预测结果独立归档。

当前采用单用户、单机架构，不要求 Redis、Celery 或向量库。业务数据与图检查点分开存储。

## 快速启动（Windows PowerShell）

需要 Node.js 22.12+（建议 LTS）、pnpm 11、Python 3.12、uv。首次安装需要联网。

```powershell
# 项目根目录：安装前端依赖
pnpm install

# 安装后端依赖；若本机有多个 Python，可改成解释器完整路径
cd apps/api
uv sync --python 3.12
cd ../..

# 可选：首次复制配置模板；已有 .env 时不要覆盖
if (-not (Test-Path apps/api/.env)) { Copy-Item apps/api/.env.example apps/api/.env }

# 自动执行迁移，然后隐藏启动 API、worker 和前端；不占住当前 shell
.\scripts\start-dev.ps1
```

- 页面：http://127.0.0.1:5173
- 模型设置：http://127.0.0.1:5173/settings/models
- 研究中心：http://127.0.0.1:5173/research
- 持仓分析：http://127.0.0.1:5173/portfolio
- 十年历史案例：http://127.0.0.1:5173/history
- 策略与概率实验：http://127.0.0.1:5173/quant
- Swagger API 文档：http://127.0.0.1:8001/docs
- 健康检查：http://127.0.0.1:8001/api/health
- 日志：`.runtime/*.log`
- 进程记录：`.runtime/dev-processes.json`

免费行情和规则分析不需要 API Key 或 Docker；首次公开行情在后台采集，可能需要数分钟。网络失败不会阻塞 API 启动；页面显示采集原因并保留旧快照。后端修改后需停止再启动；前端有 Vite 热更新。

演示体验：先停止已有服务，再执行 `.\scripts\start-dev.ps1 -Demo`。此模式使用独立的 `e2e.db` 与 `e2e-checkpoints.db`，忽略 `.env` 的模型密钥和应用登录配置，绑定本机地址，不修改 `.env`。页面保存的模型配置属于所选数据库，仍然生效；不配置模型时可离线使用规则分析。

如果前端已单独运行，但 `/api/market/quotes` 返回 500，先检查
`http://127.0.0.1:8001/api/health`。Vite 会把请求转发到 8001 端口；后端未启动时，
代理连接失败也会返回 500。没有进程清单且 8001 端口空闲时，可仅补启后端：

```powershell
.\scripts\start-dev.ps1 -ApiOnly
```

该模式执行数据库迁移、启动 API 和 worker、检查 API 健康状态并记录 PID；不会启动第二个前端。
`stop-dev.ps1` 只停止清单内的服务，单独启动的前端仍由原终端管理。

```powershell
.\scripts\stop-dev.ps1
```

脚本仅清理本项目登记的进程树，并校验 PID 的启动时间，避免误杀其他项目。端口被占用时启动会明确失败，不会自动抢占端口。

## 配置与 PostgreSQL

默认配置可直接运行。需要修改配置时，将 `apps/api/.env.example` 复制为 `apps/api/.env`（不要覆盖已有配置）。不要把密钥放入前端环境变量。

推荐使用左侧导航 **模型设置**（手机端先打开左上角菜单），也可点击行情表格旁的 **配置 API / 管理模型**：

1. 在「API 配置管理」点击「新增配置」，填写名称、API 地址与密钥。每套配置拥有独立的模型列表与 Ollama 备选设置，最多保存 30 套。
2. 在「可选模型」输入供应商的模型 ID，按回车添加；选择默认模型。
3. 可选点击「测试 API 连接」，检查当前编辑配置的连接与一次工具调用；会按供应商规则计费。
4. 点击「保存设置」，然后点击「切换启用」。切换立即生效，无需重启；回到行情工作台选择该配置中的分析模型。编辑当前启用配置并保存会立即生效，编辑其他配置不会切换供应商。
5. 从「选择配置」打开已有配置进行编辑；点击「删除配置」并确认可移除。删除当前启用配置会停用 API，直到启用另一套；不会自动退回环境密钥。旧任务仍使用提交时的不可变版本。

升级迁移 `0005_model_profiles` 会把原来页面保存的单套配置保留为「默认配置」。尚只使用 `.env` 时，可先保存当前设置，将其加入管理列表。新增、保存、切换和删除都不会自动发起模型请求。

密钥保存后不回显；留存已有密钥、更换密钥、清除当前配置密钥都在设置页完成。页面配置优先于 `.env`。以下 `.env` 方式作为尚未保存页面配置时的默认值：

```dotenv
LLM_BASE_URL=https://your-provider.example/v1
LLM_API_KEY=your-private-key
LLM_MODEL=your-default-model
LLM_MODELS=["your-default-model","your-second-model"]
```

要求支持 OpenAI 兼容 **Chat Completions + 工具调用**。Ollama 地址与模型也可在设置页修改；需自行启动本机服务并安装模型，然后手动选择，API 出错不会自动切换。当前操作见[模型配置](docs/modules/model-profiles.md)与[行情和任务](docs/modules/market-and-jobs.md)；早期设计和访问控制背景保留在 [P1 文档](docs/history/p1.md)。

```powershell
# 可选：需要 Docker Desktop 正在运行
docker compose up -d postgres
```

在 `apps/api/.env` 设置：

```dotenv
DATABASE_URL=postgresql+psycopg://stock:stock_local@127.0.0.1:5432/stock_engine
CHECKPOINT_POSTGRES_URL=postgresql://stock:stock_local@127.0.0.1:5432/stock_engine
```

然后重新执行启动脚本，它会迁移新的数据库。切换数据库不会自动搬迁 SQLite 中的历史记录。Compose 的账号密码仅用于本地开发。PostgreSQL 路径在配置上支持；本次自动化测试以 SQLite 为基线，不能据此宣称已完成 PostgreSQL 集成验证。

## 目录结构

模块职责与调用链见[源码导航](docs/architecture/source-map.md)，学习、功能、数据与历史资料见[文档总索引](docs/README.md)。

```text
stock-engine/
├── apps/
│   ├── web/
│   │   ├── src/
│   │   │   ├── api/              # HTTP 请求及前后端契约
│   │   │   ├── components/       # 复用界面组件
│   │   │   ├── pages/            # 路由页面；Quant/QuantRun/Research/History 已采用目录入口
│   │   │   ├── features/         # 量化工作流与研究共享展示
│   │   │   ├── lib/              # 时间、金额等纯函数
│   │   │   └── styles/           # 全局基础样式与 CSS Modules
│   │   └── e2e/                 # 浏览器端到端测试
│   └── api/
│       ├── app/
│       │   ├── core/config.py   # 环境变量与配置校验
│       │   ├── providers/      # 行情适配器及演示样本
│       │   ├── http/           # 系统接口、请求依赖
│       │   ├── shared/         # 时间与证券通用规则
│       │   ├── market/         # 行情路由、快照与日历
│       │   ├── jobs/           # 任务生命周期、SSE 与冻结证据组合
│       │   ├── reports/        # 报告查询与同步规则报告
│       │   ├── research/       # 研究采集、查询、历史与证据
│       │   ├── portfolio/      # 持仓契约、路由与完整写入操作
│       │   ├── model_settings/ # 模型配置路由与版本管理
│       │   ├── quant/          # 数据版本、训练、回测与实验摘要
│       │   ├── agents/         # LangGraph 状态、节点和图
│       │   ├── db.py           # 数据库连接与 ORM 模型
│       │   ├── schemas.py      # 请求 / 响应数据契约
│       │   ├── runtime/        # 进程监督、领域执行槽与采集调度
│       │   ├── worker.py       # 单实例锁、恢复与运行装配
│       │   └── main.py         # API 生命周期，不执行慢速采集
│       ├── migrations/        # Alembic 数据库迁移
│       └── tests/             # 接口和工作流测试
├── docs/                      # 分类索引、学习、功能模块与前后端规范
├── scripts/                   # Windows 服务启停
├── compose.yaml               # 可选 PostgreSQL
├── pnpm-lock.yaml             # 前端依赖锁
└── apps/api/uv.lock            # 后端依赖锁
```

## 组件目录与样式

新建或迁移的可视模块使用 PascalCase 目录，内部放置 index.tsx 与 index.less，保留命名导出。当前 pages 下的页面、features 下的可视模块以及鉴权、错误提示和 Agent 展示组件均已采用该结构；固定局部样式放在 index.less，真正共用的布局继续复用 Workbench.module.css。main.tsx 与 App.tsx 保留应用装配和外壳入口；首页直接加载，其余页面按路由懒加载，任务/报告列表与详情分别组织。Vite 通过 apps/web/build/component-less.ts 将 src 内相对路径导入的 index.less 交给 Less/CSS Modules 管线；全局 CSS、主题和原有请求/状态管理继续复用。

修改该编译规则后，在根目录执行 scripts/check-styles.ps1。它以隐藏进程使用随机本机端口验证样式隔离、热更新和生产提取；依赖现有 pnpm、Node 22.6+ 的类型剥离支持以及 Microsoft Edge，不启动业务 API。读取 .runtime/styles.exit-code（0 才算通过），详细输出在 styles.stdout.log / styles.stderr.log。测试临时源码自动清理，截图和产物保留在 .runtime/p0-less-*。

## 检查与测试

```powershell
# 根目录：类型、规范与生产构建
pnpm typecheck
pnpm lint
# 构建在独立隐藏进程运行，输出写入 .runtime
.\scripts\build-web.ps1

# 后端：使用 uv 或直接调用虚拟环境解释器
cd apps/api
uv run pytest -q
uv run ruff check .
cd ../..

# 浏览器测试使用隔离演示库，先停止已有服务；默认 Microsoft Edge
.\scripts\stop-dev.ps1
.\scripts\start-dev.ps1 -Demo
pnpm test:e2e
.\scripts\stop-dev.ps1
```

其他平台可将 Playwright 配置中的 `channel: 'msedge'` 删除，并安装 Chromium。生产构建输出在 `apps/web/dist`，本地 Vite 代理不包含在静态构建中；正式部署时需为 `/api` 配置反向代理，为页面路由配置 SPA fallback。

## Agent 流式研究与报告抽屉

提交研究后，任务页按时间顺序展示计算步骤、模型返回的可展示思考内容、工具参数及完整结果、Markdown 正文。正文与结构化解读按真实模型增量更新，前端逐字呈现；模型未提供思考字段时明确提示，规则模式不生成虚构思考。

报告随规则节点和模型输出逐步形成。桌面端使用右侧可调宽抽屉，支持拖拽、宽度记忆、方向键调整和 Esc 收起；移动端从报告卡片打开全屏抽屉。收起报告不会取消任务，可点击卡片重新打开。完成后保留分析过程，通过「打开完整报告」查看归档结果。

事件存入现有 `JobEvent` 表，断线续传、刷新可回放；无需数据库迁移。部分报告标为草稿，完整 JSON、结构与引用校验通过后才归档。旧任务只能回放原先保存的节点事件。实现说明见 [Agent 流式输出](docs/modules/agent-stream.md)。

## 阅读顺序

P3 使用方式、CSV 数据契约、防泄漏规则和成交边界见 [P3 文档](docs/modules/quant.md)。首个目标为「未来 5 日涨幅 ≥20%」，所有预测仅是所选数据版本上的研究结果；全市场覆盖、上线概率、Level-2 与实盘执行尚未完成。

1. [P2 功能与操作](docs/modules/research.md)：研究、持仓、历史与证据冻结；[P2 数据源核验](docs/data/research-sources.md)。[P1 配置](docs/history/p1.md) 和 [P0](docs/history/p0.md) 保留为历史基线。
2. [面向前端开发者的学习路线](docs/learning/agent-development.md)：从一次点击理解后端、LangGraph 与数据库。
3. [架构与数据约定](docs/architecture/overview.md)：模块边界、快照、时区和未来扩展。
4. [验证记录](docs/history/verification.md)：测试结果、已修复问题与未验证范围。

默认脚本绑定本机地址。P1 已提供单用户访问密钥、进程内限流和独立任务执行；外网部署仍需 HTTPS 反向代理、SSE 禁用缓冲、SPA fallback，并确认公开数据的再分发权限。

## 运行诊断与持久数据

worker 的进程启动、退出、超时、取消和启动失败写入 `.runtime/worker.stderr.log`，结构化字段为任务类别、任务 ID、结果和退出码，不写模型密钥、完整命令参数或持仓。入口与故障测试见[源码导航](docs/architecture/source-map.md)。

备份须同时保护业务数据库、独立 checkpoint 与 `QUANT_ARTIFACT_DIR` 指向的量化文件；先停止本项目写入进程，再按实际配置备份。SQLite 如存在 WAL/SHM，使用一致性备份或停机确认完成 checkpoint 后复制，不单独拷贝仍在写入的主库文件。`.runtime/` 日志与 PID 可重建，数据库和被引用的产物不是缓存。本轮重构没有搬迁这些目录；未引用产物的处理边界见[量化文档](docs/modules/quant.md)。
