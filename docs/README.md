# 文档总索引

首次启动看[项目 README](../README.md)，coding agent 从 [AGENTS.md](../AGENTS.md) 开始。本文负责导航和文档归属，功能是否已实现以当前源码及对应验证证据为准。

## 分类目录

```text
docs/
├── README.md                 # 总索引与维护约定
├── agent-prompts.md          # 通用与跨端任务提示词
├── refactor-plan.md          # 目录与模块优化方案、分阶段状态
├── agent-rules/              # 公共开发约定
│   ├── frontend/             # 前端规范与提示词
│   └── backend/              # 后端规范与提示词
├── learning/                 # 学习路线、概念与练习
├── modules/                  # 当前功能模块说明
├── architecture/             # 架构与源码导航
├── data/                     # 数据来源与口径核验
└── history/                  # 阶段基线与验证记录
```

每个分类目录都有 `README.md` 索引，前后端目录分别维护自己的规范和提示词。

| 分类             | 索引入口                                   | 内容                                           |
| ---------------- | ------------------------------------------ | ---------------------------------------------- |
| 开发规范         | [开发规范总索引](agent-rules/README.md)    | 公共流程、验证、Windows 进程卫生               |
| 前端规范与提示词 | [前端索引](agent-rules/frontend/README.md) | 页面、组件、样式、流式展示与任务模板           |
| 后端规范与提示词 | [后端索引](agent-rules/backend/README.md)  | API、迁移、任务、Agent、数据量化与任务模板     |
| 学习文档         | [学习索引](learning/README.md)             | 前端到 Python、LangGraph、数据库与量化的十二课 |
| 功能模块         | [功能模块索引](modules/README.md)          | 行情任务、研究持仓、量化、模型配置、流式和界面 |
| 架构与源码       | [架构索引](architecture/README.md)         | 模块职责、数据流、调用链与代码入口             |
| 数据来源         | [数据索引](data/README.md)                 | 来源核验、数据口径与能力限制                   |
| 历史记录         | [历史索引](history/README.md)              | P0/P1 基线、有日期的测试与未验证范围           |

## 按目的阅读

| 目的                     | 文档                                       | 定位                                |
| ------------------------ | ------------------------------------------ | ----------------------------------- |
| 定位代码与调用链         | [源码导航](architecture/source-map.md)     | 当前模块职责与入口                  |
| 理解整体设计             | [架构与数据约定](architecture/overview.md) | 模块边界、数据与时间语义            |
| 评估目录与模块优化       | [重构方案](refactor-plan.md)               | 当前判断、优化理由、分批实施与验收  |
| 使用行情、任务与报告     | [行情与任务](modules/market-and-jobs.md)   | 从快照提交到报告归档的当前闭环      |
| 从前端知识学习 Agent     | [学习路线](learning/agent-development.md)  | 概念映射、阅读路径与练习            |
| 使用研究、持仓和历史功能 | [P2](modules/research.md)                  | 已实现功能及证据边界                |
| 使用量化实验             | [P3](modules/quant.md)                     | 数据契约、防泄漏、成交和研究局限    |
| 管理模型供应商           | [模型配置](modules/model-profiles.md)      | 操作、不可变版本与并发修改          |
| 理解流式事件与草稿报告   | [Agent 流式输出](modules/agent-stream.md)  | 事件语义、消费与归档条件            |
| 修改界面框架             | [工作区界面](modules/ui-workspace.md)      | 导航、主题、抽屉与交互              |
| 核验公开数据来源         | [P2 数据源核验](data/research-sources.md)  | 有日期的实测、来源与口径限制        |
| 查历史测试与环境限制     | [验证记录](history/verification.md)        | 每次验证的证据，不是永久通过保证    |
| 理解早期范围和配置       | [P0](history/p0.md)、[P1](history/p1.md)   | 阶段基线；当前启动方式见项目 README |
| 给 coding agent 下任务   | [提示词模板](agent-prompts.md)             | 可复制的输入、执行要求与完成标准    |

## 开发规范

- [全局规则](agent-rules/global.md)：改动范围、文件编辑、验证分级与 Windows 进程卫生。
- **前端目录 `agent-rules/frontend/`**：[前端提示词](agent-rules/frontend/prompts.md)、[页面规范](agent-rules/frontend/page-development.md)、[组件规范](agent-rules/frontend/component-development.md)。覆盖 React Router、请求、查询缓存、antd、CSS Modules 与无障碍。
- **后端目录 `agent-rules/backend/`**：[后端提示词](agent-rules/backend/prompts.md)、[后端规范](agent-rules/backend/backend-development.md)、[Agent 开发规范](agent-rules/backend/agent-development.md)、[数据与量化规范](agent-rules/backend/data-quant.md)。覆盖 API、事务、迁移、图、恢复、SSE、数据可见时点与撮合。

前后端提示词分别维护在各自目录；通用排障、审查、文档整理和跨端任务从[公共提示词入口](agent-prompts.md)进入。

## 文档维护

1. **入口保持短。** `AGENTS.md` 只放每次任务需要的边界和明确触发条件；专项步骤写入相应细则，不要求每次通读全部 docs。
2. **一处维护事实。** 命令定义见 `package.json`、`pyproject.toml` 和 `scripts/`，版本见配置与锁文件；模块入口见源码导航，事件字段见流式文档，量化数据契约见 P3。其他文档用链接引用。
3. **区分文档性质。** 功能说明记录当前行为；规范约束后续改动；阶段计划和验证记录保留当时上下文。更新历史文档时增加状态说明，不把当年未实现内容写成现在仍缺失。
4. **按变更同步。** 新页面更新源码导航与相关操作文档；协议/字段变更更新对应契约；数据口径变更更新来源或 P3；新的普遍开发约束才写入规范。无需每个小改动新建一篇文档。
5. **证据可核验。** 验证记录写日期、改动范围、实际命令、数据模式、结果与限制；区分 mock、演示、公开源和真实模型联调。未执行写“未执行”，失败写原因。
6. **链接可迁移。** 项目内用相对 Markdown 链接，避免把个人盘符当必需依赖；新增文件必须有入口链接。外部参考路径只记录来源，不要求读者拥有参考项目。
7. **按用途归档。** 教学和练习归 learning，当前功能说明归 modules，设计和入口归 architecture，外部来源核验归 data，阶段基线和验证日志归 history；前后端规范与提示词各自归档。
8. **同步两级索引。** 新文档先加入所属分类 README；新增分类再更新总索引。移动或重命名同步项目 README、AGENTS 和其他引用；原位置不保留第二份正文，避免后续维护分叉。

新增专项文档建议包含：适用范围、源码入口、执行步骤或行为约定、完成标准、相关链接。内容仅保留适用项目的约束，避免复制整套第三方技术栈。

## 本次参考与改造

结构参考本机 `E:/BRDKurin/project/code/a2a-frontend/AGENTS.md` 与其 `docs/`：保留短入口、任务触发式阅读、模块导航和分级验证。前端按用户要求采用目录内 `index.tsx + index.less`，在 Vite 中保留 CSS Modules 隔离，存量 CSS 渐进迁移。参考项目的 Next.js App Router、Zustand、axios、`/api/A2A` 与 CDN 部署规则不适用于本项目；请求、状态与路由继续使用 React Router、TanStack Query、fetch 和 `/api`。

授权遵循当前任务与适用上级指令，已授权的普通编辑无需逐文件再次确认。Windows 进程规则采用本项目现有 PID 清单、启动时间核验和进程树清理方式。
