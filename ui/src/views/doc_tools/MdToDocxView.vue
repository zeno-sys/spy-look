<template>
  <div class="page-container">
    <div class="page-header">
      <div><h3>文档工具 · MD 转 DOCX</h3></div>
    </div>

    <div class="page-body">
      <el-card class="section-card">
        <el-collapse v-model="headingCollapse">
          <el-collapse-item name="heading">
            <template #title>
              <div class="collapse-title">
                <span>标题样式（HeadingStyleConfig）</span>
                <el-button
                  size="small"
                  text
                  type="primary"
                  @click.stop="resetHeadingConfig"
                >
                  重置样式
                </el-button>
              </div>
            </template>
            <el-form :model="headingConfig" label-position="top" class="form-block">
              <el-row :gutter="16">
                <el-col :xs="24" :sm="8">
                  <el-form-item label="启用标题编号">
                    <el-switch v-model="headingConfig.numbering_enabled" :disabled="processing" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="8">
                  <el-form-item label="使用 Word 多级列表">
                    <el-switch
                      v-model="headingConfig.use_word_numbering"
                      :disabled="processing || !headingConfig.numbering_enabled"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="8">
                  <el-form-item label="一级标题带尾点">
                    <el-switch
                      v-model="headingConfig.trailing_dot_on_top_level"
                      :disabled="processing || !headingConfig.numbering_enabled"
                    />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-row :gutter="16">
                <el-col :xs="24" :sm="8">
                  <el-form-item label="标题字体">
                    <el-input
                      v-model="headingConfig.font_name"
                      placeholder="黑体"
                      :disabled="processing"
                      clearable
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="8">
                  <el-form-item label="编号最大层级">
                    <el-input-number
                      v-model="headingConfig.max_numbering_level"
                      :min="1"
                      :max="6"
                      :disabled="processing || !headingConfig.numbering_enabled"
                      style="width:100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="4">
                  <el-form-item label="编号分隔符">
                    <el-input
                      v-model="headingConfig.number_separator"
                      :disabled="processing || !headingConfig.numbering_enabled"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="4">
                  <el-form-item label="编号后缀">
                    <el-input
                      v-model="headingConfig.number_suffix"
                      :disabled="processing || !headingConfig.numbering_enabled"
                    />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-divider content-position="left">字号 / 段前 / 段后（h1 → h6，单位 pt）</el-divider>

              <div class="level-grid">
                <div class="level-head" />
                <div v-for="n in 6" :key="'h'+n" class="level-head">H{{ n }}</div>

                <div class="level-label">字号</div>
                <el-input-number
                  v-for="(_, i) in headingConfig.font_sizes_pt"
                  :key="'fs'+i"
                  v-model="headingConfig.font_sizes_pt[i]"
                  :min="8"
                  :max="72"
                  :step="1"
                  :disabled="processing"
                  controls-position="right"
                  size="small"
                />

                <div class="level-label">段前</div>
                <el-input-number
                  v-for="(_, i) in headingConfig.space_before_pt"
                  :key="'sb'+i"
                  v-model="headingConfig.space_before_pt[i]"
                  :min="0"
                  :max="96"
                  :step="1"
                  :disabled="processing"
                  controls-position="right"
                  size="small"
                />

                <div class="level-label">段后</div>
                <el-input-number
                  v-for="(_, i) in headingConfig.space_after_pt"
                  :key="'sa'+i"
                  v-model="headingConfig.space_after_pt[i]"
                  :min="0"
                  :max="96"
                  :step="1"
                  :disabled="processing"
                  controls-position="right"
                  size="small"
                />
              </div>
            </el-form>
          </el-collapse-item>
        </el-collapse>
      </el-card>

      <el-card class="section-card" style="margin-top:16px">
        <template #header><span>输入 Markdown</span></template>
        <el-radio-group v-model="inputMode" :disabled="processing">
          <el-radio-button value="paste">粘贴文本</el-radio-button>
          <el-radio-button value="upload">上传文件</el-radio-button>
        </el-radio-group>

        <div class="input-row">
          <el-form label-position="top" class="form-block">
            <el-form-item label="文档标题">
              <el-input
                v-model="title"
                placeholder="Document"
                :disabled="processing"
                clearable
                maxlength="120"
                show-word-limit
              />
              <p class="hint">用于 Word 文档标题与下载文件名；上传文件时留空则使用文件名。</p>
            </el-form-item>

            <div v-if="inputMode === 'paste'" class="input-area">
              <el-form-item label="Markdown 内容">
                <el-input
                  v-model="markdownContent"
                  type="textarea"
                  :rows="14"
                  placeholder="在此粘贴 Markdown 文本…"
                  :disabled="processing"
                />
              </el-form-item>
            </div>

            <div v-else class="input-area input-area--upload">
              <el-upload
                drag
                :auto-upload="false"
                :limit="1"
                accept=".md,.markdown,.txt,text/markdown,text/plain"
                :on-change="onFileChange"
                :on-remove="onFileRemove"
                :disabled="processing"
              >
                <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                <div class="el-upload__text">拖拽 Markdown 到此处，或 <em>点击选择</em></div>
                <template #tip>
                  <div class="el-upload__tip">支持 .md / .markdown / .txt（UTF-8）</div>
                </template>
              </el-upload>
            </div>
          </el-form>
        </div>
      </el-card>

      <div class="action-bar">
        <el-button
          type="primary"
          :loading="processing"
          :disabled="!canStart"
          @click="startConvert"
        >
          {{ processing ? '转换中...' : '转换为 DOCX' }}
        </el-button>
      </div>

      <el-card v-if="lastFilename" class="section-card" style="margin-top:16px">
        <template #header><span>最近一次结果</span></template>
        <p class="result-line">
          已生成 <code>{{ lastFilename }}</code>
          <el-button size="small" type="primary" link @click="redownload">重新下载</el-button>
        </p>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { apiDownloadPost, apiGet } from '../../composables/useApi'

interface HeadingStyleConfig {
  numbering_enabled: boolean
  use_word_numbering: boolean
  max_numbering_level: number
  number_separator: string
  number_suffix: string
  trailing_dot_on_top_level: boolean
  font_name: string
  font_sizes_pt: number[]
  space_before_pt: number[]
  space_after_pt: number[]
}

const DEFAULT_HEADING: HeadingStyleConfig = {
  numbering_enabled: true,
  use_word_numbering: true,
  max_numbering_level: 6,
  number_separator: '.',
  number_suffix: ' ',
  trailing_dot_on_top_level: true,
  font_name: '黑体',
  font_sizes_pt: [18, 16, 14, 13, 12, 11],
  space_before_pt: [24, 18, 14, 12, 10, 8],
  space_after_pt: [18, 14, 12, 10, 8, 6],
}

const inputMode = ref<'paste' | 'upload'>('paste')
const title = ref('')
const markdownContent = ref('')
const selectedFile = ref<File | null>(null)
const processing = ref(false)
const lastFilename = ref('')
const lastBlob = ref<Blob | null>(null)
const headingCollapse = ref<string[]>([])
const headingConfig = reactive<HeadingStyleConfig>(structuredClone(DEFAULT_HEADING))

const canStart = computed(() => {
  if (processing.value) return false
  if (inputMode.value === 'upload') return !!selectedFile.value
  return !!markdownContent.value.trim()
})

function applyHeadingDefaults(data: HeadingStyleConfig) {
  Object.assign(headingConfig, {
    ...data,
    font_sizes_pt: [...data.font_sizes_pt],
    space_before_pt: [...data.space_before_pt],
    space_after_pt: [...data.space_after_pt],
  })
}

function resetHeadingConfig() {
  applyHeadingDefaults(DEFAULT_HEADING)
  ElMessage.success('已恢复默认标题样式')
}

async function loadDefaults() {
  try {
    const data = await apiGet<HeadingStyleConfig>('/doc-tools/admin/md-to-docx/defaults')
    applyHeadingDefaults(data)
    Object.assign(DEFAULT_HEADING, {
      ...data,
      font_sizes_pt: [...data.font_sizes_pt],
      space_before_pt: [...data.space_before_pt],
      space_after_pt: [...data.space_after_pt],
    })
  } catch {
    // 后端不可用时沿用本地默认值
  }
}

function onFileChange(file: UploadFile) {
  selectedFile.value = file.raw ?? null
  if (!title.value.trim() && file.name) {
    title.value = file.name.replace(/\.(md|markdown|txt)$/i, '')
  }
}

function onFileRemove() {
  selectedFile.value = null
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function currentHeadingPayload(): HeadingStyleConfig {
  return {
    numbering_enabled: headingConfig.numbering_enabled,
    use_word_numbering: headingConfig.use_word_numbering,
    max_numbering_level: headingConfig.max_numbering_level,
    number_separator: headingConfig.number_separator,
    number_suffix: headingConfig.number_suffix,
    trailing_dot_on_top_level: headingConfig.trailing_dot_on_top_level,
    font_name: headingConfig.font_name.trim() || '黑体',
    font_sizes_pt: [...headingConfig.font_sizes_pt],
    space_before_pt: [...headingConfig.space_before_pt],
    space_after_pt: [...headingConfig.space_after_pt],
  }
}

async function startConvert() {
  processing.value = true
  try {
    const heading = currentHeadingPayload()
    let body: FormData | {
      markdown_content: string
      title: string
      heading_config: HeadingStyleConfig
    }
    const fallbackName = `${(title.value.trim() || 'Document').replace(/\s+/g, '_')}.docx`

    if (inputMode.value === 'upload') {
      if (!selectedFile.value) {
        ElMessage.warning('请先选择 Markdown 文件')
        return
      }
      const formData = new FormData()
      formData.append('file', selectedFile.value)
      if (title.value.trim()) {
        formData.append('title', title.value.trim())
      }
      formData.append('heading_config', JSON.stringify(heading))
      body = formData
    } else {
      const md = markdownContent.value.trim()
      if (!md) {
        ElMessage.warning('请先粘贴 Markdown 内容')
        return
      }
      body = {
        markdown_content: md,
        title: title.value.trim() || 'Document',
        heading_config: heading,
      }
    }

    const { blob, filename } = await apiDownloadPost(
      '/doc-tools/admin/md-to-docx',
      body,
      fallbackName,
    )
    lastBlob.value = blob
    lastFilename.value = filename
    triggerDownload(blob, filename)
    ElMessage.success('DOCX 已生成并开始下载')
  } catch (e: any) {
    ElMessage.error(e.message || '转换失败')
  } finally {
    processing.value = false
  }
}

function redownload() {
  if (!lastBlob.value || !lastFilename.value) return
  triggerDownload(lastBlob.value, lastFilename.value)
}

onMounted(() => {
  loadDefaults()
})
</script>

<style scoped>
.input-row {
  margin-top: 12px;
}

.form-block {
  max-width: 960px;
}

.collapse-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding-right: 12px;
  font-weight: 600;
}

.section-card :deep(.el-collapse) {
  border: none;
}

.section-card :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 40px;
  line-height: 1.4;
  border-bottom: none;
  font-size: 14px;
}

.section-card :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}

.section-card :deep(.el-collapse-item__content) {
  padding-bottom: 4px;
}

.hint {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--el-text-color-secondary);
}

.input-area--upload {
  margin-bottom: 8px;
}

.input-area--upload :deep(.el-upload-dragger) {
  padding: 16px 12px;
}

.input-area--upload :deep(.el-upload-dragger .el-icon--upload) {
  margin-bottom: 6px;
  font-size: 36px;
}

.input-area--upload :deep(.el-upload__tip) {
  margin-top: 4px;
}

.level-grid {
  display: grid;
  grid-template-columns: 52px repeat(6, minmax(0, 1fr));
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.level-head {
  font-size: 12px;
  font-weight: 600;
  text-align: center;
  color: var(--el-text-color-secondary);
}

.level-label {
  font-size: 12px;
  color: var(--el-text-color-regular);
}

.level-grid :deep(.el-input-number) {
  width: 100%;
}

.action-bar {
  margin-top: 16px;
}

.result-line {
  margin: 0;
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.result-line code {
  margin: 0 6px;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--el-fill-color-light);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
}

@media (max-width: 768px) {
  .level-grid {
    grid-template-columns: 40px repeat(3, minmax(0, 1fr));
  }
}
</style>
