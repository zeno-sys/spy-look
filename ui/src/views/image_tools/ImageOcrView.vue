<template>
  <div class="page-container ocr-page">
    <div class="page-header">
      <div>
        <h3>图片工具 · 图片 OCR</h3>
        <p class="page-sub">本地 PP-OCRv6（CPU）识别 · 上传图片后查看叠加框与完整文本</p>
      </div>
    </div>

    <div class="page-body">
      <el-card class="section-card upload-card">
        <div class="upload-row">
          <el-upload
            class="upload-compact"
            drag
            :auto-upload="false"
            :limit="1"
            accept=".png,.jpg,.jpeg,.webp,.bmp,image/png,image/jpeg,image/webp,image/bmp"
            :on-change="onFileChange"
            :on-remove="onFileRemove"
            :disabled="processing"
          >
            <div class="upload-compact-inner">
              <el-icon class="upload-compact-icon"><UploadFilled /></el-icon>
              <span class="el-upload__text">拖拽或 <em>点击选择</em> 图片</span>
              <span class="el-upload__tip">png / jpg / webp / bmp，≤10 MB</span>
            </div>
          </el-upload>
          <el-button
            type="primary"
            class="start-btn"
            :loading="processing"
            :disabled="!selectedFile || processing"
            @click="startOcr"
          >
            {{ processing ? '识别中...' : '开始识别' }}
          </el-button>
        </div>
      </el-card>

      <template v-if="result">
        <el-card class="section-card result-card" :class="{ 'result-card--collapsed': !previewExpanded }">
          <template #header>
            <div class="card-header">
              <button type="button" class="preview-toggle" @click="previewExpanded = !previewExpanded">
                <el-icon class="preview-toggle-icon" :class="{ expanded: previewExpanded }">
                  <ArrowRight />
                </el-icon>
                <span>
                  识别预览
                  <span class="meta">
                    共 {{ result.count }} 行 · 图像 {{ result.width }}×{{ result.height }}
                  </span>
                </span>
                <span class="preview-toggle-label">{{ previewExpanded ? '收起' : '展开' }}</span>
              </button>
              <div v-show="previewExpanded" class="toolbar">
                <label class="toolbar-item">
                  <el-checkbox v-model="showBoxes" /> 显示框
                </label>
                <label class="toolbar-item">
                  <el-checkbox v-model="showLabels" /> 显示文字
                </label>
                <label class="toolbar-item">
                  透明度
                  <el-slider v-model="opacity" :min="10" :max="100" :show-tooltip="false" class="toolbar-slider" />
                </label>
                <label class="toolbar-item">
                  最低分
                  <el-slider v-model="minScore" :min="50" :max="100" :show-tooltip="false" class="toolbar-slider" />
                  <span class="score-val">{{ (minScore / 100).toFixed(2) }}</span>
                </label>
              </div>
            </div>
          </template>

          <div v-show="previewExpanded" class="preview-grid">
            <section class="panel">
              <div class="panel-title">
                <span>原图 · 文本框</span>
                <span class="panel-title-actions">
                  <span class="hint-inline">点击图片放大 · 点击框联动高亮</span>
                  <el-button size="small" text type="primary" @click="openZoom">放大</el-button>
                </span>
              </div>
              <div class="viewer" title="点击图片放大" @click="openZoom">
                <OcrCanvas
                  :result="result"
                  :items="filteredItems"
                  :active-id="activeId"
                  :show-boxes="showBoxes"
                  :show-labels="showLabels"
                  :opacity="opacity"
                  @select="selectItem"
                />
              </div>
            </section>

            <section class="panel">
              <div class="panel-title">
                <span>识别文本列表</span>
                <span>显示 {{ filteredItems.length }} / {{ result.items.length }}</span>
              </div>
              <div ref="listEl" class="list">
                <div
                  v-for="it in filteredItems"
                  :key="it.id"
                  class="row"
                  :class="{ active: activeId === it.id }"
                  :data-id="it.id"
                  @click="selectItem(it.id)"
                >
                  <div>
                    <div class="name">{{ it.text }}</div>
                    <div class="sub">
                      box=[{{ it.xmin }}, {{ it.ymin }}]–[{{ it.xmax }}, {{ it.ymax }}]
                    </div>
                  </div>
                  <div class="score">{{ it.score.toFixed(3) }}</div>
                </div>
                <div v-if="!filteredItems.length" class="empty-list">当前筛选下无文本行</div>
              </div>
            </section>
          </div>
        </el-card>

        <el-card class="section-card result-card" :class="{ 'result-card--collapsed': !fullTextExpanded }">
          <template #header>
            <div class="card-header">
              <button type="button" class="preview-toggle" @click="fullTextExpanded = !fullTextExpanded">
                <el-icon class="preview-toggle-icon" :class="{ expanded: fullTextExpanded }">
                  <ArrowRight />
                </el-icon>
                <span>识别结果</span>
                <span class="preview-toggle-label">{{ fullTextExpanded ? '收起' : '展开' }}</span>
              </button>
              <div v-show="fullTextExpanded" class="result-actions">
                <el-button size="small" type="primary" :disabled="!fullText" @click="copyFullText">
                  一键复制
                </el-button>
              </div>
            </div>
          </template>
          <div v-show="fullTextExpanded">
            <el-input
              v-model="fullText"
              type="textarea"
              :rows="10"
              placeholder="识别完成后可在此查看、编辑后复制"
            />
            <p v-if="result.count === 0" class="hint-muted" style="margin-top: 8px">
              未识别到文本（或置信度均低于阈值）
            </p>
          </div>
        </el-card>
      </template>
    </div>

    <el-dialog
      v-model="zoomVisible"
      title="原图 · 文本框"
      width="92vw"
      top="4vh"
      append-to-body
      destroy-on-close
      class="ocr-zoom-dialog"
      @closed="onZoomClosed"
    >
      <div class="zoom-toolbar">
        <label class="toolbar-item">
          <el-checkbox v-model="showBoxes" /> 显示框
        </label>
        <label class="toolbar-item">
          <el-checkbox v-model="showLabels" /> 显示文字
        </label>
        <span class="hint-muted">点击文本框可联动右侧列表高亮 · Esc / 点击遮罩关闭</span>
      </div>
      <div v-if="result" class="zoom-viewer">
        <OcrCanvas
          :result="result"
          :items="filteredItems"
          :active-id="activeId"
          :show-boxes="showBoxes"
          :show-labels="showLabels"
          :opacity="opacity"
          enlarge
          @select="selectItem"
        />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { ArrowRight, UploadFilled } from '@element-plus/icons-vue'
import OcrCanvas from './OcrCanvas.vue'
import type { OcrResult } from './OcrCanvas.vue'

const selectedFile = ref<File | null>(null)
const processing = ref(false)
const result = ref<OcrResult | null>(null)
const fullText = ref('')
const showBoxes = ref(true)
const showLabels = ref(true)
const opacity = ref(100)
const minScore = ref(50)
const activeId = ref<number | null>(null)
const listEl = ref<HTMLElement | null>(null)
const zoomVisible = ref(false)
const previewExpanded = ref(true)
const fullTextExpanded = ref(true)

const filteredItems = computed(() => {
  if (!result.value) return []
  const min = minScore.value / 100
  return result.value.items.filter((it) => it.score >= min)
})

function onFileChange(file: UploadFile) {
  selectedFile.value = file.raw ?? null
}

function onFileRemove() {
  selectedFile.value = null
}

function openZoom() {
  if (!result.value) return
  zoomVisible.value = true
}

function onZoomClosed() {
  zoomVisible.value = false
}

function selectItem(id: number) {
  activeId.value = id
  nextTick(() => {
    const row = listEl.value?.querySelector(`.row[data-id="${id}"]`)
    row?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  })
}

async function startOcr() {
  if (!selectedFile.value || processing.value) return
  processing.value = true
  result.value = null
  fullText.value = ''
  activeId.value = null
  try {
    const fd = new FormData()
    fd.append('file', selectedFile.value)
    const res = await fetch('/image-tools/admin/ocr', { method: 'POST', body: fd })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail))
    }
    const data = (await res.json()) as OcrResult
    result.value = data
    fullText.value = data.full_text ?? ''
    previewExpanded.value = true
    fullTextExpanded.value = true
    if (!data.count) {
      ElMessage.info('未识别到文本')
    } else {
      ElMessage.success(`识别完成，共 ${data.count} 行`)
    }
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  } finally {
    processing.value = false
  }
}

async function copyFullText() {
  const text = fullText.value
  if (!text) {
    ElMessage.warning('没有可复制的内容')
    return
  }
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch {
    // fallback
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.left = '-9999px'
    document.body.appendChild(ta)
    ta.select()
    try {
      document.execCommand('copy')
      ElMessage.success('已复制到剪贴板')
    } catch {
      ElMessage.error('复制失败，请手动选择文本复制')
    } finally {
      document.body.removeChild(ta)
    }
  }
}
</script>

<style scoped>
.page-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--sl-text-muted);
}

.upload-card :deep(.el-card__body) {
  padding: 12px 16px;
}

.upload-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 16px;
}

.upload-compact {
  flex: 1 1 280px;
  max-width: 420px;
}

.upload-compact :deep(.el-upload) {
  width: 100%;
}

.upload-compact :deep(.el-upload-dragger) {
  width: 100%;
  padding: 10px 14px;
  height: auto;
}

.upload-compact :deep(.el-upload-list) {
  margin-top: 6px;
}

.upload-compact-inner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 6px 10px;
  line-height: 1.3;
}

.upload-compact-icon {
  font-size: 22px;
  color: var(--sl-text-muted);
}

.upload-compact :deep(.el-upload__text) {
  font-size: 13px;
  margin: 0;
}

.upload-compact :deep(.el-upload__tip) {
  margin: 0;
  font-size: 12px;
  color: var(--sl-text-muted);
}

.start-btn {
  flex-shrink: 0;
}

.hint-muted {
  color: var(--sl-text-muted);
  font-size: 12px;
}

.result-card {
  margin-top: 16px;
}

.result-card--collapsed :deep(.el-card__body) {
  display: none;
  padding: 0;
}

.preview-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  padding: 0;
  margin: 0;
  cursor: pointer;
  color: inherit;
  font: inherit;
  text-align: left;
}

.preview-toggle:hover {
  color: var(--el-color-primary);
}

.preview-toggle-icon {
  transition: transform 0.15s ease;
  font-size: 14px;
}

.preview-toggle-icon.expanded {
  transform: rotate(90deg);
}

.preview-toggle-label {
  margin-left: 4px;
  font-size: 12px;
  color: var(--sl-text-muted);
  font-weight: 400;
}

.section-card + .section-card {
  margin-top: 16px;
}

.card-header {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.meta {
  margin-left: 8px;
  font-size: 12px;
  color: var(--sl-text-muted);
  font-weight: 400;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 16px;
  align-items: center;
}

.toolbar-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--sl-text-muted);
  cursor: default;
}

.toolbar-slider {
  width: 100px;
}

.score-val {
  font-variant-numeric: tabular-nums;
  min-width: 2.5em;
}

.preview-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.85fr);
  gap: 14px;
  min-height: 420px;
}

.panel {
  background: var(--sl-bg-elevated);
  border: 1px solid var(--sl-border);
  border-radius: var(--sl-radius-sm);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
  max-height: 62vh;
}

.panel-title {
  padding: 10px 14px;
  border-bottom: 1px solid var(--sl-border);
  font-size: 13px;
  color: var(--sl-text-muted);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.panel-title-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.hint-inline {
  font-size: 12px;
}

.viewer {
  flex: 1;
  overflow: auto;
  padding: 12px;
  cursor: zoom-in;
  background:
    linear-gradient(45deg, #eceff3 25%, transparent 25%),
    linear-gradient(-45deg, #eceff3 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #eceff3 75%),
    linear-gradient(-45deg, transparent 75%, #eceff3 75%);
  background-size: 20px 20px;
  background-position: 0 0, 0 10px, 10px -10px, -10px 0;
}

.zoom-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 16px;
  align-items: center;
  margin-bottom: 12px;
}

.zoom-viewer {
  overflow: auto;
  max-height: calc(92vh - 140px);
  padding: 12px;
  text-align: center;
  background:
    linear-gradient(45deg, #eceff3 25%, transparent 25%),
    linear-gradient(-45deg, #eceff3 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #eceff3 75%),
    linear-gradient(-45deg, transparent 75%, #eceff3 75%);
  background-size: 20px 20px;
  background-position: 0 0, 0 10px, 10px -10px, -10px 0;
  border-radius: var(--sl-radius-sm);
}

.list {
  flex: 1;
  overflow: auto;
}

.row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  align-items: start;
  padding: 10px 12px;
  border-bottom: 1px solid var(--sl-border);
  cursor: pointer;
}

.row:hover,
.row.active {
  background: #eff6ff;
}

.row .name {
  font-size: 14px;
  font-weight: 600;
  word-break: break-all;
  line-height: 1.35;
}

.row .sub {
  font-size: 12px;
  color: var(--sl-text-muted);
  margin-top: 3px;
}

.row .score {
  font-variant-numeric: tabular-nums;
  font-size: 13px;
  color: var(--el-color-primary);
  font-weight: 650;
  white-space: nowrap;
}

.empty-list {
  padding: 24px;
  text-align: center;
  color: var(--sl-text-muted);
  font-size: 13px;
}

.result-actions {
  display: flex;
  gap: 8px;
}

@media (max-width: 960px) {
  .preview-grid {
    grid-template-columns: 1fr;
  }

  .panel {
    max-height: 420px;
  }
}
</style>
