<template>
  <div class="page-container">
    <div class="page-header">
      <div><h3>视频工具 · 语音转文字</h3></div>
      <div class="header-actions">
        <el-button @click="goToConfig">工具配置</el-button>
      </div>
    </div>

    <div class="page-body">
      <el-card class="section-card">
        <template #header><span>输入视频</span></template>
        <el-radio-group v-model="inputMode" :disabled="processing">
          <el-radio-button value="upload">上传文件</el-radio-button>
          <el-radio-button value="url">视频链接</el-radio-button>
        </el-radio-group>

        <el-row :gutter="16" class="input-row">
          <el-col :xs="24" :md="16">
            <div v-if="inputMode === 'upload'" class="input-area">
              <el-upload
                drag
                :auto-upload="false"
                :limit="1"
                accept=".mp4,video/mp4"
                :on-change="onFileChange"
                :on-remove="onFileRemove"
                :disabled="processing"
              >
                <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                <div class="el-upload__text">拖拽 MP4 到此处，或 <em>点击选择</em></div>
                <template #tip>
                  <div class="el-upload__tip">仅支持 .mp4 格式</div>
                </template>
              </el-upload>
            </div>

            <div v-else class="input-area">
              <el-input
                v-model="videoUrl"
                placeholder="https://example.com/video.mp4"
                :disabled="processing"
                clearable
              />
              <p class="hint">粘贴 MP4 直链，非哔哩哔哩/抖音等网页分享链接。</p>
            </div>

            <el-button
              type="primary"
              class="start-btn"
              :loading="processing"
              :disabled="!canStart"
              @click="startTranscribe"
            >
              {{ processing ? '转写中...' : '开始转写' }}
            </el-button>
          </el-col>

          <el-col :xs="24" :md="8">
            <div class="side-panel">
              <div class="side-panel-title">在线视频解析</div>
              <p class="hint">
                从哔哩哔哩、抖音等平台提取 MP4 下载地址或下载下来，再粘贴或上传到左侧使用本工具转写。
              </p>
              <ul class="tool-links">
                <li>
                  <a href="https://greenvideo.cc/" target="_blank" rel="noopener noreferrer">GreenVideo</a>
                  <span class="tool-desc">多平台解析下载</span>
                </li>
                <li>
                  <a href="https://peanutdl.com/zh" target="_blank" rel="noopener noreferrer">PeanutDL</a>
                  <span class="tool-desc">在线视频解析下载</span>
                </li>
              </ul>
            </div>
          </el-col>
        </el-row>
      </el-card>

      <el-card class="section-card" style="margin-top:16px">
        <template #header><span>处理进度</span></template>
        <el-scrollbar max-height="240px">
          <pre class="log-panel">{{ progressLog || '等待开始...' }}</pre>
        </el-scrollbar>
      </el-card>

      <el-card v-if="resultText !== null" class="section-card" style="margin-top:16px">
        <template #header>
          <div class="card-header">
            <span>识别结果</span>
            <div class="result-actions">
              <el-button size="small" @click="copyResult">复制</el-button>
              <el-button size="small" type="primary" plain @click="copyPromptVersion">
                复制提示词版本
              </el-button>
            </div>
          </div>
        </template>
        <el-input v-model="resultText" type="textarea" :rows="12" readonly />
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { apiGet, apiStreamPost } from '../../composables/useApi'

const router = useRouter()

const inputMode = ref<'upload' | 'url'>('upload')
const selectedFile = ref<File | null>(null)
const videoUrl = ref('')
const processing = ref(false)
const progressLog = ref('')
const resultText = ref<string | null>(null)

const canStart = computed(() => {
  if (processing.value) return false
  if (inputMode.value === 'upload') return !!selectedFile.value
  return !!videoUrl.value.trim()
})

function onFileChange(file: UploadFile) {
  selectedFile.value = file.raw ?? null
}

function onFileRemove() {
  selectedFile.value = null
}

function appendLog(line: string) {
  progressLog.value = progressLog.value ? `${progressLog.value}\n${line}` : line
}

function goToConfig() {
  router.push({ name: 'videoToolsConfig' })
}

function collectMissingConfig(data: Record<string, any>): string[] {
  const missing: string[] = []
  if (!String(data.ffmpeg_path ?? '').trim()) missing.push('FFmpeg 路径')
  if (!String(data.asr?.base_url ?? '').trim()) missing.push('ASR Base URL')
  if (!String(data.asr?.api_key ?? '').trim()) missing.push('ASR API Key')
  if (!String(data.asr?.model ?? '').trim()) missing.push('ASR 模型')
  return missing
}

async function ensureConfigReady(): Promise<boolean> {
  try {
    const data = await apiGet('/video-tools/admin/config')
    const missing = collectMissingConfig(data)
    if (missing.length === 0) return true

    try {
      await ElMessageBox.confirm(
        `请先完成工具配置后再转写。\n\n缺少：${missing.join('、')}`,
        '未完成配置',
        {
          type: 'warning',
          confirmButtonText: '去配置',
          cancelButtonText: '取消',
        },
      )
      goToConfig()
    } catch {
      // 用户取消
    }
    return false
  } catch (e: any) {
    ElMessage.error(e.message || '读取配置失败')
    return false
  }
}

async function startTranscribe() {
  if (!(await ensureConfigReady())) return

  processing.value = true
  progressLog.value = ''
  resultText.value = null

  try {
    let body: FormData | { url: string }
    if (inputMode.value === 'upload') {
      if (!selectedFile.value) {
        ElMessage.warning('请先选择 MP4 文件')
        return
      }
      const formData = new FormData()
      formData.append('file', selectedFile.value)
      body = formData
    } else {
      body = { url: videoUrl.value.trim() }
    }

    await apiStreamPost('/video-tools/admin/voice-to-text', body, (event, data) => {
      if (event === 'progress' && typeof data.message === 'string') {
        appendLog(data.message)
      } else if (event === 'done' && typeof data.text === 'string') {
        resultText.value = data.text
        appendLog('转写完成')
        ElMessage.success('语音转文字完成')
      } else if (event === 'error') {
        const detail = typeof data.detail === 'string' ? data.detail : '转写失败'
        appendLog(`错误: ${detail}`)
        ElMessage.error(detail)
      }
    })
  } catch (e: any) {
    appendLog(`错误: ${e.message || '请求失败'}`)
    ElMessage.error(e.message || '请求失败')
  } finally {
    processing.value = false
  }
}

async function copyToClipboard(text: string, successMsg: string) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success(successMsg)
  } catch {
    ElMessage.error('复制失败')
  }
}

function buildNotesPrompt(transcript: string): string {
  return `以下是一段视频的语音转写文本。请根据内容生成一份详细、结构化的学习笔记，可直接用于复习与查阅。

要求：
1. 提炼核心观点、关键结论与重要定义
2. 按主题分章节整理，使用清晰的小标题（Markdown 格式）
3. 对口语化表达进行书面化整理，补全必要上下文
4. 如有步骤、方法或建议，单独列出「要点清单」或「行动项」
5. 在文末用 3～5 条一句话总结全文

---

【转写文本】

${transcript.trim()}

---

请开始生成笔记。`
}

async function copyResult() {
  if (!resultText.value) return
  await copyToClipboard(resultText.value, '已复制到剪贴板')
}

async function copyPromptVersion() {
  if (!resultText.value) return
  await copyToClipboard(buildNotesPrompt(resultText.value), '已复制提示词版本，可粘贴到在线大模型生成笔记')
}
</script>

<style scoped>
.input-row {
  margin-top: 16px;
}

.input-area {
  min-height: 180px;
}

.start-btn {
  margin-top: 16px;
}

.side-panel {
  height: 100%;
  min-height: 180px;
  padding: 14px 16px;
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color-lighter);
}

.side-panel-title {
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.hint {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}

.tool-links {
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
  font-size: 13px;
  line-height: 1.8;
}

.tool-links li + li {
  margin-top: 8px;
}

.tool-links a {
  color: var(--el-color-primary);
  text-decoration: none;
  font-weight: 500;
}

.tool-links a:hover {
  text-decoration: underline;
}

.tool-desc {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

@media (max-width: 992px) {
  .side-panel {
    margin-top: 16px;
    min-height: auto;
  }
}

.result-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.log-panel {
  margin: 0;
  padding: 8px 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--el-text-color-regular);
}
</style>
