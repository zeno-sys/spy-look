## Why

图片工具已有 OCR，现有 PP-FormulaNet+ M 单文件 demo 可将公式图识别为 LaTeX，但缺少产品化入口。需要在「图片工具」下增加「公式识别」，便于本地上传公式截图并复制 LaTeX。

## What Changes

- 在图片工具菜单中新增 **公式识别** 页面与路由。
- 将 `test_formula_only.py` 沉淀为可复用服务，模型从仓库根 `models/pp_formulanet_plus_m.onnx` 加载。
- 新增 API：上传图片 → 返回 LaTeX、预览图 data URI。
- 前端：上传、原图预览、LaTeX 结果展示与一键复制；预览/结果区可收起（对齐 OCR 页交互习惯）。
- 补充依赖：`pillow`、`ftfy`、`tokenizers`。

## Capabilities

### New Capabilities

- `formula-recognition`：公式识别 API、前端页面与图片工具菜单入口。

### Modified Capabilities

- （无）`image-ocr` 行为不变；仅在图片工具菜单增加并列入口。

## Impact

- **后端**：`api/tools/image_tools/services/formula.py`、schemas/routes 扩展；`pyproject.toml` 新依赖。
- **前端**：`tools.ts`、router、新页面组件。
- **模型**：`models/pp_formulanet_plus_m.onnx`（已 gitignore）。
- **非目标**：GPU、批量、公式检测裁剪（调用方上传已裁好的公式图）。
