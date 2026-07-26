<template>
  <div class="page-container skills-page">
    <div class="page-header">
      <div>
        <h3>Agent 资源 · Skills 管理</h3>
        <p class="page-sub">持久化管理 识别结果：导入、标签筛选、版本历史与 zip 导出</p>
      </div>
      <div class="header-actions">
        <el-button @click="openTagManager">标签管理</el-button>
        <el-dropdown trigger="click" @command="onImportCommand">
          <el-button type="primary">
            导入 / 新建
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="zip">上传 Zip</el-dropdown-item>
              <el-dropdown-item command="folder">上传文件夹</el-dropdown-item>
              <el-dropdown-item command="github">从 GitHub 拉取</el-dropdown-item>
              <el-dropdown-item command="create" divided>新建空 Skill</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <div class="page-body">
      <el-card class="section-card filter-card" shadow="never">
        <div class="filter-row">
          <el-input
            v-model="keyword"
            clearable
            placeholder="搜索 name / description"
            class="filter-search"
            @keyup.enter="loadSkills"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-select
            v-model="selectedTagIds"
            multiple
            clearable
            collapse-tags
            collapse-tags-tooltip
            placeholder="标签筛选（任一匹配）"
            class="filter-tags"
          >
            <el-option
              v-for="tag in tags"
              :key="tag.id"
              :label="tag.name"
              :value="tag.id"
            >
              <span class="tag-option">
                <span class="tag-dot" :style="{ background: tag.color }" />
                {{ tag.name }}
              </span>
            </el-option>
          </el-select>
          <el-button type="primary" :loading="loading" @click="loadSkills">筛选</el-button>
        </div>
      </el-card>

      <el-card class="section-card" shadow="never" v-loading="loading">
        <el-table :data="skills" stripe empty-text="暂无 Skill，点击右上角导入" @row-click="openDetail">
          <el-table-column prop="name" label="Name" min-width="160">
            <template #default="{ row }">
              <span class="skill-name">{{ row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="Description" min-width="280">
            <template #default="{ row }">
              <button
                type="button"
                class="desc-link"
                :title="'点击查看完整描述'"
                @click.stop="openDescDialog(row)"
              >
                {{ row.description || '—' }}
              </button>
            </template>
          </el-table-column>
          <el-table-column label="标签" min-width="160">
            <template #default="{ row }">
              <div class="tag-list">
                <el-tag
                  v-for="t in row.tags"
                  :key="t.id"
                  size="small"
                  class="skill-tag"
                  :style="{ '--tag-color': t.color }"
                >
                  {{ t.name }}
                </el-tag>
                <span v-if="!row.tags?.length" class="muted">—</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="current_version" label="版本" width="80" align="center">
            <template #default="{ row }">v{{ row.current_version }}</template>
          </el-table-column>
          <el-table-column label="更新" width="170">
            <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click.stop="openDetail(row)">详情</el-button>
              <el-button link type="primary" @click.stop="downloadSkill(row.id)">下载</el-button>
              <el-button link type="danger" @click.stop="removeSkill(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <!-- Detail drawer -->
    <el-drawer
      v-model="detailOpen"
      size="56%"
      :title="detail?.name ? `Skill · ${detail.name}` : 'Skill 详情'"
      destroy-on-close
      @closed="onDetailClosed"
    >
      <div v-if="detail" class="detail" v-loading="detailLoading">
        <div class="detail-meta">
          <p class="detail-desc">{{ detail.description }}</p>
          <div class="detail-stats">
            <span>当前 v{{ detail.current_version }}</span>
            <span>{{ formatBytes(detail.size_bytes) }}</span>
            <span>更新 {{ formatTime(detail.updated_at) }}</span>
          </div>
          <div class="detail-actions">
            <el-button type="primary" @click="downloadSkill(detail.id)">下载 Zip</el-button>
            <el-button @click="startEditMd">编辑 SKILL.md</el-button>
            <el-button @click="triggerReplaceZip">替换整包</el-button>
            <input
              ref="replaceZipInput"
              type="file"
              accept=".zip,application/zip"
              class="hidden-input"
              @change="onReplaceZip"
            />
          </div>
        </div>

        <el-divider content-position="left">标签</el-divider>
        <div class="detail-tags">
          <el-select
            v-model="detailTagIds"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="选择或创建标签"
            class="detail-tag-select"
            @change="onDetailTagsChange"
          >
            <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id">
              <span class="tag-option">
                <span class="tag-dot" :style="{ background: tag.color }" />
                {{ tag.name }}
              </span>
            </el-option>
          </el-select>
        </div>

        <el-divider content-position="left">SKILL.md</el-divider>
        <div v-if="editingMd" class="editor-block">
          <div ref="editorHost" class="cm-host" />
          <el-input
            v-model="editChangelog"
            class="changelog-input"
            placeholder="变更说明（必填）"
          />
          <div class="editor-actions">
            <el-button @click="cancelEditMd">取消</el-button>
            <el-button type="primary" :loading="savingMd" @click="saveSkillMd">保存为新版本</el-button>
          </div>
        </div>
        <div v-else class="md-preview markdown-body" v-html="previewHtml" />

        <el-divider content-position="left">文件清单</el-divider>
        <ul class="file-list">
          <li v-for="f in detail.files" :key="f">{{ f }}</li>
        </ul>

        <el-divider content-position="left">版本历史</el-divider>
        <el-timeline>
          <el-timeline-item
            v-for="v in detail.versions"
            :key="v.version"
            :timestamp="formatTime(v.created_at)"
            :type="v.version === detail.current_version ? 'primary' : undefined"
          >
            <div class="version-row">
              <strong>v{{ v.version }}</strong>
              <span class="muted">{{ formatBytes(v.size_bytes) }}</span>
              <span>{{ v.changelog }}</span>
              <span class="version-actions">
                <el-button link type="primary" @click="downloadSkill(detail.id, v.version)">下载</el-button>
                <el-button
                  v-if="v.version !== detail.current_version"
                  link
                  type="warning"
                  @click="restoreVersion(v.version)"
                >
                  恢复
                </el-button>
              </span>
            </div>
          </el-timeline-item>
        </el-timeline>
      </div>
    </el-drawer>

    <!-- Import dialogs -->
    <el-dialog v-model="zipDialog" title="上传 Zip" width="480px" destroy-on-close>
      <el-upload drag :auto-upload="false" :limit="1" accept=".zip,application/zip" :on-change="onZipPick">
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽或点击选择 zip（≤5MB）</div>
      </el-upload>
      <el-input v-model="importChangelog" class="mt-12" placeholder="变更说明（必填）" />
      <template #footer>
        <el-button @click="zipDialog = false">取消</el-button>
        <el-button type="primary" :loading="importing" :disabled="!zipFile" @click="submitZip">导入</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="folderDialog" title="上传文件夹" width="480px" destroy-on-close>
      <p class="hint">选择 Skill 根文件夹（内含 SKILL.md）。浏览器会展开目录内文件。</p>
      <input ref="folderInput" type="file" class="hidden-input" webkitdirectory multiple @change="onFolderPick" />
      <el-button @click="folderInput?.click()">选择文件夹</el-button>
      <p v-if="folderFiles.length" class="hint">已选 {{ folderFiles.length }} 个文件</p>
      <el-input v-model="importChangelog" class="mt-12" placeholder="变更说明（必填）" />
      <template #footer>
        <el-button @click="folderDialog = false">取消</el-button>
        <el-button type="primary" :loading="importing" :disabled="!folderFiles.length" @click="submitFolder">
          导入
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="githubDialog" title="从 GitHub 拉取" width="520px" destroy-on-close>
      <el-input
        v-model="githubUrl"
        placeholder="https://github.com/owner/repo 或 .../tree/main/path/to/skill"
      />
      <el-input v-model="importChangelog" class="mt-12" placeholder="变更说明（必填）" />
      <template #footer>
        <el-button @click="githubDialog = false">取消</el-button>
        <el-button type="primary" :loading="importing" :disabled="!githubUrl.trim()" @click="submitGithub">
          拉取并导入
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="createDialog" title="新建空 Skill" width="480px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="name（= 文件夹名）" required>
          <el-input v-model="createName" placeholder="my-skill" />
        </el-form-item>
        <el-form-item label="description" required>
          <el-input v-model="createDesc" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="变更说明" required>
          <el-input v-model="importChangelog" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="descDialogOpen"
      :title="descDialogTitle"
      width="560px"
      destroy-on-close
    >
      <p class="desc-dialog-body">{{ descDialogText }}</p>
    </el-dialog>

    <!-- Tag manager -->
    <el-dialog v-model="tagManagerOpen" title="标签管理" width="560px" destroy-on-close>
      <div class="tag-create-row">
        <el-input v-model="newTagName" placeholder="新标签名" />
        <el-color-picker v-model="newTagColor" />
        <el-button type="primary" :loading="tagSaving" @click="createTag">添加</el-button>
      </div>
      <el-table :data="tags" size="small" class="mt-12">
        <el-table-column label="颜色" width="70">
          <template #default="{ row }">
            <el-color-picker
              :model-value="row.color"
              size="small"
              @change="(c: string | null) => updateTagColor(row, c)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" />
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button link type="danger" @click="removeTag(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, shallowRef, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { ArrowDown, Search, UploadFilled } from '@element-plus/icons-vue'
import { EditorState } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, drawSelection, highlightActiveLine } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { markdown } from '@codemirror/lang-markdown'
import { syntaxHighlighting, defaultHighlightStyle, bracketMatching } from '@codemirror/language'
import { apiDelete, apiDownloadGet, apiGet, apiPatch, apiPost } from '../../composables/useApi'
import { renderMarkdownHtml } from '../doc_tools/md_reader/renderMarkdown'
import 'katex/dist/katex.min.css'
import 'highlight.js/styles/github.css'

interface TagItem {
  id: number
  name: string
  color: string
}

interface SkillListItem {
  id: number
  name: string
  description: string
  current_version: number
  created_at: string | null
  updated_at: string | null
  tags: TagItem[]
}

interface VersionItem {
  id: number
  version: number
  changelog: string
  size_bytes: number
  created_at: string | null
}

interface SkillDetail extends SkillListItem {
  skill_md: string
  files: string[]
  size_bytes: number
  versions: VersionItem[]
}

const API = '/agent-resources/admin'

const skills = ref<SkillListItem[]>([])
const tags = ref<TagItem[]>([])
const loading = ref(false)
const keyword = ref('')
const selectedTagIds = ref<number[]>([])

const detailOpen = ref(false)
const detailLoading = ref(false)
const detail = ref<SkillDetail | null>(null)
const detailTagIds = ref<number[]>([])
let tagging = false

const editingMd = ref(false)
const editChangelog = ref('')
const savingMd = ref(false)
const editorHost = ref<HTMLElement | null>(null)
const editorView = shallowRef<EditorView | null>(null)

const zipDialog = ref(false)
const folderDialog = ref(false)
const githubDialog = ref(false)
const createDialog = ref(false)
const importing = ref(false)
const importChangelog = ref('初始版本')
const zipFile = ref<File | null>(null)
const folderFiles = ref<File[]>([])
const folderInput = ref<HTMLInputElement | null>(null)
const githubUrl = ref('')
const createName = ref('')
const createDesc = ref('')
const replaceZipInput = ref<HTMLInputElement | null>(null)

const tagManagerOpen = ref(false)
const newTagName = ref('')
const newTagColor = ref('#64748b')
const tagSaving = ref(false)

const descDialogOpen = ref(false)
const descDialogTitle = ref('')
const descDialogText = ref('')

function openDescDialog(row: SkillListItem) {
  descDialogTitle.value = row.name ? `描述 · ${row.name}` : '描述'
  descDialogText.value = row.description || '（无描述）'
  descDialogOpen.value = true
}

const previewHtml = computed(() => {
  if (!detail.value?.skill_md) return ''
  return renderMarkdownHtml(detail.value.skill_md)
})

watch(selectedTagIds, () => {
  loadSkills()
})

function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString()
}

function formatBytes(n: number | undefined): string {
  if (!n && n !== 0) return '—'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(2)} MB`
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function loadTags() {
  const res = await apiGet<{ items: TagItem[] }>(`${API}/tags`)
  tags.value = res.items || []
}

async function loadSkills() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (keyword.value.trim()) params.q = keyword.value.trim()
    if (selectedTagIds.value.length) params.tag_ids = selectedTagIds.value.join(',')
    const res = await apiGet<{ items: SkillListItem[] }>(`${API}/skills`, params)
    skills.value = res.items || []
  } catch (e: any) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function openDetail(row: SkillListItem) {
  detailOpen.value = true
  detailLoading.value = true
  editingMd.value = false
  try {
    const data = await apiGet<SkillDetail>(`${API}/skills/${row.id}`)
    detail.value = data
    detailTagIds.value = (data.tags || []).map((t) => t.id)
  } catch (e: any) {
    ElMessage.error(e.message || '加载详情失败')
    detailOpen.value = false
  } finally {
    detailLoading.value = false
  }
}

function onDetailClosed() {
  detail.value = null
  destroyEditor()
  editingMd.value = false
}

async function downloadSkill(id: number, version?: number) {
  try {
    const { blob, filename } = await apiDownloadGet(
      `${API}/skills/${id}/download`,
      version != null ? { version } : undefined,
      'skill.zip',
    )
    triggerDownload(blob, filename)
  } catch (e: any) {
    ElMessage.error(e.message || '下载失败')
  }
}

async function removeSkill(row: SkillListItem) {
  try {
    await ElMessageBox.confirm(`确定删除 Skill「${row.name}」？此操作不可恢复。`, '删除确认', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await apiDelete(`${API}/skills/${row.id}`)
    ElMessage.success('已删除')
    if (detail.value?.id === row.id) detailOpen.value = false
    await loadSkills()
  } catch (e: any) {
    ElMessage.error(e.message || '删除失败')
  }
}

async function ensureTagByName(name: string): Promise<number | null> {
  const existing = tags.value.find((t) => t.name === name)
  if (existing) return existing.id
  const created = await apiPost<TagItem>(`${API}/tags`, {
    name,
    color: newTagColor.value || '#64748b',
  })
  tags.value = [...tags.value, created].sort((a, b) => a.name.localeCompare(b.name))
  return created.id
}

async function onDetailTagsChange(values: Array<string | number>) {
  if (!detail.value || tagging) return
  tagging = true
  try {
    const ids: number[] = []
    for (const v of values) {
      if (typeof v === 'number') {
        ids.push(v)
      } else {
        const id = await ensureTagByName(String(v).trim())
        if (id != null) ids.push(id)
      }
    }
    const updated = await apiPost<SkillDetail>(`${API}/skills/${detail.value.id}/tags`, {
      tag_ids: ids,
    })
    detail.value = { ...detail.value, ...updated, skill_md: detail.value.skill_md, files: detail.value.files, versions: detail.value.versions }
    detailTagIds.value = (updated.tags || []).map((t) => t.id)
    await loadSkills()
  } catch (e: any) {
    ElMessage.error(e.message || '更新标签失败')
    detailTagIds.value = (detail.value.tags || []).map((t) => t.id)
  } finally {
    tagging = false
  }
}

function destroyEditor() {
  editorView.value?.destroy()
  editorView.value = null
}

async function startEditMd() {
  if (!detail.value) return
  editingMd.value = true
  editChangelog.value = ''
  await nextTick()
  destroyEditor()
  if (!editorHost.value) return
  const state = EditorState.create({
    doc: detail.value.skill_md,
    extensions: [
      lineNumbers(),
      drawSelection(),
      highlightActiveLine(),
      history(),
      bracketMatching(),
      syntaxHighlighting(defaultHighlightStyle),
      markdown(),
      keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
      EditorView.lineWrapping,
      EditorView.theme({
        '&': { height: '360px', fontSize: '13px' },
        '.cm-scroller': { overflow: 'auto', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace' },
      }),
    ],
  })
  editorView.value = new EditorView({ state, parent: editorHost.value })
}

function cancelEditMd() {
  destroyEditor()
  editingMd.value = false
}

async function saveSkillMd() {
  if (!detail.value || !editorView.value) return
  const content = editorView.value.state.doc.toString()
  const changelog = editChangelog.value.trim()
  if (!changelog) {
    ElMessage.warning('请填写变更说明')
    return
  }
  savingMd.value = true
  try {
    const updated = await apiPost<SkillDetail>(`${API}/skills/${detail.value.id}/skill-md`, {
      content,
      changelog,
    })
    detail.value = updated
    detailTagIds.value = (updated.tags || []).map((t) => t.id)
    editingMd.value = false
    destroyEditor()
    ElMessage.success(`已保存为 v${updated.current_version}`)
    await loadSkills()
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    savingMd.value = false
  }
}

function triggerReplaceZip() {
  replaceZipInput.value?.click()
}

async function onReplaceZip(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !detail.value) return
  let changelog = ''
  try {
    const { value } = await ElMessageBox.prompt('请填写变更说明', '替换整包', {
      inputPlaceholder: '例如：同步上游更新',
      confirmButtonText: '上传',
    })
    changelog = (value || '').trim()
  } catch {
    return
  }
  if (!changelog) {
    ElMessage.warning('变更说明不能为空')
    return
  }
  const fd = new FormData()
  fd.append('file', file)
  fd.append('changelog', changelog)
  detailLoading.value = true
  try {
    const res = await fetch(`${API}/skills/${detail.value.id}/replace-zip`, { method: 'POST', body: fd })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail))
    }
    detail.value = await res.json()
    ElMessage.success('已替换并生成新版本')
    await loadSkills()
  } catch (e: any) {
    ElMessage.error(e.message || '替换失败')
  } finally {
    detailLoading.value = false
  }
}

async function restoreVersion(version: number) {
  if (!detail.value) return
  let changelog = `恢复自 v${version}`
  try {
    const { value } = await ElMessageBox.prompt('变更说明', `恢复到 v${version}`, {
      inputValue: changelog,
      confirmButtonText: '恢复为新版本',
    })
    changelog = (value || '').trim() || changelog
  } catch {
    return
  }
  detailLoading.value = true
  try {
    const updated = await apiPost<SkillDetail>(
      `${API}/skills/${detail.value.id}/restore/${version}`,
      { changelog },
    )
    detail.value = updated
    ElMessage.success(`已恢复为 v${updated.current_version}`)
    await loadSkills()
  } catch (e: any) {
    ElMessage.error(e.message || '恢复失败')
  } finally {
    detailLoading.value = false
  }
}

function onImportCommand(cmd: string) {
  importChangelog.value = cmd === 'create' ? '初始版本' : '导入'
  zipFile.value = null
  folderFiles.value = []
  githubUrl.value = ''
  createName.value = ''
  createDesc.value = ''
  if (cmd === 'zip') zipDialog.value = true
  else if (cmd === 'folder') folderDialog.value = true
  else if (cmd === 'github') githubDialog.value = true
  else if (cmd === 'create') createDialog.value = true
}

function onZipPick(file: UploadFile) {
  zipFile.value = (file.raw as File) || null
}

function onFolderPick(ev: Event) {
  const input = ev.target as HTMLInputElement
  folderFiles.value = Array.from(input.files || [])
}

async function submitZip() {
  if (!zipFile.value) return
  if (!importChangelog.value.trim()) {
    ElMessage.warning('请填写变更说明')
    return
  }
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', zipFile.value)
    fd.append('changelog', importChangelog.value.trim())
    const res = await fetch(`${API}/skills/from-zip`, { method: 'POST', body: fd })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail))
    }
    const data = (await res.json()) as SkillDetail
    ElMessage.success(`已导入 ${data.name} v${data.current_version}`)
    zipDialog.value = false
    await loadSkills()
    openDetail(data)
  } catch (e: any) {
    ElMessage.error(e.message || '导入失败')
  } finally {
    importing.value = false
  }
}

async function submitFolder() {
  if (!folderFiles.value.length) return
  if (!importChangelog.value.trim()) {
    ElMessage.warning('请填写变更说明')
    return
  }
  importing.value = true
  try {
    const fd = new FormData()
    for (const f of folderFiles.value) {
      const rel = (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name
      fd.append('files', f, rel)
    }
    fd.append('changelog', importChangelog.value.trim())
    const res = await fetch(`${API}/skills/from-files`, { method: 'POST', body: fd })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail))
    }
    const data = (await res.json()) as SkillDetail
    ElMessage.success(`已导入 ${data.name} v${data.current_version}`)
    folderDialog.value = false
    await loadSkills()
    openDetail(data)
  } catch (e: any) {
    ElMessage.error(e.message || '导入失败')
  } finally {
    importing.value = false
  }
}

async function submitGithub() {
  if (!githubUrl.value.trim()) return
  if (!importChangelog.value.trim()) {
    ElMessage.warning('请填写变更说明')
    return
  }
  importing.value = true
  try {
    const data = await apiPost<SkillDetail>(`${API}/skills/from-github`, {
      url: githubUrl.value.trim(),
      changelog: importChangelog.value.trim(),
    })
    ElMessage.success(`已导入 ${data.name} v${data.current_version}`)
    githubDialog.value = false
    await loadSkills()
    openDetail(data)
  } catch (e: any) {
    ElMessage.error(e.message || '拉取失败')
  } finally {
    importing.value = false
  }
}

async function submitCreate() {
  if (!createName.value.trim() || !createDesc.value.trim()) {
    ElMessage.warning('请填写 name 与 description')
    return
  }
  if (!importChangelog.value.trim()) {
    ElMessage.warning('请填写变更说明')
    return
  }
  importing.value = true
  try {
    const data = await apiPost<SkillDetail>(`${API}/skills`, {
      name: createName.value.trim(),
      description: createDesc.value.trim(),
      changelog: importChangelog.value.trim(),
    })
    ElMessage.success(`已创建 ${data.name}`)
    createDialog.value = false
    await loadSkills()
    openDetail(data)
  } catch (e: any) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    importing.value = false
  }
}

function openTagManager() {
  tagManagerOpen.value = true
}

async function createTag() {
  const name = newTagName.value.trim()
  if (!name) {
    ElMessage.warning('请输入标签名')
    return
  }
  tagSaving.value = true
  try {
    await apiPost(`${API}/tags`, { name, color: newTagColor.value || '#64748b' })
    newTagName.value = ''
    await loadTags()
    ElMessage.success('已添加')
  } catch (e: any) {
    ElMessage.error(e.message || '添加失败')
  } finally {
    tagSaving.value = false
  }
}

async function updateTagColor(row: TagItem, color: string | null) {
  if (!color) return
  try {
    await apiPatch(`${API}/tags/${row.id}`, { color })
    row.color = color
    await loadTags()
    await loadSkills()
    if (detail.value) {
      detail.value.tags = detail.value.tags.map((t) =>
        t.id === row.id ? { ...t, color } : t,
      )
    }
  } catch (e: any) {
    ElMessage.error(e.message || '更新颜色失败')
  }
}

async function removeTag(row: TagItem) {
  try {
    await ElMessageBox.confirm(`删除标签「${row.name}」？`, '确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await apiDelete(`${API}/tags/${row.id}`)
    await loadTags()
    await loadSkills()
    if (detail.value) {
      detailTagIds.value = detailTagIds.value.filter((id) => id !== row.id)
    }
  } catch (e: any) {
    ElMessage.error(e.message || '删除失败')
  }
}

onMounted(async () => {
  try {
    await Promise.all([loadTags(), loadSkills()])
  } catch (e: any) {
    ElMessage.error(e.message || '初始化失败')
  }
})
</script>

<style scoped>
.skills-page .page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.filter-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.filter-search {
  width: min(320px, 100%);
}

.filter-tags {
  min-width: 260px;
  flex: 1;
}

.skill-name {
  font-weight: 600;
  color: #0f172a;
}

.desc-link {
  display: block;
  width: 100%;
  max-width: 100%;
  padding: 0;
  border: none;
  background: none;
  text-align: left;
  font: inherit;
  color: #334155;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.desc-link:hover {
  color: #0369a1;
  text-decoration: underline;
}

.desc-dialog-body {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  color: #334155;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.skill-tag {
  border-color: color-mix(in srgb, var(--tag-color) 40%, transparent);
  background: color-mix(in srgb, var(--tag-color) 14%, white);
  color: color-mix(in srgb, var(--tag-color) 80%, #0f172a);
}

.tag-option {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.tag-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.muted {
  color: #94a3b8;
}

.detail-desc {
  margin: 0 0 8px;
  color: #334155;
  line-height: 1.5;
}

.detail-stats {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  font-size: 13px;
  color: #64748b;
  margin-bottom: 12px;
}

.detail-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.detail-tag-select {
  width: 100%;
}

.md-preview {
  padding: 12px 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  max-height: 480px;
  overflow: auto;
}

.file-list {
  margin: 0;
  padding-left: 18px;
  color: #475569;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
}

.version-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  align-items: baseline;
}

.version-actions {
  margin-left: auto;
}

.cm-host {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 10px;
}

.changelog-input {
  margin-bottom: 10px;
}

.editor-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.hidden-input {
  display: none;
}

.hint {
  color: #64748b;
  font-size: 13px;
  margin: 0 0 10px;
}

.mt-12 {
  margin-top: 12px;
}

.tag-create-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.tag-create-row .el-input {
  flex: 1;
}
</style>
