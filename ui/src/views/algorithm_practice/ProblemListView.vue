<template>
  <div class="algo-page">
    <!-- Header -->
    <header class="algo-header">
      <div class="algo-header-left">
        <h1 class="algo-title">算法练习</h1>
        <span class="algo-subtitle">题目列表</span>
      </div>
      <div class="algo-header-actions">
        <el-button :icon="PriceTag" @click="tagDialogVisible = true">标签管理</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreateDialog">新建题目</el-button>
      </div>
    </header>

    <!-- Toolbar + tag filter -->
    <div class="algo-toolbar">
      <!-- Tag filter (left) -->
      <div v-if="tags.length" class="algo-tag-filter">
        <button
          class="algo-tag-chip"
          :class="{ active: selectedTagIds.length === 0 }"
          @click="clearTagFilter"
        >
          全部
        </button>
        <button
          v-for="t in tags"
          :key="t.id"
          class="algo-tag-chip"
          :class="{ active: selectedTagIds.includes(t.id) }"
          :style="{ '--tag-color': t.color }"
          @click="toggleTagFilter(t.id)"
        >
          {{ t.name }}
        </button>
      </div>

      <!-- Search & sort (right) -->
      <div class="algo-toolbar-controls">
        <el-input
          v-model="searchQuery"
          placeholder="搜索题目标题…"
          :prefix-icon="Search"
          clearable
          class="algo-search"
          @input="onSearchInput"
        />
        <el-select v-model="sortMode" placeholder="排序" class="algo-sort" @change="reloadList">
          <el-option label="最近更新" value="updated_desc" />
          <el-option label="最早更新" value="updated_asc" />
          <el-option label="最新创建" value="created_desc" />
        </el-select>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="problemsLoading" class="algo-empty">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>加载中…</p>
    </div>

    <!-- Empty state -->
    <div v-else-if="!problems.length" class="algo-empty">
      <el-icon :size="40" class="algo-empty-icon"><Document /></el-icon>
      <p v-if="searchQuery || selectedTagIds.length">未找到匹配的题目</p>
      <p v-else>暂无题目，点击「新建题目」开始练习</p>
    </div>

    <!-- Problem list -->
    <div v-else class="algo-list">
      <el-tooltip
        v-for="item in problems"
        :key="item.id"
        :content="item.description_preview || '无描述'"
        placement="top"
        effect="dark"
        :show-after="300"
        :disabled="!item.description_preview"
      >
        <div class="algo-list-item" @click="goPractice(item.id)">
          <div class="algo-item-main">
            <span class="algo-item-title">{{ item.title }}</span>
          </div>
          <div class="algo-item-meta">
            <div class="algo-item-tags">
              <span
                v-for="t in item.tags"
                :key="t.id"
                class="algo-item-tag"
                :style="{ background: t.color + '22', color: t.color, borderColor: t.color + '44' }"
              >
                {{ t.name }}
              </span>
            </div>
            <span class="algo-item-time">{{ formatTime(item.updated_at) }}</span>
            <div class="algo-item-actions" @click.stop>
              <el-button size="small" :icon="EditPen" circle title="编辑" @click="openEditDialog(item)" />
              <el-button size="small" type="danger" :icon="Delete" circle title="删除" @click="onDelete(item)" />
            </div>
          </div>
        </div>
      </el-tooltip>
    </div>

    <!-- Create / Edit Dialog -->
    <el-dialog
      v-model="formDialogVisible"
      :title="editingId ? '编辑题目' : '新建题目'"
      width="620px"
      :close-on-click-modal="false"
    >
      <el-form label-position="top" class="algo-form">
        <el-form-item label="标题">
          <el-input v-model="formData.title" placeholder="输入题目标题" />
        </el-form-item>
        <el-form-item label="描述（Markdown）">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="8"
            placeholder="用 Markdown 描述题目内容，支持代码块、列表等"
          />
        </el-form-item>
        <el-form-item label="标签">
          <el-select
            v-model="formData.tag_ids"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入标签"
            class="algo-full-width"
          >
            <el-option
              v-for="t in tags"
              :key="t.id"
              :label="t.name"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- Tag Management Dialog -->
    <el-dialog v-model="tagDialogVisible" title="标签管理" width="520px">
      <div class="algo-tag-mgmt">
        <div class="algo-tag-create">
          <el-input v-model="newTagName" placeholder="标签名" class="algo-tag-name-input" />
          <el-color-picker v-model="newTagColor" size="small" />
          <el-button type="primary" :icon="Plus" @click="onCreateTag">添加</el-button>
        </div>
        <div class="algo-tag-list">
          <div v-for="t in tags" :key="t.id" class="algo-tag-row">
            <span class="algo-tag-dot" :style="{ background: t.color }"></span>
            <span class="algo-tag-name">{{ t.name }}</span>
            <el-button size="small" :icon="Delete" circle type="danger" @click="onDeleteTag(t)" />
          </div>
          <div v-if="!tags.length" class="algo-tag-empty">暂无标签</div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Delete,
  Document,
  EditPen,
  Loading,
  Plus,
  PriceTag,
  Search,
} from '@element-plus/icons-vue'
import { useAlgorithm, type ProblemListItem } from '../../composables/useAlgorithm'

const router = useRouter()
const {
  problems,
  problemsLoading,
  tags,
  listTags,
  listProblems,
  getProblem,
  createProblem,
  updateProblem,
  deleteProblem,
  setProblemTags,
  createTag,
  deleteTag,
} = useAlgorithm()

// --- search & filter ---

const searchQuery = ref('')
const selectedTagIds = ref<number[]>([])
const sortMode = ref('updated_desc')
let searchTimer: ReturnType<typeof setTimeout> | null = null

function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => reloadList(), 300)
}

function toggleTagFilter(id: number) {
  const idx = selectedTagIds.value.indexOf(id)
  if (idx >= 0) selectedTagIds.value.splice(idx, 1)
  else selectedTagIds.value.push(id)
  reloadList()
}

function clearTagFilter() {
  selectedTagIds.value = []
  reloadList()
}

async function reloadList() {
  await listProblems({
    q: searchQuery.value || undefined,
    tag_ids: selectedTagIds.value.length ? selectedTagIds.value : undefined,
    sort: sortMode.value,
  })
}

// --- navigation ---

function goPractice(id: number) {
  router.push(`/algorithm/practice?id=${id}`)
}

// --- create / edit ---

const formDialogVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const formData = ref({
  title: '',
  description: '',
  tag_ids: [] as number[],
})

function openCreateDialog() {
  editingId.value = null
  formData.value = { title: '', description: '', tag_ids: [] }
  formDialogVisible.value = true
}

function openEditDialog(item: ProblemListItem) {
  editingId.value = item.id
  formData.value = {
    title: item.title,
    description: '',
    tag_ids: item.tags.map(t => t.id),
  }
  // Fetch full description
  getProblem(item.id).then(detail => {
    formData.value.description = detail.description
  })
  formDialogVisible.value = true
}

async function onSave() {
  if (!formData.value.title.trim()) {
    ElMessage.warning('请输入标题')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateProblem(editingId.value, {
        title: formData.value.title,
        description: formData.value.description,
      })
      if (formData.value.tag_ids.length) {
        await setProblemTags(editingId.value, formData.value.tag_ids)
      }
      ElMessage.success('题目已更新')
    } else {
      await createProblem({
        title: formData.value.title,
        description: formData.value.description,
        tag_ids: formData.value.tag_ids,
      })
      ElMessage.success('题目已创建')
    }
    formDialogVisible.value = false
    await reloadList()
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function onDelete(item: ProblemListItem) {
  try {
    await ElMessageBox.confirm(`确定删除「${item.title}」？`, '删除题目', {
      type: 'warning',
    })
    await deleteProblem(item.id)
    ElMessage.success('已删除')
    await reloadList()
  } catch {
    // cancelled
  }
}

// --- tag management ---

const tagDialogVisible = ref(false)
const newTagName = ref('')
const newTagColor = ref('#64748b')

async function onCreateTag() {
  if (!newTagName.value.trim()) {
    ElMessage.warning('请输入标签名')
    return
  }
  try {
    await createTag(newTagName.value.trim(), newTagColor.value)
    newTagName.value = ''
    newTagColor.value = '#64748b'
  } catch (e: any) {
    ElMessage.error(e.message || '创建失败')
  }
}

async function onDeleteTag(t: { id: number; name: string }) {
  try {
    await ElMessageBox.confirm(`确定删除标签「${t.name}」？`, '删除标签', {
      type: 'warning',
    })
    await deleteTag(t.id)
  } catch (e: any) {
    ElMessage.error(e.message || '删除失败')
  }
}

// --- helpers ---

function formatTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins} 分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days} 天前`
  return d.toLocaleDateString('zh-CN')
}

// --- lifecycle ---

onMounted(async () => {
  await Promise.all([listTags(), reloadList()])
})
</script>

<style scoped>
.algo-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px 32px 48px;
}

.algo-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.algo-header-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.algo-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--sl-text);
  margin: 0;
}

.algo-subtitle {
  font-size: 14px;
  color: var(--sl-text-muted);
}

.algo-header-actions {
  display: flex;
  gap: 10px;
}

.algo-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.algo-tag-filter {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.algo-toolbar-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.algo-search {
  width: 260px;
}

.algo-sort {
  width: 140px;
}

.algo-tag-chip {
  padding: 4px 14px;
  border: 1px solid var(--sl-border);
  border-radius: 20px;
  background: var(--sl-bg-elevated);
  color: var(--sl-text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}

.algo-tag-chip:hover {
  border-color: var(--sl-border-strong);
}

.algo-tag-chip.active {
  background: var(--tag-color, var(--sl-accent));
  color: #fff;
  border-color: transparent;
}

.algo-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 64px 0;
  color: var(--sl-text-muted);
}

.algo-empty-icon {
  color: var(--sl-text-faint);
}

.algo-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.algo-list-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  background: var(--sl-bg-elevated);
  border: 1px solid var(--sl-border);
  border-radius: var(--sl-radius-sm);
  cursor: pointer;
  transition: all 0.15s;
}

.algo-list-item:hover {
  border-color: var(--sl-border-strong);
  box-shadow: var(--sl-shadow-sm);
}

.algo-item-main {
  flex: 1;
  min-width: 0;
}

.algo-item-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--sl-text);
}

.algo-item-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
  gap: 6px;
  max-width: 460px;
}

.algo-item-tag {
  padding: 2px 8px;
  border: 1px solid;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.algo-item-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 1;
  min-width: 0;
}

.algo-item-time {
  font-size: 12px;
  color: var(--sl-text-faint);
  white-space: nowrap;
}

.algo-item-actions {
  display: flex;
  gap: 6px;
  opacity: 0;
  transition: opacity 0.15s;
}

.algo-list-item:hover .algo-item-actions {
  opacity: 1;
}

/* Form */
.algo-form {
  padding: 4px 0;
}

.algo-full-width {
  width: 100%;
}

/* Tag management */
.algo-tag-mgmt {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.algo-tag-create {
  display: flex;
  align-items: center;
  gap: 10px;
}

.algo-tag-name-input {
  flex: 1;
}

.algo-tag-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 320px;
  overflow-y: auto;
}

.algo-tag-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border: 1px solid var(--sl-border);
  border-radius: var(--sl-radius-sm);
}

.algo-tag-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

.algo-tag-name {
  flex: 1;
  font-size: 14px;
  color: var(--sl-text);
}

.algo-tag-empty {
  text-align: center;
  color: var(--sl-text-muted);
  padding: 24px 0;
}
</style>
