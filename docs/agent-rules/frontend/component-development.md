# 组件开发规范

适用于 `apps/web/src/components/` 和页面私有组件。界面规格见[工作区界面](../../modules/ui-workspace.md)，页面数据获取见[页面规范](page-development.md)。任务提示词见[前端提示词](prompts.md)。

## 复用与接口

- 新组件先搜索已有组件、hooks 和样式。独立可视组件和业务模块采用 PascalCase 目录，入口为 `index.tsx`，局部样式为 `index.less`，保留有名称的组件与现有命名导出习惯。无独立样式的逻辑入口不创建空 Less 文件。存量组件按功能迁移，避免同名 TSX 文件与目录并存。
- 表单、表格和通用交互优先使用现有 antd 组件；特殊侧栏、分隔条和流式展示沿用现有实现。使用本项目安装版本支持的 API。
- 展示组件优先以 props 接收数据和回调。TS 类型使用推断、联合类型和窄化；外部输入先校验，不以 `any` 掩盖契约缺失。
- 事件处理与副作用说明触发条件和清理路径；只对实际高频渲染或已测量问题使用缓存优化。

## 样式与主题

- 新目录组件通过 `import styles from './index.less'` 引入局部样式，类名采用 camelCase。`build/component-less.ts` 将 src 内相对/绝对路径引用的 `index.less` 交给 Vite 的 Less/CSS Modules 管线；不提交物理 `index.module.less`，不对该入口使用 query 后缀或别名导入。旧 `.module.css` 继续工作，页面共用布局仍复用 `styles/Workbench.module.css`，不逐组件复制。
- 编译适配或样式导入规则变化时运行根目录 `scripts/check-styles.ps1`；结果见 `.runtime/styles.exit-code` 与日志。它使用隔离临时页面和随机本机端口，验证同名类隔离、嵌套、资源路径、旧样式共存、热更新与生产 CSS 提取，并在结束后关闭测试服务。
- antd 主题在 `styles/theme.ts`，自定义变量在 `styles/global.css`。新增颜色、间距先查已有 token/变量；行情红涨绿跌保持一致。
- antd 样式优先使用组件公开的主题和样式入口；确需覆盖内部类时使用局部类限定的 `:global(...)`，按实际 DOM 和 portal 挂载位置核验影响范围。
- 动态宽度等运行时值可以经 CSS 自定义属性传入；固定视觉规则留在样式文件。避免全局选择器和无依据的 `!important`。

## 交互与无障碍

- 图标按钮提供可访问名称；交互使用正确的按钮/链接元素。抽屉处理 Esc、焦点进入/恢复和移动端关闭行为。
- 拖拽分隔条同时提供键盘操作、边界值和可见焦点。响应式检查实际内容宽度，宽表格在自身区域滚动。
- 动画尊重 `prefers-reduced-motion`；加载和错误信息可被读屏理解。至少核对桌面、窄屏及本次改动涉及的临界宽度。

## 流式组件

- `AgentStream` 消费事件展示，`stream.ts` 组织展示数据，`ReportWorkspace` 管理报告选择与抽屉；业务终态由任务/事件契约决定。
- 关闭抽屉、改变宽度或切换侧栏不取消任务；无正文不等于未执行，无新事件不等于已完成。
- Markdown 沿用安全渲染路径；模型内容不能成为可执行 HTML、脚本或任意远程图片。只展示供应商实际返回的公开思考字段。
- 触及事件映射或草稿状态时同时遵循 [Agent 开发规范](../backend/agent-development.md)，验证完成、失败、取消、重试与回放。
