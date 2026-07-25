## Context

Spy-Look 以「工具合集」组织能力：侧栏 `tools.ts` 定义分组，各工具在 `api/tools/<name>/` 挂载 FastAPI 子路由，前端 Vue 页面调用 `/…/admin/…`。图片 OCR 已有可运行的 PP-OCRv6 CPU demo（`test_ocr_only.py`），模型放在仓库根 `models/`，依赖已写入 `pyproject.toml`，但尚未产品化接入。

## Goals / Non-Goals

**Goals:**

- 侧栏与首页出现「图片工具」，其下可进入「图片 OCR」。
- 用户上传常见图片格式后，服务端用本地 ONNX 模型完成检测+识别，返回结构化结果。
- 前端预览对齐 demo `html_output`：原图叠框、列表联动、置信度过滤/透明度等基础控件。
- 额外提供完整识别文本区域与一键复制（全部文本，按阅读顺序换行拼接）。

**Non-Goals:**

- GPU / DirectML 加速、模型热更新、在线下载模型。
- OCR 结果入库、历史记录、批量目录扫描。
- 版面分析、表格结构化、手写专用模型。

## Decisions

1. **服务模块形态**
   - 将 demo 核心（`PPOCRV6CPU`、预处理/后处理）提取为 `api/tools/image_tools/services/ocr.py`（或保留同目录并修正路径），`test_ocr_only.py` 可薄封装调用或保留为 CLI 入口。
   - `MODELS_DIR` 解析为仓库根 `models/`（`api` 的上一级），与现有文件布局一致；不存在时返回明确错误。

2. **模型生命周期**
   - 进程内懒加载单例 `PPOCRV6CPU`，首次请求加载 ONNX；避免每请求重新读模型。
   - OCR 为 CPU 密集型，API 内用 `asyncio.to_thread` 跑推理，避免阻塞事件循环。

3. **API 设计**
   - 前缀：`/image-tools/admin`（与 video/doc 工具一致）。
   - `POST /image-tools/admin/ocr`：`multipart/form-data`，字段 `file`。
   - 响应 JSON：
     - `width` / `height`
     - `image_data_uri`：JPEG data URI（供前端叠框预览，与 demo 一致）
     - `items[]`：`id`, `text`, `score`, `points`, `xmin/ymin/xmax/ymax`, `color`
     - `full_text`：按行拼接的完整文本（`\n` 分隔），便于一键复制
   - 限制：常见图片扩展名（png/jpg/jpeg/webp/bmp）；大小上限约 10MB。

4. **前端页面**
   - 路由：`/image-tools/ocr`；菜单 id：`image-tools`。
   - 布局：左原图+SVG 叠加，右文本列表（参考 `html_output`）；下方或侧栏增加「完整识别结果」只读/可编辑文本框 +「一键复制」。
   - 图标：Element Plus `Picture`（已全局注册）。

5. **错误处理**
   - 模型缺失：HTTP 503/400，中文提示放置路径。
   - 无法解码图片 / 空文件：400。
   - 无文本：200 + 空 `items` 与空 `full_text`，前端提示「未识别到文本」。

## Risks / Trade-offs

- **[Risk] 大图 CPU 推理耗时长** → Mitigation：限制上传体积；前端 loading；后续可加超时提示。
- **[Risk] 模型未随仓库分发** → Mitigation：API 返回清晰缺失提示；文档说明需放入 `models/`。
- **[Risk] data URI 使响应偏大** → Mitigation：JPEG 质量约 92；仅返回一次预览图，不另存磁盘。
- **[Trade-off] 进程内单例模型** → 简化部署；多 worker 时各进程各加载一份（本地单进程场景可接受）。

## Migration Plan

1. 放置模型到 `models/`（若尚未存在）。
2. 部署含新路由与前端构建的版本。
3. 回滚：移除路由注册与菜单项即可，无 DB 迁移。

## Open Questions

- （无阻塞项）后续是否需要可调 `drop_score` 由前端传入——首版使用服务端默认即可。
