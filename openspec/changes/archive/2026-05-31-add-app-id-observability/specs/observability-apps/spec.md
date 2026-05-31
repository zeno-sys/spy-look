## ADDED Requirements

### Requirement: 按日志聚合列出应用

网关必须提供 `GET /logs/apps`，返回去重后的 `app_id` 及每个应用的 `log_count`、`first_created_at`、`last_created_at`，按 `last_created_at` 降序排列，并支持 `limit`、`offset` 与 distinct `app_id` 总数 `total`。

#### Scenario: 分页获取应用列表

- **WHEN** 客户端请求 `GET /logs/apps?limit=20&offset=0`
- **THEN** 响应最多包含 20 条应用摘要，且带有 distinct `app_id` 的 `total` 计数

### Requirement: 在指定应用下列出会话

网关必须提供 `GET /logs/sessions`，且要求查询参数 `app_id`。结果仅包含至少有一条日志行的 `app_id` 等于该参数值的会话。

#### Scenario: 查询单个应用下的会话

- **WHEN** 客户端请求 `GET /logs/sessions?app_id=billing-service`
- **THEN** 返回的每个会话行仅聚合 `app_id` 为 `billing-service` 的日志，并含每会话的 `log_count` 与时间范围

#### Scenario: 缺少 app_id 时拒绝

- **WHEN** 客户端请求 `GET /logs/sessions` 且未带 `app_id`
- **THEN** 系统返回 HTTP 400 或 422，提示必须提供 `app_id`

### Requirement: 按 app_id 筛选日志

网关必须在 `GET /logs` 上支持可选查询参数 `app_id`。提供时，结果仅包含 `app_id` 匹配的行。

#### Scenario: 按应用与会话联合筛选

- **WHEN** 客户端请求 `GET /logs?app_id=copilot&session_id=thread-9`
- **THEN** 返回的每条日志行的 `app_id` 为 `copilot`，`session_id` 为 `thread-9`

### Requirement: 观测 UI 提供三级导航

内置观测页 `/` 必须提供：

1. 无查询参数时默认展示应用列表；
2. URL 含 `app_id` 时展示该应用下的会话列表；
3. URL 同时含 `app_id` 与 `session_id` 时展示该会话下的请求日志列表。

在会话视图与日志视图之间导航时必须保留 `app_id`；必须能清除应用范围并返回应用列表。

#### Scenario: 从应用到会话再到日志

- **WHEN** 运维打开 `/`，选择应用 `worker-a`，再选择会话 `default`
- **THEN** 浏览器 URL 含 `app_id=worker-a` 与 `session_id=default`，表格仅显示该组合的日志

#### Scenario: 从日志返回会话列表

- **WHEN** 运维正在查看 `app_id=worker-a&session_id=thread-1` 的日志并返回会话层
- **THEN** URL 含 `app_id=worker-a` 且不含 `session_id`，会话列表仅显示 `worker-a` 下的会话

### Requirement: 管理页为 Key 配置 app_id

上游配置页必须为每条网关客户端 Key 展示 `app_id`；新增 Key 时必须填写 `app_id`；必须支持编辑已有 Key 的 `app_id`。

#### Scenario: 在配置页新增带 app_id 的 Key

- **WHEN** 管理员在配置页输入新 API Key 与 `app_id` 并提交
- **THEN** 列表中出现该 Key，且显示所填 `app_id`
