# Agent 流式输出与报告抽屉

[返回功能模块索引](README.md)

## 范围与参考

继续使用 FastAPI、LangGraph、现有任务与检查点存储。展示参考 a2a-frontend 的 ReasoningBlock、ToolCallsBlock、ResizableDrawer 和 ReportWorkspace；a2a-backend 仅参考正文增量与结构化展示事件分离的方式，不依赖 AgentOS/Agno。

图标从参考项目 IconParkFont 指定的 `font_5232871_h05hk79sydm.js` 提取 5 个静态 SVG symbol，保存在 `apps/web/public/icons/agent.svg`。页面不执行图标集远程脚本。

## 数据流

`assistant.py` 在任务模式调用模型 `.stream()`；`streaming.py` 把文本、公开思考字段和结构化预览发送到 LangGraph custom channel。`run_job.py` 消费 custom + updates，验证任务租约与取消状态后，按到达顺序提交到现有 `JobEvent`。`jobs/routes.py` 以 SSE `progress` 事件输出，任务终止且所有分页排空后发送 `done`。

| kind                    | 主要 payload                    | 展示                           |
| ----------------------- | ------------------------------- | ------------------------------ |
| model.start / model.end | block_id, message               | 一轮模型开始与结束             |
| reasoning.delta         | block_id, text                  | 模型提供的可展示思考增量       |
| content.delta           | block_id, text                  | 正文增量                       |
| tool.start              | call_id, name, arguments        | 工具开始、名称与参数           |
| tool.end / tool.error   | call_id, name, result / message | 工具结果或拒绝原因             |
| report.start            | block_id                        | 清空该次报告的未完成模型预览   |
| report.delta            | block_id, insight               | 白名单字段的部分报告预览       |
| report.patch            | patch                           | 已完成规则节点及已校验模型结果 |
| node                    | node, message, detail           | 规则与图执行记录               |

任务执行事件含 `attempt`；数据库事件 ID 负责排序和去重，block_id / call_id 负责配对。同一任务重试保留历史，并将上次未结束的片段标为中断。已有 queued / running / failed / cancelled / succeeded 事件兼容。

`useJobStream` 批量提交前端状态、自动重连；token 不触发逐条 HTTP 状态刷新。报告选择、尺寸、展示状态在 `ReportWorkspace` 内，关闭抽屉不关闭 SSE。正文仅渲染安全 Markdown，不执行 HTML 或加载模型指定的图片。

## 前端代码入口

任务详情在 `pages/Job/index.tsx`，列表在 `pages/Jobs/index.tsx`，两者分别按需加载。`components/agent/` 下的 AgentStream、GeneratedReport、StreamText、ReportWorkspace、IconParkFont 各自使用 `index.tsx + index.less`；面板标题样式共用 `panel.module.css`。`useJobStream.ts` 与 `stream.ts` 保留纯逻辑入口，样式迁移不改变订阅、投影和报告校验边界。

## 模型兼容边界

API 需要支持流式 Chat Completions 和 function calling。OpenAI 兼容适配器保留响应中可选的 `reasoning_content`；原生文本 reasoning/thinking block 同样可展示。模型未返回公开思考字段时，不推测或补造。最终模型解读使用强制 `ModelInsight` 工具调用，部分参数只作草稿，完整参数须经过严格 JSON 解析、Pydantic 和 evidence_id 校验。

没有增加额外模型请求。工具仍只读冻结的行情、因子、风险、研究资料及已纳入的持仓；生成式渲染不赋予模型执行 HTML/JavaScript 的能力。

## 验证

- `tests/test_agent_stream.py` 使用真实 ChatOpenAI HTTP 客户端与本地 MockTransport，覆盖公开思考字段、分片工具参数、正文、部分报告、100 条以上事件分页、Last-Event-ID，以及无效引用和截断 JSON 不归档。
- `tests/test_p1.py` 保留任务生命周期、检查点恢复、取消及重试限制回归；FakeModel 同时实现流式协议。
- `e2e/agent-stream.spec.ts` 使用隔离事件与 API 响应，覆盖逐字显示、工具完整结果、事件去重、报告拖拽、关闭期间继续输出、失败恢复、原生 EventSource 历史回放、移动端和焦点恢复。验证不调用真实模型。
