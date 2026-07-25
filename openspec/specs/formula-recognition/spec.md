# formula-recognition Specification

## Purpose
图片工具下的公式识别：本地 PP-FormulaNet+ M 将公式图识别为 LaTeX，提供上传 API、预览与一键复制。

## Requirements

### Requirement: Formula recognition menu entry
系统 MUST 在「图片工具」分组中提供「公式识别」菜单项，导航至 `/image-tools/formula`。

#### Scenario: 从侧栏进入公式识别
- **WHEN** 用户展开「图片工具」子菜单
- **THEN** 可见「公式识别」，点击后进入公式识别页

### Requirement: Formula recognition API
系统 MUST 提供 `POST /image-tools/admin/formula`，接受 multipart 图片字段 `file`，使用本地 PP-FormulaNet+ M ONNX 模型识别，并返回 `latex` 与预览用 `image_data_uri`。

#### Scenario: 上传公式图成功识别
- **WHEN** 用户上传有效公式图片且模型可用
- **THEN** API 返回 200 且 `latex` 为识别出的 LaTeX 字符串

#### Scenario: 模型缺失
- **WHEN** `pp_formulanet_plus_m.onnx` 不在期望目录
- **THEN** API MUST 返回错误并提示模型路径

### Requirement: Formula result display and copy
公式识别页 MUST 展示上传图预览与可编辑的 LaTeX 结果，并 MUST 提供一键复制 LaTeX。

#### Scenario: 一键复制
- **WHEN** 用户点击一键复制且存在 LaTeX
- **THEN** 剪贴板包含当前结果文本
