## 1. 后端 API

- [x] 1.1 在 `api/app.py` 注册 `GET /model-capability-probe` 静态页路由（返回 `web/model-capability-probe.html`）
- [x] 1.2 实现 `GET /admin/model-capability-probe/options`：返回已启用上游列表；并行对各上游 GET `/models` 填充 `models_by_upstream`
- [x] 1.3 实现 `POST /admin/model-capability-probe`：校验 `upstream` / `custom` 两种 body；`upstream` 模式用 `get_upstream_runtime`；调用 `asyncio.to_thread(probe_model_capabilities, ...)` 并附加 `total_elapsed_ms`
- [x] 1.4 在 `api/schemas.py`（或 app 内）定义请求体验证：`mode`、`upstream_id`、`uri`、`api_key`、`model`、可选 `timeout` / `max_tokens`
- [x] 1.5 清理 `api/capability_probe.py` 中 `main()` 硬编码密钥；保留模块可被路由 import

## 2. 前端测试页

- [x] 2.1 新建 `web/model-capability-probe.html` 与 `web/css/model-capability-probe.css`（或复用 index 样式变量），含返回应用列表链接
- [x] 2.2 新建 `web/js/model-capability-probe.js`：加载 options、上游/模型下拉、上游/自定义模式切换、发起 POST、探测中禁用按钮
- [x] 2.3 实现 `renderCapabilityReport(report)`：按 dict 渲染中文卡片（四项能力徽章、detail/error/status_code、thinking 子项与汇总）；跳过项与 `print_capability_report` 语义一致
- [x] 2.4 模型选择支持下拉 + 手动输入（`/models` 失败或模型未列出时仍可测）

## 3. 应用列表入口

- [x] 3.1 在 `web/index.html` 应用列表 masthead「对外调用」与「刷新」之间添加「模型能力测试」链接按钮

## 4. 验证

- [x] 4.1 手动验证：上游模式对默认上游某模型探测，报告 UI 正确展示支持/不支持/跳过
- [x] 4.2 手动验证：自定义模式填写 uri/api_key/model 可独立探测；无效 upstream_id 返回 400
