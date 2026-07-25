## 1. 后端 OCR 服务

- [x] 1.1 将 demo 核心逻辑沉淀为 `api/tools/image_tools/services/ocr.py`，`MODELS_DIR` 指向仓库根 `models/`
- [x] 1.2 提供懒加载单例与 `ocr_image_bytes` / 结构化结果组装（含 `full_text`、`image_data_uri`）
- [x] 1.3 新增 schemas、routes（`POST /image-tools/admin/ocr`）、router，并在 `main.py` 注册

## 2. 前端图片工具入口与 OCR 页

- [x] 2.1 在 `tools.ts` 增加「图片工具」分组与「图片 OCR」菜单项
- [x] 2.2 注册路由 `/image-tools/ocr`
- [x] 2.3 实现 OCR 页面：上传、叠框预览+列表联动、完整结果展示、一键复制

## 3. 收尾

- [x] 3.1 侧栏 `default-openeds` 包含 `image-tools`（如需要）
- [x] 3.2 冒烟：上传样例图可识别，复制完整文本可用
