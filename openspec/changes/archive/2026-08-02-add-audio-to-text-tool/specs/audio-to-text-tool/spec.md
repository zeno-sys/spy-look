# audio-to-text-tool

## ADDED Requirements

### Requirement: 音频转文字上传转写

后端 MUST 提供 `POST /video-tools/admin/audio-to-text`，接受 `multipart/form-data` 的 `file` 字段（MP3 / WAV / M4A / FLAC / AAC / OGG / OPUS / WMA / AIFF / AMR / MKA），转写结果 MUST 以 SSE 流式返回。

#### Scenario: 上传 MP3 转写

WHEN 用户上传一个合法的 MP3 文件
THEN 服务端返回 `progress` 事件直至 `done`，`done` 的 `text` 字段为转写文本

### Requirement: 音频直链转写

后端 MUST 支持 `application/json` 请求体 `{"url": "...", "url_type": "direct"}`，自动下载音频后转写。

#### Scenario: 直链转写

WHEN 用户提交一个可访问的音频直链
THEN 服务端下载成功后执行转写并以 SSE 返回结果；下载失败时返回 `error` 事件

### Requirement: 格式与大小限制

后端 MUST 拒绝非音频扩展名的上传文件，并 SHALL 对下载/上传文件执行大小上限校验（默认 500MB）。

#### Scenario: 非法格式

WHEN 用户上传 `.txt` 文件
THEN 服务端返回 `error` 事件，提示仅支持音频格式

### Requirement: 前端入口与页面

前端 MUST 在「媒体工具」侧栏提供「音频转文字」菜单项，页面 MUST 提供上传与直链两种输入方式，并 MUST 展示 SSE 进度与转写结果（含复制与提示词版本按钮）。

#### Scenario: 菜单进入

WHEN 用户点击「媒体工具 → 音频转文字」
THEN 打开 `/video-tools/audio-to-text` 页面并可发起转写
