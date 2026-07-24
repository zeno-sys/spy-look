<template>
  <div class="page-container md-reader">
    <div class="page-header">
      <div><h3>文档工具 · MD 编辑器</h3></div>
      <div class="header-actions">
        <el-button size="small" :disabled="busy" @click="createDocument">新建</el-button>
        <el-button size="small" :disabled="busy" @click="createFromClipboard">粘贴新建</el-button>
        <el-upload
          :show-file-list="false"
          accept=".md,.markdown,.txt"
          :disabled="busy"
          :http-request="onUploadMd"
        >
          <el-button size="small" :disabled="busy">上传 .md</el-button>
        </el-upload>
        <el-button
          size="small"
          :disabled="!currentId || busy"
          @click="downloadCurrent"
        >
          下载当前
        </el-button>
      </div>
    </div>

    <div class="page-body reader-body">
      <aside class="file-pane" :class="{ collapsed: filePaneCollapsed }">
        <div class="pane-header">
          <template v-if="!filePaneCollapsed">
            <span class="pane-header-title">
              文件
              <em v-if="documents.length">{{ documents.length }}</em>
            </span>
            <div class="pane-header-actions">
              <el-button
                link
                size="small"
                title="新建"
                :disabled="busy"
                @click="createDocument"
              >
                <el-icon :size="15"><Plus /></el-icon>
              </el-button>
              <el-upload
                :show-file-list="false"
                accept=".md,.markdown,.txt"
                :disabled="busy"
                :http-request="onUploadMd"
              >
                <el-button link size="small" title="上传" :disabled="busy">
                  <el-icon :size="15"><Upload /></el-icon>
                </el-button>
              </el-upload>
              <el-button
                link
                size="small"
                :title="filePaneCollapsed ? '展开文件列表' : '收起文件列表'"
                @click="filePaneCollapsed = !filePaneCollapsed"
              >
                <el-icon :size="14"><DArrowLeft /></el-icon>
              </el-button>
            </div>
          </template>
          <el-button
            v-else
            link
            size="small"
            title="展开文件列表"
            @click="filePaneCollapsed = !filePaneCollapsed"
          >
            <el-icon :size="14"><DArrowRight /></el-icon>
          </el-button>
        </div>
        <template v-if="!filePaneCollapsed">
          <div v-if="docsLoading" class="pane-empty">加载中…</div>
          <div v-else-if="!documents.length" class="pane-empty">
            暂无文档<br />点击上方 + 新建或上传
          </div>
          <ul v-else class="file-list">
            <li
              v-for="doc in documents"
              :key="doc.id"
              :class="{ active: doc.id === currentId }"
              :title="fileTooltip(doc)"
              @click="openDocument(doc.id)"
            >
              <el-icon class="file-icon" :size="14"><Document /></el-icon>
              <span class="file-name">{{ doc.title }}</span>
              <span class="file-size">{{ formatBytes(doc.content_bytes) }}</span>
              <el-dropdown
                trigger="click"
                class="file-more"
                @command="(cmd: string | number | object) => onFileCommand(String(cmd), doc)"
              >
                <el-button link size="small" class="file-more-btn" @click.stop>
                  <el-icon :size="14"><MoreFilled /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="rename">重命名</el-dropdown-item>
                    <el-dropdown-item command="download">下载</el-dropdown-item>
                    <el-dropdown-item command="delete" divided>
                      <span class="danger-text">删除</span>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </li>
          </ul>
        </template>
      </aside>

      <section class="main-pane">
        <div class="top-bar">
          <div class="top-left">
            <template v-if="currentId">
              <el-input
                v-model="titleDraft"
                size="small"
                class="title-input"
                @change="commitRename"
              />
              <span class="save-status" :class="saveStatus">{{ saveStatusLabel }}</span>
            </template>
            <span v-else class="muted">选择或新建文档</span>
          </div>
          <div class="top-right">
            <span class="recent-label">最近</span>
            <el-button
              v-for="item in recent"
              :key="item.id"
              size="small"
              text
              type="primary"
              class="recent-btn"
              :disabled="busy"
              @click="openDocument(item.id)"
            >
              {{ truncate(item.title, 16) }}
            </el-button>
            <span v-if="!recent.length" class="muted">暂无</span>
          </div>
        </div>

        <div class="editor-toolbar">
          <el-radio-group v-model="viewMode" size="small" :disabled="!currentId">
            <el-radio-button value="source">源码</el-radio-button>
            <el-radio-button value="preview">预览</el-radio-button>
          </el-radio-group>
          <el-upload
            v-if="currentId && viewMode === 'source'"
            :show-file-list="false"
            accept="image/png,image/jpeg,image/gif,image/webp"
            :disabled="busy"
            :http-request="onUploadImage"
          >
            <el-button size="small" :disabled="busy">插入图片</el-button>
          </el-upload>
        </div>

        <div class="workspace">
          <div class="content-pane">
            <div
              v-show="viewMode === 'source'"
              ref="editorHost"
              class="editor-host"
              :class="{ 'is-active-pane': viewMode === 'source' }"
            />
            <div
              v-show="viewMode === 'preview'"
              ref="previewHost"
              class="preview-host md-preview"
              :class="{ 'is-active-pane': viewMode === 'preview' }"
              v-html="previewHtml"
            />
            <div v-if="!currentId" class="content-placeholder">从左侧打开文档开始编辑</div>
          </div>

          <aside class="outline-pane" :class="{ collapsed: outlineCollapsed }">
            <div class="pane-header">
              <span v-if="!outlineCollapsed">大纲</span>
              <el-button
                link
                size="small"
                :title="outlineCollapsed ? '展开大纲' : '收起大纲'"
                @click="outlineCollapsed = !outlineCollapsed"
              >
                <el-icon :size="14">
                  <DArrowLeft v-if="outlineCollapsed" />
                  <DArrowRight v-else />
                </el-icon>
              </el-button>
            </div>
            <ul v-if="!outlineCollapsed" class="outline-list">
              <li v-if="!outline.length" class="pane-empty">无标题</li>
              <li
                v-for="item in outline"
                :key="`${item.line}-${item.text}`"
                :class="`lv-${item.level}`"
                @click="jumpToHeading(item.line)"
              >
                {{ item.text }}
              </li>
            </ul>
          </aside>
        </div>
      </section>
    </div>

    <Teleport to="body">
      <div
        v-if="imgViewerVisible"
        class="md-img-lightbox"
        role="dialog"
        aria-modal="true"
        @click.self="closeImgViewer"
      >
        <button type="button" class="md-img-lightbox__close" title="关闭" @click="closeImgViewer">
          ×
        </button>
        <button
          v-if="imgViewerUrls.length > 1"
          type="button"
          class="md-img-lightbox__nav prev"
          title="上一张"
          @click.stop="switchImg(-1)"
        >
          ‹
        </button>
        <img
          class="md-img-lightbox__img"
          :src="imgViewerUrls[imgViewerIndex]"
          alt="预览图片"
          @click.stop
        />
        <button
          v-if="imgViewerUrls.length > 1"
          type="button"
          class="md-img-lightbox__nav next"
          title="下一张"
          @click.stop="switchImg(1)"
        >
          ›
        </button>
        <div v-if="imgViewerUrls.length > 1" class="md-img-lightbox__counter">
          {{ imgViewerIndex + 1 }} / {{ imgViewerUrls.length }}
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadRequestOptions } from 'element-plus'
import { DArrowLeft, DArrowRight, Document, MoreFilled, Plus, Upload } from '@element-plus/icons-vue'
import { EditorState } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, drawSelection, highlightActiveLine } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { markdown } from '@codemirror/lang-markdown'
import { syntaxHighlighting, defaultHighlightStyle, bracketMatching } from '@codemirror/language'
import { apiDelete, apiGet, apiPatch, apiPost } from '../../composables/useApi'
import { parseAtxOutline } from './md_reader/outline'
import { renderMarkdownHtml } from './md_reader/renderMarkdown'
import mermaid from 'mermaid'
import 'katex/dist/katex.min.css'
import 'highlight.js/styles/github.css'

interface DocListItem {
  id: number
  title: string
  content_bytes: number
  updated_at: string | null
  created_at?: string | null
}

interface DocDetail extends DocListItem {
  content: string
}

interface RecentItem {
  id: number
  title: string
  opened_at: string | null
}

type SaveStatus = 'idle' | 'dirty' | 'saving' | 'saved' | 'error'
type ViewMode = 'source' | 'preview'

const documents = ref<DocListItem[]>([])
const recent = ref<RecentItem[]>([])
const docsLoading = ref(false)
const busy = ref(false)
const currentId = ref<number | null>(null)
const content = ref('')
const titleDraft = ref('')
const viewMode = ref<ViewMode>('source')
const outlineCollapsed = ref(false)
const filePaneCollapsed = ref(false)
const saveStatus = ref<SaveStatus>('idle')
const editorHost = ref<HTMLElement | null>(null)
const previewHost = ref<HTMLElement | null>(null)
const editorView = shallowRef<EditorView | null>(null)
const imgViewerVisible = ref(false)
const imgViewerUrls = ref<string[]>([])
const imgViewerIndex = ref(0)

let saveTimer: ReturnType<typeof setTimeout> | null = null
let applyingEditor = false
let mermaidId = 0

mermaid.initialize({
  startOnLoad: false,
  securityLevel: 'strict',
  theme: 'neutral',
})

const outline = computed(() => parseAtxOutline(content.value))
const previewHtml = computed(() => renderMarkdownHtml(content.value, outline.value))

const saveStatusLabel = computed(() => {
  switch (saveStatus.value) {
    case 'dirty':
      return '未保存'
    case 'saving':
      return '保存中…'
    case 'saved':
      return '已保存'
    case 'error':
      return '保存失败'
    default:
      return ''
  }
})

function formatBytes(n: number): string {
  if (n < 1024) return `${n}B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(n < 10 * 1024 ? 1 : 0)}K`
  return `${(n / (1024 * 1024)).toFixed(1)}M`
}

function formatUpdatedAt(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (x: number) => String(x).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function fileTooltip(doc: DocListItem): string {
  const parts = [doc.title, formatBytes(doc.content_bytes)]
  const t = formatUpdatedAt(doc.updated_at)
  if (t) parts.push(`更新 ${t}`)
  return parts.join('\n')
}

async function downloadDoc(doc: DocListItem) {
  try {
    let text = ''
    if (currentId.value === doc.id) {
      text = content.value
    } else {
      const detail = await apiGet<DocDetail>(`/doc-tools/admin/documents/${doc.id}`)
      text = detail.content || ''
    }
    const name = doc.title || 'document.md'
    const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = name.toLowerCase().endsWith('.md') ? name : `${name}.md`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    ElMessage.error(e.message || '下载失败')
  }
}

function onFileCommand(cmd: string, doc: DocListItem) {
  if (cmd === 'rename') void renameDocument(doc)
  else if (cmd === 'delete') void removeDocument(doc)
  else if (cmd === 'download') void downloadDoc(doc)
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text
  return `${text.slice(0, max - 1)}…`
}

function openImgViewer(src: string) {
  const host = previewHost.value
  if (!host) return
  const imgs = Array.from(host.querySelectorAll('img'))
    .map((img) => img.currentSrc || img.getAttribute('src') || img.src)
    .filter((u): u is string => Boolean(u))
  if (!imgs.length) return
  const index = imgs.indexOf(src)
  imgViewerUrls.value = imgs
  imgViewerIndex.value = index >= 0 ? index : 0
  imgViewerVisible.value = true
}

function closeImgViewer() {
  imgViewerVisible.value = false
}

function switchImg(delta: number) {
  const n = imgViewerUrls.value.length
  if (n <= 1) return
  imgViewerIndex.value = (imgViewerIndex.value + delta + n) % n
}

function onPreviewClick(event: MouseEvent) {
  const raw = event.target
  if (!(raw instanceof Element)) return
  // Ignore mermaid / katex internals
  if (raw.closest('.mermaid-chart, .mermaid, .katex')) return
  const target = raw.closest('img')
  if (!(target instanceof HTMLImageElement)) return
  const src = target.currentSrc || target.getAttribute('src') || target.src
  if (!src) return
  event.preventDefault()
  event.stopPropagation()
  openImgViewer(src)
}

function onLightboxKeydown(event: KeyboardEvent) {
  if (!imgViewerVisible.value) return
  if (event.key === 'Escape') closeImgViewer()
  else if (event.key === 'ArrowLeft') switchImg(-1)
  else if (event.key === 'ArrowRight') switchImg(1)
}

async function refreshList() {
  docsLoading.value = true
  try {
    const res = await apiGet<{ items: DocListItem[] }>('/doc-tools/admin/documents')
    documents.value = res.items || []
  } catch (e: any) {
    ElMessage.error(e.message || '加载文档列表失败')
  } finally {
    docsLoading.value = false
  }
}

async function refreshRecent() {
  try {
    const res = await apiGet<{ items: RecentItem[] }>('/doc-tools/admin/recent')
    recent.value = res.items || []
  } catch {
    /* ignore */
  }
}

function scheduleSave() {
  if (!currentId.value) return
  saveStatus.value = 'dirty'
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    void persistContent()
  }, 1500)
}

async function persistContent() {
  if (!currentId.value) return
  const id = currentId.value
  const body = content.value
  saveStatus.value = 'saving'
  try {
    const doc = await apiPatch<DocDetail>(`/doc-tools/admin/documents/${id}`, { content: body })
    if (currentId.value === id) {
      saveStatus.value = 'saved'
      const idx = documents.value.findIndex((d) => d.id === id)
      if (idx >= 0) {
        documents.value[idx] = {
          ...documents.value[idx],
          content_bytes: doc.content_bytes,
          updated_at: doc.updated_at,
          title: doc.title,
        }
      }
    }
  } catch (e: any) {
    saveStatus.value = 'error'
    ElMessage.error(e.message || '自动保存失败')
  }
}

function destroyEditor() {
  editorView.value?.destroy()
  editorView.value = null
}

function insertAtCursor(text: string) {
  const view = editorView.value
  if (!view) {
    content.value += text
    scheduleSave()
    return
  }
  const { from, to } = view.state.selection.main
  view.dispatch({
    changes: { from, to, insert: text },
    selection: { anchor: from + text.length },
  })
}

async function uploadImageBlob(blob: Blob, filename: string): Promise<string | null> {
  if (!currentId.value) {
    ElMessage.warning('请先打开文档')
    return null
  }
  const fd = new FormData()
  fd.append('file', blob, filename)
  const res = await fetch(`/doc-tools/admin/documents/${currentId.value}/images`, {
    method: 'POST',
    body: fd,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail))
  }
  const data = await res.json()
  return data.url as string
}

function buildEditor() {
  if (!editorHost.value) return
  destroyEditor()
  const startState = EditorState.create({
    doc: content.value,
    extensions: [
      lineNumbers(),
      highlightActiveLine(),
      drawSelection(),
      history(),
      bracketMatching(),
      markdown(),
      syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
      keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
      EditorView.lineWrapping,
      EditorView.updateListener.of((update) => {
        if (!update.docChanged || applyingEditor) return
        content.value = update.state.doc.toString()
        scheduleSave()
      }),
      EditorView.domEventHandlers({
        paste(event) {
          const items = event.clipboardData?.items
          if (!items || !currentId.value) return false
          for (const item of items) {
            if (!item.type.startsWith('image/')) continue
            event.preventDefault()
            const file = item.getAsFile()
            if (!file) return true
            void (async () => {
              try {
                const url = await uploadImageBlob(file, file.name || 'paste.png')
                if (url) insertAtCursor(`\n![](${url})\n`)
              } catch (e: any) {
                ElMessage.error(e.message || '图片上传失败')
              }
            })()
            return true
          }
          return false
        },
      }),
      EditorView.theme({
        '&': { height: '100%', fontSize: '14px' },
        '.cm-scroller': { overflow: 'auto', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace' },
        '.cm-content': { minHeight: '100%' },
      }),
    ],
  })
  editorView.value = new EditorView({
    state: startState,
    parent: editorHost.value,
  })
}

function syncEditorFromContent() {
  const view = editorView.value
  if (!view) {
    buildEditor()
    return
  }
  const cur = view.state.doc.toString()
  if (cur === content.value) return
  applyingEditor = true
  view.dispatch({
    changes: { from: 0, to: view.state.doc.length, insert: content.value },
  })
  applyingEditor = false
}

async function openDocument(id: number) {
  if (busy.value) return
  if (saveTimer) {
    clearTimeout(saveTimer)
    saveTimer = null
  }
  if (currentId.value && saveStatus.value === 'dirty') {
    await persistContent()
  }
  busy.value = true
  try {
    const doc = await apiGet<DocDetail>(`/doc-tools/admin/documents/${id}`)
    currentId.value = doc.id
    titleDraft.value = doc.title
    content.value = doc.content || ''
    saveStatus.value = 'saved'
    await nextTick()
    if (viewMode.value === 'source') syncEditorFromContent()
    await refreshRecent()
  } catch (e: any) {
    ElMessage.error(e.message || '打开文档失败')
  } finally {
    busy.value = false
  }
}

async function createDocument() {
  busy.value = true
  try {
    const doc = await apiPost<DocDetail>('/doc-tools/admin/documents', {
      title: '未命名.md',
      content: '',
    })
    await refreshList()
    await openDocument(doc.id)
  } catch (e: any) {
    ElMessage.error(e.message || '新建失败')
  } finally {
    busy.value = false
  }
}

async function createFromClipboard() {
  busy.value = true
  try {
    const text = await navigator.clipboard.readText()
    if (!text.trim()) {
      ElMessage.warning('剪贴板没有文本')
      return
    }
    const doc = await apiPost<DocDetail>('/doc-tools/admin/documents', {
      title: '未命名.md',
      content: text,
    })
    await refreshList()
    await openDocument(doc.id)
    ElMessage.success('已从剪贴板新建')
  } catch (e: any) {
    ElMessage.error(e.message || '读取剪贴板失败')
  } finally {
    busy.value = false
  }
}

async function onUploadMd(options: UploadRequestOptions) {
  busy.value = true
  try {
    const fd = new FormData()
    fd.append('file', options.file as File)
    const res = await fetch('/doc-tools/admin/documents/upload', { method: 'POST', body: fd })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail))
    }
    const doc = (await res.json()) as DocDetail
    await refreshList()
    await openDocument(doc.id)
    ElMessage.success('上传成功')
    options.onSuccess?.(doc as any)
  } catch (e: any) {
    ElMessage.error(e.message || '上传失败')
    options.onError?.(e)
  } finally {
    busy.value = false
  }
}

async function onUploadImage(options: UploadRequestOptions) {
  try {
    const file = options.file as File
    const url = await uploadImageBlob(file, file.name)
    if (url) {
      insertAtCursor(`\n![](${url})\n`)
      ElMessage.success('图片已插入')
    }
    options.onSuccess?.({} as any)
  } catch (e: any) {
    ElMessage.error(e.message || '图片上传失败')
    options.onError?.(e)
  }
}

async function commitRename() {
  if (!currentId.value) return
  const title = titleDraft.value.trim()
  if (!title) {
    ElMessage.warning('标题不能为空')
    return
  }
  try {
    const doc = await apiPatch<DocDetail>(`/doc-tools/admin/documents/${currentId.value}`, { title })
    titleDraft.value = doc.title
    await refreshList()
    await refreshRecent()
  } catch (e: any) {
    ElMessage.error(e.message || '重命名失败')
  }
}

async function renameDocument(doc: DocListItem) {
  try {
    const { value } = await ElMessageBox.prompt('输入新文件名', '重命名', {
      inputValue: doc.title,
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
    const title = (value || '').trim()
    if (!title) return
    await apiPatch(`/doc-tools/admin/documents/${doc.id}`, { title })
    if (currentId.value === doc.id) titleDraft.value = title.endsWith('.md') ? title : `${title}.md`
    await refreshList()
    await refreshRecent()
  } catch {
    /* cancel */
  }
}

async function removeDocument(doc: DocListItem) {
  try {
    await ElMessageBox.confirm(`确定删除「${doc.title}」？不可恢复。`, '删除文档', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await apiDelete(`/doc-tools/admin/documents/${doc.id}`)
    if (currentId.value === doc.id) {
      currentId.value = null
      content.value = ''
      titleDraft.value = ''
      saveStatus.value = 'idle'
      destroyEditor()
    }
    await refreshList()
    await refreshRecent()
    ElMessage.success('已删除')
  } catch (e: any) {
    ElMessage.error(e.message || '删除失败')
  }
}

function downloadCurrent() {
  if (!currentId.value) return
  const name = titleDraft.value || 'document.md'
  const blob = new Blob([content.value], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name.toLowerCase().endsWith('.md') ? name : `${name}.md`
  a.click()
  URL.revokeObjectURL(url)
}

function jumpToHeading(line: number) {
  if (viewMode.value === 'source') {
    const view = editorView.value
    if (!view) return
    const max = view.state.doc.lines
    const ln = Math.min(Math.max(line, 1), max)
    const lineObj = view.state.doc.line(ln)
    view.dispatch({
      selection: { anchor: lineObj.from },
      effects: EditorView.scrollIntoView(lineObj.from, { y: 'start' }),
    })
    view.focus()
    return
  }
  const el = previewHost.value?.querySelector(`#md-h-${line}`)
  el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function fitMermaidSvg(svg: SVGSVGElement) {
  try {
    const bbox = svg.getBBox()
    if (!(bbox.width > 0) || !(bbox.height > 0)) return
    const pad = 4
    const x = bbox.x - pad
    const y = bbox.y - pad
    const w = bbox.width + pad * 2
    const h = bbox.height + pad * 2
    svg.setAttribute('viewBox', `${x} ${y} ${w} ${h}`)
    svg.setAttribute('width', String(Math.ceil(w)))
    svg.setAttribute('height', String(Math.ceil(h)))
    svg.style.width = '100%'
    svg.style.maxWidth = '100%'
    svg.style.height = 'auto'
    svg.style.display = 'block'
    svg.style.margin = '0 auto'
  } catch {
    /* getBBox may fail if svg not laid out yet */
  }
}

async function runMermaid() {
  await nextTick()
  const host = previewHost.value
  if (!host || viewMode.value !== 'preview') return
  const nodes = host.querySelectorAll('.mermaid:not([data-processed])')
  if (!nodes.length) return

  for (const node of Array.from(nodes)) {
    if (!(node instanceof HTMLElement)) continue
    if (node.querySelector('svg.mermaid-fitted')) {
      node.dataset.processed = 'true'
      continue
    }
    node.dataset.processed = 'true'
    // Id must stay on the final SVG — Mermaid CSS is scoped as `#id .node ...`
    const id = `sl-mermaid-${++mermaidId}`
    const source = (node.textContent || '').trim()
    if (!source) continue
    try {
      const { svg } = await mermaid.render(id, source)
      const wrap = document.createElement('div')
      wrap.className = 'mermaid mermaid-chart'
      wrap.dataset.processed = 'true'
      wrap.innerHTML = svg
      node.replaceWith(wrap)
      // Must be in DOM before getBBox; trim oversized viewBox that causes blank space
      await nextTick()
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
      const svgEl = wrap.querySelector('svg')
      if (svgEl instanceof SVGSVGElement) {
        fitMermaidSvg(svgEl)
        svgEl.classList.add('mermaid-fitted')
      }
    } catch (err) {
      node.classList.add('mermaid-chart')
      node.innerHTML = `<code class="mermaid-error">${String(err)}</code>`
    } finally {
      document.getElementById(`d${id}`)?.remove()
    }
  }
}

watch(viewMode, async (mode) => {
  if (mode === 'source') {
    await nextTick()
    syncEditorFromContent()
  } else {
    await runMermaid()
  }
})

watch(previewHtml, () => {
  if (viewMode.value === 'preview') void runMermaid()
})

onMounted(async () => {
  await refreshList()
  await refreshRecent()
  await nextTick()
  previewHost.value?.addEventListener('click', onPreviewClick, true)
  window.addEventListener('keydown', onLightboxKeydown)
})

onBeforeUnmount(() => {
  if (saveTimer) clearTimeout(saveTimer)
  destroyEditor()
  previewHost.value?.removeEventListener('click', onPreviewClick, true)
  window.removeEventListener('keydown', onLightboxKeydown)
})
</script>

<style scoped>
.md-reader {
  min-height: 0;
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.reader-body {
  display: flex;
  gap: 0;
  min-height: calc(100vh - 160px);
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.file-pane {
  width: 260px;
  flex-shrink: 0;
  border-right: 1px solid var(--el-border-color-lighter);
  display: flex;
  flex-direction: column;
  background: #f7f8f8;
  transition: width 0.2s ease;
}

.file-pane.collapsed {
  width: 40px;
}

.pane-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
  padding: 6px 8px 6px 12px;
  font-size: 12px;
  font-weight: 600;
  border-bottom: 1px solid var(--el-border-color-lighter);
  min-height: 36px;
  color: var(--el-text-color-regular);
}

.pane-header-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  letter-spacing: 0.02em;
}

.pane-header-title em {
  font-style: normal;
  font-weight: 500;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color);
  border-radius: 999px;
  padding: 0 6px;
  line-height: 18px;
}

.pane-header-actions {
  display: inline-flex;
  align-items: center;
  gap: 0;
}

.file-pane.collapsed .pane-header,
.outline-pane.collapsed .pane-header {
  justify-content: center;
  padding: 8px 4px;
}

.pane-empty {
  padding: 20px 14px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
  text-align: center;
}

.file-list {
  list-style: none;
  margin: 0;
  padding: 4px;
  overflow: auto;
  flex: 1;
}

.file-list li {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 6px 0 8px;
  border-radius: 6px;
  cursor: pointer;
  position: relative;
}

.file-list li:hover {
  background: rgba(15, 118, 110, 0.06);
}

.file-list li.active {
  background: rgba(15, 118, 110, 0.12);
}

.file-list li.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 7px;
  bottom: 7px;
  width: 2px;
  border-radius: 1px;
  background: #0f766e;
}

.file-icon {
  flex-shrink: 0;
  color: #0f766e;
  opacity: 0.75;
}

.file-list li.active .file-icon {
  opacity: 1;
}

.file-name {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  font-weight: 450;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--el-text-color-primary);
}

.file-list li.active .file-name {
  font-weight: 600;
  color: #0f766e;
}

.file-size {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
  opacity: 0.85;
}

.file-more {
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.12s ease;
}

.file-list li:hover .file-more,
.file-list li.active .file-more {
  opacity: 1;
}

.file-more-btn {
  padding: 2px !important;
  height: 22px;
  width: 22px;
}

.danger-text {
  color: var(--el-color-danger);
}

.main-pane {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  flex-wrap: wrap;
}

.top-left,
.top-right {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.title-input {
  width: 220px;
}

.save-status {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.save-status.saving {
  color: var(--el-color-primary);
}

.save-status.saved {
  color: var(--el-color-success);
}

.save-status.error,
.save-status.dirty {
  color: var(--el-color-warning);
}

.recent-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}

.recent-btn {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.muted {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.editor-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
}

.workspace {
  flex: 1;
  min-height: 0;
  display: flex;
}

.content-pane {
  flex: 1;
  min-width: 0;
  position: relative;
}

.editor-host,
.preview-host {
  position: absolute;
  inset: 0;
  overflow: auto;
  z-index: 0;
  pointer-events: none;
}

.editor-host.is-active-pane,
.preview-host.is-active-pane {
  z-index: 2;
  pointer-events: auto;
}

.preview-host {
  padding: 20px 24px 40px;
}

.content-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.outline-pane {
  width: 220px;
  flex-shrink: 0;
  border-left: 1px solid var(--el-border-color-lighter);
  background: #fafafa;
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
}

.outline-pane.collapsed {
  width: 40px;
}

.outline-list {
  list-style: none;
  margin: 0;
  padding: 8px 0;
  overflow: auto;
  flex: 1;
}

.outline-list li {
  padding: 4px 12px;
  font-size: 12px;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.outline-list li:hover {
  background: #eef6f4;
  color: var(--el-color-primary);
}

.outline-list .lv-1 { padding-left: 12px; font-weight: 600; }
.outline-list .lv-2 { padding-left: 20px; }
.outline-list .lv-3 { padding-left: 28px; }
.outline-list .lv-4 { padding-left: 36px; }
.outline-list .lv-5 { padding-left: 44px; }
.outline-list .lv-6 { padding-left: 52px; }
</style>

<style>
.md-preview h1,
.md-preview h2,
.md-preview h3,
.md-preview h4,
.md-preview h5,
.md-preview h6 {
  margin: 1.2em 0 0.6em;
  line-height: 1.35;
  scroll-margin-top: 12px;
}

.md-preview p {
  margin: 0.75em 0;
  line-height: 1.7;
}

.md-preview ul,
.md-preview ol {
  margin: 0.75em 0;
  padding-left: 1.75em;
  line-height: 1.7;
}

.md-preview ul {
  list-style-type: disc;
}

.md-preview ol {
  list-style-type: decimal;
}

.md-preview li {
  margin: 0.28em 0;
  padding-left: 0.15em;
}

.md-preview li > ul,
.md-preview li > ol {
  margin: 0.2em 0 0.2em 0.15em;
}

.md-preview ul ul {
  list-style-type: circle;
}

.md-preview ul ul ul {
  list-style-type: square;
}

.md-preview ol ol {
  list-style-type: lower-alpha;
}

.md-preview ol ol ol {
  list-style-type: lower-roman;
}

.md-preview li > p {
  margin: 0.25em 0;
}

.md-preview .task-list-item {
  list-style: none;
}

.md-preview .task-list-item input[type='checkbox'] {
  margin-right: 0.45em;
  vertical-align: middle;
}

.md-preview pre {
  overflow: auto;
  padding: 12px 14px;
  border-radius: 6px;
  background: #f6f8fa;
}

.md-preview code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.92em;
}

.md-preview :not(pre) > code {
  padding: 0.15em 0.4em;
  border-radius: 4px;
  background: #f0f2f5;
}

.md-preview table {
  border-collapse: collapse;
  width: 100%;
  margin: 1em 0;
}

.md-preview th,
.md-preview td {
  border: 1px solid #d0d7de;
  padding: 6px 10px;
}

.md-preview img {
  max-width: 100%;
  cursor: zoom-in;
  border-radius: 4px;
}

.md-img-lightbox {
  position: fixed;
  inset: 0;
  z-index: 5000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.78);
  padding: 48px 64px;
  box-sizing: border-box;
}

.md-img-lightbox__img {
  max-width: min(96vw, 1400px);
  max-height: 90vh;
  object-fit: contain;
  border-radius: 4px;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.45);
  cursor: default;
}

.md-img-lightbox__close {
  position: absolute;
  top: 12px;
  right: 16px;
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
  font-size: 28px;
  line-height: 1;
  cursor: pointer;
}

.md-img-lightbox__close:hover {
  background: rgba(255, 255, 255, 0.28);
}

.md-img-lightbox__nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 44px;
  height: 44px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
  font-size: 32px;
  line-height: 1;
  cursor: pointer;
}

.md-img-lightbox__nav:hover {
  background: rgba(255, 255, 255, 0.28);
}

.md-img-lightbox__nav.prev {
  left: 16px;
}

.md-img-lightbox__nav.next {
  right: 16px;
}

.md-img-lightbox__counter {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  color: rgba(255, 255, 255, 0.9);
  font-size: 13px;
}

.md-preview .mermaid,
.md-preview .mermaid-chart {
  margin: 1em 0;
  padding: 0;
  background: transparent;
  text-align: center;
  overflow: hidden;
  line-height: normal;
}

.md-preview .mermaid-chart svg {
  display: block;
  margin: 0 auto;
  max-width: 100%;
  height: auto !important;
}

.md-preview .mermaid-error {
  color: #cf222e;
  white-space: pre-wrap;
}
</style>
