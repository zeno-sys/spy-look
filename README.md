# 启动命令

```bash
uv run main.py
```

# Spy-Look 设计说明

Spy-Look 是一个面向 OpenAI 兼容接口的轻量网关：对外提供稳定的 `/v1/*` 入口，对内转发到上游模型服务，并补齐认证、错误归一化、可观测日志与简易管理能力。

另外，还支持会话功能，使用会话功能只需在请求体中增加 `session_id` 字段即可。

---

## 1. 设计目标与边界

### 目标

- **接口兼容优先**：尽量保持与 OpenAI 风格一致的路径与错误格式，减少调用侧改造成本。
- **网关职责清晰**：承担鉴权、转发、错误标准化、日志沉淀，不承担模型编排/路由策略。
- **低依赖可运行**：基于 FastAPI + httpx + sqlite，适合本地与小规模场景快速落地。
- **可观测可追溯**：请求元信息、延迟、token 统计（非流式）和请求/响应体均可落库查询。

### 当前边界（明确不做）

- 不做多上游负载均衡与智能路由。
- 不做租户级配额、限流、计费策略。
- 不做复杂权限体系（多把对外 Key 存 SQLite，`Bearer` 匹配其一即通过；无租户 / RBAC 等）。
- 不做生产级日志分片、冷热分层或归档策略。

---

## 2. 系统上下文与请求模型

网关处于“客户端”与“上游 LLM 服务”之间，逻辑上是一个协议和语义适配层：

1. 客户端携带 `Authorization: Bearer <gateway_key>` 调用网关。
2. 网关完成鉴权、参数透传与上游请求发起。
3. 上游响应返回后，网关进行错误归一化和日志记录。
4. 网关将标准化结果返回客户端（支持非流式 JSON 与流式 SSE）。

核心接口：

- `GET /v1/models`
- `POST /v1/chat/completions`
- `GET /healthz`
- `GET /logs` / `DELETE /logs/{log_id}`（网关内部观测面；`GET /logs` 支持 `session_id` 等过滤与分页）
- `GET /logs/sessions`（按会话聚合的列表，支持 `limit` / `offset` 分页，返回 `total`）
- `GET /`（内置观测页面：先会话列表，点进会话后再看该会话下的请求日志；URL 使用 `?session_id=...` 与日志视图同步）

---

## 3. 架构分层与模块职责

### 3.1 入口层（`api/app.py`）

- 负责 FastAPI 生命周期管理（启动初始化、关闭释放连接）。
- 定义全部 HTTP 路由与请求处理流程。
- 将鉴权、上游调用、错误转换、日志记录串成完整链路。
- `POST /v1/chat/completions` 可选读取 body 中的 **`session_id`**（仅网关用于落库与观测）；**转发上游前会从 JSON 中移除该字段**，避免非标准字段干扰真实模型。
- 提供异常兜底处理，将 `HTTPException` 统一转为 OpenAI 风格错误体。

### 3.2 鉴权层（`api/auth.py`）

- 校验 `Authorization` 头格式与 `Bearer` token。
- 与 SQLite 表 `spy_look_client_keys` 中**任意一条** `api_key` 匹配即通过；密钥仅通过管理页或自行写库配置，**不从代码常量种子**。
- 鉴权失败直接返回结构化 `401` 错误，错误码为 `invalid_api_key`。

### 3.3 上游访问层（`api/upstream_client.py`）

- 以 `httpx.AsyncClient` 封装上游连接与超时配置。
- 统一注入上游 `Authorization` 与 `Content-Type` 请求头。
- 暴露三类能力：模型列表、非流式对话、流式对话。
- 流式场景返回 `(response, async_iterator)`，由入口层继续包装成客户端流。

### 3.4 错误语义层（`api/errors.py`）

- 提供 OpenAI 风格错误响应构造器。
- 将网络超时映射为 `504 / timeout_error`。
- 将连接类失败映射为 `502 / upstream_error`。
- 若上游错误体已是 `{"error": ...}` 结构则透传，否则标准化为统一错误体。

### 3.5 观测与存储层（`api/usage.py` + `web/`）

- 网关对外 Key（`spy_look_client_keys`）与上游（`spy_look_upstreams`）**仅以 SQLite 为准**，通过 `/upstream-config` 管理；无内置默认种子。
- 请求事件写入 sqlite（`spy_look.db`，位于项目根目录）并输出 JSON 日志；每条记录带 **`session_id`**，用于会话维度隔离。
- `GET /logs` 支持按路径、模型、IP、**`session_id`**、时间区间过滤与分页；落库的 `request_body` 与上游一致（**不含** `session_id`）。
- `GET /logs/sessions` 对 `session_id` 做聚合统计（条数、首末时间），供内置页会话列表使用，并与 `limit` / `offset` 分页对齐。
- 支持按 `id` 删除日志。
- 内置页面（静态资源在 `web/`，由 FastAPI 托管）：默认进入**会话列表**；选择会话后进入**该会话的请求日志表**（`session_id` 与地址栏 `?session_id=` 同步，便于书签与刷新）。

---

## 项目结构

```
spy-look/
├── main.py             # 启动入口（uv run main.py）
├── api/                # FastAPI 后端（API + 静态托管）
│   ├── app.py
│   ├── auth.py
│   ├── errors.py
│   ├── upstream_client.py
│   ├── usage.py
│   └── schemas.py
├── web/                # 管理页静态资源（HTML / CSS / JS）
│   ├── index.html
│   ├── upstream-config.html
│   ├── css/
│   └── js/
├── spy_look.db         # 运行时 SQLite（首次启动后生成）
├── pyproject.toml
└── README.md
```

环境变量（可选）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SPY_LOOK_HOST` | `127.0.0.1` | 监听地址 |
| `SPY_LOOK_PORT` | `8000` | 监听端口 |
| `SPY_LOOK_RELOAD` | 关闭 | 设为 `1` / `true` 开启热重载 |

---

## 4. 关键流程设计

### 4.1 非流式对话（`stream=false`）

1. 解析请求体；校验为 JSON 对象。若有 **`session_id`** 则解析出会话桶（缺省或空白则 **`default`**），并构造**去掉 `session_id` 后的 body** 用于上游。
2. 从上游 body 提取 `model`、`stream`。
3. 调用上游 `/chat/completions`（仅携带上游 body）。
4. 解析响应 JSON；若含 `usage` 则提取 token 统计。
5. 按统一事件结构落日志（含 request/response body 与 **`session_id`** 列）。
6. 若上游报错，做错误归一化后返回；否则透传成功响应。

### 4.2 流式对话（`stream=true`）

1. 同样先解析 **`session_id`** 并构造**不含 `session_id`** 的上游 body，再建立上游流式请求。
2. 若上游在握手阶段直接报错，则立即标准化返回错误 JSON。
3. 若握手成功，网关边读边转发字节流给客户端。
4. 在流结束阶段统一收尾：关闭上游响应、计算耗时、落库完整拼接后的流内容（并写入对应 **`session_id`**）。

设计取舍：流式场景记录“完整拼接文本”，便于排障，但会带来较大存储开销。

### 4.3 模型列表

- 直接代理 `/models`，并记录访问事件（不含 token 数据）；观测落库的 **`session_id` 固定为 `default`**（与对话会话无关）。
- 对上游错误走统一归一化策略。

---

## 5. 数据与日志模型

日志表 `spy_look_logs` 的核心字段：

- 请求维度：`path`, `model`, `client_ip`
- **会话维度：`session_id`**（文本；对话请求**未带** `session_id` **或为空字符串**时网关记为 **`default`**）
- 结果维度：`status_code`, `latency_ms`
- token 维度：`input_tokens`, `output_tokens`, `total_tokens`
- 内容维度：`request_body`, `response_body`（与上游一致；**对话**类请求体中不会出现网关扩展字段 `session_id`）
- 时间维度：`created_at`

**调用约定（对话）**：客户端可在 `POST /v1/chat/completions` 的 JSON 根级增加 **`session_id`** 字符串，用于在库内区分多路对话或租户会话；网关**不会**把它转发给上游。未传或传空字符串时，日志归入 **`default`** 会话桶。

**观测 API 摘要**：

| 接口 | 作用 |
|------|------|
| `GET /logs` | 分页查询原始日志行；Query 含 `session_id` 时只返回该会话 |
| `GET /logs/sessions` | 按 `session_id` 聚合列表；Query：`limit`（默认 50，最大 200）、`offset`；响应含 `items`、`total`、`limit`、`offset` |
| `DELETE /logs/{log_id}` | 按主键删除一条日志 |

已有库会通过表结构定义自动创建；首次启动生成 `spy_look.db`。

该模型既能支持线上排障（按状态码/时间/会话回溯），也能支持基础成本分析（按 token 聚合）与按会话浏览内置页。

---

## 6. 统一错误语义（对调用方的契约）

网关尽量保持 OpenAI 式错误结构：

- 顶层固定：`{"error": {...}}`
- 字段语义：`message`, `type`, `param`, `code`

典型映射策略：

- 网关鉴权失败：`401 invalid_api_key`
- 上游超时：`504 upstream_timeout`
- 上游不可达：`502 upstream_unavailable`
- 上游返回非 JSON：`invalid_upstream_response`

这样可以保证调用方用一套错误解析逻辑处理“网关错误 + 上游错误”。

---

## 7. 已有优点与演进方向

### 已有优点

- 架构简单，职责边界清楚，学习和二次改造成本低。
- 错误语义统一，接口契约稳定。
- 同时支持流式与非流式，具备最小可用观测能力。

### 可演进方向（设计层面）

- **配置管理**：从硬编码 dataclass 演进为环境变量/配置中心。
- **安全性**：支持多 Key、按 Key 维度统计、最小权限策略。
- **可靠性**：增加重试/熔断/限流与上游健康探测。
- **可观测性**：日志脱敏、结构化指标、追踪 ID 贯穿。
- **可扩展性**：抽象上游适配器，支持多后端协议与路由策略。

---

## 8. 一句话总结

Spy-Look 的核心价值不是“封装一次调用”，而是把 **OpenAI 兼容入口、统一错误语义、可追溯且可按会话隔离的日志能力** 收敛到一个轻量中间层，为后续扩展（安全、治理、路由）留出清晰演进路径。
