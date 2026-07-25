## Why

图片工具已有 OCR 与公式识别；现有 PP-DocLayoutV3 单文件 demo 可检测文档版面区域并输出阅读顺序，但缺少产品化入口。需要在「图片工具」下增加「版面识别」，页面交互对齐 demo 的 `html_output`。

## What Changes

- 菜单新增 **版面识别**（`/image-tools/layout`）。
- 将 `test_layout_only.py` 沉淀为服务，模型从 `models/pp_doclayoutv3.onnx` 加载。
- API：上传图片 → 返回检测框、标签、阅读顺序、预览图。
- 前端：原图叠框 + 阅读顺序序号/连线 + 列表联动 + 图例/筛选/工具栏（对齐 html_output）；支持放大与区块收起。

## Capabilities

### New Capabilities

- `layout-recognition`：版面检测 API、前端页面与菜单入口。

### Modified Capabilities

- （无）

## Impact

- **后端**：`services/layout.py`、schemas/routes。
- **前端**：tools、router、Layout 页面组件。
- **模型**：`models/pp_doclayoutv3.onnx`。
