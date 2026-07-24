<template>
  <div class="page-container">
    <div class="page-header">
      <div><h3>文档工具 · MD 标题编号</h3></div>
    </div>

    <div class="page-body">
      <el-card class="section-card">
        <el-collapse v-model="configCollapse">
          <el-collapse-item name="config">
            <template #title>
              <div class="collapse-title">
                <span>编号配置（HeadingNumberingConfig）</span>
                <el-button size="small" text type="primary" @click.stop="resetConfig">
                  重置配置
                </el-button>
              </div>
            </template>
            <el-form :model="config" label-position="top" class="form-block">
              <el-row :gutter="16">
                <el-col :xs="24" :sm="8">
                  <el-form-item label="起始级别">
                    <el-input-number
                      v-model="config.start_level"
                      :min="1"
                      :max="6"
                      :disabled="processing"
                      style="width:100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="8">
                  <el-form-item label="结束级别">
                    <el-input-number
                      v-model="config.end_level"
                      :min="config.start_level"
                      :max="6"
                      :disabled="processing"
                      style="width:100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="8">
                  <el-form-item label="移除已有编号">
                    <el-switch v-model="config.strip_existing_number" :disabled="processing" />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-row :gutter="16">
                <el-col :xs="24" :sm="8">
                  <el-form-item label="默认编号风格">
                    <el-select v-model="config.default_style" :disabled="processing" style="width:100%">
                      <el-option
                        v-for="opt in styleOptions"
                        :key="opt.value"
                        :label="opt.label"
                        :value="opt.value"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="8">
                  <el-form-item label="层级分隔符">
                    <el-input v-model="config.level_separator" :disabled="processing" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="8">
                  <el-form-item label="编号后缀">
                    <el-input v-model="config.number_suffix" :disabled="processing" />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-form-item label="标题模板">
                <el-input
                  v-model="config.heading_template"
                  placeholder="{number} {title}"
                  :disabled="processing"
                />
                <p class="hint">模板需包含 &#123;number&#125; 与 &#123;title&#125;，例如「&#123;number&#125; &#123;title&#125;」。</p>
              </el-form-item>

              <el-divider content-position="left">按级别覆盖风格（可选）</el-divider>
              <el-row :gutter="12">
                <el-col v-for="n in 6" :key="'ls'+n" :xs="12" :sm="8" :md="4">
                  <el-form-item :label="'H' + n">
                    <el-select
                      v-model="levelStyleOverrides[n]"
                      clearable
                      placeholder="跟随默认"
                      :disabled="processing"
                      style="width:100%"
                    >
                      <el-option
                        v-for="opt in styleOptions"
                        :key="opt.value"
                        :label="opt.label"
                        :value="opt.value"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
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
          <div class="split-layout">
            <div class="split-pane">
              <div class="pane-label">
                {{ inputMode === 'paste' ? 'Markdown 内容' : '上传文件' }}
              </div>
              <div class="pane-body">
                <el-input
                  v-if="inputMode === 'paste'"
                  v-model="markdownContent"
                  type="textarea"
                  resize="none"
                  placeholder="在此粘贴 Markdown 文本…"
                  :disabled="processing"
                  class="md-textarea"
                />
                <div v-else class="upload-pane">
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
                  <p v-if="selectedFile" class="hint">已加载：{{ selectedFile.name }}</p>
                </div>
              </div>
            </div>

            <div class="split-pane">
              <div class="pane-label pane-label--outline">
                <span>大纲预览</span>
                <span class="outline-count">{{ inputOutline.length }} 个标题</span>
              </div>
              <div class="pane-body outline-panel">
                <el-scrollbar class="outline-scroll">
                  <ul v-if="inputOutline.length" class="outline-list">
                    <li
                      v-for="(item, idx) in inputOutline"
                      :key="'in'+idx"
                      class="outline-item"
                      :class="[
                        `outline-item--h${item.level}`,
                        { 'is-out-of-range': !item.inRange },
                      ]"
                      :style="{ '--outline-depth': item.level - 1 }"
                    >
                      <span class="outline-rail" aria-hidden="true" />
                      <span class="outline-badge">H{{ item.level }}</span>
                      <span class="outline-title" :title="item.title">{{ item.title }}</span>
                    </li>
                  </ul>
                  <div v-else class="outline-empty">
                    <div class="outline-empty-icon" aria-hidden="true">§</div>
                    <p class="outline-empty-title">暂无大纲</p>
                    <p class="outline-empty-desc">粘贴或上传 Markdown 后，标题结构会显示在这里</p>
                  </div>
                </el-scrollbar>
              </div>
            </div>
          </div>
        </div>
      </el-card>

      <div class="action-bar">
        <el-button
          type="primary"
          :loading="processing"
          :disabled="!canStart"
          @click="startNumbering"
        >
          {{ processing ? '处理中...' : '生成编号' }}
        </el-button>
      </div>

      <el-card v-if="resultText !== null" class="section-card" style="margin-top:16px">
        <template #header>
          <div class="card-header">
            <span>编号结果</span>
            <div class="result-actions">
              <el-button size="small" @click="copyResult">复制</el-button>
              <el-button size="small" type="primary" plain @click="downloadResult">下载 .md</el-button>
            </div>
          </div>
        </template>

        <div class="split-layout">
          <div class="split-pane">
            <div class="pane-label">Markdown 结果</div>
            <div class="pane-body">
              <el-input
                v-model="resultText"
                type="textarea"
                resize="none"
                class="md-textarea"
              />
            </div>
          </div>

          <div class="split-pane">
            <div class="pane-label pane-label--outline">
              <span>大纲预览</span>
              <span class="outline-count">{{ resultOutline.length }} 个标题</span>
            </div>
            <div class="pane-body outline-panel">
              <el-scrollbar class="outline-scroll">
                <ul v-if="resultOutline.length" class="outline-list">
                  <li
                    v-for="(item, idx) in resultOutline"
                    :key="'out'+idx"
                    class="outline-item"
                    :class="[
                      `outline-item--h${item.level}`,
                      { 'is-out-of-range': !item.inRange },
                    ]"
                    :style="{ '--outline-depth': item.level - 1 }"
                  >
                    <span class="outline-rail" aria-hidden="true" />
                    <span class="outline-badge">H{{ item.level }}</span>
                    <span class="outline-title" :title="item.title">{{ item.title }}</span>
                  </li>
                </ul>
                <div v-else class="outline-empty">
                  <div class="outline-empty-icon" aria-hidden="true">§</div>
                  <p class="outline-empty-title">结果中暂无标题</p>
                  <p class="outline-empty-desc">生成编号后，标题结构会显示在这里</p>
                </div>
              </el-scrollbar>
            </div>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { apiGet } from '../../composables/useApi'

type NumberingStyle =
  | 'arabic'
  | 'roman'
  | 'roman_lower'
  | 'alpha'
  | 'alpha_lower'
  | 'chinese'

interface HeadingNumberingConfig {
  start_level: number
  end_level: number
  level_separator: string
  number_suffix: string
  heading_template: string
  default_style: NumberingStyle
  level_styles: Record<number, NumberingStyle>
  strip_existing_number: boolean
}

interface OutlineItem {
  level: number
  title: string
  inRange: boolean
}

const HEADING_RE = /^(\s{0,3})(#{1,6})\s+(.+?)\s*$/
const FENCE_RE = /^\s*```/

const styleOptions: { value: NumberingStyle; label: string }[] = [
  { value: 'arabic', label: '阿拉伯数字 1,2,3' },
  { value: 'roman', label: '罗马数字 I,II,III' },
  { value: 'roman_lower', label: '小写罗马 i,ii,iii' },
  { value: 'alpha', label: '字母 A,B,C' },
  { value: 'alpha_lower', label: '小写字母 a,b,c' },
  { value: 'chinese', label: '中文 一,二,三' },
]

const DEFAULT_CONFIG: HeadingNumberingConfig = {
  start_level: 1,
  end_level: 6,
  level_separator: '.',
  number_suffix: '.',
  heading_template: '{number} {title}',
  default_style: 'arabic',
  level_styles: {},
  strip_existing_number: true,
}

const inputMode = ref<'paste' | 'upload'>('paste')
const markdownContent = ref('')
const selectedFile = ref<File | null>(null)
const processing = ref(false)
const resultText = ref<string | null>(null)
const configCollapse = ref<string[]>([])
const config = reactive<HeadingNumberingConfig>(structuredClone(DEFAULT_CONFIG))
const levelStyleOverrides = reactive<Record<number, NumberingStyle | undefined>>({
  1: undefined,
  2: undefined,
  3: undefined,
  4: undefined,
  5: undefined,
  6: undefined,
})

const canStart = computed(() => {
  if (processing.value) return false
  if (inputMode.value === 'upload') return !!selectedFile.value
  return !!markdownContent.value.trim()
})

const numberingRange = computed(() => {
  const start = Math.min(Math.max(config.start_level, 1), 6)
  const end = Math.min(Math.max(config.end_level, start), 6)
  return { start, end }
})

function parseOutline(text: string | null | undefined): OutlineItem[] {
  if (!text?.trim()) return []
  const { start, end } = numberingRange.value
  const items: OutlineItem[] = []
  let inCodeBlock = false

  for (const line of text.split(/\r?\n/)) {
    if (FENCE_RE.test(line)) {
      inCodeBlock = !inCodeBlock
      continue
    }
    if (inCodeBlock) continue

    const match = HEADING_RE.exec(line)
    if (!match) continue
    const level = match[2].length
    const title = match[3].replace(/\s*#+\s*$/, '').trim()
    if (!title) continue
    items.push({
      level,
      title,
      inRange: level >= start && level <= end,
    })
  }
  return items
}

const inputOutline = computed(() => parseOutline(markdownContent.value))
const resultOutline = computed(() => parseOutline(resultText.value))

function applyConfigDefaults(data: HeadingNumberingConfig) {
  Object.assign(config, {
    ...data,
    level_styles: { ...(data.level_styles || {}) },
  })
  for (let n = 1; n <= 6; n++) {
    levelStyleOverrides[n] = data.level_styles?.[n]
  }
}

function resetConfig() {
  applyConfigDefaults(DEFAULT_CONFIG)
  ElMessage.success('已恢复默认编号配置')
}

async function loadDefaults() {
  try {
    const data = await apiGet<HeadingNumberingConfig>('/doc-tools/admin/md-heading-numbering/defaults')
    applyConfigDefaults(data)
    Object.assign(DEFAULT_CONFIG, {
      ...data,
      level_styles: { ...(data.level_styles || {}) },
    })
  } catch {
    // 后端不可用时沿用本地默认值
  }
}

async function onFileChange(file: UploadFile) {
  selectedFile.value = file.raw ?? null
  if (!file.raw) return
  try {
    markdownContent.value = await file.raw.text()
  } catch {
    ElMessage.warning('读取文件内容失败，大纲预览可能为空')
  }
}

function onFileRemove() {
  selectedFile.value = null
  markdownContent.value = ''
}

function currentConfigPayload(): HeadingNumberingConfig {
  const level_styles: Record<number, NumberingStyle> = {}
  for (let n = 1; n <= 6; n++) {
    const style = levelStyleOverrides[n]
    if (style) level_styles[n] = style
  }
  const { start, end } = numberingRange.value
  return {
    start_level: start,
    end_level: end,
    level_separator: config.level_separator,
    number_suffix: config.number_suffix,
    heading_template: config.heading_template.trim() || '{number} {title}',
    default_style: config.default_style,
    level_styles,
    strip_existing_number: config.strip_existing_number,
  }
}

async function startNumbering() {
  processing.value = true
  resultText.value = null
  try {
    const numberingConfig = currentConfigPayload()
    let body: FormData | { markdown_content: string; config: HeadingNumberingConfig }

    if (inputMode.value === 'upload') {
      if (!selectedFile.value) {
        ElMessage.warning('请先选择 Markdown 文件')
        return
      }
      const formData = new FormData()
      formData.append('file', selectedFile.value)
      formData.append('config', JSON.stringify(numberingConfig))
      body = formData
    } else {
      const md = markdownContent.value.trim()
      if (!md) {
        ElMessage.warning('请先粘贴 Markdown 内容')
        return
      }
      body = { markdown_content: md, config: numberingConfig }
    }

    const res = await fetch('/doc-tools/admin/md-heading-numbering', {
      method: 'POST',
      headers: body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
      body: body instanceof FormData ? body : JSON.stringify(body),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      const detail =
        typeof err.detail === 'string'
          ? err.detail
          : err.error?.message || JSON.stringify(err.detail ?? err)
      throw new Error(detail)
    }
    const data = await res.json()
    resultText.value = typeof data.markdown_content === 'string' ? data.markdown_content : ''
    ElMessage.success('标题编号完成')
  } catch (e: any) {
    ElMessage.error(e.message || '处理失败')
  } finally {
    processing.value = false
  }
}

async function copyResult() {
  if (!resultText.value) return
  try {
    await navigator.clipboard.writeText(resultText.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

function downloadResult() {
  if (!resultText.value) return
  const blob = new Blob([resultText.value], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'numbered.md'
  a.click()
  URL.revokeObjectURL(url)
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

.hint {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--el-text-color-secondary);
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

.split-layout {
  --pane-body-height: 380px;
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
  gap: 16px;
  align-items: stretch;
}

.split-pane {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.pane-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 28px;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-regular);
}

.pane-label--outline {
  font-weight: 600;
  color: var(--sl-text);
}

.pane-body {
  height: var(--pane-body-height);
  min-height: var(--pane-body-height);
}

.md-textarea {
  height: 100%;
}

.md-textarea :deep(.el-textarea) {
  height: 100%;
}

.md-textarea :deep(textarea) {
  height: 100% !important;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
  line-height: 1.5;
}

.upload-pane {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 8px;
  border-radius: var(--sl-radius-sm);
  border: 1px solid var(--sl-border);
  background: var(--sl-bg-elevated);
}

.upload-pane :deep(.el-upload) {
  width: 100%;
}

.upload-pane :deep(.el-upload-dragger) {
  width: 100%;
  padding: 24px 12px;
}

.upload-pane :deep(.el-upload-dragger .el-icon--upload) {
  margin-bottom: 6px;
  font-size: 36px;
}

.outline-panel {
  display: flex;
  flex-direction: column;
  padding: 8px;
  border-radius: var(--sl-radius-sm);
  background:
    linear-gradient(165deg, rgba(254, 243, 199, 0.45) 0%, transparent 42%),
    linear-gradient(180deg, #fffef9 0%, #faf6ee 100%);
  border: 1px solid var(--sl-border-strong);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
  box-sizing: border-box;
}

.outline-scroll {
  flex: 1;
  min-height: 0;
  height: 100%;
}

.outline-count {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  color: var(--sl-accent-hover);
  background: var(--sl-accent-subtle);
  border: 1px solid var(--sl-accent-border);
}

.outline-list {
  margin: 0;
  padding: 4px 2px 8px;
  list-style: none;
}

.outline-item {
  --outline-depth: 0;
  --badge-bg: #fef3c7;
  --badge-fg: #92400e;
  --badge-border: rgba(194, 120, 3, 0.22);
  --rail-color: rgba(194, 120, 3, 0.28);

  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 2px 0;
  padding: 7px 10px 7px calc(10px + var(--outline-depth) * 14px);
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.35;
  color: var(--sl-text);
  transition: background 0.15s ease, transform 0.15s ease;
}

.outline-item:hover {
  background: rgba(254, 240, 138, 0.35);
}

.outline-item--h1 {
  --badge-bg: #c27803;
  --badge-fg: #fffef9;
  --badge-border: transparent;
  font-weight: 600;
}

.outline-item--h2 {
  --badge-bg: #fde68a;
  --badge-fg: #92400e;
  --badge-border: rgba(194, 120, 3, 0.2);
  font-weight: 600;
}

.outline-item--h3 {
  --badge-bg: #fef3c7;
  --badge-fg: #a16207;
}

.outline-item--h4,
.outline-item--h5,
.outline-item--h6 {
  --badge-bg: #faf6ee;
  --badge-fg: #78716c;
  --badge-border: var(--sl-border-strong);
  color: var(--sl-text-secondary);
  font-size: 12.5px;
}

.outline-item.is-out-of-range {
  opacity: 0.42;
}

.outline-item.is-out-of-range:hover {
  opacity: 0.7;
}

.outline-rail {
  position: absolute;
  left: calc(8px + var(--outline-depth) * 14px);
  top: 50%;
  width: 8px;
  height: 1px;
  background: var(--rail-color);
  opacity: 0;
}

.outline-item--h2 .outline-rail,
.outline-item--h3 .outline-rail,
.outline-item--h4 .outline-rail,
.outline-item--h5 .outline-rail,
.outline-item--h6 .outline-rail {
  opacity: 1;
}

.outline-badge {
  flex: 0 0 auto;
  min-width: 28px;
  padding: 1px 6px;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-align: center;
  color: var(--badge-fg);
  background: var(--badge-bg);
  border: 1px solid var(--badge-border);
  font-variant-numeric: tabular-nums;
}

.outline-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.outline-empty {
  height: 100%;
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 24px 16px;
  text-align: center;
}

.outline-empty-icon {
  width: 40px;
  height: 40px;
  margin-bottom: 4px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  font-size: 18px;
  font-weight: 700;
  color: var(--sl-accent);
  background: var(--sl-accent-subtle);
  border: 1px solid var(--sl-accent-border);
}

.outline-empty-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--sl-text);
}

.outline-empty-desc {
  margin: 0;
  max-width: 220px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--sl-text-muted);
}

.action-bar {
  margin-top: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.result-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 992px) {
  .split-layout {
    grid-template-columns: 1fr;
  }
}
</style>
