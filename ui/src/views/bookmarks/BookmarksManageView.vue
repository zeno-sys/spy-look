<template>
  <div class="bm-page">
    <!-- Header -->
    <header class="bm-header">
      <div class="bm-header-left">
        <h1 class="bm-title">网页收藏</h1>
        <span class="bm-subtitle">书签管理</span>
      </div>
      <div class="bm-header-actions">
        <el-button :icon="PriceTag" @click="tagDialogVisible = true">标签管理</el-button>
        <el-button :icon="FolderAdd" @click="groupDialogVisible = true">分组管理</el-button>
        <el-button type="primary" :icon="Plus" @click="openAddDialog">添加书签</el-button>
      </div>
    </header>

    <!-- TOP5 Section -->
    <section v-if="top5.length" class="bm-top5">
      <div class="bm-section-label">
        <el-icon><Trophy /></el-icon>
        <span>近 7 日常用 TOP 5</span>
      </div>
      <div class="bm-top5-list">
        <div
          v-for="(item, idx) in top5"
          :key="item.id"
          class="bm-top5-card"
          @click="onBookmarkClick(item)"
        >
          <span class="bm-top5-rank">{{ idx + 1 }}</span>
          <img
            v-if="item.favicon_url"
            :src="item.favicon_url"
            class="bm-top5-favicon"
            @error="onFaviconError($event, item.title)"
          />
          <span v-else class="bm-top5-favicon bm-favicon-fallback">{{ getInitial(item.title) }}</span>
          <div class="bm-top5-info">
            <span class="bm-top5-name">{{ item.title || getDomain(item.url) }}</span>
            <span class="bm-top5-count">{{ item.access_count_7d }} 次访问</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Pinned Section -->
    <section v-if="pinned.length" class="bm-pinned">
      <div class="bm-section-label">
        <el-icon><Top /></el-icon>
        <span>置顶书签</span>
      </div>
      <div class="bm-pinned-list">
        <div
          v-for="item in pinned"
          :key="item.id"
          class="bm-pinned-card"
          @click="onBookmarkClick(item)"
        >
          <img
            v-if="item.favicon_url"
            :src="item.favicon_url"
            class="bm-pinned-favicon"
            @error="onFaviconError($event, item.title)"
          />
          <span v-else class="bm-pinned-favicon bm-favicon-fallback">{{ getInitial(item.title) }}</span>
          <span class="bm-pinned-name">{{ item.title || getDomain(item.url) }}</span>
          <el-icon class="bm-pinned-unpin" @click.stop="togglePin(item)"><Top /></el-icon>
        </div>
      </div>
    </section>

    <!-- Main split layout -->
    <div class="bm-split">
      <!-- Left Sidebar -->
      <aside class="bm-sidebar">
        <div class="bm-sidebar-section">
          <div class="bm-sidebar-label">分组</div>
          <button
            class="bm-group-item"
            :class="{ active: selectedGroupId === null }"
            @click="selectGroup(null)"
          >
            <el-icon><Files /></el-icon>
            <span class="bm-group-name">全部书签</span>
          </button>
          <button
            v-for="g in groups"
            :key="g.id"
            class="bm-group-item"
            :class="{ active: selectedGroupId === g.id }"
            @click="selectGroup(g.id)"
          >
            <el-icon><FolderOpened /></el-icon>
            <span class="bm-group-name">{{ g.name }}</span>
            <span class="bm-group-count">{{ g.bookmark_count ?? 0 }}</span>
          </button>
          <button
            class="bm-group-item"
            :class="{ active: selectedGroupId === -1 }"
            @click="selectGroup(-1)"
          >
            <el-icon><FolderRemove /></el-icon>
            <span class="bm-group-name">未分组</span>
          </button>
        </div>

        <div v-if="tags.length" class="bm-sidebar-section">
          <div class="bm-sidebar-label">标签筛选</div>
          <div class="bm-tag-filter-list">
            <button
              v-for="t in tags"
              :key="t.id"
              class="bm-tag-chip"
              :class="{ active: selectedTagIds.includes(t.id) }"
              :style="{ '--tag-color': t.color }"
              @click="toggleTagFilter(t.id)"
            >
              {{ t.name }}
            </button>
          </div>
        </div>
      </aside>

      <!-- Right Main -->
      <main class="bm-main">
        <div class="bm-toolbar">
          <el-input
            v-model="searchQuery"
            placeholder="搜索标题或 URL…"
            :prefix-icon="Search"
            clearable
            class="bm-search"
            @input="onSearchInput"
          />
          <div class="bm-view-toggle">
            <button
              class="bm-view-btn"
              :class="{ active: viewMode === 'card' }"
              title="卡片视图"
              @click="setViewMode('card')"
            >
              <el-icon><Grid /></el-icon>
            </button>
            <button
              class="bm-view-btn"
              :class="{ active: viewMode === 'list' }"
              title="列表视图"
              @click="setViewMode('list')"
            >
              <el-icon><Menu /></el-icon>
            </button>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="bookmarksLoading" class="bm-empty">
          <el-icon class="is-loading" :size="32"><Loading /></el-icon>
          <p>加载中…</p>
        </div>

        <!-- Empty states -->
        <div v-else-if="!bookmarks.length" class="bm-empty">
          <el-icon :size="40" class="bm-empty-icon"><Link /></el-icon>
          <p v-if="searchQuery || selectedTagIds.length">未找到匹配的书签</p>
          <p v-else>暂无书签，点击「添加书签」开始收藏</p>
        </div>

        <!-- Card view -->
        <div v-else-if="viewMode === 'card'" class="bm-card-grid">
          <article
            v-for="item in bookmarks"
            :key="item.id"
            class="bm-card"
            @click="onBookmarkClick(item)"
          >
            <div class="bm-card-header">
              <img
                v-if="item.favicon_url"
                :src="item.favicon_url"
                class="bm-card-favicon"
                @error="onFaviconError($event, item.title)"
              />
              <span v-else class="bm-card-favicon bm-favicon-fallback">{{ getInitial(item.title) }}</span>
              <div class="bm-card-meta">
                <span class="bm-card-title">{{ item.title || getDomain(item.url) }}</span>
                <span class="bm-card-domain">{{ getDomain(item.url) }}</span>
              </div>
              <button
                class="bm-card-pin"
                :class="{ active: item.pinned }"
                title="置顶"
                @click.stop="togglePin(item)"
              >
                <el-icon><Top /></el-icon>
              </button>
            </div>
            <div class="bm-card-tags">
              <span
                v-for="t in item.tags"
                :key="t.id"
                class="bm-card-tag"
                :style="{ '--tag-color': t.color }"
              >{{ t.name }}</span>
            </div>
            <div class="bm-card-footer">
              <span class="bm-card-access">
                <el-icon><View /></el-icon>
                {{ item.access_count }}
              </span>
              <div class="bm-card-actions">
                <button class="bm-icon-btn" title="编辑" @click.stop="openEditDialog(item)">
                  <el-icon><EditPen /></el-icon>
                </button>
                <button class="bm-icon-btn bm-icon-btn--danger" title="删除" @click.stop="onDeleteBookmark(item)">
                  <el-icon><Delete /></el-icon>
                </button>
              </div>
            </div>
          </article>
        </div>

        <!-- List view -->
        <div v-else class="bm-list-view">
          <div
            v-for="item in bookmarks"
            :key="item.id"
            class="bm-list-row"
            @click="onBookmarkClick(item)"
          >
            <img
              v-if="item.favicon_url"
              :src="item.favicon_url"
              class="bm-list-favicon"
              @error="onFaviconError($event, item.title)"
            />
            <span v-else class="bm-list-favicon bm-favicon-fallback">{{ getInitial(item.title) }}</span>
            <div class="bm-list-info">
              <span class="bm-list-title">{{ item.title || getDomain(item.url) }}</span>
              <span class="bm-list-url">{{ item.url }}</span>
            </div>
            <div class="bm-list-tags">
              <span
                v-for="t in item.tags"
                :key="t.id"
                class="bm-card-tag"
                :style="{ '--tag-color': t.color }"
              >{{ t.name }}</span>
            </div>
            <span class="bm-list-access">{{ item.access_count }} 次</span>
            <button
              class="bm-card-pin"
              :class="{ active: item.pinned }"
              title="置顶"
              @click.stop="togglePin(item)"
            >
              <el-icon><Top /></el-icon>
            </button>
            <div class="bm-list-actions">
              <button class="bm-icon-btn" title="编辑" @click.stop="openEditDialog(item)">
                <el-icon><EditPen /></el-icon>
              </button>
              <button class="bm-icon-btn bm-icon-btn--danger" title="删除" @click.stop="onDeleteBookmark(item)">
                <el-icon><Delete /></el-icon>
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>

    <!-- Add / Edit Bookmark Dialog -->
    <el-dialog
      v-model="addDialogVisible"
      :title="editingBookmark ? '编辑书签' : '添加书签'"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form label-position="top" class="bm-form">
        <el-form-item label="URL">
          <div class="bm-url-row">
            <el-input
              v-model="addForm.url"
              placeholder="https://example.com"
              :disabled="!!editingBookmark"
            />
            <el-button
              v-if="!editingBookmark"
              :loading="fetchingMeta"
              :disabled="!addForm.url"
              @click="onFetchMetadata"
            >
              抓取
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="addForm.title" placeholder="页面标题" />
        </el-form-item>
        <el-form-item v-if="addForm.favicon_url" label="图标">
          <div class="bm-favicon-preview">
            <img :src="addForm.favicon_url" class="bm-preview-img" @error="onPreviewError" />
            <span class="bm-favicon-url">{{ addForm.favicon_url }}</span>
          </div>
        </el-form-item>
        <el-form-item label="分组">
          <el-select v-model="addForm.group_id" placeholder="选择分组（可选）" clearable class="bm-full-width">
            <el-option
              v-for="g in groups"
              :key="g.id"
              :label="g.name"
              :value="g.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-select
            v-model="addForm.tag_ids"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入标签"
            class="bm-full-width"
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
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSaveBookmark">保存</el-button>
      </template>
    </el-dialog>

    <!-- Tag Management Dialog -->
    <el-dialog v-model="tagDialogVisible" title="标签管理" width="480px">
      <div class="bm-tag-mgmt">
        <div class="bm-tag-add-row">
          <el-input v-model="newTagForm.name" placeholder="标签名" class="bm-tag-name-input" />
          <el-color-picker v-model="newTagForm.color" size="small" />
          <el-button :icon="Plus" @click="onCreateTag" :loading="tagCreating">添加</el-button>
        </div>
        <div class="bm-tag-list">
          <div v-for="t in tags" :key="t.id" class="bm-tag-row">
            <div class="bm-tag-color-dot" :style="{ background: t.color }" />
            <el-input
              v-model="t.name"
              size="small"
              class="bm-tag-edit-name"
              @change="onUpdateTag(t)"
            />
            <el-color-picker v-model="t.color" size="small" @change="onUpdateTag(t)" />
            <el-button
              size="small"
              :icon="Delete"
              circle
              @click="onDeleteTag(t)"
            />
          </div>
          <div v-if="!tags.length" class="bm-empty-mini">暂无标签</div>
        </div>
      </div>
    </el-dialog>

    <!-- Group Management Dialog -->
    <el-dialog v-model="groupDialogVisible" title="分组管理" width="440px">
      <div class="bm-group-mgmt">
        <div class="bm-group-add-row">
          <el-input v-model="newGroupForm.name" placeholder="分组名" @keyup.enter="onCreateGroup" />
          <el-button :icon="Plus" @click="onCreateGroup" :loading="groupCreating">添加</el-button>
        </div>
        <div class="bm-group-list">
          <div v-for="g in groups" :key="g.id" class="bm-group-row">
            <el-icon><FolderOpened /></el-icon>
            <el-input
              v-model="g.name"
              size="small"
              class="bm-group-edit-name"
              @change="onUpdateGroup(g)"
            />
            <span class="bm-group-edit-count">{{ g.bookmark_count ?? 0 }} 个书签</span>
            <el-button
              size="small"
              :icon="Delete"
              circle
              :disabled="(g.bookmark_count ?? 0) > 0"
              :title="(g.bookmark_count ?? 0) > 0 ? '请先清空分组内书签' : '删除分组'"
              @click="onDeleteGroup(g)"
            />
          </div>
          <div v-if="!groups.length" class="bm-empty-mini">暂无分组</div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Link,
  Delete,
  EditPen,
  Files,
  FolderAdd,
  FolderOpened,
  FolderRemove,
  Grid,
  Loading,
  Menu,
  Plus,
  PriceTag,
  Search,
  Top,
  Trophy,
  View,
} from '@element-plus/icons-vue'
import { useGroups, useTags, useBookmarks, type BookmarkItem, type GroupItem } from '../../composables/useBookmarks'

const {
  groups,
  listGroups,
  createGroup,
  updateGroup,
  deleteGroup,
} = useGroups()

const {
  tags,
  listTags,
  createTag,
  updateTag,
  deleteTag,
} = useTags()

const {
  bookmarks,
  pinned,
  top5,
  bookmarksLoading,
  listBookmarks,
  listPinned,
  getTop5,
  createBookmark,
  updateBookmark,
  deleteBookmark,
  setBookmarkTags,
  recordAccess,
  fetchMetadata,
} = useBookmarks()

// --------------------------------------------------------------------------- //
// Filters & view state
// --------------------------------------------------------------------------- //

const selectedGroupId = ref<number | null>(null)  // null = all, -1 = ungrouped
const selectedTagIds = ref<number[]>([])
const searchQuery = ref('')
const viewMode = ref<'card' | 'list'>(
  (localStorage.getItem('bm-view-mode') as 'card' | 'list') || 'card'
)

let searchTimer: ReturnType<typeof setTimeout> | null = null

function setViewMode(mode: 'card' | 'list') {
  viewMode.value = mode
  localStorage.setItem('bm-view-mode', mode)
}

function selectGroup(groupId: number | null) {
  selectedGroupId.value = groupId
  refreshBookmarks()
}

function toggleTagFilter(tagId: number) {
  const idx = selectedTagIds.value.indexOf(tagId)
  if (idx >= 0) {
    selectedTagIds.value.splice(idx, 1)
  } else {
    selectedTagIds.value.push(tagId)
  }
  refreshBookmarks()
}

function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(refreshBookmarks, 300)
}

function refreshBookmarks() {
  const filters: Record<string, any> = {}
  if (searchQuery.value) filters.q = searchQuery.value
  if (selectedGroupId.value !== null && selectedGroupId.value !== -1) {
    filters.group_id = selectedGroupId.value
  } else if (selectedGroupId.value === -1) {
    // ungrouped: we filter on the frontend since backend doesn't have an "ungrouped" filter
    // actually, group_id=null should work — pass it as null explicitly
    // The list_bookmarks function handles group_id=None as "all groups"
    // For ungrouped, we need a special case — let's filter on frontend
  }
  if (selectedTagIds.value.length) filters.tag_ids = selectedTagIds.value
  listBookmarks(filters).then(() => {
    if (selectedGroupId.value === -1) {
      // Filter to only show ungrouped bookmarks
      // eslint-disable-next-line vue/no-mutating-props
      // We need to filter the bookmarks array — since it's a ref, we can do this
      const ungrouped = bookmarks.value.filter(b => b.group_id === null)
      bookmarks.value = ungrouped
    }
  })
}

async function refreshAll() {
  await Promise.all([listGroups(), listTags()])
  await refreshBookmarks()
  await Promise.all([listPinned(), getTop5()])
}

// --------------------------------------------------------------------------- //
// Bookmark click & access recording
// --------------------------------------------------------------------------- //

function onBookmarkClick(item: BookmarkItem) {
  window.open(item.url, '_blank', 'noopener,noreferrer')
  recordAccess(item.id)
  // Optimistically update local state
  item.access_count++
  // Refresh top5 and pinned in background
  getTop5()
}

// --------------------------------------------------------------------------- //
// Pin toggle
// --------------------------------------------------------------------------- //

async function togglePin(item: BookmarkItem) {
  try {
    await updateBookmark(item.id, { pinned: !item.pinned })
    item.pinned = !item.pinned
    await listPinned()
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  }
}

// --------------------------------------------------------------------------- //
// Add / Edit bookmark dialog
// --------------------------------------------------------------------------- //

const addDialogVisible = ref(false)
const editingBookmark = ref<BookmarkItem | null>(null)
const fetchingMeta = ref(false)
const saving = ref(false)

const addForm = ref({
  url: '',
  title: '',
  favicon_url: '',
  group_id: null as number | null,
  tag_ids: [] as number[],
})

function openAddDialog() {
  editingBookmark.value = null
  addForm.value = { url: '', title: '', favicon_url: '', group_id: null, tag_ids: [] }
  addDialogVisible.value = true
}

function openEditDialog(item: BookmarkItem) {
  editingBookmark.value = item
  addForm.value = {
    url: item.url,
    title: item.title,
    favicon_url: item.favicon_url,
    group_id: item.group_id,
    tag_ids: item.tags.map(t => t.id),
  }
  addDialogVisible.value = true
}

async function onFetchMetadata() {
  if (!addForm.value.url) return
  fetchingMeta.value = true
  try {
    const result = await fetchMetadata(addForm.value.url)
    if (result.error) {
      ElMessage.warning('抓取失败，请手动填写标题')
    } else {
      ElMessage.success('抓取成功')
    }
    if (result.title) addForm.value.title = result.title
    if (result.favicon_url) addForm.value.favicon_url = result.favicon_url
  } catch (e: any) {
    ElMessage.error(e?.message || '抓取失败')
  } finally {
    fetchingMeta.value = false
  }
}

async function onSaveBookmark() {
  if (!addForm.value.url) {
    ElMessage.warning('请输入 URL')
    return
  }
  saving.value = true
  try {
    if (editingBookmark.value) {
      // Edit mode
      const id = editingBookmark.value.id
      await updateBookmark(id, {
        title: addForm.value.title,
        favicon_url: addForm.value.favicon_url,
        group_id: addForm.value.group_id,
      })
      await setBookmarkTags(id, addForm.value.tag_ids)
      ElMessage.success('书签已更新')
    } else {
      // Create mode
      const created = await createBookmark({
        url: addForm.value.url,
        title: addForm.value.title,
        favicon_url: addForm.value.favicon_url,
        group_id: addForm.value.group_id,
      })
      if (addForm.value.tag_ids.length) {
        await setBookmarkTags(created.id, addForm.value.tag_ids)
      }
      ElMessage.success('书签已添加')
    }
    addDialogVisible.value = false
    await refreshAll()
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

// --------------------------------------------------------------------------- //
// Delete bookmark
// --------------------------------------------------------------------------- //

async function onDeleteBookmark(item: BookmarkItem) {
  try {
    await ElMessageBox.confirm(
      `确定删除书签「${item.title || item.url}」吗？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return  // user cancelled
  }
  try {
    await deleteBookmark(item.id)
    ElMessage.success('已删除')
    await refreshAll()
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败')
  }
}

// --------------------------------------------------------------------------- //
// Tag management
// --------------------------------------------------------------------------- //

const tagDialogVisible = ref(false)
const tagCreating = ref(false)
const newTagForm = ref({ name: '', color: '#64748b' })

async function onCreateTag() {
  if (!newTagForm.value.name.trim()) return
  tagCreating.value = true
  try {
    await createTag(newTagForm.value.name, newTagForm.value.color)
    newTagForm.value = { name: '', color: '#64748b' }
    ElMessage.success('标签已创建')
  } catch (e: any) {
    ElMessage.error(e?.message || '创建失败')
  } finally {
    tagCreating.value = false
  }
}

async function onUpdateTag(t: any) {
  try {
    await updateTag(t.id, { name: t.name, color: t.color })
    ElMessage.success('标签已更新')
  } catch (e: any) {
    ElMessage.error(e?.message || '更新失败')
    await listTags()  // refresh to revert
  }
}

async function onDeleteTag(t: any) {
  try {
    await ElMessageBox.confirm(`确定删除标签「${t.name}」吗？`, '删除确认', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消'
    })
    await deleteTag(t.id)
    ElMessage.success('已删除')
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e?.message || '删除失败')
  }
}

// --------------------------------------------------------------------------- //
// Group management
// --------------------------------------------------------------------------- //

const groupDialogVisible = ref(false)
const groupCreating = ref(false)
const newGroupForm = ref({ name: '' })

async function onCreateGroup() {
  if (!newGroupForm.value.name.trim()) return
  groupCreating.value = true
  try {
    await createGroup(newGroupForm.value.name)
    newGroupForm.value = { name: '' }
    ElMessage.success('分组已创建')
  } catch (e: any) {
    ElMessage.error(e?.message || '创建失败')
  } finally {
    groupCreating.value = false
  }
}

async function onUpdateGroup(g: GroupItem) {
  try {
    await updateGroup(g.id, { name: g.name })
    ElMessage.success('分组已更新')
  } catch (e: any) {
    ElMessage.error(e?.message || '更新失败')
    await listGroups()
  }
}

async function onDeleteGroup(g: GroupItem) {
  try {
    await ElMessageBox.confirm(`确定删除分组「${g.name}」吗？`, '删除确认', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消'
    })
    await deleteGroup(g.id)
    ElMessage.success('已删除')
    if (selectedGroupId.value === g.id) selectedGroupId.value = null
    await refreshAll()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e?.message || '删除失败')
  }
}

// --------------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------------- //

function getDomain(url: string): string {
  try {
    return new URL(url).hostname
  } catch {
    return url
  }
}

function getInitial(title: string): string {
  if (!title) return '?'
  return title.charAt(0).toUpperCase()
}

function onFaviconError(e: Event, title: string) {
  const img = e.target as HTMLImageElement
  img.style.display = 'none'
  // Show the fallback sibling (letter avatar)
  const fallback = img.nextElementSibling as HTMLElement
  if (fallback) fallback.style.display = 'flex'
}

function onPreviewError(e: Event) {
  const img = e.target as HTMLImageElement
  img.style.display = 'none'
}

// --------------------------------------------------------------------------- //
// Lifecycle
// --------------------------------------------------------------------------- //

onMounted(() => {
  refreshAll()
})
</script>

<style scoped>
.bm-page {
  padding: 24px 32px;
  max-width: 1400px;
  margin: 0 auto;
}

/* Header */
.bm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
.bm-header-left { display: flex; align-items: baseline; gap: 12px; }
.bm-title { font-size: 22px; font-weight: 700; color: var(--sl-text); }
.bm-subtitle { font-size: 13px; color: var(--sl-text-muted); }
.bm-header-actions { display: flex; gap: 8px; }

/* Section labels (TOP5, Pinned) */
.bm-section-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--sl-text-secondary);
  margin-bottom: 10px;
}
.bm-section-label .el-icon { color: var(--sl-accent); }

/* TOP5 */
.bm-top5 {
  margin-bottom: 20px;
  background: var(--sl-bg-elevated);
  border: 1px solid var(--sl-border);
  border-radius: var(--sl-radius-md);
  padding: 14px 16px;
}
.bm-top5-list {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 4px;
}
.bm-top5-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: var(--sl-bg);
  border: 1px solid var(--sl-border);
  border-radius: var(--sl-radius-sm);
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
  flex-shrink: 0;
}
.bm-top5-card:hover { border-color: var(--sl-accent-border); box-shadow: var(--sl-shadow-sm); }
.bm-top5-rank {
  font-size: 15px;
  font-weight: 700;
  color: var(--sl-accent);
  min-width: 18px;
}
.bm-top5-favicon { width: 20px; height: 20px; border-radius: 4px; flex-shrink: 0; }
.bm-top5-info { display: flex; flex-direction: column; gap: 1px; }
.bm-top5-name { font-size: 13px; font-weight: 500; color: var(--sl-text); max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bm-top5-count { font-size: 11px; color: var(--sl-text-muted); }

/* Pinned */
.bm-pinned {
  margin-bottom: 20px;
  background: var(--sl-bg-elevated);
  border: 1px solid var(--sl-border);
  border-radius: var(--sl-radius-md);
  padding: 14px 16px;
}
.bm-pinned-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.bm-pinned-card {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--sl-accent-subtle);
  border: 1px solid var(--sl-accent-border);
  border-radius: var(--sl-radius-sm);
  cursor: pointer;
  transition: background 0.15s;
}
.bm-pinned-card:hover { background: var(--sl-accent-muted); }
.bm-pinned-favicon { width: 16px; height: 16px; border-radius: 3px; flex-shrink: 0; }
.bm-pinned-name { font-size: 13px; color: var(--sl-text); max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bm-pinned-unpin { color: var(--sl-accent); cursor: pointer; font-size: 14px; }

/* Split layout */
.bm-split {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}

/* Left sidebar */
.bm-sidebar {
  width: 240px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.bm-sidebar-section {
  background: var(--sl-bg-elevated);
  border: 1px solid var(--sl-border);
  border-radius: var(--sl-radius-md);
  padding: 12px;
}
.bm-sidebar-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--sl-text-muted);
  margin-bottom: 8px;
  padding-left: 4px;
}
.bm-group-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 10px;
  border: none;
  background: none;
  border-radius: var(--el-border-radius-small);
  cursor: pointer;
  font-size: 13px;
  color: var(--sl-text-secondary);
  transition: background 0.12s, color 0.12s;
  text-align: left;
}
.bm-group-item:hover { background: var(--sl-sidebar-hover); }
.bm-group-item.active { background: var(--sl-sidebar-active); color: var(--sl-text); font-weight: 500; }
.bm-group-item .el-icon { font-size: 15px; color: var(--sl-text-muted); }
.bm-group-item.active .el-icon { color: var(--sl-accent); }
.bm-group-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bm-group-count {
  font-size: 11px;
  color: var(--sl-text-faint);
  background: var(--sl-bg);
  padding: 1px 7px;
  border-radius: 8px;
}

/* Tag filter */
.bm-tag-filter-list { display: flex; flex-wrap: wrap; gap: 6px; }
.bm-tag-chip {
  padding: 3px 10px;
  border: 1px solid var(--sl-border);
  border-radius: 12px;
  background: none;
  cursor: pointer;
  font-size: 12px;
  color: var(--sl-text-secondary);
  transition: all 0.12s;
}
.bm-tag-chip:hover { border-color: var(--tag-color, var(--sl-accent-border)); }
.bm-tag-chip.active {
  background: var(--tag-color, var(--sl-accent));
  border-color: var(--tag-color, var(--sl-accent));
  color: #fff;
}

/* Right main */
.bm-main { flex: 1; min-width: 0; }
.bm-toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
}
.bm-search { flex: 1; }
.bm-view-toggle { display: flex; gap: 4px; }
.bm-view-btn {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--sl-border);
  border-radius: var(--el-border-radius-small);
  background: var(--sl-bg-elevated);
  cursor: pointer;
  color: var(--sl-text-muted);
  transition: all 0.12s;
}
.bm-view-btn.active { border-color: var(--sl-accent); color: var(--sl-accent); background: var(--sl-accent-subtle); }

/* Empty / loading */
.bm-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 60px 20px;
  color: var(--sl-text-muted);
  font-size: 14px;
}
.bm-empty-icon { color: var(--sl-text-faint); }

/* Card grid */
.bm-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
}
.bm-card {
  background: var(--sl-bg-elevated);
  border: 1px solid var(--sl-border);
  border-radius: var(--sl-radius-md);
  padding: 14px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.bm-card:hover { border-color: var(--sl-accent-border); box-shadow: var(--sl-shadow-md); }
.bm-card-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.bm-card-favicon { width: 24px; height: 24px; border-radius: 6px; flex-shrink: 0; }
.bm-card-meta { flex: 1; min-width: 0; }
.bm-card-title {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--sl-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bm-card-domain { font-size: 11px; color: var(--sl-text-muted); }
.bm-card-pin {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: none;
  border-radius: 6px;
  cursor: pointer;
  color: var(--sl-text-faint);
  transition: all 0.12s;
}
.bm-card-pin:hover { background: var(--sl-accent-subtle); color: var(--sl-accent); }
.bm-card-pin.active { color: var(--sl-accent); }
.bm-card-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 10px; min-height: 4px; }
.bm-card-tag {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--tag-color, #64748b) 12%, transparent);
  color: var(--tag-color, #64748b);
  border: 1px solid color-mix(in srgb, var(--tag-color, #64748b) 25%, transparent);
}
.bm-card-footer { display: flex; align-items: center; justify-content: space-between; }
.bm-card-access {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--sl-text-muted);
}
.bm-card-access .el-icon { font-size: 13px; }
.bm-card-actions { display: flex; gap: 4px; }
.bm-icon-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: none;
  border-radius: 6px;
  cursor: pointer;
  color: var(--sl-text-muted);
  transition: all 0.12s;
}
.bm-icon-btn:hover { background: var(--sl-bg); color: var(--sl-text); }
.bm-icon-btn--danger:hover { color: #dc2626; background: rgba(220, 38, 38, 0.08); }

/* List view */
.bm-list-view { display: flex; flex-direction: column; gap: 2px; }
.bm-list-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: var(--sl-bg-elevated);
  border: 1px solid var(--sl-border);
  border-radius: var(--sl-radius-sm);
  cursor: pointer;
  transition: border-color 0.12s;
}
.bm-list-row:hover { border-color: var(--sl-accent-border); }
.bm-list-favicon { width: 20px; height: 20px; border-radius: 4px; flex-shrink: 0; }
.bm-list-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.bm-list-title { font-size: 13px; font-weight: 500; color: var(--sl-text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bm-list-url { font-size: 11px; color: var(--sl-text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bm-list-tags { display: flex; gap: 4px; flex-shrink: 0; }
.bm-list-access { font-size: 12px; color: var(--sl-text-muted); min-width: 60px; text-align: right; }
.bm-list-actions { display: flex; gap: 4px; }

/* Favicon fallback */
.bm-favicon-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #f0f0f0, #e0e0e0);
  color: var(--sl-text-muted);
  font-size: 12px;
  font-weight: 600;
  border-radius: 6px;
}

/* Dialogs */
.bm-form { padding: 0 4px; }
.bm-url-row { display: flex; gap: 8px; width: 100%; }
.bm-url-row .el-input { flex: 1; }
.bm-full-width { width: 100%; }
.bm-favicon-preview { display: flex; align-items: center; gap: 8px; }
.bm-preview-img { width: 24px; height: 24px; border-radius: 4px; }
.bm-favicon-url { font-size: 12px; color: var(--sl-text-muted); word-break: break-all; }

/* Tag management */
.bm-tag-mgmt { display: flex; flex-direction: column; gap: 16px; }
.bm-tag-add-row { display: flex; align-items: center; gap: 8px; }
.bm-tag-name-input { flex: 1; }
.bm-tag-list { display: flex; flex-direction: column; gap: 8px; }
.bm-tag-row { display: flex; align-items: center; gap: 8px; }
.bm-tag-color-dot { width: 16px; height: 16px; border-radius: 50%; flex-shrink: 0; }
.bm-tag-edit-name { flex: 1; }

/* Group management */
.bm-group-mgmt { display: flex; flex-direction: column; gap: 16px; }
.bm-group-add-row { display: flex; gap: 8px; }
.bm-group-add-row .el-input { flex: 1; }
.bm-group-list { display: flex; flex-direction: column; gap: 8px; }
.bm-group-row { display: flex; align-items: center; gap: 8px; }
.bm-group-row > .el-icon { color: var(--sl-text-muted); }
.bm-group-edit-name { flex: 1; }
.bm-group-edit-count { font-size: 12px; color: var(--sl-text-muted); white-space: nowrap; }

.bm-empty-mini { text-align: center; color: var(--sl-text-muted); font-size: 13px; padding: 20px; }
</style>
