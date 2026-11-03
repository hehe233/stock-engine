# 目录与功能模块重构方案

[返回文档总索引](README.md) · [架构索引](architecture/README.md) · [源码导航](architecture/source-map.md)

评估日期：2026-11-03。本文记录结构评估、实施方案和进度；P0、P1 结构改造已完成并通过对应验证，后续按 P2–P3 分阶段推进。项目定位以 [AGENTS.md](../AGENTS.md) 和 [项目 README](../README.md) 为准：单用户、单机的 A 股研究与 Agent 学习项目，当前处于 P3 研究验证阶段。

前端组织方式按用户明确要求修订：参考 `E:/BRDKurin/project/code/a2a-frontend`，页面、可视业务模块和独立组件采用「语义目录 + `index.tsx` + `index.less`」。保留 CSS Modules 的局部作用域，样式语言迁到 Less；P0 已接入 Less/CSS Modules 并将 ErrorNotice 迁为目录组件；P1 已迁移 Quant/QuantRun/Research/History 及其领域模块；其余页面以后续功能改动为单位渐进迁移。

## 实施状态与优先级

这里的 P0–P3 是重构优先级，与项目功能阶段无关。正文的现状证据保留评估时上下文；已经完成的内容以本节和验证记录为准。

| 优先级 | 内容                                                          | 当前状态                                      |
| ------ | ------------------------------------------------------------- | --------------------------------------------- |
| P0     | Less/CSS Modules 构建基础；公共请求、时间、证券及采集依赖拆分 | 已完成；验证见[记录](history/verification.md) |
| P1     | Quant 工作台/详情、研究共享表格；后端业务路由与冻结证据归属   | 已完成；验证见[记录](history/verification.md) |
| P2     | HTTP/查询缓存、响应契约、worker 进程监督与量化产物读取        | 待实施                                        |
| P3     | 按实际需求拆 ORM、生成类型与迁移持久数据目录                  | 条件实施                                      |

P0 具体入口：前端 build/component-less.ts、ErrorNotice/index.tsx 和 index.less；后端 http/dependencies.py、shared/time.py、shared/securities.py、providers/base.py、providers/runner.py、providers/normalization.py。调用方和测试已经切换公共导入；表结构、API 路径与任务执行语义不变。

### P1 本批改造与原因

| 已实施改造                                                                                                        | 为什么这样优化                                                                               |
| ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `pages/Quant/`、`pages/QuantRun/` 分别懒加载；`features/quant/` 拆出工作台、导入、实验表单、审计和报告            | 数据导入、参数编辑和结果阅读独立变化，各自管理交互状态，页面不再同时承担两个路由的完整实现   |
| Research、History 迁成目录入口，共用 `features/research/components/ResearchDataset/` 与 `SourceNotice/`           | 消除页面间实现依赖；修改研究表格或来源说明只需维护一处                                       |
| 可视模块使用 `index.tsx + index.less`；共用布局通过 TS 导入原 Workbench CSS Module                                | 固定样式与模块同目录，同时避免复制整份布局规则或通过多处 CSS composition 产生重复构建样式    |
| 路由按 market/model_settings/jobs/reports/research/portfolio 分组；main 统一装配                                  | 按业务直接找到接口与操作；旧主路由及 research_routes 已移除，HTTP 路径与响应保持兼容         |
| 任务、持仓、模型配置写入锁与提交归 service；同步规则报告归 reports/service                                        | 完整操作从其他调用方使用时也有相同约束，不依赖路由帮忙加锁或提交；事件和业务写入保持同一事务 |
| 研究拆成 collection/queries/history/evidence/demo/catalog/schemas；量化摘要归 quant/evidence，组合归 jobs/context | 研究模块不再读取量化 ORM，任务拥有跨领域编排；重试继续使用原提交证据                         |
| 量化导入经 research/queries 的 archived_history 读取普通数据                                                      | 研究侧掌握来源选择，量化侧只负责转换与审计，避免双方深入对方存储实现                         |

本批没有迁移数据库、checkpoint 或量化产物目录，没有调整研究/概率口径。根 schemas.py 暂保留现有共享响应契约，worker 监督与 quant/data.py 的产物拆分留在 P2；Dashboard、Portfolio、ModelSettings 和 Agent 展示组件尚未批量改目录。

### 接下来 P2 的顺序与理由

1. **先整理 HTTP、领域请求和查询缓存。** 从 api/client.ts 独立 request，再按领域集中 query key 与失效规则；保留 cookie、超时、SSE 和既有 key 形状。原因：P1 已把模块拆开，跨页面刷新规则仍分散，容易出现操作成功而其他视图仍显示旧值。
2. **核对响应契约与缺失语义。** 在实际 API 消费点补齐 schema 和前端类型；先维护明确契约，再决定是否值得自动生成类型。原因：重构后调用路径更清楚，但时间、来源和 unknown/null 的含义仍需跨端一致。
3. **抽取 worker 进程监督。** 先覆盖退出、超时、取消与回收，再合并重复运行管理。原因：这部分直接影响故障恢复，不能只把相似代码搬到基类。
4. **独立量化产物接口。** 集中路径、哈希核验和分页读取，保留当前文件布局。原因：训练、下载与查询应共用完整性规则，避免各自解释产物细节。

以下原始问题与现状段落保留评估时上下文；链接已指向迁移后的归属，当前入口以本节与源码导航为准。

## 1. 总体判断

**顶层结构合理，应保留；功能内部的职责归属和跨模块依赖需要渐进整理。**

`apps/web`、`apps/api`、`scripts`、`docs` 分别承载前端、后端、Windows 运行管理和文档，符合现有运行方式。后端已有 provider、service、worker、LangGraph 和量化计算的职责划分；前端已有统一请求、TanStack Query、页面路由、CSS Modules 和独立流式消费模块。这些基础值得保留。

主要问题来自功能逐步扩展后组织方式不一致：后端同时存在根目录路由、横向 services 和纵向 quant 包；前端部分领域已有独立请求文件，但大型页面仍集中表单、查询、操作和结果展示。优化目标是让一次功能修改更集中，让调用方通过稳定接口使用能力，而不是单纯增加目录或减少文件行数。

### 1.1 保留的设计及理由

| 现有设计                           | 判断与理由                                                                                          | 依据                                                                             |
| ---------------------------------- | --------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| 前后端同仓、分别管理依赖           | 适合单人跨端开发；保留 pnpm、uv 和各自锁文件，无需引入多仓或新的构建编排框架                        | [根配置](../package.json)、[后端配置](../apps/api/pyproject.toml)                |
| API 与独立 worker                  | 慢任务与 HTTP 生命周期分离已经存在，继续在此基础上维护取消、超时和恢复                              | [应用入口](../apps/api/app/main.py)、[worker](../apps/api/app/worker.py)         |
| 不可变快照、配置版本和量化数据版本 | 是研究可追溯性的基础，目录调整不得改变这些业务语义                                                  | [数据库模型](../apps/api/app/db.py)、[任务创建](../apps/api/app/jobs/service.py) |
| 量化按功能聚合，计算与执行分离     | `quant/` 已有 routes、schemas、data、service、engine、backtest 等分工，可作为其他模块渐进聚合的参考 | [量化目录](../apps/api/app/quant/)                                               |
| SQLAlchemy 直接查询                | 当前规模无需通用 Repository / BaseService；应优先解决已有职责混杂，避免新增纯转发层                 | [现有架构约定](architecture/overview.md)                                         |
| docs 按用途分类，AGENTS 按任务导航 | 当前功能、学习、规范和历史分开，整体合理；只需补齐计划入口及随迁移更新事实                          | [文档总索引](README.md)、[Agent 入口](../AGENTS.md)                              |

### 1.2 已确认的主要结构问题

| 问题                         | 源码证据                                                                                                         | 维护影响                                               |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| 公共依赖放在具体业务路由中   | `research_routes.py`、`quant/routes.py` 都从 `app.routes` 导入 `SessionDep`                                      | 修改或拆分主路由会牵动其他领域；通用依赖应向下独立     |
| 主路由聚合多个业务领域       | `routes.py` 同时定义 health/config、模型配置、行情、分析报告、任务及 SSE                                         | 不相关功能共享一个变更入口，事务和传输职责难以单独阅读 |
| 研究数据模块承担多类变化     | `research_data.py` 同时包含 enqueue、process_one、dataset、history_statistics、frozen_context、schedule_research | 新增数据源、修改统计与调整任务证据会落到同一文件       |
| 功能聚合方式不统一           | `quant/` 是纵向包，研究和持仓分散在根目录、services、providers                                                   | 需要先记住历史命名，才能找到一次功能修改涉及的文件     |
| 大型前端页面混合多个用户流程 | `Quant.tsx` 同时导出 `QuantPage`、`QuantRunPage`，`main.tsx` 两个懒加载都指向该文件                              | 列表、导入、参数配置和结果展示难以独立演进             |
| 通用传输与领域调用同文件     | `api/client.ts` 同时提供 request 和行情、任务、报告、模型配置、认证方法                                          | 通用传输成为业务调用集合的依赖，领域划分不清晰         |

## 2. 优化原则

1. **先解除具体耦合，再按功能整理。** 优先独立公共依赖和明确事务归属，不先做全仓目录搬迁。
2. **保留单机模块化应用。** 多进程用于任务隔离，不据此引入微服务、分布式队列或分布式事务。
3. **接口包含行为约定。** 不仅规定函数参数，还规定快照版本、数据模式、时间含义、事务提交者、错误和取消语义。
4. **按用户行为和变化原因拆分。** 领域内聚合请求、状态与展示；只有真实复用的能力才进入共享目录。
5. **一次迁移一种职责。** 路径迁移尽量保持 HTTP 契约、表结构、检查点和历史数据不变；行为改动独立验证。
6. **用结果验收。** 验收调用方向、数据一致性、恢复能力和查找成本，不以目录层数或行数达标代替设计判断。

## 3. 优化项、理由与完成标准

以下优先级是重构顺序，与项目 P0/P1/P2/P3 阶段无关：A 为优先实施，B 为随后按功能推进，C 为有实际需求时再做。

### 3.1 A / P0：独立公共依赖（已实施）

**现状。** 除 `SessionDep` 放在 `routes.py` 外，[research_schemas.py](../apps/api/app/research/schemas.py)、[quant/data.py](../apps/api/app/quant/data.py) 等还从 [providers/public.py](../apps/api/app/providers/public.py) 导入 `SHANGHAI`、`normalize_symbol`；研究 provider 从该文件导入 `ProviderError`、`run_collector`。一个具体行情适配文件同时承载了通用规则和子进程执行。

**方案。**

- 新建 `app/http/dependencies.py`，承接 `get_session`、`SessionDep`；业务路由只依赖该文件，不互相导入。保持 Session 创建、关闭与异常处理方式。
- 把确实跨领域使用的时区、证券代码规范化分别迁到 `app/shared/time.py`、`app/shared/securities.py`；数据源字段映射、源时间解析仍由 provider 负责。
- `ProviderError` 放在 `providers/base.py` 或专用错误文件，采集子进程封装放在 `providers/runner.py`。先保留既有参数和错误描述，不顺手改写采集行为。
- `utc_now`、`as_utc` 当前在 `db.py`；如同时迁入 `shared/time.py`，一次更新明确的调用方，避免维护两套时间实现。共享目录只接纳已证明有多个调用方的能力。

**为什么。** schema 校验和量化数据处理不应需要了解具体公开行情适配器；基础依赖从业务入口独立后，拆分某个路由不会传播到其他领域。这是减少真实依赖，收益高于统一所有文件命名。

**完成标准。** 其他路由不再从主业务路由导入 `SessionDep`；通用证券与时间规则不依赖 `providers.public`；既有证券格式、未知时间、异常码及测试替换点保持一致。移动函数后检查 monkeypatch 的目标路径，不只检查生产 import。

### 3.2 A / P1：按功能收拢路由，明确事务由谁提交（已实施）

**现状。** [routes.py](../apps/api/app/jobs/routes.py) 横跨多个领域；`create_analysis` 在路由内执行图、构造报告并提交事务，`cancel_job` 在路由内修改任务与事件。[research_routes.py](../apps/api/app/research/routes.py) 同时处理研究查询和持仓增删改。与此同时，`services/jobs.py` 已承担创建、重试和领取，职责不是完全缺失，而是尚未收齐。

**方案。**

1. 先把行情、模型配置、研究任务、报告、研究资料、持仓的路由按领域拆出，`main.py` 只做装配；health/config 归 `http/system.py`。HTTP 路径、响应、认证和状态码保持兼容。
2. 将任务取消放回任务生命周期接口；将持仓修改和删除放回持仓操作接口；把同步规则报告的执行与保存放入报告用例。路由保留输入校验、HTTP 错误映射和响应转换。简单只读查询不必强行套一层转发函数。
3. 对每个写入用例明确 Session 和 commit 的所有者。底层组装或写入辅助函数可 flush，但不随意提交调用者的事务。队列容量锁、持仓锁也与完整写入操作一起迁移，避免移动后绕过锁。
4. `POST /api/analyses` 是现有短时规则分析兼容接口，保留其行为；不能在目录整理时直接删除或悄悄改为异步。

**为什么。** 拆文件只能改善定位，统一事务归属才能避免后续调用同一操作时漏写事件或部分提交。保留直接 SQLAlchemy 查询，避免用通用 CRUD 框架掩盖不同业务的约束。

**完成标准。** API 路径和行为不变；路由不再自行编排多步业务写入；失败路径不会留下半份业务结果。异步成功报告、任务成功状态及成功事件继续在同一事务提交，参考 [run_job.py](../apps/api/app/agents/run_job.py) 当前实现。

### 3.3 A / P1：拆开研究数据职责，把跨领域证据组装放到任务侧（已实施）

**现状。** [research_data.py](../apps/api/app/research/collection.py) 同时处理请求去重、采集执行、快照查询、资金派生、历史窗口统计、演示初始化、调度和冻结证据。`frozen_context` 直接 join `QuantRun` 与 `QuantDataset` 并解释实验报告字段；研究资料模块因此知道量化存储细节。

**方案。** 按现有函数群迁移，避免为每个函数建文件：

| 拟归属                   | 迁入职责                                                  | 对外约定                                           |
| ------------------------ | --------------------------------------------------------- | -------------------------------------------------- |
| `research/collection.py` | enqueue、process_one、recover_requests、schedule_research | 请求去重、领取、超时、失败保留旧快照               |
| `research/queries.py`    | dataset、snapshot_view、资金和行业查询组装                | 返回已有来源、日期、缺失和分页语义                 |
| `research/history.py`    | history_statistics、history_list                          | 只给描述统计，不包装成胜率                         |
| `research/evidence.py`   | 研究与历史证据的截止时点选择                              | 同证券、同模式、提交前已可见                       |
| `quant/evidence.py`      | 当前 frozen_context 中的实验摘要查询                      | 已成功、截止时间、证券和实验时段匹配，保留研究限制 |
| `jobs/context.py`        | 组合研究、量化及显式选择的持仓证据                        | 在提交事务中生成一次 JSON 可序列化快照             |

演示初始化和历史案例目录归研究模块；provider 仍只负责取数和标准化。证券、模式、截止时间、行情日期在组合入口明确传入。初次迁移保留现有选择逻辑、数量限制和缺失原因；若需改进证据覆盖，另立行为变更。

**为什么。** 新增量化摘要字段应由量化模块维护；任务模块本来就需要组合多个领域，因此由它承担编排最自然。这样可避免 `research → quant → research` 的业务逻辑互相深入。特别是 `quant/data.py` 当前会读取研究历史快照，迁移时要同时把该来源读取收口到研究查询接口，不能只移动 frozen_context 的函数名。

**完成标准。** 研究模块不再直接读取量化 ORM；量化转换历史数据通过研究侧明确的读取接口获得输入；任务执行和重试仍使用提交时冻结的 context，不重新读取最新数据。保留缺失证据、目标证券席位、个股行情日期及持仓 opt-in 的回归验证。

### 3.4 A / P1：先拆前端量化页面，再解决页面之间的依赖（本批已实施）

**现状。** [Quant.tsx](../apps/web/src/pages/Quant/index.tsx) 包含数据版本选择、CSV 预览导入、实验表单、列表、指标、回测结果及逐笔预测；两个路由页面共用同一源文件。另有 [History.tsx](../apps/web/src/pages/History/index.tsx) 直接从 `./Research` 导入 `ResearchDataset`，页面成为另一个页面的组件库。

**方案。**

- 在 `features/quant/` 内按流程拆出 `QuantWorkspace/`、`DatasetImportPanel/`、`ExperimentForm/`、`QuantRunReport/` 等目录，每个可视模块以 `index.tsx` 为入口，独立样式放在同目录 `index.less`；表单草稿留在使用它的模块中，查询和失效策略在领域内聚合。
- 当前 `pages/Quant.tsx` 迁为 `pages/Quant/index.tsx`，详情迁为 `pages/QuantRun/index.tsx`；页面自身布局放在对应 `index.less`，具体业务布局留在 feature。分别按需加载，保留 `main.tsx` 路由注册及现有 URL；拆分后的包大小和加载速度需要实际构建测量。
- 把 `ResearchDataset/`、`SourceNotice/` 放到 `features/research/components/`，各自使用 `index.tsx + index.less`；Research 和 History 页面共同使用，禁止页面之间导入展示实现。
- 随后整理 ModelSettings、Portfolio、Dashboard。现有 `components/agent/` 的订阅和投影逻辑继续复用，其中独立展示组件也逐批迁成组件目录和成对入口；稳定行为是保留对象，不将旧的平铺文件命名作为永久例外。
- 样式与实现同目录维护；`styles/` 只维护主题、全局和确实复用的布局。现有 Workbench CSS 在调用方迁完前继续保留；不能把其中全部规则复制进每个 `index.less`。`App.tsx` 继续作为持久外壳组合入口，需要拆出的侧栏等采用同样的目录约定，不改变 Outlet 的挂载身份。

**为什么。** “选择数据版本”“导入”“创建实验”“阅读报告”是独立变化的流程，比按 JSX 行数切块更稳定。目录名表达功能，固定入口降低定位成本；实现与样式一起移动，新增私有组件、hooks、类型也有明确位置。研究表格移到领域模块可消除已有的页面间依赖。Less 用于组织局部样式，CSS Modules 继续保证不同目录中的同名类不会相互影响。

**完成标准。** 独立可视模块按目录和成对入口组织，样式按 CSS Modules 实际编译；页面不互相导入，列表和详情入口可单独阅读；预览失效、文件大小限制、导入结果选中、分页和取消后的缓存更新保持正确；桌面/窄屏、错误/空态及深链接通过验证。

#### 3.4.1 参考事实与本项目的 Less 适配前置工作

已核对参考项目的 `docs/agent-rules/component-development.md`、`src/components/ui/ResizableDrawer/index.tsx` 与 `index.less`、`src/features/suppliers/SupplierManagementPage/index.tsx`、`src/types/css.d.ts` 及 `next.config.ts`。其代码使用 `import styles from './index.less'`，并通过 Next.js/webpack 配置将普通 `.less` 按 CSS Modules 处理；文件名本身不产生局部作用域。参考路径仅用于说明依据，项目运行不依赖本机另一个仓库。

P0 已在 [package.json](../apps/web/package.json) 声明 Less，并在 [vite.config.ts](../apps/web/vite.config.ts) 注册 build/component-less.ts。以下是该适配应持续满足的要求：

1. 给 web 工作区增加 Less 开发依赖并更新锁文件，沿用本项目 Vite；不复制参考项目的 Next.js、less-loader 或 webpack 配置。
2. 明确实现 `index.less` 的 CSS Modules 处理链。本项目已安装的 Vite 源码以 `.module` 文件名模式判定 CSS Modules，用户指定的 `index.less` 需要显式适配；可采用限定在本项目组件路径的 Vite 插件，将其交给 Less 与 CSS Modules 管线处理并导出类名映射，具体实现须在本项目验证。不能仅改后缀、添加 `css.modules` 选项或 TypeScript 声明就宣称迁移完成。
3. 为 `*/index.less` 补充与实际导出一致的类型声明，camelCase 类名原样使用；类型声明是编译约定，不代替运行时样式处理。全局样式保持明确的全局入口，不将第三方或全局 Less 自动套入组件规则。
4. 先以两个具有同名局部类的组件验证隔离，检查开发热更新、生产 CSS 提取、资源相对路径和 Less 嵌套；确认旧 `.module.css` 能在过渡期继续工作。使用一个实际页面完成视觉与交互验收后，再扩展迁移。
5. antd 覆盖仍结合局部类和实际 portal 挂载位置；保留本项目主题和前缀，不照搬参考项目的 `a2a` 前缀或 `@ant-prefix` 注入。

构建判断已与本项目安装目录 `apps/web/node_modules/vite/dist/node/chunks/config.js` 中的 `cssModuleRE` 和 `compilePostCSS` 核对；该安装路径仅是本次检查位置，不是需要修改或长期依赖的配置入口。P0 已加入依赖、编译适配及仅针对 */index.less 的类型声明；以真实浏览器和构建测试验证这些约定。

[页面规范](agent-rules/frontend/page-development.md)、[组件规范](agent-rules/frontend/component-development.md) 和 AGENTS 已同步：新建/迁移模块采用目录入口，未迁移的 CSS Modules 与平铺组件继续工作。

### 3.5 B：分开 HTTP 传输、领域请求与查询缓存约定

**现状。** [api/client.ts](../apps/web/src/api/client.ts) 混合基础 request 和多个领域方法，research/quant 又依赖它。query key 和失效操作分布在页面及 [useJobStream.ts](../apps/web/src/components/agent/useJobStream.ts) 中。已有合理的统一请求与缓存体系，无需替换。

**方案。**

1. `api/http.ts` 只承接现有 request；在 `api/market.ts`、`jobs.ts`、`reports.ts`、`model-settings.ts`、`portfolio.ts`、`research.ts`、`quant.ts` 等按实际调用拆分领域契约。认证和应用配置可保留小型专用文件；不强制每个文件继续拆成 types/client 两份。
2. 旧 `api/client.ts` 可作为短期兼容导出；所有调用迁移且搜索确认无旧依赖后移除，不能永久保留两份实现。CSV 下载和 SSE 维持各自的传输方式。
3. 各领域在 `features/<领域>/queries.ts` 集中 query key、查询选项和必要的 mutation 协调。首轮保留 key 形状；后续更名时同时更新 useJobStream、页面和全部失效调用。
4. 切分不改变 cookie 认证、30 秒默认超时、可传入 signal、安全错误、查询重试和后台轮询策略。

**为什么。** 基础传输可独立维护，领域请求可直接定位；缓存身份与失效规则集中后，减少“请求成功但其他视图仍旧”的维护风险。不要为了封装再引入全局状态库或第二套请求客户端。

**完成标准。** 所有普通 JSON 请求继续经过同一个 request；新增或更名 query key 时有对应失效验证；模型切换后相关配置视图更新，任务终态仍刷新详情且不会每 token 发请求。

### 3.6 B：提取 worker 的进程机械操作，保留各类任务状态差异

**现状。** [worker.py](../apps/api/app/worker.py) 的 `run` 同时协调行情、研究采集、Agent 和量化。Agent 与量化分支重复 Popen、poll、超时、kill/wait 和退出处理，但 Agent 有租约与检查点，量化中断按失败处理，不是同一种任务协议。子进程 stdout/stderr 当前写入 DEVNULL。

**方案。**

- 保留 `app.worker` 启动入口和本机单实例锁；把子进程启动、存活检查、终止等待及单调时钟超时判断提取到小型 `runtime/processes.py`。这些操作有两个已存在的调用方。
- Agent 执行槽和量化执行槽各自负责领取、取消状态、失败写回及恢复策略；行情/研究调度单独组织。worker 主循环只协调它们，不引入通用插件注册系统。
- 保留最多一个 Agent 子进程、一个量化子进程和两条采集协调线程的当前运行约定；抽取代码不扩大并发。
- 增加任务 ID、类型、退出码和安全失败类别的结构化日志。需要子进程日志时使用有大小/保留策略的文件并脱敏，不把原始模型响应、凭证或个人持仓写入日志。

**为什么。** 进程回收和超时机制可以复用，业务状态机应明确区分。将进程监督独立后，可以用可控短进程或替身验证异常退出，而不必运行整个采集和模型链。日志改善故障定位，但不需要引入新的监控平台。

**完成标准。** 单实例锁仍先于中断恢复；取消/超时后进程被回收；旧执行者不能覆盖新状态；量化仍不借用 Agent checkpoint；启动方式和 Windows PID 管理不变。先补足进程层行为验证再移动逻辑，不能只凭函数改名后的单元测试通过验收。

### 3.7 B：量化文件读写形成明确接口，保持纯计算模块稳定

**现状。** [quant/data.py](../apps/api/app/quant/data.py) 兼有解析、校验、审计、文件路径、版本保存和历史转换；[quant/routes.py](../apps/api/app/quant/routes.py) 内还实现产物校验、读取全部文件计算哈希和 DuckDB 分页。[quant/service.py](../apps/api/app/quant/service.py) 已有任务协调，features/engine/backtest 的计算划分可继续使用。

**方案。** 将输入解析/校验聚合为 `quant/datasets.py`，历史转换保留明确来源接口；将固定产物路径、哈希验证、文件读取和预测分页收拢至 `quant/artifacts.py`，路由使用它的结果返回响应。文件版本保存与元数据提交的失败清理要有明确约定：只清理本次未完成的写入，不删除已引用版本。必要时细分，但不因文件数量追求统一模板。

**为什么。** 文件路径、完整性和查询是一组必须同时满足的规则；把它们放到同一接口可避免新增下载/查询入口时遗漏校验。训练算法不是本次结构问题，应尽量减少触碰。

**完成标准。** 仍只访问固定允许的产物，哈希被篡改时拒绝读取，SQL 参数绑定和模式隔离不变；失败保存不留下对调用方可见的半完成版本。现阶段没有吞吐测量，不能认定全文件哈希已构成性能瓶颈，也不能为优化擅自跳过校验。

### 3.8 B/C：完善契约与行为测试，再逐步整理测试归属

**现状。** 测试并非空白：[test_p1.py](../apps/api/tests/test_p1.py) 覆盖任务、恢复、鉴权、行情，[test_p2.py](../apps/api/tests/test_p2.py) 覆盖研究与持仓，[test_quant.py](../apps/api/tests/test_quant.py) 覆盖数值流程与产物；模型配置和流式已有专门测试。主要不足是阶段命名混合功能，以及部分接口返回字典而前端手写类型，难以只靠类型检查发现两端漂移。现有前端配置提供 Playwright，但没有单独的单元测试脚本。

**方案。**

- B：优先为本次要迁移的接口确认行为基线。先给研究数据、持仓、量化列表/详情等补充必要的明确响应 schema；对业务结果、null、模式、时点和错误码做契约验证，不只验证键名存在。
- B：SSE 是独立协议。后端事件与前端 `projectEvents` 的语义用共享语义夹具核对，覆盖重复、重试、分页排空、终态和草稿；不要认为生成 HTTP 类型即可覆盖 SSE。
- C：再把 test_p1/test_p2 按 market、jobs、research、portfolio 等职责迁移，保持可收集的测试和夹具行为，更新验证矩阵与文档命令；不以改文件名代替补行为覆盖。
- C：当稳定响应 schema 足够完整、手写类型维护确有成本时，再评估 OpenAPI 类型生成；生成文件与手写请求分开，工具及检查命令另行落地。当前不直接加入未验证的生成链。
- 若抽出的纯事件投影或表单逻辑需要快速测试，再选择轻量前端测试工具；保留跨端 Playwright 验证，不为目录迁移机械增加一套测试框架。

**为什么。** 重构最易损坏跨层契约，已有行为测试应成为迁移的保护，而不是重命名时一起被改写成与实现完全相同的断言。类型生成解决重复声明，无法替代数据语义和恢复验证。

### 3.9 C：按需求拆数据库模型，运行数据目录先明确归属

**现状。** [db.py](../apps/api/app/db.py) 集中了 Base、连接、时间函数及全部领域 ORM；[migrations/env.py](../apps/api/migrations/env.py) 通过 `Base.metadata` 获取模型。当前文件规模尚可，不能仅因集中就判为严重问题。配置中的 SQLite、checkpoint、量化产物默认路径相对运行目录；启动脚本固定以 `apps/api` 为工作目录。`.gitignore` 已排除数据库、缓存及量化产物。

**方案。**

- 若以后模型数量或修改冲突明显增加，再将连接/Base 迁到 `db/base.py`、`db/session.py`，各领域拥有自己的 models；显式提供唯一模型注册入口供 Alembic 和测试加载。此时同步所有导入，不留下同名 `db.py` 与 `db/` 的含糊过渡。
- 纯 Python 归属迁移不应改变表名、列或约束；核对 Alembic metadata 表集合，临时库升到 head 后应无意外删除/建表差异。不要为“搬文件”生成破坏性迁移。
- 运行数据先在 README 明确数据库、检查点、产物的配置和备份集合；`.runtime/` 仍只放日志、PID、临时检查输出。持久数据不能作为缓存清理。
- 未来需要统一数据根目录时，再设计兼容现有配置的迁移工具：预检、备份、停止写入、复制、核对哈希与引用、切换、回滚。默认路径改变不能悄悄创建空库，不能靠移动产物文件就假设引用已迁好。

**为什么。** ORM 拆分收益小于前述真实耦合，且有漏注册模型的风险；持久数据搬迁风险明显高于源码搬迁，应独立计划。单机研究项目尤其需要保留历史任务和实验，而不是只追求目录整齐。

### 3.10 B：文档保持现有分类，补齐计划状态和运行说明

现有 docs 已按 learning、modules、architecture、data、history、agent-rules 分类，不建议再次整体归档。按用户指定路径，将本方案放在 `docs/refactor-plan.md`，由总索引和架构索引共同引用，并明确“待实施”；不要把目标目录写进当前源码导航造成误导。

每一批实际迁移时，同步源码导航、受影响的功能说明、开发规范中的路径和测试命令。`AGENTS.md` 保持短入口；仅在模块归属或通用规则真正改变时更新。README 的安装与运行命令继续以 package 配置、锁文件和 scripts 为依据；P0/P1 历史文档不随当前重构被重写成新事实。

`scripts/start-dev.ps1`、`stop-dev.ps1`、`build-web.ps1` 已处理隐藏进程、输出重定向与 PID 信息，继续复用。后续可补一份简短运行手册说明工作目录、模式、产物备份和构建退出码；只有确有重复时才提取 PowerShell 共用函数。纯文档和路径整理不需要启动服务、抓取公开数据或调用付费模型。

## 4. 建议的目录与功能归属

### 4.1 顶层继续保留

```text
stock-engine/
├── apps/
│   ├── web/                 # 前端应用、配置与浏览器测试
│   └── api/                 # Python 应用、迁移与后端测试
├── docs/                    # 保留现有分类，新增本方案入口
├── scripts/                 # Windows 启停与构建入口
├── .runtime/                # 日志、PID、临时输出，非持久研究数据
├── AGENTS.md                # 简短项目约束与阅读导航
├── README.md                # 安装、运行与使用入口
├── package.json / pnpm-lock.yaml
└── compose.yaml             # 可选 PostgreSQL
```

不新增空的 `packages/`、`domain/`、`infrastructure/` 层，也不强行把 Python 与 TypeScript 契约做成同一个运行时包。下方是分批实施后的方向示意，目录名尚未全部存在；没有迁移需求的模块保持原位，不按图一次性建立全部文件。

### 4.2 后端：功能包负责业务，共享能力只保留必要部分

```text
apps/api/app/
├── main.py                  # 应用装配与生命周期
├── worker.py                # 保留 python -m app.worker 入口
├── core/                    # 配置、安全与认证
├── http/
│   ├── dependencies.py      # SessionDep 等公共 HTTP 依赖
│   └── system.py            # health/config 等系统接口
├── shared/
│   ├── time.py              # UTC、上海时区和既有转换约定
│   └── securities.py        # 通用证券标识规范化
├── db.py                    # 近期保留连接与 ORM；拆分属于条件项
├── market/                  # 行情 routes、schemas、快照操作、日历
├── model_settings/          # 配置 routes、schemas、版本及活动指针
├── jobs/
│   ├── routes.py            # 提交、查询、取消、重试
│   ├── service.py           # 任务生命周期与事务
│   ├── context.py           # 跨领域冻结证据组合
│   └── events.py            # 持久事件查询与 SSE 输出约定
├── reports/                 # 已归档报告查询、同步规则报告用例
├── research/
│   ├── routes.py / schemas.py
│   ├── collection.py        # 请求队列、采集协调及调度
│   ├── queries.py           # 研究快照与派生查询
│   ├── history.py           # 历史窗口统计
│   ├── evidence.py          # 研究证据读取
│   ├── catalog.py           # 现有历史观察目录
│   └── demo.py              # 隔离演示初始化
├── portfolio/               # 持仓 routes、schemas、导入与估值
├── quant/
│   ├── routes.py / schemas.py / service.py
│   ├── datasets.py          # 数据集解析、审计与版本保存
│   ├── artifacts.py         # 产物路径、完整性及读取
│   ├── evidence.py          # 对外提供冻结实验摘要
│   └── features.py / engine.py / backtest.py / run.py
├── agents/                  # 图、工具、模型协议、流式与 run_job 入口
├── providers/               # 外部适配、标准化、演示样本与采集进程
└── runtime/                 # worker 执行槽与进程监督
```

`services/`、根目录 `routes.py` / `schemas.py` 只在对应职责迁完后退场，迁移中允许新旧路径共存。旧路径如需兼容只能转发，不复制实现，并在该批任务中写清删除条件。没有实际复杂度的领域可以只含 routes 和少量实现，不强制全部拥有 service、repository、commands、queries 等模板文件。

### 4.3 前端：语义目录内统一 index.tsx 与 index.less

```text
apps/web/src/
├── main.tsx                 # 保留路由注册与 Provider 装配
├── App.tsx                  # 保留持久外壳
├── api/
│   ├── http.ts              # 唯一 JSON request
│   └── 按领域组织的请求与契约文件
├── pages/                   # 路由页面目录，只协调页面级组合
│   ├── Quant/
│   │   ├── index.tsx
│   │   └── index.less
│   ├── QuantRun/
│   │   ├── index.tsx
│   │   └── index.less
│   └── Research/            # History、Portfolio 等页面采用同样结构
│       ├── index.tsx
│       └── index.less
├── features/
│   ├── quant/
│   │   ├── QuantWorkspace/
│   │   │   ├── index.tsx
│   │   │   └── index.less
│   │   ├── DatasetImportPanel/
│   │   │   ├── index.tsx
│   │   │   ├── index.less
│   │   │   └── types.ts     # 仅在需要时增加私有类型或 hooks
│   │   ├── QuantRunReport/  # 同样使用 index.tsx + index.less
│   │   └── queries.ts       # 纯逻辑文件保留描述性名称
│   ├── research/
│   │   ├── components/
│   │   │   ├── ResearchDataset/
│   │   │   │   ├── index.tsx
│   │   │   │   └── index.less
│   │   │   └── SourceNotice/
│   │   │       ├── index.tsx
│   │   │       └── index.less
│   │   └── queries.ts
│   ├── portfolio/           # 可视模块按目录组织，内部成对放置入口与样式
│   └── model-settings/      # 配置选择、表单和操作反馈
├── components/
│   ├── agent/               # 保留流式职责，展示组件逐批迁移
│   │   ├── AgentStream/
│   │   │   ├── index.tsx
│   │   │   └── index.less
│   │   ├── ReportWorkspace/ # 同样使用 index.tsx + index.less
│   │   ├── useJobStream.ts
│   │   └── stream.ts
│   ├── layout/              # 侧栏等采用独立组件目录
│   └── ErrorNotice/
│       ├── index.tsx
│       └── index.less
├── lib/                     # 无业务副作用的格式等函数
└── styles/                  # 主题、全局、真正共享的布局样式
```

**命名与入口约定：**

- 页面、独立组件和可视业务模块使用 PascalCase 目录；`index.tsx` 实现并导出有名称的 React 组件，`index.less` 存放自身样式。调用方导入目录，例如 `features/quant/DatasetImportPanel`，不深入导入其私有实现。
- 组件内部使用 `import styles from './index.less'`，类名采用 camelCase；这要求先完成 3.4.1 的编译适配，不能直接在当前配置下批量改名。保留本项目既有命名导出习惯，不为统一文件名同时改变所有导出形式。
- `quant/`、`research/` 这类领域分组不必建立无实际 UI 的 `index.tsx`；hooks、查询、纯函数、类型仍使用 `useXxx.ts`、`queries.ts`、`types.ts` 等有含义的文件名。没有独立样式的纯逻辑或透传入口无需制造空 Less 文件。
- 小型私有子组件可留在父模块，独立复用或拥有独立样式后再建目录。目录入口不要成为导出整个领域的巨大汇总文件。
- 迁移 `Quant.tsx` 为 `Quant/index.tsx` 时，在同一批次删除旧实现并更新导入和懒加载；不能长期同时保留同名文件和目录，避免解析到旧入口。

**依赖约定：** 页面 → 功能模块/通用展示 → 领域请求 → `api/http.ts`。功能专属组件留在 feature；通用组件不反向依赖页面。Query 管理服务端数据，组件管理交互草稿，领域计算继续在后端。`components/agent/` 的现有职责和订阅生命周期保持稳定，其展示组件同样遵循目录约定，纯流式逻辑仍使用描述性文件名。

### 4.4 功能名称与代码归属

| 用户能力           | 主要归属             | 与其他能力的关系                                     |
| ------------------ | -------------------- | ---------------------------------------------------- |
| 行情浏览与刷新     | market               | 产生不可变行情批次；不负责模型解释                   |
| 研究资料与历史案例 | research             | history 是研究资料的历史视图，不等同全市场历史库     |
| 持仓               | portfolio            | 维护用户录入和估值，只有明确选择时成为任务证据       |
| 研究任务与实时过程 | jobs + agents        | jobs 管生命周期和持久事件，agents 管计算图与受控工具 |
| 已归档报告         | reports              | 与任务共享报告契约；草稿不冒充已归档结果             |
| 量化实验           | quant                | 独立版本、训练与成交模拟，向任务提供有时间限制的摘要 |
| 模型供应商配置     | model_settings       | 保存不可变配置版本，任务绑定提交版本                 |
| 导航、鉴权和主题   | 前端外壳 + core/http | 跨功能基础能力，不混入证券研究规则                   |

“研究任务”和“研究资料”在现有命名中都含 research，但前者是执行流程，后者是数据证据；明确区分能减少新功能归属歧义。菜单无需为目录调整而更名，历史研究页面也不应仅因带有“历史”就搬进 quant。

## 5. 分批实施顺序

首选先完成第 1 批和第 2 批的小范围改动，再处理跨领域证据和运行时。每批都应能独立审查、验收和回退；下表的完成标准是将来执行重构时的要求，不是本次已经通过的测试。

| 批次          | 范围和主要文件                                                                            | 依赖与预期收益                                        | 验收重点                                                            |
| ------------- | ----------------------------------------------------------------------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------- |
| 1：公共依赖   | `routes.py` 的 SessionDep；`providers/public.py` 的通用规则；全部直接调用方               | 无前置目录迁移；先解除明确反向依赖                    | 导入关系、校验行为、Session 关闭、现有回归                          |
| 2：前端试点   | 先接入 Less 与 index.less 的 CSS Modules 处理；再将 Quant、QuantRun、研究表格迁成目录入口 | 可在第 1 批后独立完成；先验证构建适配，再推广组件结构 | 样式隔离、HMR、生产构建、quant/p2 流程、类型与 ESLint、深链接及窄屏 |
| 3：业务收口   | 按领域拆路由；任务/持仓/报告写入迁回用例；研究数据与证据组合拆分                          | 依赖第 1 批；降低跨领域表结构依赖，统一事务归属       | API 契约、任务冻结、持仓 opt-in、配置版本、失败原子性               |
| 4：请求与契约 | `api/client.ts`、领域 API、queries；受影响响应 schema                                     | 使用第 2/3 批形成的领域划分；保持缓存失效一致         | 请求路径、响应语义、模型切换、SSE 终态刷新                          |
| 5：运行与产物 | worker 进程监督、quant 文件/分页接口                                                      | 依赖行为基线；先有进程失败验证再抽取                  | 取消/超时/回收、恢复策略、哈希拒绝与数据隔离                        |
| 6：条件优化   | ORM 分文件、测试重分组、生成类型、数据目录迁移                                            | 仅在维护成本或数据需求明确后启动                      | metadata 完整性、旧数据可读、命令同步、迁移回滚                     |

每批同时更新 [源码导航](architecture/source-map.md)、相关模块文档和 [验证矩阵](agent-rules/global.md) 中受影响的路径。先用当前文件名选定测试，迁完后同步执行入口；禁止测试文件已迁移而文档仍要求旧命令。

第 2 批内部依次执行「构建支持与一个样式隔离样例 → 量化工作台/详情 → 研究共享表格 → 其他独立组件」。每步验收后再扩大迁移；此时同步当前组件规范、页面规范及 AGENTS 中的样式约定，不把尚未实施的目录提前写成现状。

### 5.1 迁移前后的验证清单

| 影响范围           | 现有验证入口                                                                              | 必须保留的行为                                              |
| ------------------ | ----------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| 行情和规则报告     | `test_workflow.py`、`test_p1.py`；`workbench.spec.ts`                                     | 同快照分析、缺失保持未知、公开/演示隔离、失败保留旧批次     |
| 任务、事件与 Agent | `test_p1.py`、`test_agent_stream.py`、`test_model_protocol.py`；`agent-stream.spec.ts`    | 租约、幂等报告、checkpoint 恢复、事件排空、无效报告不归档   |
| 研究与持仓         | `test_p2.py`；`p2.spec.ts`                                                                | 来源和时点、导入原子性、交易日历、缺行情不制造亏损          |
| 模型配置           | `test_model_settings.py`、`test_model_profiles.py`、`test_profile_migration.py`；对应 E2E | revision 冲突、密钥隔离、旧任务版本不变、删除活动配置不回退 |
| 量化               | `test_quant.py`；`quant.spec.ts`                                                          | 防未来数据、按时间分区、成交拒绝、产物哈希、取消和模式隔离  |
| 外壳与布局         | `app-shell.spec.ts`，加受影响页面人工检查                                                 | 导航、移动抽屉、键盘操作、SSE 不因布局操作重挂载            |

以上后端测试在 `apps/api/tests/`，前端 E2E 在 `apps/web/e2e/`。表中仅列已存在入口，不承诺覆盖新提取的所有运行时场景；worker 进程层需要按 3.6 节补足行为验证。

执行时按 [全局规则](agent-rules/global.md) 选择最小相关集合：后端在 `apps/api` 运行 `uv run pytest` 的对应文件和 Ruff；前端在根目录运行 `pnpm typecheck`，对改动文件执行 ESLint。构建使用 `scripts/build-web.ps1` 并读取实际退出码。浏览器测试需事先确认现有服务归属，再使用隔离演示模式；Playwright 配置不会自动启动服务。跨领域导入、模型注册或运行时变化扩大验证范围。

性能需要单独比较同一固定输入的 API 耗时、SQL 查询次数、前端产物大小、事件投影时间或峰值内存。当前未做这些测量，因此本方案只承诺结构目标，不宣称改造后的提速比例。

### 5.2 兼容与回滚

- 初期每批只改代码归属和调用方式，不改 HTTP 路径、表结构、任务 ID、事件 ID、checkpoint thread_id、数据模式或产物目录。若确需改协议或数据结构，另作显式迁移。
- 记录旧到新路径及所有调用方，兼容导出只存在于过渡期；每批结束检查是否留下第二份实现、循环导入或失效测试替换点。
- 有版本控制时按可独立回退的批次提交；初稿与 P0 时没有 Git 元数据，P1 时已具备 Git，并另外保存本批源码备份。当前改动尚未提交，不能把本文当成已有提交。
- 涉及持久数据时同时保护业务库、checkpoint 和量化产物；回滚代码并不能撤销已修改的表结构或文件布局。应先在临时数据副本演练，再处理用户数据。
- 不为了清理目录删除仍被任务或报告引用的快照与产物；出现失败先回退本批修改，避免叠加下一批扩大排查范围。

## 6. 暂不建议实施的改造

1. **微服务、Redis/Celery 或多 worker 扩容。** 单 API、单 worker 是明确运行前提；没有并发容量证据前，新增协调系统会扩大部署和恢复复杂度。
2. **通用 Repository、BaseService 或通用任务插件框架。** 当前更需要少量清晰的业务接口，这类抽象容易增加跳转而不隐藏复杂规则。
3. **一次性迁移全仓目录。** 前端 `index.tsx + index.less` 是明确目标，但应在构建适配后按模块推进；不能与后端、测试、脚本和数据迁移合成一次大改。
4. **因项目包含量化就把研究与持仓全部归入 quant。** 数据证据、用户持仓、任务执行和数值实验有不同生命周期，应通过明确接口协作。
5. **用目录重构承诺全市场覆盖、真实时点数据或实盘能力。** 这些是数据与产品能力建设，需要独立数据来源和验证，不是重新组织文件可以解决的问题。
6. **立即重写全部 README/历史文档或迁移本地数据库。** 只同步实际变化的入口；历史记录保留当时范围，持久数据单独管理。

## 7. 本次评估依据与限制

本次读取项目入口、目录、依赖/脚本配置、架构与模块文档，抽查行情/任务/证据/量化链路、前端路由与页面、数据模型、迁移注册及测试定义。源码证据链接已随各优化项列出；证据范围是当前文件，不是历史验证记录中的通过次数。

初稿阶段仅新增方案并同步文档总索引、架构索引，未实施代码重构，未修改数据、配置或运行服务。检查范围为文档格式、相对链接、引用文件和关键符号；未执行业务测试、浏览器测试、性能测试、真实供应商联调或 PostgreSQL 集成验证，也不由静态阅读推断其通过。

初稿检查记录（2026-11-03）：`pnpm exec prettier --check docs/refactor-plan.md docs/README.md docs/architecture/README.md` 通过；当时三个文件的 79 个相对链接目标均存在，未发现 Unicode 替换字符。关键接口、函数和测试入口已与源码抽查核对。当前目录无 Git 元数据，无法提供 Git 差异校验。

前一轮目录约定修订只修改本文：按用户指定的参考项目，将前端目标细化为 `index.tsx + index.less`，补充 CSS Modules 编译适配、目录约定及实施顺序。当时 AGENTS、开发规范、源码和依赖尚未变更；后续 P0 已按实施状态更新，实际验证见历史记录，不沿用初稿检查作为本次结论。
