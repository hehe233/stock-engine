# 后端开发规范

适用于 `apps/api/app/`、迁移与后端测试。模块设计见[架构](../../architecture/overview.md)，图和任务生命周期另见 [Agent 规范](agent-development.md)。任务提示词见[后端提示词](prompts.md)。

## 职责与 API 契约

- 路由负责输入校验、授权、查询与入队；Pydantic schema 定义运行时契约，service 协调业务与事务，provider 获取并标准化外部数据。
- 慢速网络采集、模型调用和量化训练沿用 worker 的有界子进程路径；API 生命周期不执行慢速采集。兼容短时规则分析接口按既有行为维护。
- 新增接口沿用 `/api` 及领域路由，先明确请求/响应、缺失值、状态码和重复提交语义；跨端修改同时更新 `apps/web/src/api/`。
- research、portfolio、quant 的响应模型在各自 `schemas.py`；版本化证据保留扩展字段，路由使用 `response_model_exclude_unset=True` 区分未提供与显式 null。响应模型独立于当下输入校验，避免对历史记录重新套用提交限制；相关回归在 `test_response_contracts.py`。
- 输入错误、缺失资源、版本冲突和未知异常分别处理；日志保留可诊断信息，响应返回安全描述，不能泄漏密钥或内部堆栈。
- 当前规模沿用同步 SQLAlchemy 与直接 `select`，不因单个功能引入通用 Repository、BaseService 或新的常驻队列。
- 请求 Session 依赖从 `app.http.dependencies` 导入；公共 UTC/上海时区约定与证券代码规则分别从 `app.shared.time`、`app.shared.securities` 导入。采集错误、子进程执行和源字段标准化归 `providers/base.py`、`runner.py`、`normalization.py`，业务模块不借具体行情适配器获取这些能力。

## 数据库与迁移

1. 请求、后台任务和子进程各自管理 Session，事务保持短小；跨进程不共享 Session 或以进程内变量作为共同配置事实。
2. ORM 结构变更须有 Alembic 迁移，审查自动生成结果及数据兼容性；在临时数据库验证升级和旧数据保留。
3. 迁移运行在用户实际库前核对目标与任务授权。`start-dev.ps1` 会执行 `alembic upgrade head`，启动也可能改变数据库结构。
4. 业务数据库与 LangGraph checkpoint 独立配置、分别验证。切换数据库不自动搬迁数据；保留被报告或实验引用的快照与文件。
5. 时间入库使用 UTC，返回带时区时间；SQLite 读取恢复时区的约定见架构，界面统一显示北京时间。

## 采集与 worker

- 使用已有队列、条件 UPDATE、单实例约束、超时和取消路径。一个 API + 一个 worker 是当前部署前提，多进程/多机扩展需重新设计协调边界。
- provider 标准化单位、证券类别、来源与源时间；失败保留旧快照并记录失败原因，公开模式不回退演示数据。
- 领取成功才执行；完成时校验执行者与当前状态，过期执行者不能覆盖新状态。新增任务类型要处理退出、超时和中断后的状态。
- `runtime/processes.py` 负责进程机制，agent_slot/quant_slot 负责各自状态与恢复，collection 负责采集调度；修改监督路径运行 `test_process_supervision.py`，确认终止后 wait 回收、旧租约不能覆写、启动失败不会停掉 worker。
- 采集与数据口径变更同时读[数据规范](data-quant.md)，并用固定输入覆盖缺字段、无日期和供应商异常。

## 模型配置与凭证

- `model_profiles` 是可变管理入口，`model_configurations` 是不可变版本；提交任务绑定版本 ID。修改活动指针不改变历史任务依据。
- 编辑、启用与删除沿用 revision 冲突检查和事务；删除活动配置停用 API，不自动切换供应商或恢复环境密钥。
- 列表与响应只返回白名单字段和密钥是否存在。更换 Base URL 时遵循现有独立密钥规则；保存与切换不能隐式调用模型。
- 详细行为及验证入口见[多套 API 配置](../../modules/model-profiles.md)。模型协议测试使用已有 MockTransport，真实供应商联调明确记录环境和结果。

完成标准：受影响接口、事务或故障路径已有验证；迁移与旧数据行为可说明；文档和前端契约同步；未验证的数据库或供应商单独列明。
