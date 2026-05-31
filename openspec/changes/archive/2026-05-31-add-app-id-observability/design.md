## 背景

Spy-Look 是本地 OpenAI 兼容网关：对外校验 `spy_look_client_keys` 中的 Bearer Key，请求经默认上游转发，观测数据写入 `spy_look_logs`。当前日志维度以 **`session_id`**（请求体可选字段，网关 strip 后不转发）为主；`spy_look_client_keys` 仅有 `api_key`，鉴权层不返回调用方身份，日志表无应用维度。

已确认的产品决策：**`app_id` 全局唯一**；观测入口为 **应用 → 会话 → 日志** 三级。

## 目标 / 非目标

**目标：**

- 注册/编辑网关 API Key 时配置全局唯一 `app_id`。
- 每次受鉴权请求落库时，根据 Bearer Key 解析 `app_id` 并写入 `spy_look_logs.app_id`（快照，不转发上游）。
- 提供按应用聚合的 API，以及带 `app_id` 过滤的会话/日志查询。
- 观测首页改为三级导航，URL 与 `app_id`、`session_id` 同步。

**非目标：**

- 允许客户端在 body 中覆盖 `app_id`。
- 观测 API（`/logs*`）与管理 API 的鉴权加固。
- Key 轮换、一应用多 Key 的复杂建模（一 Key 一 `app_id`；多环境用不同 `app_id` 字符串区分）。
- 历史日志按新 Key 配置做回填（backfill）。

## 技术决策

### 1. 数据模型：`app_id` 存在 Key 表与日志表

- **`spy_look_client_keys`**：新增 `app_id TEXT NOT NULL UNIQUE`（创建时必填）。
- **`spy_look_logs`**：新增 `app_id TEXT NOT NULL DEFAULT 'unknown'`；索引 `(app_id, created_at)` 与 `(app_id, session_id)` 以支撑聚合与筛选。

**理由**：日志冗余 `app_id`，避免 Key 删除或改名后历史语义丢失；查询与 UI 不依赖 join。

**备选**：仅存 `client_key_id` → 观测需 join，Key 删除后展示差。

### 2. `app_id` 格式与校验

- 非空字符串；trim 后长度 1–64。
- 字符集：`[a-zA-Z0-9][a-zA-Z0-9._-]*`（与常见 service slug 一致）。
- 表级 **UNIQUE**；冲突返回 400。

**理由**：全局唯一由数据库保证；限制字符集避免 URL/query 编码问题。

### 3. 鉴权依赖返回 `app_id`

- 将 `verify_gateway_key` 改为 `resolve_gateway_client(authorization) -> str`（返回 `app_id`），内部 `SELECT app_id FROM spy_look_client_keys WHERE api_key = ?`。
- `/v1/models` 与 `/v1/chat/completions` 使用 `Depends(resolve_gateway_client)`，handler 将 `app_id` 传入 `log_event`。

**理由**：单次数据库查询同时完成校验与身份解析；避免 handler 再查 Key 明文。

### 4. 历史数据与缺省值

- 迁移前已存在的日志行：新列默认 `unknown`，必要时 `UPDATE` 补齐空值。
- 已有 `spy_look_client_keys` 行：`_init_db` 后为无 `app_id` 的行写入 `legacy-key-{id}`（保证 UNIQUE）；管理页提示运维改为正式名称；新插入 Key 必须显式提供 `app_id`。

**理由**：单机工具优先可启动；占位 id 可被发现并替换；本变更包含 PATCH 编辑 `app_id`。

### 5. 管理 API

- `POST /admin/gateway-client-keys`：body 增加必填 `app_id`（与 `gateway_api_key` 同级）。
- `PATCH /admin/gateway-client-keys/{key_id}`：允许更新 `app_id`（校验 UNIQUE）；**不**回溯修改历史日志中的 `app_id`。
- `GET` 列表 meta 返回 `app_id`。

### 6. 观测 API

| 端点 | 行为 |
|------|------|
| `GET /logs/apps` | 按 `app_id` 聚合：`log_count`、`first_created_at`、`last_created_at`；支持 `limit`/`offset`/`total` |
| `GET /logs/sessions?app_id=` | **必填** `app_id`；在该应用下按 `session_id` 分组 |
| `GET /logs?app_id=` | 可选；与 `session_id` 等现有参数 AND |

`/v1/models` 落库时使用解析出的 `app_id`，`session_id` 仍为 `default`。

### 7. 观测 UI 路由

```
/                                    → 应用列表（viewApps）
/?app_id=billing                     → 该应用会话列表（viewSessions）
/?app_id=billing&session_id=u-42   → 该会话日志（viewLogs，session_id 只读）
```

- 面包屑/返回：日志 → 会话列表（保留 `app_id`）→ 应用列表（清除 query）。
- 日志筛选项保留 path/model 等；`app_id` 由 URL 注入，只读展示。

### 8. 日志表不存 api_key 或 key_id

仅冗余 `app_id` 文本；需对照「哪把 Key」时查管理页 Key 列表。

## 风险与权衡

| 风险 | 缓解 |
|------|------|
| 修改 `app_id` 后历史日志仍显示旧值 | 文档说明；必要时接受或未来做 backfill |
| 占位 `legacy-key-{id}` 暴露迁移痕迹 | 管理页展示并鼓励重命名 |
| URL 中 `app_id` + `session_id` 变长 | slug 限制 64 字符；仅观测页使用 |
| 三级 UI 改动面较大 | 复用现有表格与分页；按 tasks 分步实现 |

## 迁移计划

1. 部署新版本；`_init_db` 执行 `ALTER TABLE`（通过 pragma 检测列是否已存在）。
2. 为旧 `client_keys` 补 `legacy-key-{id}`；为旧 `logs` 设 `unknown`。
3. 运维在 `/upstream-config` 将占位 `app_id` 改为正式名称；新建 Key 时填写正式 `app_id`。
4. 回滚：新列可保留；旧版本代码忽略新列即可。

## 待决问题

- （无）全局唯一 `app_id` 与三级观测入口已确认。
