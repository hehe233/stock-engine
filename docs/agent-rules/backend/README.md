# 后端规范与提示词索引

[返回开发规范索引](../README.md) · [返回文档总索引](../../README.md)

适用于 `apps/api/`。先读 [AGENTS.md](../../../AGENTS.md) 和[全局规则](../global.md)，再按修改范围选择：

| 文档                                   | 触发条件                                       |
| -------------------------------------- | ---------------------------------------------- |
| [后端任务提示词](prompts.md)           | 需要 API、数据迁移、Agent 或量化任务模板       |
| [后端开发规范](backend-development.md) | 修改路由、schema、service、数据库、采集或配置  |
| [Agent 开发规范](agent-development.md) | 修改图、工具、任务租约、checkpoint、SSE 或归档 |
| [数据与量化规范](data-quant.md)        | 修改数据口径、持仓、特征/标签、训练或成交模拟  |

当前行为见[功能模块索引](../../modules/README.md)，入口见[源码导航](../../architecture/source-map.md)。跨端协议变化同步前端类型、消费方和相关规范；示例与测试优先使用隔离数据。
