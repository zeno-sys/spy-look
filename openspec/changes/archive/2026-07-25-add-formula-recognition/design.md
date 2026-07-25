## Context

公式识别 demo 使用 PP-FormulaNet+ M（ONNX/CPU）+ tokenizers + PIL + ftfy，输出 LaTeX。图片工具已有 OCR 的上传/API/页面模式，可复用同一 `/image-tools/admin` 前缀与 Vite 代理。

## Goals / Non-Goals

**Goals:**

- 菜单「图片工具 → 公式识别」。
- 上传公式图，返回可编辑/可复制的 LaTeX，并展示原图预览。
- 模型懒加载单例，`asyncio.to_thread` 推理。

**Non-Goals:**

- 从整页自动检测公式框（输入假定为公式区域图）。
- KaTeX 渲染（首版以 LaTeX 文本为主；后续可加）。
- 删除 demo 文件（实现后可另删）。

## Decisions

1. **服务**：`services/formula.py`，模型搜索路径与 OCR 一致（优先仓库根 `models/`）。
2. **API**：`POST /image-tools/admin/formula`，multipart `file`；响应 `{ latex, image_data_uri, width, height }`。
3. **前端**：紧凑上传区 + 可收起原图预览 + 可收起 LaTeX 结果与一键复制。
4. **依赖**：`pillow`、`ftfy`、`tokenizers`。

## Risks / Trade-offs

- **[Risk] 整页图识别效果差** → Mitigation：页面提示建议上传公式裁剪图。
- **[Risk] 模型较大、首次加载慢** → Mitigation：懒加载 + loading 状态。
