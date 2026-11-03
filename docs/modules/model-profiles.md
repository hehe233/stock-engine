# 多套 API 配置管理

[返回功能模块索引](README.md)

入口：侧栏「模型设置」→「API 配置管理」。每套配置包含名称、Base URL、独立密钥、可选模型、默认模型及 Ollama 备选设置，最多 30 套，名称不可重复。

## 操作约定

- 新增：填写后保存为未启用配置，不覆盖当前供应商；再点击「切换启用」。
- 编辑：下拉选择一套配置，修改后保存。当前启用配置的修改即时生效；未启用配置的修改不影响当前服务。
- 切换：使用已保存版本，刷新工作台的模型列表；未保存的修改需要先保存，或确认放弃。
- 删除：先显示确认操作。删除非活动配置不影响当前服务；删除活动配置停用 API，不自动切换其他供应商或 `.env` 密钥。规则模式仍可使用。
- 测试：测试当前编辑配置，不保存、不启用，不读取其他配置密钥；明确点击才产生一次模型调用。
- 密钥：只在替换时输入，保存后不回显；新配置不会继承其他配置的密钥，更换 Base URL 必须替换或清除密钥。

停止服务后运行 `scripts/start-dev.ps1` 自动升级到当前 Alembic head；多套配置管理的迁移基线为 `0005`。原页面配置成为「默认配置」，地址、密钥、模型列表和历史任务均保留。若只有环境配置，先保存当前设置即可将其纳入管理。

删除配置是删除可管理入口，历史不可变配置版本仍保留以恢复已提交任务。当前存储仍未做静态加密；真正撤销凭证需在供应商侧操作。

## 学习：可变配置与不可变版本

`model_profiles` 保存稳定的配置 ID、名称和 `configuration_id` 指针；`model_configurations` 保存不可变内容。编辑产生新版本并移动指针。`service_states.model_settings` 同时记录活动 profile_id 与版本 id，API 和 worker 从同一数据库读取。历史任务绑定自己的配置版本，不依赖之后的配置名称或活动指针。

读取列表只返回白名单字段和 `has_api_key`。修改、切换、删除携带版本 revision；版本过期返回 409，已删除返回 404。单进程部署用已有 settings_lock 串行化写操作；新增/修改配置、移动活动指针在一个事务内提交。

阅读顺序：`pages/ModelSettings/index.tsx` → `features/model-settings/SettingsForm/index.tsx` → `api/model-settings.ts` / `features/model-settings/queries.ts` → `model_settings/routes.py` → `model_settings/service.py` → `db.py` → `0005_model_profiles.py`。回归测试见 `test_model_profiles.py`、`test_profile_migration.py` 和 `model-profiles.spec.ts`。

## API

| 方法 | 路径（前缀 `/api/settings/models`） | 行为                         |
| ---- | ----------------------------------- | ---------------------------- |
| GET  | `/profiles`                         | 脱敏列表及活动配置 ID        |
| POST | `/profiles`                         | 新建，201，默认不启用        |
| POST | `/profiles/{id}/update`             | 按 revision 更新、重命名     |
| POST | `/profiles/{id}/activate`           | 按 revision 启用             |
| POST | `/profiles/{id}/delete`             | 按 revision 删除管理入口     |
| POST | `/profiles/test`                    | 测试尚未保存的配置           |
| POST | `/profiles/{id}/test`               | 测试指定配置的草稿与独立密钥 |

原 `/api/settings/models` GET/POST/test 接口保留，保存会更新当前活动配置；无活动配置时创建「默认配置」。这个兼容入口便于已有调用方逐步迁移。
