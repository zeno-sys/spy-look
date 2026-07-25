## ADDED Requirements

### Requirement: Image tools menu entry
系统 MUST 在侧栏与首页工具列表中提供「图片工具」分组，且该分组 MUST 包含可导航至图片 OCR 页的「图片 OCR」菜单项。

#### Scenario: 从侧栏进入图片 OCR
- **WHEN** 用户打开应用并展开「图片工具」子菜单
- **THEN** 可见「图片 OCR」入口，点击后进入 `/image-tools/ocr` 页面

### Requirement: OCR upload API
系统 MUST 提供 `POST /image-tools/admin/ocr`，接受 `multipart/form-data` 的图片文件字段 `file`，并使用本地 PP-OCRv6 ONNX 模型完成检测与识别；成功响应 MUST 包含图像尺寸、预览用 `image_data_uri`、按阅读顺序排列的文本行 `items`（含文本、置信度与框坐标），以及换行拼接的 `full_text`。

#### Scenario: 上传有效图片成功识别
- **WHEN** 用户上传一张含文字的 PNG/JPEG 图片且模型文件可用
- **THEN** API 返回 200，`items` 非空（若图中有可识别文字），且 `full_text` 为各行文本按顺序以换行符拼接

#### Scenario: 模型文件缺失
- **WHEN** 检测或识别 ONNX 模型不在配置的 `models/` 路径
- **THEN** API MUST 返回错误响应，并提示模型缺失及期望路径

#### Scenario: 不支持的文件类型
- **WHEN** 用户上传非图片或不支持的扩展名
- **THEN** API MUST 返回 400 错误

### Requirement: OCR result preview and copy
图片 OCR 页面 MUST 展示原图叠加文本框预览与文本列表联动（对齐 demo `html_output` 交互），MUST 展示完整识别结果文本，并 MUST 提供一键复制完整结果的能力。

#### Scenario: 叠加框与列表联动
- **WHEN** OCR 成功返回结果
- **THEN** 页面显示原图与文本框叠加，点击框或列表项可高亮对应项

#### Scenario: 一键复制完整文本
- **WHEN** 用户点击「一键复制」（或等价按钮）且存在识别结果
- **THEN** 剪贴板包含完整识别文本（与页面完整结果区域一致）
