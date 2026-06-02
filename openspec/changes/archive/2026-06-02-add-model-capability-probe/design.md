## Context

Spy-Look 为本地 OpenAI 兼容网关，观测页（`/`）提供应用 → 会话 → 日志三级导航；上游配置在 `/upstream-config`，已有 `POST /admin/upstreams/test` 仅验证 GET `/models` 连通性。

`api/capability_probe.py` 已实现 `probe_model_capabilities(uri, api_key, model)`，依次探测：

| 键 | 含义 |
|----|------|
| `chat_completion` | 基础对话 |
| `tool_calling` | 工具调用 |
| `json_mode` | Pydantic 等价结构化输出 |
| `thinking` | 开/关 thinking 参数的行为 |

另有 `print_capability_report()` 供 CLI 彩色输出，**不适用于 Web**。用户要求在 Web 上将返回 dict **解析并美观展示**。

应用列表 masthead 现有按钮顺序：上游配置 → 对外调用 → 刷新；需在「对外调用」与「刷新」之间插入「模型能力测试」。

## Goals / Non-Goals

**Goals:**

- 提供独立测试页与后端 API，复用 `probe_model_capabilities`，不重复探测逻辑。
- 支持两种输入模式：**选择已启用上游 + 模型名**，或 **自定义 uri / api_key / model**。
- 前端将探测 dict 渲染为中文卡片报告（支持/不支持/已跳过、说明、错误、HTTP 状态、thinking 子探测等）。
- 入口位于应用列表页 masthead，按钮文案「模型能力测试」。

**Non-Goals:**

- 探测结果入库、历史记录、定时批量探测。
- 管理 API / 测试页鉴权（与现有 `/admin/*`、观测页一致，依赖本机信任边界）。
- 修改网关转发或上游 failover 行为。
- 在 CLI 之外复用 ANSI 终端着色函数。

## Decisions

### 1. 独立页面 vs 模态框

**决策**：新建 `/model-capability-probe` 独立 HTML 页（与 `/upstream-config` 同级），应用列表按钮为 `<a href="/model-capability-probe">`。

**理由**：探测耗时长（多轮 HTTP，默认 timeout 120s），独立页可容纳表单、进度与完整报告，避免模态框滚动与超时体验差。

**备选**：Modal — 实现快但 UX  cramped，放弃。

### 2. API 设计

**决策**：

| 方法 | 路径 | 作用 |
|------|------|------|
| `GET` | `/admin/model-capability-probe/options` | 返回 `{ upstreams: [...], models_by_upstream: { "<id>": ["model-id", ...] } }`；上游仅含 `enabled=1` 条目，含 `id`、`name`、`base_url`（masked key 不回传）；模型列表通过各上游 GET `/models` 拉取，失败则该 id 对应空数组 |
| `POST` | `/admin/model-capability-probe` | 执行探测，body 二选一：`{ mode: "upstream", upstream_id, model }` 或 `{ mode: "custom", uri, api_key, model }`；可选 `timeout`、`max_tokens`；响应为 `probe_model_capabilities` 的 dict，并附加 `total_elapsed_ms` |

**理由**：与现有 `/admin/upstreams/test` 风格一致；options 与 probe 分离，页面加载快、模型列表可懒加载。

**实现细节**：

- `upstream` 模式用 `get_upstream_runtime(upstream_id)` 取完整 `base_url`、`api_key`；未找到或未启用 → 400。
- `custom` 模式校验非空 `uri`、`api_key`、`model`。
- 探测在 **同步** 函数中执行（`probe_model_capabilities` 使用 `httpx.Client`）；FastAPI 路由用 `async def` 但内部 `await asyncio.to_thread(probe_model_capabilities, ...)` 避免阻塞事件循环。
- 在 `probe_model_capabilities` 返回前由路由层记录 `total_elapsed_ms`（或在 probe 内追加，二选一，实现时保持单一来源）。

### 3. 前端报告渲染

**决策**：在 `web/js/model-capability-probe.js` 实现 `renderCapabilityReport(report)`，逻辑对齐 `print_capability_report` 的字段映射，但输出 DOM：

- 顶栏：uri、endpoint、model、总耗时。
- 四项能力卡片：`chat_completion`、`tool_calling`、`json_mode`、`thinking`。
- 徽章：`支持`（绿）/ `不支持`（红）/ `已跳过`（黄，detail 含「跳过」）。
- 字段展示：`detail`、`error`（截断）、`status_code`、`elapsed_ms`（若后续 probe 添加）、`finish_reason`、`parsed`（`<pre>` JSON）、`content_preview`、`mode_label`、`summary`、`enabled`/`disabled` 子项。
- 底部汇总：`supported_count / tested_count`。

**标签映射**：在 JS 内维护与 `_CAPABILITY_LABELS`、`_THINKING_MODE_LABELS` 相同的中文映射（或后端 GET options 附带 `labels` 常量，减少重复 — 优先 **JS 常量**，与 probe 变更解耦）。

**理由**：用户明确要求 dict 美观展示；Web 不能用 ANSI。复用 probe 的 dict 结构，前端只做 presentation。

### 4. 上游与模型下拉

**决策**：

- 默认 **上游模式**；切换至 **自定义模式** 时显示 uri / api_key / model 文本框。
- 上游下拉：options API 的 `upstreams`；变更时刷新模型下拉（`models_by_upstream[upstream_id]`）。
- 模型下拉允许 **手动输入**（`<input list="...">` 或 select + 「其他」输入框），因 `/models` 可能失败或模型未列出。

### 5. 入口位置

**决策**：仅 **应用列表**（`viewApps`）masthead 增加按钮；会话/日志页 masthead **不**加（proposal 明确「应用列表页面」）。

按钮 HTML 插入于「对外调用」与「刷新」之间：

```html
<a class="ghost-btn action-btn" href="/model-capability-probe">模型能力测试</a>
```

### 6. 清理 probe 模块

**决策**：删除或清空 `capability_probe.main()` 中硬编码的 `api_key` 与默认 URI；`if __name__ == "__main__"` 可保留为从环境变量读取的 CLI 入口（可选，非阻塞）。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 单次探测多轮 HTTP，请求可能 30s–数分钟 | 前端按钮禁用 + 「探测中…」；POST timeout 与 probe `timeout` 一致；文档说明 |
| options 拉取各上游 `/models` 慢 | 并行请求；失败上游返回空模型列表，不阻塞页面 |
| 自定义模式在页面输入 api_key | 与上游配置页一致，仅本机管理；不在响应中回显 key |
| 探测消耗上游配额 | 非目标持久化；按钮旁简短提示「将发起真实 Chat 请求」 |
| JS 与 Python 标签映射重复 | 变更 probe 字段时同步更新 JS 常量（tasks 中注明） |

## Migration Plan

1. 部署后端路由 + 静态页，无数据库迁移。
2. 回滚：移除路由与静态资源即可，无数据副作用。

## Open Questions

- （无阻塞项）是否在 probe 各子项写入 `elapsed_ms`：建议在实现阶段于 `_test_*` 返回中追加，便于 UI 展示单项耗时（tasks 可选子任务）。
