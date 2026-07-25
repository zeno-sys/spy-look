## ADDED Requirements

### Requirement: Layout recognition menu entry
系统 MUST 在「图片工具」中提供「版面识别」菜单项，导航至 `/image-tools/layout`。

#### Scenario: 从侧栏进入
- **WHEN** 用户展开「图片工具」
- **THEN** 可见「版面识别」并进入版面识别页

### Requirement: Layout detection API
系统 MUST 提供 `POST /image-tools/admin/layout`，接受 multipart 图片 `file`，使用本地 PP-DocLayoutV3 模型检测，返回预览图与检测项（含标签、分数、框坐标、阅读顺序）。

#### Scenario: 上传成功
- **WHEN** 用户上传有效文档图且模型可用
- **THEN** API 返回 200，`items` 含检测结果（可为空）

#### Scenario: 模型缺失
- **WHEN** `pp_doclayoutv3.onnx` 不存在
- **THEN** API MUST 返回错误并提示路径

### Requirement: Layout preview interaction
版面识别页 MUST 展示原图叠框、阅读顺序可视化（序号/连线）与列表联动，交互对齐 demo `html_output`。

#### Scenario: 框与列表联动
- **WHEN** 检测成功
- **THEN** 点击框或列表项可高亮对应项
