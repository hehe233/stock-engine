# 源码模块导航

[返回架构索引](README.md)

本页记录稳定职责和阅读入口，不维护完整文件树。先选领域，再用 `rg --files apps/web/src apps/api/app` 或 `rg -n '<符号>' apps` 确认当前实现。路径相对项目根目录。

P0 公共入口：后端请求依赖在 `apps/api/app/http/dependencies.py`，时间与证券规则在 `shared/time.py`、`shared/securities.py`，采集进程与标准化在 `providers/runner.py`、`providers/normalization.py`。前端组件样式编译在 `apps/web/build/component-less.ts`，目录示例是 `components/ErrorNotice/index.tsx` 与 `index.less`，隔离验证在 `apps/web/tests/component-less.test.ts`。

| 领域                 | 前端入口                                                                    | 后端入口与相关测试                                                                                                                                            |
| -------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 路由、应用外壳、鉴权 | `apps/web/src/main.tsx`、`App.tsx`、`components/AuthGate.tsx`               | `apps/api/app/core/security.py`；`apps/web/e2e/app-shell.spec.ts`                                                                                             |
| 行情与分析入口       | `apps/web/src/pages/Dashboard.tsx`、`api/client.ts`                         | `apps/api/app/routes.py`、`services/market.py`、`providers/`；`apps/api/tests/test_workflow.py`、`test_p1.py`                                                 |
| 任务、流式与报告     | `apps/web/src/pages/Jobs.tsx`、`Reports.tsx`、`components/agent/`           | `apps/api/app/services/jobs.py`、`agents/`、`worker.py`；`apps/api/tests/test_agent_stream.py`、`test_p1.py`                                                  |
| 模型配置             | `apps/web/src/pages/ModelSettings.tsx`、`api/client.ts`                     | `apps/api/app/services/model_settings.py`、`agents/models.py`；`apps/api/tests/test_model_settings.py`、`test_model_profiles.py`、`test_profile_migration.py` |
| 研究与历史案例       | `apps/web/src/pages/Research.tsx`、`History.tsx`、`api/research.ts`         | `apps/api/app/research_routes.py`、`services/research_data.py`、`providers/research.py`、`research_catalog.py`；`apps/api/tests/test_p2.py`                   |
| 持仓                 | `apps/web/src/pages/Portfolio.tsx`、`api/research.ts`                       | `apps/api/app/services/portfolio.py`、`research_schemas.py`；`apps/api/tests/test_p2.py`                                                                      |
| 量化实验             | `apps/web/src/pages/Quant.tsx`、`api/quant.ts`                              | `apps/api/app/quant/`；`apps/api/tests/test_quant.py`、`apps/web/e2e/quant.spec.ts`                                                                           |
| 主题与通用展示       | `apps/web/src/styles/`、`components/ErrorNotice/index.tsx`、`lib/format.ts` | [工作区界面](../modules/ui-workspace.md)                                                                                                                      |
| 数据库与契约         | `apps/web/src/api/types.ts` 及各领域 API 文件                               | `apps/api/app/db.py`、`schemas.py`、`research_schemas.py`、`quant/schemas.py`、`apps/api/migrations/`                                                         |
| 配置与进程           | `apps/web/vite.config.ts`、`playwright.config.ts`                           | `apps/api/app/core/config.py`、`main.py`、`scripts/`；运行记录在 `.runtime/`                                                                                  |

## 三条关键阅读链

- **提交研究**：`Dashboard.tsx` → `api/client.ts` → `routes.py` → `services/jobs.py` → `worker.py` → `agents/run_job.py` → `research.py` / `assistant.py` → 事件与报告入库 → `useJobStream.ts` / `stream.ts` → `AgentStream.tsx` / `ReportWorkspace.tsx`。
- **更新证据**：`Research.tsx` → `api/research.ts` → `research_routes.py` → `services/research_data.py` → worker 隔离采集 → `providers/research.py` → 新快照；任务通过 `frozen_context` 冻结可见证据。
- **量化实验**：`Quant.tsx` → `api/quant.ts` → `quant/routes.py` → `data.py` / `service.py` → worker → `quant/run.py` → `features.py` / `engine.py` / `backtest.py` → 产物与报告。

测试命令及选择依据见[全局规则](../agent-rules/global.md)。新增能力先检查对应链路，只有跨领域影响时才扩大阅读范围。
