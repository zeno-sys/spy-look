## 1. 后端

- [x] 1.1 沉淀 `services/formula.py`（模型路径指向仓库根 `models/`，懒加载单例）
- [x] 1.2 扩展 schemas 与 `POST /image-tools/admin/formula`
- [x] 1.3 添加 `pillow` / `ftfy` / `tokenizers` 依赖

## 2. 前端

- [x] 2.1 `tools.ts` 增加「公式识别」菜单；注册路由
- [x] 2.2 实现公式识别页：上传、预览、LaTeX 结果、一键复制、可收起

## 3. 验证

- [x] 3.1 API/导入冒烟通过
