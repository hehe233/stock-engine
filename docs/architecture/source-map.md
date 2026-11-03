# 源码模块导航

[返回架构索引](README.md)

本页记录稳定职责和阅读入口，不维护完整文件树。先选领域，再用 `rg --files apps/web/src apps/api/app` 或 `rg -n '<符号>' apps` 确认当前实现。路径相对项目根目录。

P0 公共入口：后端请求依赖在 `apps/api/app/http/dependencies.py`，时间与证券规则在 `shared/time.py`、`shared/securities.py`，采集进程与标准化在 `providers/runner.py`、`providers/normalization.py`。前端组件样式编译在 `apps/web/build/component-less.ts`，目录示例是 `components/ErrorNotice/index.tsx` 与 `index.less`，隔离验证在 `apps/web/tests/component-less.test.ts`。

| 领域                 | 前端入口                                                                                                           | 后端入口与相关测试                                                                                                                                                                     |
| -------------------- | ------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 路由、应用外壳、鉴权 | `apps/web/src/main.tsx`、`App.tsx`、`components/AuthGate/index.tsx`                                                | `apps/api/app/core/security.py`；`apps/web/e2e/app-shell.spec.ts`                                                                                                                      |
| 行情与分析入口       | `apps/web/src/pages/Dashboard/index.tsx`、`api/market.ts`、`api/jobs.ts`                                           | `apps/api/app/market/routes.py`、`market/service.py`、`reports/routes.py`、`providers/`；`apps/api/tests/test_workflow.py`、`test_p1.py`                                               |
| 任务、流式与报告     | `apps/web/src/pages/Jobs/index.tsx`、`Job/index.tsx`、`Reports/index.tsx`、`Report/index.tsx`、`components/agent/` | `apps/api/app/jobs/service.py`、`agents/`、`worker.py`；`apps/api/tests/test_agent_stream.py`、`test_p1.py`                                                                            |
| 模型配置             | `apps/web/src/pages/ModelSettings/index.tsx`、`api/model-settings.ts`                                              | `apps/api/app/model_settings/service.py`、`agents/models.py`；`apps/api/tests/test_model_settings.py`、`test_model_profiles.py`、`test_profile_migration.py`                           |
| 研究与历史案例       | `apps/web/src/pages/Research/index.tsx`、`History/index.tsx`、`api/research.ts`                                    | `apps/api/app/research/routes.py`、`research/collection.py`、`research/queries.py`、`research/history.py`、`providers/research.py`、`research/catalog.py`；`apps/api/tests/test_p2.py` |
| 持仓                 | `apps/web/src/pages/Portfolio/index.tsx`、`api/portfolio.ts`                                                       | `apps/api/app/portfolio/routes.py`、`portfolio/service.py`、`portfolio/schemas.py`；`apps/api/tests/test_p2.py`                                                                        |
| 量化实验             | `apps/web/src/pages/Quant/index.tsx`、`pages/QuantRun/index.tsx`、`features/quant/`、`api/quant.ts`                | `apps/api/app/quant/`；`apps/api/tests/test_quant.py`、`apps/web/e2e/quant.spec.ts`                                                                                                    |
| 主题与通用展示       | `apps/web/src/styles/`、`components/ErrorNotice/index.tsx`、`lib/format.ts`                                        | [工作区界面](../modules/ui-workspace.md)                                                                                                                                               |
| 数据库与契约         | `apps/web/src/api/types.ts` 及各领域 API 文件                                                                      | `apps/api/app/db.py`、`schemas.py`、`research/schemas.py`、`portfolio/schemas.py`、`quant/schemas.py`、`apps/api/migrations/`                                                          |
| 配置与进程           | `apps/web/vite.config.ts`、`playwright.config.ts`                                                                  | `apps/api/app/core/config.py`、`main.py`、`scripts/`；运行记录在 `.runtime/`                                                                                                           |

## 三条关键阅读链

- **提交研究**：`Dashboard/index.tsx` → `api/jobs.ts` → `jobs/routes.py` → `jobs/service.py` → `jobs/context.py` → `worker.py` → `runtime/agent_slot.py` → `agents/run_job.py` → `research.py` / `assistant.py` → 事件与报告入库 → `useJobStream.ts` / `stream.ts` → `AgentStream/index.tsx` / `ReportWorkspace/index.tsx`。
- **更新证据**：`Research/index.tsx` → `api/research.ts` → `research/routes.py` → `research/collection.py` → worker 隔离采集 → `providers/research.py` → 新快照；任务通过 `jobs/context.py` 组合 `research/evidence.py`、`quant/evidence.py` 及显式持仓，冻结可见证据。
- **量化实验**：`Quant/index.tsx` → `api/quant.ts` → `quant/routes.py` → `datasets.py` / `service.py` → `runtime/quant_slot.py` → `quant/run.py` → `features.py` / `engine.py` / `backtest.py` → 产物与报告。

测试命令及选择依据见[全局规则](../agent-rules/global.md)。新增能力先检查对应链路，只有跨领域影响时才扩大阅读范围。

## P1 模块与事务归属

- `pages/Quant/` 与 `pages/QuantRun/` 分别懒加载；导入草稿和预览在 `features/quant/DatasetImportPanel/`，实验参数在 `ExperimentForm/`，报告与预测分页在 `QuantRunReport/`。可视模块均有 `index.tsx + index.less`，共同布局复用 `styles/Workbench.module.css`。
- `features/research/components/ResearchDataset/` 与 `SourceNotice/` 由 Research、History 共同使用，页面之间不再导入实现。
- `http/system.py` 负责 health/config；market、model_settings、jobs、reports、research、portfolio 和 quant 的路由由 `main.py` 装配。URL 和认证保持兼容。
- `jobs/service.py` 负责新建、取消、重试的写入与提交；新建和重试在 service 内共用容量锁。事件辅助函数只添加记录，不自行提交。`reports/service.py` 保存短时规则报告。
- `portfolio/service.py` 的导入、更新、删除共用持仓锁；`model_settings/service.py` 的保存、启用、删除共用配置锁。请求 Session 结束时关闭，未提交事务回滚；worker Session 生命周期仍由调用方管理。
- 研究采集、快照查询、历史统计和证据分别归 `research/collection.py`、`queries.py`、`history.py`、`evidence.py`。`quant/datasets.py` 经 `research/queries.py` 的 `archived_history` 读取普通数据，不直接读取研究 ORM。
- 事务失败与重试冻结验证见 `apps/api/tests/test_refactor_transactions.py`；浏览器迁移验证见 `apps/web/e2e/refactor-p1.spec.ts`。

## P2 请求、契约与运行边界

- JSON 传输统一为 `apps/web/src/api/http.ts`，领域请求位于同级 auth/config/market/jobs/reports/model-settings/research/portfolio/quant；查询配置和失效规则位于 `features/<领域>/queries.ts`。页面保留展示相关轮询频率，key 形状保持兼容。
- 研究、持仓与量化路由显式声明各自 `schemas.py` 的响应模型；历史证据允许扩展字段，省略字段保持省略，显式 null 保持未知。契约回归在 `test_response_contracts.py`。
- `worker.py` 只装配单实例锁、恢复与主循环；`runtime/processes.py` 管启动/超时/kill/wait，agent_slot 与 quant_slot 各自处理领域状态，collection 管原有双采集通道。进程故障回归在 `test_process_supervision.py`。
- `quant/datasets.py` 管输入、审计和版本元数据；`artifacts.py` 管固定路径、流式 SHA-256、DuckDB 分页及文件写入清理；`service.py` 在完整产物就绪后发布任务结果。失败回归在 `test_artifact_publication.py`。
- 前端 HTTP/缓存回归在 `apps/web/e2e/query-contracts.spec.ts`；跨端共享事件样例位于 `tests/fixtures/agent-replay.json`，由后端 `test_agent_stream.py`、前端 query-contracts 和 agent-stream 浏览器测试消费。

## P3 前端目录与加载边界

- `pages/` 下每个页面以 `index.tsx + index.less` 组织；Jobs/Job、Reports/Report 分别承载列表与详情。首页 Dashboard 直接加载，其余页面在 `main.tsx` 懒加载；路由内容内的 Suspense 保持 App 与 AuthGate 挂载。
- `features/market/QuoteTable/` 负责列与表格展示，Dashboard 持有筛选、查询和分析提交；`features/portfolio/PositionEditor/`、`PositionImportPanel/`、`PositionTable/` 分别负责编辑、导入和列表操作，Portfolio 页面组合总览。
- `features/model-settings/SettingsForm/` 管理表单、密钥草稿与保存/测试；ModelSettings 页面管理配置选择/启用/删除及未保存确认。
- `components/AuthGate/` 与 `components/agent/` 下独立展示组件使用成对入口；useJobStream、stream 等纯逻辑文件保持描述性名称。Agent 面板共用 `panel.module.css`，共享工作台布局仍在 `styles/Workbench.module.css`，报告和路线图专属规则归各页面。
- 迁移行为回归在 `apps/web/e2e/refactor-p3.spec.ts`；首页资源对比与范围见[重构方案](../refactor-plan.md)和[验证记录](../history/verification.md)。
