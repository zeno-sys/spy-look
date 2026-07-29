<template>
  <div class="read-later-page">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">稍后阅读</h2>
        <p class="page-desc">暂存待读的链接，读完可归档或转为书签</p>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="showAddDialog = true">
          <el-icon><Plus /></el-icon>
          添加链接
        </el-button>
      </div>
    </div>

    <!-- Tabs & search -->
    <div class="toolbar">
      <el-radio-group v-model="activeTab" @change="onTabChange" size="small">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="pending">待读</el-radio-button>
        <el-radio-button value="read">已读</el-radio-button>
        <el-radio-button value="archived">归档</el-radio-button>
      </el-radio-group>
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
      <div v-if="items.length === 0" class="empty-state">
        <el-icon :size="48"><CollectionTag /></el-icon>
        <p>暂无内容</p>
      </div>
      <div v-else class="item-list">
        <div
          v-for="item in items"
          :key="item.id"
          class="item-card"
          :class="{ 'is-read': item.status === 'read', 'is-archived': item.status === 'archived' }"
        >
          <div class="card-main">
            <div class="card-title-row">
              <span class="status-dot" :class="item.status" />
              <a
                class="item-title"
                :href="item.url"
                target="_blank"
                rel="noopener noreferrer"
                @click="onOpen(item)"
              >{{ item.title || item.url }}</a>
            </div>
            <div class="item-url">{{ item.url }}</div>
            <div v-if="item.summary" class="item-summary">{{ item.summary }}</div>
            <div class="item-meta">
              <span class="meta-time">{{ formatTime(item.created_at) }}</span>
              <span v-if="item.bookmark_id" class="meta-badge">
                <el-icon><Link /></el-icon>
                已关联书签
              </span>
            </div>
          </div>
          <div class="card-actions">
            <el-button
              v-if="item.status === 'pending'"
              text
              size="small"
              @click="markAsRead(item)"
            >
              <el-icon><Select /></el-icon>
            </el-button>
            <el-button
              v-if="item.status !== 'archived'"
              text
              size="small"
              @click="archive(item)"
            >
              <el-icon><FolderRemove /></el-icon>
            </el-button>
            <el-button v-if="!item.bookmark_id" text size="small" @click="convertToBookmark(item)">
              <el-icon><CollectionTag /></el-icon>
            </el-button>
            <el-button text size="small" type="danger" @click="removeItem(item)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- Add dialog -->
    <el-dialog v-model="showAddDialog" title="添加稍后阅读" width="520px" @closed="resetAddForm">
      <el-form :model="addForm" label-position="top">
        <el-form-item label="URL" required>
          <el-input v-model="addForm.url" placeholder="https://…" />
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="addForm.title" placeholder="留空则自动抓取" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="addForm.summary"
            type="textarea"
            :rows="3"
            placeholder="简短备注…"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleAdd">
          添加
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, CollectionTag, Link, Select, FolderRemove, Delete } from '@element-plus/icons-vue'
import { useReadLater, type ReadLaterItem } from '../../composables/useReadLater'

const router = useRouter()
const { items, loading, listItems, updateItem, deleteItem, createItem } = useReadLater()

const activeTab = ref('all')
const searchQuery = ref('')
const showAddDialog = ref(false)
const submitting = ref(false)
const addForm = ref({ url: '', title: '', summary: '' })

let searchTimer: ReturnType<typeof setTimeout> | null = null

async function loadItems() {
  const status = activeTab.value === 'all' ? undefined : activeTab.value
  const q = searchQuery.value || undefined
  await listItems(status, q)
}

function onTabChange() {
  loadItems()
}

function onSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => loadItems(), 300)
}

async function onOpen(item: ReadLaterItem) {
  if (item.status === 'pending') {
    await updateItem(item.id, { status: 'read' }).catch(() => {})
  }
}

async function markAsRead(item: ReadLaterItem) {
  await updateItem(item.id, { status: 'read' })
  ElMessage.success('已标记为已读')
}

async function archive(item: ReadLaterItem) {
  await updateItem(item.id, { status: 'archived' })
  ElMessage.success('已归档')
}

function convertToBookmark(item: ReadLaterItem) {
  router.push({
    path: '/bookmarks/manage',
    query: { addUrl: item.url, addTitle: item.title },
  })
}

async function removeItem(item: ReadLaterItem) {
  try {
    await ElMessageBox.confirm('确定删除这个稍后阅读项？', '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await deleteItem(item.id)
    ElMessage.success('已删除')
  } catch (e: any) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error(e?.message || '删除失败')
    }
  }
}

function resetAddForm() {
  addForm.value = { url: '', title: '', summary: '' }
}

async function handleAdd() {
  if (!addForm.value.url.trim()) {
    ElMessage.warning('请输入 URL')
    return
  }
  submitting.value = true
  try {
    await createItem({
      url: addForm.value.url,
      title: addForm.value.title,
      summary: addForm.value.summary,
    })
    showAddDialog.value = false
    ElMessage.success('已添加到稍后阅读')
  } catch (e: any) {
    ElMessage.error(e?.detail || '添加失败')
  } finally {
    submitting.value = false
  }
}

function formatTime(ts: string | null) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleDateString('zh-CN') + ' ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

onMounted(loadItems)
</script>

<style scoped>
.read-later-page {
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
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.search-input {
  width: 240px;
  flex-shrink: 0;
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

.item-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.item-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px 16px;
  transition: border-color 0.2s;
}

.item-card:hover {
  border-color: #cbd5e1;
}

.item-card.is-read {
  opacity: 0.7;
}

.item-card.is-archived {
  opacity: 0.45;
}

.card-main {
  flex: 1;
  min-width: 0;
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.pending {
  background: #3b82f6;
}

.status-dot.read {
  background: #10b981;
}

.status-dot.archived {
  background: #94a3b8;
}

.item-title {
  font-size: 15px;
  font-weight: 500;
  color: #1e293b;
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-title:hover {
  color: #3b82f6;
}

.item-url {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-summary {
  font-size: 13px;
  color: #64748b;
  margin-top: 6px;
  line-height: 1.5;
}

.item-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 6px;
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

.card-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: 12px;
  flex-shrink: 0;
}
</style>
