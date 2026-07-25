## Why

项目已有基于 PP-OCRv6（ONNX / CPU）的图片 OCR 单文件 demo，以及 `models/` 下的检测/识别模型，但缺少产品化入口：侧栏无「图片工具」菜单，也没有可上传图片、预览叠加框并复制全文的 Web 页面。现在需要把 demo 接入 Spy-Look 工具合集，让本地即可完成图片文字识别。

## What Changes

- 新增工具分组 **图片工具**（侧栏子菜单 + 首页卡片），首个能力为 **图片 OCR**。
- 将 `test_ocr_only.py` 中的 OCR 推理逻辑沉淀为可复用服务模块，模型从仓库根目录 `models/` 加载。
- 新增后端 API：上传图片 → 返回 OCR 结构化结果（文本行、置信度、框坐标）及预览用图像数据。
- 新增前端 OCR 页：交互与 demo 的 `html_output` 对齐（原图叠框 + 列表联动高亮），并增加 **识别结果完整展示** 与 **一键复制**。

## Capabilities

### New Capabilities

- `image-ocr`：图片 OCR 上传识别 API、前端页面（叠加框预览、文本列表、完整结果与一键复制）、侧栏「图片工具」入口。

### Modified Capabilities

- （无）

## Impact

- **后端**：新增 `api/tools/image_tools/`（router、routes、schemas、services）；`api/main.py` 注册路由；依赖已在 `pyproject.toml`（onnxruntime / opencv / pyclipper / shapely）。
- **前端**：`ui/src/config/tools.ts` 增加工具定义；`router`、OCR 页面组件。
- **模型**：使用仓库根 `models/ch_PP-OCRv6_det_small.onnx` 与 `ch_PP-OCRv6_rec_small.onnx`（`.gitignore` 已忽略，需本地放置）。
- **非目标**：GPU 推理、批量文件夹识别、结果持久化入库、在线模型下载。
