# model-capability-probe Specification

## Purpose
TBD - created by archiving change add-model-capability-probe. Update Purpose after archive.
## Requirements
### Requirement: 应用列表提供模型能力测试入口

观测首页应用列表 masthead MUST 在「对外调用」按钮与「刷新」按钮之间展示名为「模型能力测试」的导航控件，点击后进入模型能力测试页（`/model-capability-probe`）。

#### Scenario: 从应用列表进入测试页

- **WHEN** 用户打开 `/` 且处于应用列表视图
- **THEN** masthead 中「对外调用」与「刷新」之间可见「模型能力测试」
- **AND** 点击后浏览器导航至 `/model-capability-probe`

### Requirement: 模型能力测试页支持上游与自定义两种探测模式

模型能力测试页 MUST 允许用户选择已启用上游及其模型发起探测，也 MUST 允许用户手动填写 `uri`、`api_key`、`model` 发起探测；两种模式互斥，且 MUST 在提交前校验必填字段非空。

#### Scenario: 上游模式选择模型并探测

- **WHEN** 用户在上游模式下选择已启用上游与模型名并点击开始探测
- **THEN** 前端 MUST 向 `POST /admin/model-capability-probe` 发送 `{ "mode": "upstream", "upstream_id": <number>, "model": "<string>" }`

#### Scenario: 自定义模式填写连接信息并探测

- **WHEN** 用户切换至自定义模式并填写 uri、api_key、model 后点击开始探测
- **THEN** 前端 MUST 向 `POST /admin/model-capability-probe` 发送 `{ "mode": "custom", "uri": "<string>", "api_key": "<string>", "model": "<string>" }`

### Requirement: 后端暴露探测选项与执行 API

系统 MUST 提供 `GET /admin/model-capability-probe/options`，返回已启用上游列表及各上游可用模型 id（通过上游 GET `/models` 获取，失败时该上游对应空列表）。

系统 MUST 提供 `POST /admin/model-capability-probe`：在 `upstream` 模式下从 SQLite 解析上游 `base_url` 与 `api_key`；在 `custom` 模式下使用请求体参数；两种模式 MUST 调用 `probe_model_capabilities` 并返回其结构化 dict（可附加 `total_elapsed_ms`）。无效 `upstream_id`、未启用上游或缺少必填字段 MUST 返回 4xx。

#### Scenario: 上游模式成功返回探测报告

- **WHEN** 客户端 POST `{ "mode": "upstream", "upstream_id": 1, "model": "gpt-4o" }` 且上游 1 已启用且探测成功
- **THEN** 响应 MUST 为 JSON，包含 `uri`、`endpoint`、`model` 及 `chat_completion`、`tool_calling`、`json_mode`、`thinking` 等能力项

#### Scenario: 自定义模式缺少 model 被拒绝

- **WHEN** 客户端 POST `{ "mode": "custom", "uri": "http://x/v1", "api_key": "sk-test" }` 且未提供 `model`
- **THEN** 服务端 MUST 返回 400

### Requirement: 探测结果以结构化中文 UI 展示

模型能力测试页 MUST 将 `POST /admin/model-capability-probe` 返回的 dict 解析为可读的中文报告 UI（非原始 JSON  dump），至少包含：服务地址、模型名、总耗时；每项能力（基础对话、工具调用、结构化输出、思考模式）的支持/不支持/已跳过状态、说明与错误信息；思考模式项 MUST 展示模式判定与子项（开启/关闭思考参数）摘要；底部 MUST 展示通过项数汇总。

#### Scenario: 展示混合通过报告

- **WHEN** 探测完成且响应中部分能力 `supported: true`、部分为 `false`
- **THEN** 页面 MUST 以区分样式展示各能力状态
- **AND** 汇总区 MUST 显示形如「部分通过（x/y）」的统计

#### Scenario: 基础对话失败时后续项标记跳过

- **WHEN** 响应中 `chat_completion.supported` 为 `false` 且其他项 detail 含「跳过：基础对话不可用」
- **THEN** UI MUST 将这些能力显示为「已跳过」而非「不支持」

