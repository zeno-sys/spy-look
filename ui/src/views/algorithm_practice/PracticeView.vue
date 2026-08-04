<template>
  <div class="practice-page">
    <!-- No problem selected -->
    <div v-if="!problemId" class="practice-empty">
      <el-icon :size="48" class="practice-empty-icon"><Document /></el-icon>
      <p>请从题目列表选择一道题开始练习</p>
      <el-button type="primary" @click="$router.push('/algorithm/problems')">返回列表</el-button>
    </div>

    <template v-else>
      <!-- Loading -->
      <div v-if="loading" class="practice-loading">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        <p>加载题目…</p>
      </div>

      <template v-else-if="problem">
        <!-- Toolbar -->
        <header class="practice-toolbar">
          <div class="practice-toolbar-left">
            <el-button :icon="ArrowLeft" text @click="$router.push('/algorithm/problems')">返回</el-button>
            <span class="practice-problem-title">{{ problem.title }}</span>
            <span v-if="dirty" class="practice-dirty-dot" title="有未保存的修改"></span>
          </div>
          <div class="practice-toolbar-right">
            <el-tooltip :content="isDark ? '切换浅色主题' : '切换暗色主题'" placement="bottom">
              <el-button :icon="isDark ? Sunny : Moon" circle size="small" @click="toggleTheme" />
            </el-tooltip>
            <el-tooltip content="复制代码" placement="bottom">
              <el-button :icon="CopyDocument" circle size="small" @click="onCopyCode" />
            </el-tooltip>
            <el-tooltip content="重置代码" placement="bottom">
              <el-button :icon="RefreshLeft" circle size="small" @click="onResetCode" />
            </el-tooltip>
            <el-button type="primary" :icon="Check" :loading="saving" @click="onSave">保存</el-button>
          </div>
        </header>

        <!-- Split body -->
        <div class="practice-body" ref="bodyRef">
          <!-- Left: description + thought -->
          <div class="practice-left" :style="{ flexBasis: leftRatioPct }">
            <div class="practice-section-label">
              <el-icon><Document /></el-icon>
              <span>题目描述</span>
            </div>
            <div class="practice-description md-preview" v-html="renderedDescription"></div>

            <div class="practice-section-label">
              <el-icon><EditPen /></el-icon>
              <span>解题思路</span>
            </div>
            <el-input
              v-model="thoughtDraft"
              type="textarea"
              :rows="6"
              placeholder="记录解题思路、关键步骤、时间复杂度等…"
              class="practice-thought"
              @input="dirty = true"
            />
          </div>

          <!-- Draggable splitter -->
          <div
            class="practice-splitter"
            :class="{ dragging: splitterDragging }"
            title="拖动调整左右比例，双击重置"
            @mousedown="onSplitterMouseDown"
            @dblclick="resetSplitter"
          >
            <div class="practice-splitter-grip"></div>
          </div>

          <!-- Right: code editor + stdin + output -->
          <div class="practice-right">
            <div class="practice-editor-wrap">
              <div ref="editorHost" class="practice-editor-host"></div>
            </div>

            <!-- stdin -->
            <div class="practice-stdin-wrap">
              <div class="practice-stdin-header" @click="stdinExpanded = !stdinExpanded">
                <span>标准输入 (stdin)</span>
                <el-icon><ArrowDown v-if="!stdinExpanded" /><ArrowUp v-else /></el-icon>
              </div>
              <el-input
                v-show="stdinExpanded"
                v-model="stdinDraft"
                type="textarea"
                :rows="3"
                placeholder="输入 stdin 内容（可选）"
                class="practice-stdin-input"
              />
            </div>

            <!-- Run bar -->
            <div class="practice-run-bar">
              <el-button
                type="primary"
                :icon="VideoPlay"
                :loading="executing"
                :disabled="executing"
                @click="onRun"
              >
                {{ executing ? '运行中…' : '运行' }}
              </el-button>
              <span v-if="executeResult" class="practice-run-meta">
                <span :class="['practice-exit-code', executeResult.exit_code === 0 ? 'success' : 'error']">
                  退出码 {{ executeResult.exit_code }}
                </span>
                <span class="practice-duration">{{ executeResult.duration_ms }}ms</span>
                <span v-if="executeResult.timed_out" class="practice-timeout">超时</span>
              </span>
            </div>

            <!-- Output -->
            <div class="practice-output">
              <div v-if="!executeResult" class="practice-output-empty">
                点击「运行」查看输出
              </div>
              <template v-else>
                <div v-if="executeResult.stdout" class="practice-output-section">
                  <div class="practice-output-label">stdout</div>
                  <pre class="practice-output-pre practice-stdout">{{ executeResult.stdout }}</pre>
                </div>
                <div v-if="executeResult.stderr" class="practice-output-section">
                  <div class="practice-output-label">stderr</div>
                  <pre class="practice-output-pre practice-stderr">{{ executeResult.stderr }}</pre>
                </div>
              </template>
            </div>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  ArrowDown,
  ArrowUp,
  Check,
  CopyDocument,
  Document,
  EditPen,
  Loading,
  Moon,
  RefreshLeft,
  Sunny,
  VideoPlay,
} from '@element-plus/icons-vue'

// CodeMirror
import { EditorState, Compartment } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, drawSelection, highlightActiveLine } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { python } from '@codemirror/lang-python'
import { syntaxHighlighting, defaultHighlightStyle, bracketMatching } from '@codemirror/language'
import { oneDark } from '@codemirror/theme-one-dark'
import { linter, lintGutter, type Diagnostic } from '@codemirror/lint'

import { renderMarkdownHtml } from '../doc_tools/md_reader/renderMarkdown'
import { useAlgorithm, type ExecuteResult, type ProblemDetail } from '../../composables/useAlgorithm'

const route = useRoute()
const {
  getProblem,
  saveSolution,
  executeCode,
  executing,
  checkSyntax,
} = useAlgorithm()

// --- state ---

const problemId = computed(() => {
  const id = route.query.id
  return id ? Number(id) : null
})

const problem = ref<ProblemDetail | null>(null)
const loading = ref(true)
const saving = ref(false)
const dirty = ref(false)

const codeDraft = ref('')
const thoughtDraft = ref('')
const stdinDraft = ref('')
const stdinExpanded = ref(false)
const executeResult = ref<ExecuteResult | null>(null)

const isDark = ref(true)

// --- draggable splitter ---

const SPLIT_KEY = 'algo-practice-left-ratio'
const SPLIT_DEFAULT = 0.4
const SPLIT_MIN = 0.2
const SPLIT_MAX = 0.8

const bodyRef = ref<HTMLElement | null>(null)
const splitterDragging = ref(false)
const leftRatio = ref(loadSplitRatio())

const leftRatioPct = computed(() => `${leftRatio.value * 100}%`)

function loadSplitRatio(): number {
  const saved = Number(localStorage.getItem(SPLIT_KEY))
  if (Number.isFinite(saved) && saved >= SPLIT_MIN && saved <= SPLIT_MAX) {
    return saved
  }
  return SPLIT_DEFAULT
}

function onSplitterMouseDown(e: MouseEvent) {
  e.preventDefault()
  splitterDragging.value = true
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'col-resize'
  window.addEventListener('mousemove', onSplitterMouseMove)
  window.addEventListener('mouseup', onSplitterMouseUp)
}

function onSplitterMouseMove(e: MouseEvent) {
  if (!splitterDragging.value || !bodyRef.value) return
  const rect = bodyRef.value.getBoundingClientRect()
  if (rect.width === 0) return
  const ratio = (e.clientX - rect.left) / rect.width
  leftRatio.value = Math.min(SPLIT_MAX, Math.max(SPLIT_MIN, ratio))
}

function onSplitterMouseUp() {
  if (!splitterDragging.value) return
  splitterDragging.value = false
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
  window.removeEventListener('mousemove', onSplitterMouseMove)
  window.removeEventListener('mouseup', onSplitterMouseUp)
  localStorage.setItem(SPLIT_KEY, String(leftRatio.value))
  editorView?.requestMeasure()
}

function resetSplitter() {
  leftRatio.value = SPLIT_DEFAULT
  localStorage.setItem(SPLIT_KEY, String(SPLIT_DEFAULT))
  editorView?.requestMeasure()
}

// --- markdown rendering ---

const renderedDescription = computed(() => {
  const desc = problem.value?.description || ''
  return renderMarkdownHtml(desc, [])
})

// --- code mirror ---

const editorHost = ref<HTMLElement | null>(null)
let editorView: EditorView | null = null
const themeCompartment = new Compartment()

// --- python syntax linting ---

let syntaxCheckSeq = 0

const pythonLinter = linter(
  async (view): Promise<Diagnostic[]> => {
    const code = view.state.doc.toString()
    if (!code.trim()) return []
    const seq = ++syntaxCheckSeq
    try {
      const errors = await checkSyntax(code)
      // Drop stale results if a newer request has been issued meanwhile
      if (seq !== syntaxCheckSeq) return []
      const diagnostics: Diagnostic[] = []
      for (const err of errors) {
        const lineNo = Math.max(1, err.line)
        const line = view.state.doc.line(lineNo)
        const from = line.from + Math.max(0, (err.col || 1) - 1)
        let to: number
        if (err.end_line && err.end_col) {
          const endLine = view.state.doc.line(Math.max(1, err.end_line))
          to = endLine.from + Math.max(0, (err.end_col || 1) - 1)
        } else {
          to = from + 1
        }
        to = Math.min(to, view.state.doc.length)
        diagnostics.push({
          from,
          to: Math.max(to, from + 1),
          severity: 'error',
          message: err.message,
        })
      }
      return diagnostics
    } catch {
      return [] // network/backend error — don't show stale lint marks
    }
  },
  { delay: 600 },
)

function buildEditor() {
  if (!editorHost.value) return
  destroyEditor()

  const extensions = [
    lineNumbers(),
    highlightActiveLine(),
    drawSelection(),
    history(),
    bracketMatching(),
    python(),
    syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
    lintGutter(),
    pythonLinter,
    keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
    EditorView.lineWrapping,
    EditorView.updateListener.of((update) => {
      if (update.docChanged) {
        codeDraft.value = update.state.doc.toString()
        dirty.value = true
      }
    }),
    themeCompartment.of(isDark.value ? oneDark : []),
    EditorView.theme({
      '&': { height: '100%', fontSize: '14px' },
      '.cm-scroller': {
        overflow: 'auto',
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
      },
      '.cm-content': { minHeight: '100%' },
    }),
  ]

  editorView = new EditorView({
    state: EditorState.create({ doc: codeDraft.value, extensions }),
    parent: editorHost.value,
  })
}

function destroyEditor() {
  editorView?.destroy()
  editorView = null
}

function toggleTheme() {
  isDark.value = !isDark.value
  editorView?.dispatch({
    effects: themeCompartment.reconfigure(isDark.value ? oneDark : []),
  })
}

// --- actions ---

async function onRun() {
  if (executing.value) return
  try {
    const result = await executeCode(codeDraft.value, stdinDraft.value)
    executeResult.value = result
  } catch (e: any) {
    ElMessage.error(e.message || '运行失败')
  }
}

async function onSave() {
  if (!problemId.value) return
  saving.value = true
  try {
    await saveSolution(problemId.value, codeDraft.value, thoughtDraft.value)
    dirty.value = false
    ElMessage.success('已保存')
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function onCopyCode() {
  try {
    await navigator.clipboard.writeText(codeDraft.value)
    ElMessage.success('代码已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

async function onResetCode() {
  try {
    await ElMessageBox.confirm('确定清空编辑器中的所有代码？', '重置代码', {
      type: 'warning',
    })
    editorView?.dispatch({
      changes: { from: 0, to: editorView.state.doc.length, insert: '' },
    })
    codeDraft.value = ''
    dirty.value = true
    ElMessage.success('已重置')
  } catch {
    // cancelled
  }
}

// --- lifecycle ---

onMounted(async () => {
  if (!problemId.value) {
    loading.value = false
    return
  }
  try {
    const detail = await getProblem(problemId.value)
    problem.value = detail
    codeDraft.value = detail.solution_code || ''
    thoughtDraft.value = detail.thought || ''
  } catch (e: any) {
    ElMessage.error(e.message || '加载题目失败')
  } finally {
    loading.value = false
  }
  await nextTick()
  buildEditor()
})

onBeforeUnmount(() => {
  destroyEditor()
  window.removeEventListener('mousemove', onSplitterMouseMove)
  window.removeEventListener('mouseup', onSplitterMouseUp)
})

// Rebuild editor when problemId changes
watch(problemId, async (newId) => {
  if (!newId) {
    loading.value = false
    return
  }
  loading.value = true
  destroyEditor()
  try {
    const detail = await getProblem(newId)
    problem.value = detail as any
    codeDraft.value = detail.solution_code || ''
    thoughtDraft.value = detail.thought || ''
    dirty.value = false
    executeResult.value = null
  } catch (e: any) {
    ElMessage.error(e.message || '加载题目失败')
  } finally {
    loading.value = false
  }
  await nextTick()
  buildEditor()
})
</script>

<style scoped>
.practice-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: calc(100vh - 60px);
}

.practice-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 80px 0;
  color: var(--sl-text-muted);
}

.practice-empty-icon {
  color: var(--sl-text-faint);
}

.practice-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 80px 0;
  color: var(--sl-text-muted);
}

/* Toolbar */
.practice-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 20px;
  border-bottom: 1px solid var(--sl-border);
  background: var(--sl-bg-elevated);
  flex-shrink: 0;
}

.practice-toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.practice-problem-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--sl-text);
}

.practice-dirty-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--sl-accent);
}

.practice-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Split body */
.practice-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* Left panel */
.practice-left {
  flex-shrink: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 16px 20px;
  overflow-y: auto;
}

/* Draggable splitter */
.practice-splitter {
  flex-shrink: 0;
  width: 6px;
  cursor: col-resize;
  background: var(--sl-bg-elevated);
  border-left: 1px solid var(--sl-border);
  border-right: 1px solid var(--sl-border);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 10;
  transition: background-color 0.15s ease;
}

.practice-splitter:hover,
.practice-splitter.dragging {
  background: var(--sl-accent);
  opacity: 0.7;
}

.practice-splitter-grip {
  width: 2px;
  height: 40px;
  border-radius: 2px;
  background: var(--sl-border);
  transition: background-color 0.15s ease;
}

.practice-splitter:hover .practice-splitter-grip,
.practice-splitter.dragging .practice-splitter-grip {
  background: #fff;
}

.practice-section-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--sl-text-muted);
  margin-bottom: 10px;
  margin-top: 4px;
}

.practice-section-label:first-child {
  margin-top: 0;
}

.practice-description {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 20px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--sl-text);
}

.practice-description :deep(h1) { font-size: 20px; font-weight: 700; margin: 16px 0 8px; }
.practice-description :deep(h2) { font-size: 17px; font-weight: 600; margin: 14px 0 6px; }
.practice-description :deep(h3) { font-size: 15px; font-weight: 600; margin: 12px 0 4px; }
.practice-description :deep(p) { margin: 8px 0; }
.practice-description :deep(ul),
.practice-description :deep(ol) { margin: 8px 0; padding-left: 24px; }
.practice-description :deep(li) { margin: 4px 0; }
.practice-description :deep(pre) {
  background: #f6f6f4;
  border-radius: 8px;
  padding: 12px 14px;
  overflow-x: auto;
  font-size: 13px;
  margin: 8px 0;
}
.practice-description :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
}
.practice-description :deep(:not(pre) > code) {
  background: #f0ede8;
  padding: 2px 5px;
  border-radius: 4px;
}
.practice-description :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}
.practice-description :deep(th),
.practice-description :deep(td) {
  border: 1px solid var(--sl-border);
  padding: 6px 10px;
  text-align: left;
}
.practice-description :deep(img) { max-width: 100%; border-radius: 8px; }

.practice-thought {
  flex-shrink: 0;
}

/* Right panel */
.practice-right {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.practice-editor-wrap {
  flex: 1;
  min-height: 200px;
  overflow: hidden;
  border-bottom: 1px solid var(--sl-border);
}

.practice-editor-host {
  height: 100%;
}

.practice-editor-host :deep(.cm-editor) {
  height: 100%;
}

/* stdin */
.practice-stdin-wrap {
  border-bottom: 1px solid var(--sl-border);
  flex-shrink: 0;
}

.practice-stdin-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 14px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  color: var(--sl-text-muted);
  background: var(--sl-bg-elevated);
}

.practice-stdin-header:hover {
  color: var(--sl-text);
}

.practice-stdin-input {
  margin: 0;
}

.practice-stdin-input :deep(.el-textarea__inner) {
  border-radius: 0;
  resize: vertical;
}

/* Run bar */
.practice-run-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 14px;
  border-bottom: 1px solid var(--sl-border);
  background: var(--sl-bg-elevated);
  flex-shrink: 0;
}

.practice-run-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
}

.practice-exit-code {
  font-weight: 600;
}

.practice-exit-code.success {
  color: #16a34a;
}

.practice-exit-code.error {
  color: #dc2626;
}

.practice-duration {
  color: var(--sl-text-muted);
}

.practice-timeout {
  color: #dc2626;
  font-weight: 600;
}

/* Output */
.practice-output {
  flex-shrink: 0;
  max-height: 240px;
  overflow-y: auto;
  background: #1e1e1e;
  padding: 8px 0;
}

.practice-output-empty {
  color: #6b7280;
  font-size: 13px;
  text-align: center;
  padding: 20px 0;
}

.practice-output-section {
  padding: 0 14px;
  margin-bottom: 8px;
}

.practice-output-label {
  font-size: 11px;
  font-weight: 600;
  color: #9ca3af;
  text-transform: uppercase;
  margin-bottom: 4px;
}

.practice-output-pre {
  margin: 0;
  padding: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.practice-stdout {
  color: #d1d5db;
}

.practice-stderr {
  color: #f87171;
}
</style>
