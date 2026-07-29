<template>
  <div class="web-clips-page">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">剪藏快照</h2>
        <p class="page-desc">抓取网页正文并保存 Markdown / HTML 快照</p>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="showClipDialog = true">
          <el-icon><Plus /></el-icon>
          剪藏网页
        </el-button>
      </div>
    </div>

    <!-- Search -->
    <div class="toolbar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索标题或 URL…"
        clearable
        size="small"
        class="search-input"
        @input="onSearch"
      />
    </div>

    <!-- List -->
    <div class="content-area" v-loading="loading">
      <div v-if="clips.length === 0" class="empty-state">
        <el-icon :size="48"><Picture /></el-icon>
        <p>暂无剪藏</p>
      </div>
      <div v-else class="clip-list">
        <div
          v-for="clip in clips"
          :key="clip.id"
          class="clip-card"
          @click="openClip(clip)"
        >
          <div class="clip-icon">
            <el-icon :size="20"><Document /></el-icon>
          </div>
          <div class="clip-info">
            <div class="clip-title">{{ clip.title || clip.url }}</div>
            <div class="clip-url">{{ clip.url }}</div>
            <div class="clip-meta">
              <span class="meta-time">{{ formatTime(clip.fetched_at) }}</span>
              <span v-if="clip.bookmark_id" class="meta-badge">
                <el-icon><Link /></el-icon>
                已关联书签
              </span>
            </div>
          </div>
          <el-popconfirm
            title="确定删除？"
            confirm-button-text="删除"
            @click.stop
            @confirm.stop="removeClip(clip)"
          >
            <template #reference>
              <el-button
                text
                size="small"
                type="danger"
                class="delete-btn"
                @click.stop
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </template>
          </el-popconfirm>
        </div>
      </div>
    </div>

    <!-- Clip dialog: input URL -->
    <el-dialog v-model="showClipDialog" title="剪藏网页" width="560px" @closed="resetClipForm">
      <el-form :model="clipForm" label-position="top">
        <el-form-item label="URL" required>
          <el-input v-model="clipForm.url" placeholder="https://…" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showClipDialog = false">取消</el-button>
        <el-button type="primary" :loading="clipping" @click="handleClip">
          抓取并保存
        </el-button>
      </template>
    </el-dialog>

    <!-- Preview dialog: view content -->
    <el-dialog v-model="showPreview" title="剪藏预览" width="720px" top="5vh" class="preview-dialog">
      <template v-if="previewItem">
        <div class="preview-header">
          <h3>{{ previewItem.title }}</h3>
          <a :href="previewItem.url" target="_blank" class="preview-url">{{ previewItem.url }}</a>
          <el-tag v-if="previewItem.bookmark_id" size="small" type="info">已关联书签</el-tag>
          <el-tag v-if="previewItem.extract_error" size="small" type="danger">
            提取异常: {{ previewItem.extract_error }}
          </el-tag>
        </div>
        <el-tabs v-model="previewTab" class="preview-tabs">
          <el-tab-pane label="Markdown" name="md">
            <pre class="preview-content">{{ previewItem.content_md || '(无内容)' }}</pre>
          </el-tab-pane>
          <el-tab-pane label="HTML 源码" name="html">
            <pre class="preview-content">{{ previewItem.content_html || '(无内容)' }}</pre>
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Picture, Document, Link, Delete } from '@element-plus/icons-vue'
import { useWebClips, type WebClipSummary, type WebClipFull } from '../../composables/useWebClips'

const { clips, loading, listClips, getClip, clipUrl, deleteClip } = useWebClips()

const searchQuery = ref('')
const showClipDialog = ref(false)
const clipping = ref(false)
const clipForm = ref({ url: '' })
const showPreview = ref(false)
const previewItem = ref<WebClipFull | null>(null)
const previewTab = ref('md')

let searchTimer: ReturnType<typeof setTimeout> | null = null

async function loadClips() {
  const q = searchQuery.value || undefined
  await listClips(q)
}

function onSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(loadClips, 300)
}

function resetClipForm() {
  clipForm.value = { url: '' }
}

async function handleClip() {
  if (!clipForm.value.url.trim()) {
    ElMessage.warning('请输入 URL')
    return
  }
  clipping.value = true
  try {
    const result = await clipUrl(clipForm.value.url)
    showClipDialog.value = false
    if (result.extract_error) {
      ElMessage.warning(`已保存，但内容提取不完整: ${result.extract_error}`)
    } else {
      ElMessage.success('剪藏成功')
    }
    // Show preview
    previewItem.value = result as any
    showPreview.value = true
  } catch (e: any) {
    ElMessage.error(e?.detail || '剪藏失败')
  } finally {
    clipping.value = false
  }
}

async function openClip(clip: WebClipSummary) {
  try {
    const full = await getClip(clip.id)
    previewItem.value = full
    previewTab.value = 'md'
    showPreview.value = true
  } catch {
    ElMessage.error('加载失败')
  }
}

async function removeClip(clip: WebClipSummary) {
  await deleteClip(clip.id)
  ElMessage.success('已删除')
}

function formatTime(ts: string | null) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleDateString('zh-CN') + ' ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

onMounted(loadClips)
</script>

<style scoped>
.web-clips-page {
  padding: 20px 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.page-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: #1e293b;
}

.page-desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: #94a3b8;
}

.toolbar {
  margin-bottom: 16px;
}

.search-input {
  width: 260px;
}

.content-area {
  flex: 1;
  overflow-y: auto;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #94a3b8;
  gap: 12px;
}

.clip-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.clip-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 16px;
  cursor: pointer;
  transition: border-color 0.2s;
}

.clip-card:hover {
  border-color: #0891b2;
}

.clip-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: #ecfeff;
  color: #0891b2;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.clip-info {
  flex: 1;
  min-width: 0;
}

.clip-title {
  font-size: 15px;
  font-weight: 500;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.clip-url {
  font-size: 12px;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.clip-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 2px;
}

.meta-time {
  font-size: 12px;
  color: #cbd5e1;
}

.meta-badge {
  font-size: 12px;
  color: #0891b2;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.delete-btn {
  flex-shrink: 0;
  visibility: hidden;
}

.clip-card:hover .delete-btn {
  visibility: visible;
}

/* Preview dialog */
.preview-dialog :deep(.el-dialog__body) {
  padding-top: 8px;
}

.preview-header {
  margin-bottom: 12px;
}

.preview-header h3 {
  margin: 0 0 4px;
  font-size: 18px;
  color: #1e293b;
}

.preview-url {
  font-size: 13px;
  color: #0891b2;
  text-decoration: none;
  display: inline-block;
  margin-bottom: 8px;
}

.preview-url:hover {
  text-decoration: underline;
}

.preview-tabs {
  margin-top: 4px;
}

.preview-content {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 16px;
  font-size: 13px;
  line-height: 1.6;
  max-height: 60vh;
  overflow-y: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
  margin: 0;
}
</style>
