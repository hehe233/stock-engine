# Stock Engine Agent Guide

本文件是 coding agent 的项目入口；适用于整个项目。开始任务先读本文件，再按任务读取相关细则。

## 项目定位

Stock Engine 是单用户、单机的 A 股研究与 Agent 学习项目，当前为 P3 研究验证版。前端使用 React、Vite、TypeScript、Ant Design、TanStack Query 和 React Router；后端使用 FastAPI、SQLAlchemy、LangGraph，量化实验使用 LightGBM、Parquet 和 DuckDB。依赖版本与命令以项目配置和锁文件为准。

## 工作流程

1. 说明本次目标、拟改文件和影响范围；已有用户授权覆盖的工作直接推进。仅在缺失信息影响正确性、实质扩大范围或执行未授权的破坏性操作时确认。
2. 用 `rg` 定位源码、直接依赖和相关测试，区分当前实现、阶段历史与待实现目标。参考项目只作为设计参考，规则须按本项目事实改写。
3. 做范围内的最小完整改动；行为、契约或操作方式改变时同步对应文档。保留用户已有修改。
4. 按[验证矩阵](docs/agent-rules/global.md)完成相关检查，核对改动内容和链接。最终说明改了什么、实际验证结果及未验证范围；历史测试结果不能作为本次结果。

## 项目边界

- 普通 HTTP 请求经 `apps/web/src/api/` 的 `request` 封装，前缀为 `/api`；SSE 使用已有 `useJobStream`。页面路由在 `main.tsx` 注册，外壳在 `App.tsx`。新建或迁移的可视模块采用目录内 `index.tsx + index.less`（CSS Modules）；存量 `.module.css` 按模块渐进迁移，细则见组件规范。
- 服务端状态由 TanStack Query 管理，临时交互状态留在组件；沿用现有请求、认证和样式体系。
- 路由校验与入队，service 协调事务，provider 标准化外部数据，worker 管理慢任务与子进程，LangGraph 节点计算和读取受控证据。新增逻辑放回对应职责层。
- 行情与研究快照、模型配置版本、量化数据版本保持可追溯；任务绑定提交时的快照、配置与证据。公开数据和演示数据保持隔离。
- 缺失值和未知源时间保持未知；规则热度、历史窗口统计、样本外概率和模型文字解读分别表达其含义。研究验证结果不代表已完成全市场覆盖或实盘能力。
- 前端使用 `pnpm`，后端使用 `uv`。Windows 服务与构建优先使用 `scripts/` 的隐藏进程脚本；日志与 PID 存在 `.runtime/`。进程清理前核实所属项目、启动时间和进程树。

## 按任务查阅

| 任务触发条件                                    | 必读文档                                                                                              |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| 编辑文件、选择验证、运行命令、处理 Windows 进程 | [全局规则](docs/agent-rules/global.md)                                                                |
| 查找业务入口或追踪跨端调用                      | [源码导航](docs/architecture/source-map.md)                                                           |
| 新增页面、路由、请求或查询状态                  | [页面规范](docs/agent-rules/frontend/page-development.md)                                             |
| 修改组件、主题、响应式或无障碍交互              | [组件规范](docs/agent-rules/frontend/component-development.md)                                        |
| 修改 API、数据库、采集、模型配置或 worker       | [后端规范](docs/agent-rules/backend/backend-development.md)                                           |
| 修改 LangGraph、工具、检查点、任务状态或 SSE    | [Agent 开发规范](docs/agent-rules/backend/agent-development.md)                                       |
| 修改数据口径、持仓、历史统计、训练或回测        | [数据与量化规范](docs/agent-rules/backend/data-quant.md)                                              |
| 使用前端或后端任务提示词                        | [前端提示词](docs/agent-rules/frontend/prompts.md)、[后端提示词](docs/agent-rules/backend/prompts.md) |
| 学习项目或查阅当前功能                          | [学习索引](docs/learning/README.md)、[功能模块索引](docs/modules/README.md)                           |
| 整理文档或使用任务提示词                        | [文档索引与维护约定](docs/README.md)、[提示词模板](docs/agent-prompts.md)                             |

功能、学习、架构、数据来源和历史记录统一从 [docs 总索引](docs/README.md) 进入；前后端规范从[开发规范索引](docs/agent-rules/README.md)进入。只读取任务所需部分，新增文档同步所属分类索引。
