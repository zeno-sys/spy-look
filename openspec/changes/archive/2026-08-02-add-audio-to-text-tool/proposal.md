## Why

「媒体工具」目前只有视频转文字，本地已有的语音/音频（录音、播客、会议音频等）无法直接转写：用户需先手动把音频封装成 MP4 再走视频转文字流程。音频是更常见的输入形态，需要与视频转文字对称的「音频转文字」入口，复用同一套 ASR / VAD 切分管线。

## What Changes

- 「媒体工具」下新增 **音频转文字**：上传本地音频（MP3 / WAV / M4A / FLAC / AAC / OGG 等）或粘贴音频直链，SSE 流式输出进度，最终返回转写文本。
- 后端复用现有 `voice_to_text` 服务：音频 → WAV → 16kHz 单声道归一化 → VAD 静音切分 → 并行 ASR；新增 `audio_to_text()` 服务函数与 `POST /video-tools/admin/audio-to-text` 端点。
- 前端新增 `AudioToTextView.vue` 页面（上传 / 直链两种输入），并在侧栏「媒体工具」下注册菜单项。
- 转写参数与视频转文字共用「工具配置」（ffmpeg_path / vad / asr），无新增配置项。

## Capabilities

### New Capabilities

- `audio-to-text`：音频转文字 API（上传与直链）、前端页面（进度、结果、复制、提示词版本）、侧栏「媒体工具」入口。

### Modified Capabilities

- `voice-to-text`：`voice_to_text.py` 抽取通用转写流程 `_media_to_text()`，`mp4_to_text` 与新增 `audio_to_text` 共用；`admin.py` 的下载/上传辅助函数参数化文件类型标签。

## Impact

- **后端**：`api/tools/video_tools/services/voice_to_text.py`、`api/tools/video_tools/routes/admin.py`；无新依赖、无数据库迁移。
- **前端**：`ui/src/views/video_tools/AudioToTextView.vue`（新增）、`ui/src/config/tools.ts`、`ui/src/router/index.ts`。
- **非目标**：音频页面链接解析（yt-dlp）、音频流实时转写、多轨/字幕对齐、转写结果入库。
