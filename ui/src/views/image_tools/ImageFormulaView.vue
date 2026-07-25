<template>
  <div class="page-container formula-page">
    <div class="page-header">
      <div>
        <h3>图片工具 · 公式识别</h3>
        <p class="page-sub">本地 PP-FormulaNet+ M（CPU）· 建议上传公式裁剪图，输出 LaTeX</p>
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
              <span class="el-upload__text">拖拽或 <em>点击选择</em> 公式图</span>
              <span class="el-upload__tip">png / jpg / webp / bmp，≤10 MB</span>
            </div>
          </el-upload>
          <el-button
            type="primary"
            class="start-btn"
            :loading="processing"
            :disabled="!selectedFile || processing"
            @click="startRecognize"
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
                  原图预览
                  <span class="meta">图像 {{ result.width }}×{{ result.height }}</span>
                </span>
                <span class="preview-toggle-label">{{ previewExpanded ? '收起' : '展开' }}</span>
              </button>
            </div>
          </template>
          <div v-show="previewExpanded" class="preview-wrap">
            <img :src="result.image_data_uri" alt="formula" class="preview-img" />
          </div>
        </el-card>

        <el-card class="section-card result-card" :class="{ 'result-card--collapsed': !latexExpanded }">
          <template #header>
            <div class="card-header">
              <button type="button" class="preview-toggle" @click="latexExpanded = !latexExpanded">
                <el-icon class="preview-toggle-icon" :class="{ expanded: latexExpanded }">
                  <ArrowRight />
                </el-icon>
                <span>识别结果（LaTeX）</span>
                <span class="preview-toggle-label">{{ latexExpanded ? '收起' : '展开' }}</span>
              </button>
              <div v-show="latexExpanded" class="result-actions">
                <el-button size="small" type="primary" :disabled="!latex" @click="copyLatex">
                  一键复制
                </el-button>
              </div>
            </div>
          </template>
          <div v-show="latexExpanded">
            <el-input
              v-model="latex"
              type="textarea"
              :rows="8"
              placeholder="识别完成后可在此查看、编辑后复制"
              class="latex-input"
            />
            <p v-if="!latex.trim()" class="hint-muted">未识别到公式内容</p>
          </div>
        </el-card>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { ArrowRight, UploadFilled } from '@element-plus/icons-vue'

interface FormulaResult {
  width: number
  height: number
  image_data_uri: string
  latex: string
}

const selectedFile = ref<File | null>(null)
const processing = ref(false)
const result = ref<FormulaResult | null>(null)
const latex = ref('')
const previewExpanded = ref(true)
const latexExpanded = ref(true)

function onFileChange(file: UploadFile) {
  selectedFile.value = file.raw ?? null
}

function onFileRemove() {
  selectedFile.value = null
}

async function startRecognize() {
  if (!selectedFile.value || processing.value) return
  processing.value = true
  result.value = null
  latex.value = ''
  try {
    const fd = new FormData()
    fd.append('file', selectedFile.value)
    const res = await fetch('/image-tools/admin/formula', { method: 'POST', body: fd })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail))
    }
    const data = (await res.json()) as FormulaResult
    result.value = data
    latex.value = data.latex ?? ''
    previewExpanded.value = true
    latexExpanded.value = true
    if (!data.latex?.trim()) {
      ElMessage.info('未识别到公式')
    } else {
      ElMessage.success('识别完成')
    }
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  } finally {
    processing.value = false
  }
}

async function copyLatex() {
  const text = latex.value
  if (!text) {
    ElMessage.warning('没有可复制的内容')
    return
  }
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch {
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

.section-card + .section-card {
  margin-top: 16px;
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

.preview-wrap {
  padding: 8px;
  text-align: center;
  background:
    linear-gradient(45deg, #eceff3 25%, transparent 25%),
    linear-gradient(-45deg, #eceff3 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #eceff3 75%),
    linear-gradient(-45deg, transparent 75%, #eceff3 75%);
  background-size: 20px 20px;
  background-position: 0 0, 0 10px, 10px -10px, -10px 0;
  border-radius: var(--sl-radius-sm);
  max-height: 360px;
  overflow: auto;
}

.preview-img {
  max-width: 100%;
  max-height: 320px;
  height: auto;
  box-shadow: var(--sl-shadow-md);
}

.result-actions {
  display: flex;
  gap: 8px;
}

.latex-input :deep(textarea) {
  font-family: ui-monospace, "Cascadia Code", "Consolas", monospace;
  font-size: 13px;
  line-height: 1.5;
}

.hint-muted {
  margin-top: 8px;
  color: var(--sl-text-muted);
  font-size: 12px;
}
</style>
