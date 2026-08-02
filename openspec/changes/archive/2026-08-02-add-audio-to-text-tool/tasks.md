# Tasks

- [x] 后端：`voice_to_text.py` 抽取 `_media_to_text()`，新增 `SUPPORTED_AUDIO_SUFFIXES` 与 `audio_to_text()`
- [x] 后端：`admin.py` 参数化下载/上传辅助函数，新增 `_parse_audio_request_input` 与 `POST /audio-to-text` SSE 端点
- [x] 前端：新增 `AudioToTextView.vue`（上传 / 直链 / 进度 / 结果复制）
- [x] 前端：`tools.ts` 增加菜单项，`router/index.ts` 注册路由
- [x] 文档：README 更新媒体工具描述与工具一览
- [x] 构建：`npm run build` 产出 `ui/dist`
