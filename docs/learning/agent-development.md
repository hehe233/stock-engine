# 从前端开发走向 Agent 开发

[返回学习索引](README.md) · [源码导航](../architecture/source-map.md)

## 先建立概念对应

| 前端熟悉的概念             | 本项目对应         | 关键区别                                             |
| -------------------------- | ------------------ | ---------------------------------------------------- |
| TypeScript interface / Zod | Pydantic 模型      | Pydantic 会在运行时校验 HTTP 数据                    |
| React Router 路由          | FastAPI 路由       | 接收 HTTP 请求，返回 JSON，不渲染组件                |
| 自定义 hook / service      | Python service     | 协调数据源、业务规则和数据库事务                     |
| store 状态                 | LangGraph State    | 保存一次工作流执行的数据，不是页面全局状态           |
| reducer / 纯函数           | LangGraph Node     | 接收 state，返回局部状态更新                         |
| 流程跳转                   | LangGraph Edge     | 显式控制下一步执行哪个节点                           |
| 本地缓存                   | SQLAlchemy Session | Session 是数据库工作单元，有提交和回滚，不是永久缓存 |
| 数据结构升级               | Alembic migration  | 可追踪地变更数据库表结构                             |
| TanStack Query cache       | 分析报告表         | Query 缓存提高 UI 响应；数据库才负责跨重启保存       |

## 第一课：沿着一次点击阅读

1. `apps/web/src/pages/Dashboard.tsx`：点击「分析」后，mutation 传入 `symbol` 和当前 `snapshot_id`。
2. `apps/web/src/api/jobs.ts`：发送 `POST /api/jobs`，附带分析模式和模型名，得到 202 + job_id。
3. `apps/api/app/schemas.py`：Pydantic 验证请求格式，不合格返回 422。
4. `jobs/service.py`：验证快照和模型列表，任务入库。`worker.py` 原子领取任务，启动受超时控制的子进程。
5. `agents/run_job.py` 打开 checkpointer；`research.py` 计算规则；`assistant.py` 在模型模式下执行「选择工具 → 读取证据 → 再判断 → 结构化输出」。
6. `run_job.py` 把 AnalysisReport、原始引用证据、任务成功状态放在同一事务中提交。
7. `pages/Jobs.tsx` 订阅 SSE，并轮询最终状态，成功后跳转报告页。刷新报告时根据 ID 从数据库读取。

练习：在浏览器 Network 面板找到请求体，复制 `snapshot_id`；去报告页确认它与报告中的快照 ID 相同。

## 第二课：理解 LangGraph 的四个基本元素

```text
START → validate → factors → risk → report → END
```

- **State**：本次执行共享的状态。`TypedDict` 描述字段类型，但不是运行时验证器，因此入口节点还要用 Pydantic 验证数据。
- **Node**：一个函数。它读取状态、返回要更新的字段；不要在节点里修改前端、发 HTTP 响应或复用数据库 Session。
- **Edge**：控制执行顺序。P1 的条件边根据 tool_calls 决定执行工具或生成报告，达到轮次预算则结束工具循环。
- **compile / invoke / stream**：compile 构建图；invoke 返回最终状态；stream 逐节点产出更新。P1 任务子进程绑定 checkpointer 后编译图，使用 stream 保存进度。

P0 使用串行节点，因此 trace 使用新数组顺序累积。并行分支会同时更新状态，需要显式定义 reducer，不能直接照搬串行写法。

**工作流不等于自主 Agent。** 规则模式的执行顺序和公式由代码决定；P1 模型模式可选择调用工具，但工具权限、最大调用次数、超时、输出类型和数据来源仍由程序控制。

练习：增加一个「检查量比异常」节点，放在风险节点前；在测试里验证其业务行为，再观察页面执行记录。

## 第三课：理解数据库的职责

`market_snapshots` 存采集批次，`analysis_runs` 存分析结果，后者通过外键引用前者。

一次分析不读取“随时变化的最新行情”，而是读取用户已经看见的那个快照。这避免页面显示 A 批数据、后端却使用 B 批数据分析的竞态。

SQLAlchemy 的常见顺序是：创建 Session → 查询 / 添加对象 → `commit()` → 关闭 Session。每个 HTTP 请求有独立 Session；后台定时任务自己创建 Session。不要把 Session 作为全局单例。

`DateTime(timezone=True)` 在 SQLite 中不会自动保留时区，所以入库前统一转成 UTC；读取后恢复 UTC 标识；前端格式化为 Asia/Shanghai。这条行为由刷新一致性测试保护。

练习：为分析记录增加一个可选备注字段。先改 ORM，再用 `uv run alembic revision --autogenerate -m "add analysis note"` 生成迁移，检查文件，再执行 `uv run alembic upgrade head`。不要只改模型就认为数据库已经变更。

## 第四课：分清三种持久化

1. **业务持久化**：本项目已经实现，报告保存到 `analysis_runs`，可以按 ID 查询。
2. **LangGraph checkpoint**：P1 实现，保存图在执行中间的状态，用于恢复、人工介入与多轮对话，需要 thread_id 和 checkpointer。
3. **长期知识 / 记忆**：要有真实跨任务检索需求再设计，不能把所有东西无差别丢入向量库。

报告已入库，不代表图已经支持断点恢复；trace 是执行步骤记录，也不是模型隐藏推理链。

## 第五课：阅读已经实现的模型接口

按以下次序阅读与练习：

1. `agents/models.py`：Base URL / API Key / 模型名怎样变成统一 ChatModel；Ollama 为什么是显式备选。
2. `agents/assistant.py`：bind_tools 告知模型工具定义，模型返回的是调用请求，真正执行由程序校验。
3. `schemas.py` 的 ModelInsight：结构校验和证据 ID 校验各能保证什么、不能保证什么。
4. `tests/test_model_protocol.py`：用 httpx.MockTransport 检查真实客户端发送的模型名、工具协议和结构化响应，无需付费调用。
5. `test_p1.py` 的检查点恢复测试：模拟模型最终节点第一次失败，第二次恢复不会重跑已经完成的工具节点。

## 第六课：理解任务、检查点和事务的边界

模型设置的完整链路可从 `pages/ModelSettings.tsx` 开始：表单提交 → `model_settings/service.py` 校验与保存不可变版本 → `/api/config` 返回无密钥的模型列表 → 创建任务绑定 model_config_id → run_job 读取该版本。API 进程与 worker 不能只靠各自的内存变量同步配置，所以这里使用共享数据库。

多套配置新增 `model_profiles`：稳定 ID 与名称指向最新不可变版本；活动配置指针决定新任务的供应商。编辑、切换和删除不会修改已提交任务使用的版本。对照 [多配置设计与操作](../modules/model-profiles.md) 阅读迁移和回归测试。

练习：提交使用模型 B 的任务，再把默认供应商改成另一家，观察原任务仍使用提交时的配置。查看 `tests/test_model_settings.py` 如何在不调用付费模型的条件下验证这一点。

任务表告诉 UI「现在是否在执行」；检查点告诉图「执行到了哪一步」；报告表保存用户最终看到的结果。三个职责不能互相替代。

领取任务使用 `UPDATE ... WHERE status = 'queued'`，只有更新一行才领取成功。lease_owner 标识本次执行者，lease_until 防止进程崩溃后任务永远卡在 running。恢复时使用相同 thread_id，给 graph.stream 传 None；重新传初始输入会改变恢复语义。

练习：运行检查点恢复测试，在失败前后观察模型调用计数；再阅读 finish_failed 和 recover_expired_jobs，区分「用户重试」与「进程崩溃后租约恢复」。远程模型调用与本地事务不能原子提交，因此恢复有可能重复调用计费。

## 第七课：免费数据不是可靠数据库

阅读 `providers/public.py` 的字段标准化，再看 `market/service.py` 的不可变快照。练习把一条记录的量比设为 null，观察分数变为不可用；把只有时分秒的更新时间传入 source_time，观察其保持未知。

五分钟采集、供应商延迟和浏览器读取是不同的时钟。源时间未知时，不应使用本机当前时间把旧行情包装成实时行情。详见 [P1 数据边界](../history/p1.md)。

## 第八课：P2 的持久队列和证据冻结

从 `pages/Research/index.tsx` 的更新按钮开始：`researchApi.refresh` → `research/routes.py` → `research/collection.py` ? `enqueue`。HTTP 只保存请求并返回 202，worker 的 `process_one` 领取请求、隔离采集、标准化、保存新批次。失败时保留旧批次与错误，页面分别展示数据和请求状态。

阅读 `providers/research.py` 的白名单：龙虎榜接口即使返回「上榜后涨幅」，也不会进入证据。阅读 `frozen_context`：任务提交后，新批次不会改变已提交任务的上下文。`read_research` 与 `read_portfolio` 是受控读取工具，模型不能直接操作数据库或券商。

练习：执行 `test_job_freezes_research_and_opt_in_holdings`，观察提交后改持仓、改批次仍不影响原任务。再运行 `test_job_evidence_uses_individual_quote_day`，理解为什么批次最大时间不能代表个股源时间。

## 第九课：金额、交易制度和历史偏差

阅读 `portfolio/service.py`：成本用 Decimal 计算，行情缺失时估值和盈亏保持 null。相同证券多笔持仓先汇总再计算集中度。T+1 依赖实际交易日历；ETF 制度由用户确认，不能用证券类别猜测。

阅读 `history_statistics`：21 个收盘价形成 20 个交易日收益区间。所有重叠窗口中挑选强弱例子是事后描述，不等于买卖规则，更不等于样本外胜率。下一阶段需要先定义标签、信息可见时点、训练/验证切分及交易约束。

练习：把某只持仓行情删除，确认页面不会显示 100% 亏损；把一个正收益窗口改为负收益，验证历史对照统计改变，但规则热度分不随历史案例自动变成「概率」。

## 第十课：数据湖文件、查询引擎与业务数据库

阅读 `quant/datasets.py` 与 `quant/artifacts.py`：Parquet 适合批量列式数据，DuckDB 直接对文件执行 SQL，SQLAlchemy 表保存数据版本与任务索引。三者的关系类似「静态资源文件 + 查询执行器 + 业务元数据」，不需要为了学习就引入常驻大数据集群。

练习：创建数据版本，观察报告中的 SHA-256；在临时测试目录修改文件，运行 `test_hash_change_rejected_and_interruption_recoverable`，理解为什么数据库记录存在还不足以保证实验可复现。

## 第十一课：概率模型和解释 Agent 的分工

`quant/features.py` 定义目标和可见时点，`quant/engine.py` 使用 LightGBM 拟合，独立时间段拟合校准器，再在更晚日期计算误差。LangGraph 模型工具只读取已完成实验摘要；语言模型不会创造训练样本或把热度分变成概率。

练习：运行未来价格扰动测试，确认过去特征完全不变；再查看标签结束日和可见时间的 purge 规则。比较校准前后 Brier，理解校准可能使测试结果更差，成功运行并不等于模型有效。

## 第十二课：从预测到交易有额外约束

阅读 `quant/backtest.py`：5 日收盘事件标签不等于下一开盘买入后的实际收益。现金、100 股数量、T+1、涨跌停、成交容量、费用和无法处理的公司行动都改变交易结果。源码拒绝没有足够字段的撮合，报告留存原因和未平仓仓位。

练习：把买入日开盘设为涨停价，验证没有成交；把计划卖出日设为跌停，观察顺延；删除一条持仓期间的价格，观察总收益变成未知。不要用「测试全通过」推断免费源覆盖完整或实盘盈利。

## 官方资料

- [FastAPI 教程](https://fastapi.tiangolo.com/tutorial/)
- [LangGraph 概览](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [SQLAlchemy 2 ORM 快速入门](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)
- [Alembic 教程](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [TanStack Query 文档](https://tanstack.com/query/latest/docs/framework/react/overview)
