## 1. 数据库与存储层

- [x] 1.1 在 `usage.py` 为 `spy_look_client_keys` 增加 `app_id`（NOT NULL UNIQUE）及迁移逻辑；已有行写入 `legacy-key-{id}`
- [x] 1.2 为 `spy_look_logs` 增加 `app_id` 列（默认 `unknown`）、索引，迁移时将历史行设为 `unknown`
- [x] 1.3 实现 `app_id` 格式校验与 `resolve_app_id_by_api_key` / `lookup_client_by_key` 查询
- [x] 1.4 更新 `add_client_key`、`list_client_keys_meta`、`get_client_key_plain`；新增 `update_client_key_app_id`
- [x] 1.5 更新 `log_event` 与 `query_logs` 写入/筛选 `app_id`
- [x] 1.6 实现 `list_log_apps`；`list_log_sessions` 增加必填 `app_id` 参数

## 2. 鉴权与 API 路由

- [x] 2.1 将 `auth.verify_gateway_key` 改为 `resolve_gateway_client` 返回 `app_id`
- [x] 2.2 `/v1/models` 与 `/v1/chat/completions` 三处 `log_event` 传入解析的 `app_id`
- [x] 2.3 `GET /logs/apps`；`GET /logs/sessions` 要求 `app_id`；`GET /logs` 支持 `app_id`
- [x] 2.4 `POST /admin/gateway-client-keys` 接受必填 `app_id`；新增 `PATCH /admin/gateway-client-keys/{key_id}` 更新 `app_id`

## 3. 管理页（upstream-config）

- [x] 3.1 表格与表单增加 `app_id` 列/输入；创建 Key 时一并提交
- [x] 3.2 支持编辑已有 Key 的 `app_id`（调用 PATCH）

## 4. 观测页（三级导航）

- [x] 4.1 默认视图改为应用列表，调用 `GET /logs/apps`
- [x] 4.2 `?app_id=` 时展示会话列表（`GET /logs/sessions?app_id=`），点击进入日志
- [x] 4.3 `?app_id=&session_id=` 时展示日志列表；面包屑/返回保留 `app_id`
- [x] 4.4 日志表增加 `app_id` 列（只读）；URL 与 `applyRoute` 逻辑同步

## 5. 文档与收尾

- [x] 5.1 更新 `README.md`：`app_id` 配置约定、观测 API、三级 UI 说明
- [x] 5.2 手动验证：双 Key 双 `app_id` 请求后，应用/会话/日志筛选与聚合正确
