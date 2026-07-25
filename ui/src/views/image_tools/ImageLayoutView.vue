<template>
  <div class="page-container layout-page">
    <div class="page-header">
      <div>
        <h3>图片工具 · 版面识别</h3>
        <p class="page-sub">本地 PP-DocLayoutV3（CPU）· 检测区域叠框与逻辑阅读顺序</p>
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
              <span class="el-upload__text">拖拽或 <em>点击选择</em> 文档图</span>
              <span class="el-upload__tip">png / jpg / webp / bmp，≤10 MB</span>
            </div>
          </el-upload>
          <el-button
            type="primary"
            class="start-btn"
            :loading="processing"
            :disabled="!selectedFile || processing"
            @click="startLayout"
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
                    共 {{ result.count }} 个框 · 阅读顺序 {{ result.ordered_count }} 步 ·
                    {{ result.width }}×{{ result.height }}
                  </span>
                </span>
                <span class="preview-toggle-label">{{ previewExpanded ? '收起' : '展开' }}</span>
              </button>
              <div v-show="previewExpanded" class="toolbar">
                <label class="toolbar-item"><el-checkbox v-model="onlyOrdered" /> 仅看有序块</label>
                <label class="toolbar-item">
                  透明度
                  <el-slider v-model="opacity" :min="10" :max="100" :show-tooltip="false" class="toolbar-slider" />
                </label>
                <label class="toolbar-item">
                  筛选
                  <el-select v-model="filterLabel" clearable placeholder="全部" style="width: 120px">
                    <el-option
                      v-for="lg in result.legend"
                      :key="lg.label"
                      :label="lg.label_zh"
                      :value="lg.label"
                    />
                  </el-select>
                </label>
              </div>
            </div>
          </template>

          <div v-show="previewExpanded" class="preview-grid">
            <section class="panel">
              <div class="panel-title panel-title--wrap">
                <span>原图 · 检测框 · 逻辑阅读顺序</span>
                <div class="panel-title-actions">
                  <label class="toolbar-item"><el-checkbox v-model="showBoxes" /> 显示框</label>
                  <label class="toolbar-item"><el-checkbox v-model="showLabels" /> 显示标签</label>
                  <label class="toolbar-item"><el-checkbox v-model="showOrder" /> 阅读顺序序号</label>
                  <label class="toolbar-item"><el-checkbox v-model="showPath" /> 阅读顺序连线</label>
                </div>
              </div>
              <div class="viewer">
                <LayoutCanvas
                  :result="result"
                  :items="filteredItems"
                  :ordered-path="orderedPath"
                  :active-id="activeId"
                  :show-boxes="showBoxes"
                  :show-labels="showLabels"
                  :show-order="showOrder"
                  :show-path="showPath"
                  :opacity="opacity"
                  @select="selectItem"
                />
              </div>
            </section>

            <section class="panel">
              <div class="panel-title">
                <span>按阅读顺序排列</span>
                <span>显示 {{ filteredItems.length }} / {{ result.items.length }} · 有序 {{ orderedPath.length }}</span>
              </div>
              <div class="legend">
                <span v-for="lg in result.legend" :key="lg.label">
                  <i :style="{ background: lg.color }" />{{ lg.label_zh }}
                </span>
              </div>
              <div ref="listEl" class="list">
                <div
                  v-for="it in filteredItems"
                  :key="it.id"
                  class="row"
                  :class="{ active: activeId === it.id, unordered: it.reading_order == null }"
                  :data-id="it.id"
                  @click="selectItem(it.id)"
                >
                  <div class="ord" :class="{ none: it.reading_order == null }">
                    {{ it.reading_order != null ? it.reading_order : '—' }}
                  </div>
                  <div>
                    <div class="name">{{ it.label_zh }}</div>
                    <div class="sub">
                      {{ it.label }} · 模型序={{ it.model_order }} · score={{ it.score.toFixed(3) }}
                    </div>
                  </div>
                  <div class="score">{{ it.reading_order != null ? 'R' + it.reading_order : '无序' }}</div>
                </div>
                <div v-if="!filteredItems.length" class="empty-list">当前筛选下无区域</div>
              </div>
            </section>
          </div>
        </el-card>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { ArrowRight, UploadFilled } from '@element-plus/icons-vue'
import LayoutCanvas from './LayoutCanvas.vue'
import type { LayoutResult } from './LayoutCanvas.vue'

const selectedFile = ref<File | null>(null)
const processing = ref(false)
const result = ref<LayoutResult | null>(null)
const previewExpanded = ref(true)
const showBoxes = ref(true)
const showLabels = ref(true)
const showOrder = ref(true)
const showPath = ref(true)
const onlyOrdered = ref(false)
const opacity = ref(100)
const filterLabel = ref('')
const activeId = ref<number | null>(null)
const listEl = ref<HTMLElement | null>(null)

const orderedPath = computed(() => {
  if (!result.value) return []
  return result.value.items
    .filter((it) => it.reading_order != null)
    .slice()
    .sort((a, b) => (a.reading_order ?? 0) - (b.reading_order ?? 0))
})

const filteredItems = computed(() => {
  if (!result.value) return []
  let items = result.value.items.filter((it) => !filterLabel.value || it.label === filterLabel.value)
  if (onlyOrdered.value) items = items.filter((it) => it.reading_order != null)
  return items.slice().sort((a, b) => {
    const ao = a.reading_order == null ? 1e9 : a.reading_order
    const bo = b.reading_order == null ? 1e9 : b.reading_order
    if (ao !== bo) return ao - bo
    return a.id - b.id
  })
})

function onFileChange(file: UploadFile) {
  selectedFile.value = file.raw ?? null
}

function onFileRemove() {
  selectedFile.value = null
}

function selectItem(id: number) {
  activeId.value = id
  nextTick(() => {
    const row = listEl.value?.querySelector(`.row[data-id="${id}"]`)
    row?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  })
}

async function startLayout() {
  if (!selectedFile.value || processing.value) return
  processing.value = true
  result.value = null
  activeId.value = null
  filterLabel.value = ''
  try {
    const fd = new FormData()
    fd.append('file', selectedFile.value)
    const res = await fetch('/image-tools/admin/layout', { method: 'POST', body: fd })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail))
    }
    const data = (await res.json()) as LayoutResult
    result.value = data
    previewExpanded.value = true
    if (!data.count) {
      ElMessage.info('未检测到版面区域')
    } else {
      ElMessage.success(`识别完成，共 ${data.count} 个区域`)
    }
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  } finally {
    processing.value = false
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

.result-card {
  margin-top: 16px;
}

.result-card--collapsed :deep(.el-card__body) {
  display: none;
  padding: 0;
}

.card-header {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  align-items: center;
  justify-content: space-between;
  width: 100%;
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

.meta {
  margin-left: 8px;
  font-size: 12px;
  color: var(--sl-text-muted);
  font-weight: 400;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  align-items: center;
}

.toolbar-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--sl-text-muted);
}

.toolbar-slider {
  width: 90px;
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

.panel-title--wrap {
  flex-wrap: wrap;
}

.panel-title-actions {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
}

.viewer {
  flex: 1;
  overflow: auto;
  padding: 12px;
  background:
    linear-gradient(45deg, #eceff3 25%, transparent 25%),
    linear-gradient(-45deg, #eceff3 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #eceff3 75%),
    linear-gradient(-45deg, transparent 75%, #eceff3 75%);
  background-size: 20px 20px;
  background-position: 0 0, 0 10px, 10px -10px, -10px 0;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--sl-border);
}

.legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--sl-text-muted);
  background: #f9fafb;
  border: 1px solid var(--sl-border);
  border-radius: 999px;
  padding: 3px 8px;
}

.legend i {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  display: inline-block;
}

.list {
  flex: 1;
  overflow: auto;
}

.row {
  display: grid;
  grid-template-columns: 36px 1fr auto;
  gap: 8px;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid var(--sl-border);
  cursor: pointer;
}

.row:hover,
.row.active {
  background: #eff6ff;
}

.row.unordered {
  opacity: 0.55;
}

.ord {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #dc2626;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
}

.ord.none {
  background: #9ca3af;
  font-size: 11px;
}

.row .name {
  font-size: 13px;
  font-weight: 600;
}

.row .sub {
  font-size: 12px;
  color: var(--sl-text-muted);
  margin-top: 2px;
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

@media (max-width: 960px) {
  .preview-grid {
    grid-template-columns: 1fr;
  }

  .panel {
    max-height: 420px;
  }
}
</style>
