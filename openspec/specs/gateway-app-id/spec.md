# gateway-app-id Specification

## Purpose
TBD - created by archiving change add-app-id-observability. Update Purpose after archive.
## Requirements
### Requirement: 客户端 Key 注册全局唯一的 app_id

网关在创建客户端 API Key 时必须要求提供非空 `app_id`。`app_id` 在 `spy_look_client_keys` 全表范围内必须唯一。trim 后的 `app_id` 必须匹配模式 `[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}`。

#### Scenario: 使用合法 app_id 创建 Key

- **WHEN** 管理员提交 `POST /admin/gateway-client-keys`，body 含 `gateway_api_key` 与 `app_id` `billing-service`
- **THEN** 系统持久化该 Key，且 `app_id` 为 `billing-service`，响应中包含 `app_id` 等元数据

#### Scenario: 拒绝重复的 app_id

- **WHEN** 管理员创建第二条 Key，其 `app_id` 已被其他 Key 占用
- **THEN** 系统返回 HTTP 400，且不创建该 Key

#### Scenario: 拒绝非法 app_id

- **WHEN** 管理员提交空的 `app_id`，或不符合允许模式的字符串
- **THEN** 系统返回 HTTP 400，且不创建该 Key

### Requirement: 允许更新客户端 Key 的 app_id

网关必须通过 `PATCH /admin/gateway-client-keys/{key_id}` 允许更新已有 Key 的 `app_id`，并适用相同的格式与唯一性规则。

#### Scenario: 成功更新 app_id

- **WHEN** 管理员为某 Key 提交新的、合法且唯一的 `app_id`
- **THEN** 该 Key 行被更新，此后经鉴权的请求落库使用新的 `app_id`

#### Scenario: 历史日志保留当时的 app_id 快照

- **WHEN** 管理员在已有请求日志之后修改某 Key 的 `app_id`
- **THEN** 已有日志行仍保留请求写入时的 `app_id`，不被回溯修改

### Requirement: 鉴权请求从 API Key 解析 app_id

对受网关客户端鉴权保护的路由，系统必须通过 Bearer token 查询 `spy_look_client_keys` 解析 `app_id`。无效或缺失的 token 必须在上游处理之前以 HTTP 401 拒绝。

#### Scenario: 合法 Key 解析出 app_id

- **WHEN** 客户端使用绑定 `app_id` `copilot` 的合法 Bearer token 调用 `POST /v1/chat/completions`
- **THEN** 网关继续转发上游，且日志记录关联 `app_id` `copilot`

#### Scenario: 非法 Key 被拒绝

- **WHEN** 客户端调用受保护路由时缺少 Bearer token，或 token 未知
- **THEN** 网关返回 HTTP 401，且不为该次尝试写入日志行

### Requirement: 日志事件持久化 app_id

对 `/v1/chat/completions` 与 `/v1/models` 写入的每条日志，必须包含 `app_id` 列，取值来自请求时刻解析的客户端 Key。网关不得接受请求 body 中的 `app_id` 作为覆盖。

#### Scenario: 对话请求同时记录 app_id 与 session_id

- **WHEN** 客户端发送带 `session_id` `thread-1` 的对话请求，且 Key 绑定 `app_id` `worker-a`
- **THEN** 日志行含 `app_id` `worker-a`、`session_id` `thread-1`，且转发上游的 body 不含 `session_id`

#### Scenario: 模型列表请求记录 app_id

- **WHEN** 客户端使用绑定 `app_id` `billing-service` 的 Key 调用 `GET /v1/models`
- **THEN** 日志行含 `app_id` `billing-service`、`session_id` `default`

### Requirement: 遗留数据具备明确的 app_id 缺省值

数据库迁移时，尚无 `app_id` 的已有日志行必须存为 `app_id` `unknown`。尚无 `app_id` 的已有客户端 Key 必须获得唯一占位符 `legacy-key-{id}`，以保证服务可继续运行，直至管理员配置正式 `app_id`。

#### Scenario: 旧日志以 unknown 展示

- **WHEN** 运维查询本能力上线之前写入的日志
- **THEN** 这些行的 `app_id` 为 `unknown`（除非日后人工回填）

