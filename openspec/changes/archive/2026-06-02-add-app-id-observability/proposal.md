## Why

Spy-Look 目前仅用请求体中的 `session_id` 对日志做会话归类，无法稳定区分「哪个下游服务」在调用网关。多个应用共用同一 API Key、或调用方未传/乱传 `session_id` 时，观测与排障都会混在一起。需要在注册网关 API Key 时绑定全局唯一的 `app_id`，落库时按 Key 解析并写入日志，并在观测入口提供「应用 → 会话 → 日志」三级导航。

## What Changes

- 在 `spy_look_client_keys` 表增加 **`app_id`** 列（**全局 UNIQUE**，必填），创建/编辑 Key 时必须配置。
- 鉴权通过后根据 `api_key` 解析 `app_id`，写入 `spy_look_logs` 新列 **`app_id`**（冗余快照，不转发上游）。
- 新增 **`GET /logs/apps`**：按 `app_id` 聚合（条数、首末时间），分页。
- **`GET /logs/sessions`** 必须带 `app_id` 查询参数，仅返回该应用下的会话。
- **`GET /logs`** 支持 `app_id` 查询参数。
- 管理页（`/upstream-config`）：新增/编辑网关 Key 时填写 `app_id`；列表展示 `app_id`。
- 观测页（`/`）：三级入口——应用列表 → 某应用下的会话列表 → 某会话下的请求日志；URL 与 `app_id`、`session_id` 同步（如 `?app_id=...&session_id=...`）。
- 历史日志与未配置 `app_id` 的旧 Key：迁移策略见 design（旧日志 `app_id` 为 `unknown`；已有 Key 写入占位 `legacy-key-{id}` 直至运维修改）。
- 更新 `README.md` 中的调用约定与观测 API 说明。

## 能力范围

### 新增能力

- `gateway-app-id`：网关客户端 Key 上的 `app_id` 配置、鉴权解析、日志落库字段。
- `observability-apps`：按 `app_id` 聚合的 API 与「应用 → 会话 → 日志」观测 UI。

### 修改的既有能力

- （无）项目尚无 `openspec/specs/` 基线能力文档；本次均为新能力规格。

## 影响范围

- **数据**：`spy_look.db` 表结构迁移（`client_keys.app_id`、`logs.app_id` + 索引）。
- **后端**：`api/usage.py`、`api/auth.py`、`api/app.py`（`log_event` 三处、管理 API、观测 API）。
- **前端**：`web/index.html`、`web/js/index.js`；`web/upstream-config.html`、`web/js/upstream-config.js`。
- **文档**：`README.md`。
- **非目标**：请求 body 中由客户端自选 `app_id`；多租户硬隔离与 Key 轮换；观测 API 鉴权加固。
