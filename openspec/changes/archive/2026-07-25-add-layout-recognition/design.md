## Context

PP-DocLayoutV3 ONNX/CPU demo 输出 poly、标签、阅读顺序；`html_output` 提供叠框、序号、虚线路径与列表联动。图片工具 API 前缀与 Vite 代理已就绪。

## Goals / Non-Goals

**Goals:** 菜单入口、懒加载推理、结构化 JSON、Vue 页复现 html_output 核心交互。  
**Non-Goals:** mask/复杂 merge、与 OCR/公式级联、删除 demo。

## Decisions

1. 服务 `layout.py`，模型搜索路径与 OCR 一致。  
2. `POST /image-tools/admin/layout` → `{ width, height, image_data_uri, items, legend, ordered_count, count }`。  
3. 标签颜色用稳定哈希（避免 Python `hash` 随机化）。  
4. 前端：紧凑上传、可收起预览、放大弹层、工具栏开关。

## Risks / Trade-offs

- 大图 CPU 推理较慢 → loading + 10MB 上限。
