## Why

运维在上游配置页只能做 `/models` 连通性探测，无法系统化验证某模型是否支持工具调用、结构化输出、思考模式等 Chat Completions 能力。已有 `api/capability_probe.py` 探测工具，但缺少 Web 入口与 API，无法在应用列表页快速发起测试并查看结构化结果。

## What Changes

- 在观测首页（应用列表）masthead 的「对外调用」与「刷新」之间新增 **「模型能力测试」** 按钮，跳转至独立测试页（如 `/model-capability-probe`）。
- 新增 **模型能力探测 API**（如 `POST /admin/model-capability-probe`），入参支持：
  - **上游模式**：选择已启用上游（`upstream_id`）+ 模型名（`model`），服务端从 SQLite 读取 `base_url`、`api_key`；
  - **自定义模式**：手动填写 `uri`、`api_key`、`model`。
- 后端调用已有 `probe_model_capabilities()`，返回完整探测 dict（含 `chat_completion`、`tool_calling`、`json_mode`、`thinking` 等项）。
- 新增测试页 UI：上游/模型下拉、自定义参数表单、发起探测、**将返回 dict 解析为可读的中文卡片式报告**（支持/不支持徽章、说明、错误、HTTP 状态、子项汇总等；风格与现有 Editorial Ops Desk 观测页一致）。
- 可选：提供 `GET /admin/model-capability-probe/options`，返回已启用上游列表及（按需）各上游可用模型 id，供下拉填充。
- 清理 `capability_probe.py` 中 `main()` 硬编码密钥示例（若仍存在），避免误提交敏感信息。

## Capabilities

### New Capabilities

- `model-capability-probe`：模型能力探测 API、测试页入口与结果展示（基于 `capability_probe.probe_model_capabilities`）。

### Modified Capabilities

- （无）现有 `observability-apps`、`gateway-app-id` 规格行为不变；仅在应用列表页增加导航入口，不改变日志观测 API。

## Impact

- **后端**：`api/app.py`（新路由）、`api/capability_probe.py`（复用/小幅导出常量供前端映射标签）；可能新增 `api/schemas.py` 请求体模型。
- **前端**：`web/index.html`（入口按钮）、新建 `web/model-capability-probe.html`、`web/js/model-capability-probe.js`、配套 CSS（或扩展现有样式）。
- **数据**：只读 SQLite 上游配置；不新增表。
- **非目标**：探测结果持久化、批量探测、观测 API 鉴权加固、在网关转发路径中自动探测。
