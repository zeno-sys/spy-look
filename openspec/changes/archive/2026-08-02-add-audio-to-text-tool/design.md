## Context

Spy-Look「媒体工具」现有视频转文字：页面链接（yt-dlp）/ 上传 MP4 / MP4 直链 → MP4 → WAV → 归一化 → VAD 切分 → 并行 ASR（硅基流动 `/audio/transcriptions`）。音频输入尚无独立入口。

## Goals / Non-Goals

**Goals:**

- 侧栏「媒体工具」下出现「音频转文字」，上传常见音频格式或粘贴音频直链即可转写。
- 复用现有 ASR / VAD / 归一化管线与「工具配置」，不新增配置项。
- 与视频转文字一致的 SSE 进度体验与结果复制能力。

**Non-Goals:**

- 页面链接解析（音频无平台页面）、实时流式转写、说话人分离、结果入库。

## Decisions

1. **服务层复用与抽象**
   - `voice_to_text.py` 抽取私有通用函数 `_media_to_text(media_path, allowed_suffixes, type_label, ...)`，承担「文件校验 → WAV → 归一化 → long_audio_to_text」公共流程。
   - `mp4_to_text()` 与新增 `audio_to_text()` 均委托 `_media_to_text`；`audio_to_text` 校验 `SUPPORTED_AUDIO_SUFFIXES`（mp3/wav/m4a/flac/aac/ogg/opus/wma/aiff/amr/mka）。
   - WAV 提取继续使用 moviepy `AudioFileClip`（底层 ffmpeg），对纯音频文件同样适用。

2. **API 设计**
   - `POST /video-tools/admin/audio-to-text`：`multipart/form-data`（字段 `file`，音频格式）或 `application/json`（`{"url": "...", "url_type": "direct"}`）。
   - 响应与视频转文字一致：SSE 流式 `progress` / `done {text}` / `error {detail}`。
   - 下载/上传辅助函数 `_download_video_url` / `_save_upload_file` 增加 `type_label`、`allowed_exts` 参数，默认值保持原视频行为不变。

3. **前端页面**
   - `AudioToTextView.vue`：输入方式为「上传文件 / 音频链接」，去掉视频专有的「页面链接」模式；上传 accept 覆盖常见音频格式。
   - 路由 `/video-tools/audio-to-text`，菜单项「音频转文字」；配置检查、进度面板、结果复制 / 提示词版本与视频页保持一致。

## Risks / Trade-offs

- **[Risk] 个别音频格式解码失败** → Mitigation：错误经 SSE 原样返回，提示用户转用 WAV/MP3。
- **[Trade-off] 不解析音频平台页面链接** → 保持范围收敛；用户可先下载音频再上传。
- **[Trade-off] 与视频转文字共用 ASR 配置** → 参数改动对两者同时生效，符合预期。

## Migration Plan

1. 部署含新路由与前端构建的版本即可，无数据库迁移。
2. 回滚：移除菜单项、路由与 `/audio-to-text` 端点即可。

## Open Questions

- （无阻塞项）后续如需差异化 ASR 参数，可在 `VideoToolsConfig` 中增加 `audio` 子配置。
