<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div>
        <h3>Spy-Look</h3>
        <span class="subtitle">{{ viewTitle }}</span>
      </div>
      <div class="header-actions">
        <el-button v-if="currentView !== 'apps'" @click="goBack">返回</el-button>
        <el-button @click="openClientInfoModal">对外调用</el-button>
        <router-link to="/upstream-config"><el-button>上游配置</el-button></router-link>
        <router-link to="/model-capability-probe"><el-button>模型能力测试</el-button></router-link>
        <el-button type="primary" :icon="Refresh" @click="refreshCurrent">刷新</el-button>
      </div>
    </el-header>

    <!-- Apps View -->
    <el-main v-show="currentView === 'apps'">
      <el-table :data="apps" highlight-current-row @row-click="selectApp" v-loading="appsLoading" stripe size="small">
        <el-table-column prop="app_id" label="应用 ID" min-width="160" />
        <el-table-column prop="log_count" label="日志数" width="100" />
        <el-table-column prop="total_input_tokens" label="输入 Token" width="120" />
        <el-table-column prop="total_output_tokens" label="输出 Token" width="120" />
        <el-table-column prop="total_total_tokens" label="总 Token" width="120" />
        <el-table-column prop="first_created_at" label="首次" width="160" />
        <el-table-column prop="last_created_at" label="最近" width="160" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="danger" size="small" text @click.stop="deleteApp(row.app_id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-if="appTotal > appPageSize" class="pagination" background layout="total, sizes, prev, pager, next"
        :total="appTotal" v-model:page-size="appPageSize" v-model:current-page="appCurrentPage"
        @size-change="loadApps" @current-change="loadApps" />
    </el-main>

    <!-- Sessions View -->
    <el-main v-show="currentView === 'sessions'">
      <div class="context-bar"><el-tag>{{ selectedApp }}</el-tag></div>
      <el-table :data="sessions" highlight-current-row @row-click="selectSession" v-loading="sessionsLoading" stripe size="small">
        <el-table-column prop="session_id" label="会话 ID" min-width="160" />
        <el-table-column prop="log_count" label="日志数" width="100" />
        <el-table-column prop="total_input_tokens" label="输入 Token" width="120" />
        <el-table-column prop="total_output_tokens" label="输出 Token" width="120" />
        <el-table-column prop="total_total_tokens" label="总 Token" width="120" />
        <el-table-column prop="first_created_at" label="首次" width="160" />
        <el-table-column prop="last_created_at" label="最近" width="160" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="danger" size="small" text @click.stop="deleteSession(row.session_id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-if="sessionTotal > sessionPageSize" class="pagination" background layout="total, sizes, prev, pager, next"
        :total="sessionTotal" v-model:page-size="sessionPageSize" v-model:current-page="sessionCurrentPage"
        @size-change="loadSessions" @current-change="loadSessions" />
    </el-main>

    <!-- Logs View -->
    <el-main v-show="currentView === 'logs'">
      <div class="context-bar">
        <el-tag type="primary">{{ selectedApp }}</el-tag>
        <el-tag>{{ selectedSession }}</el-tag>
      </div>
      <el-form :inline="true" :model="filters" size="small" class="filter-form">
        <el-form-item label="Path">
          <el-input v-model="filters.path" placeholder="path 筛选" clearable style="width:180px" />
        </el-form-item>
        <el-form-item label="Model">
          <el-input v-model="filters.model" placeholder="model" clearable style="width:160px" />
        </el-form-item>
        <el-form-item label="Session">
          <el-input v-model="filters.session_id" placeholder="session_id" clearable style="width:140px" />
        </el-form-item>
        <el-form-item label="Client IP">
          <el-input v-model="filters.client_ip" placeholder="client_ip" clearable style="width:140px" />
        </el-form-item>
        <el-form-item label="时间">
          <el-date-picker v-model="filters.timeRange" type="datetimerange" range-separator="至"
            start-placeholder="开始" end-placeholder="结束" format="YYYY-MM-DD HH:mm:ss" value-format="YYYY-MM-DD HH:mm:ss"
            style="width:340px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="applyFilters">查询</el-button>
        </el-form-item>
        <el-form-item>
          <el-switch v-model="autoRefresh" active-text="自动刷新(5s)" size="small" @change="onAutoRefreshToggle" />
        </el-form-item>
      </el-form>
      <el-table :data="logs" v-loading="logsLoading" stripe size="small" @sort-change="onSortChange">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="path" label="Path" min-width="200" show-overflow-tooltip />
        <el-table-column prop="model" label="Model" width="120" />
        <el-table-column prop="status_code" label="Status" width="80" sortable="custom">
          <template #default="{ row }">
            <el-tag :type="row.status_code === 200 ? 'success' : 'danger'" size="small">{{ row.status_code }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="latency_ms" label="Latency(ms)" width="110" sortable="custom" />
        <el-table-column prop="client_ip" label="IP" width="130" />
        <el-table-column prop="app_id" label="App" width="100" show-overflow-tooltip />
        <el-table-column prop="session_id" label="Session" width="100" show-overflow-tooltip />
        <el-table-column label="Tokens(in/out/total)" width="180">
          <template #default="{ row }">{{ row.input_tokens }} / {{ row.output_tokens }} / {{ row.total_tokens }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="160" sortable="custom" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openModal('请求体', formatBody(row.request_body))">请求</el-button>
            <el-button size="small" @click="openBodyModal(row)">响应</el-button>
            <el-button size="small" type="danger" text @click="deleteLog(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-if="logTotal > logPageSize" class="pagination" background layout="total, sizes, prev, pager, next"
        :total="logTotal" v-model:page-size="logPageSize" v-model:current-page="logCurrentPage"
        @size-change="onLogPageSizeChange" @current-change="onLogPageChange" />
    </el-main>

    <!-- Body Modal -->
    <el-dialog v-model="modalVisible" :title="modalTitle" width="70%" destroy-on-close center>
      <div v-if="modalStreamToggle" style="margin-bottom:8px">
        <el-button size="small" @click="toggleStreamView">{{ modalStreamMode ? '转为非流式' : '转为流式视图' }}</el-button>
      </div>
      <pre class="json-preview" v-html="modalContent"></pre>
    </el-dialog>

    <!-- App Picker Dialog -->
    <el-dialog v-model="showAppPicker" title="选择应用" width="400px" destroy-on-close center>
      <p class="hint">请先选择要查看对外调用说明的应用</p>
      <el-select v-model="appPickerSelected" placeholder="选择 App ID" filterable style="width:100%">
        <el-option v-for="id in appPickerOptions" :key="id" :label="id" :value="id" />
      </el-select>
      <template #footer>
        <el-button @click="cancelAppPicker">取消</el-button>
        <el-button type="primary" :disabled="!appPickerSelected" @click="confirmAppPicker">确定</el-button>
      </template>
    </el-dialog>

    <!-- Client Info Dialog -->
    <el-dialog v-model="showClientInfo" :title="clientInfoTitle" width="600px" destroy-on-close center>
      <div v-if="clientInfoLoading" style="text-align:center;padding:20px"><el-icon class="is-loading"><Loading /></el-icon> 加载中...</div>
      <div v-else class="client-info" v-html="clientInfoHtml"></div>
    </el-dialog>
  </el-container>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Refresh, Loading } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiGet, apiDelete } from '../composables/useApi'

const route = useRoute()
const router = useRouter()

const currentView = ref<'apps' | 'sessions' | 'logs'>('apps')
const selectedApp = ref('')
const selectedSession = ref('')

const apps = ref<any[]>([])
const appTotal = ref(0)
const appCurrentPage = ref(1)
const appPageSize = ref(20)
const appsLoading = ref(false)

const sessions = ref<any[]>([])
const sessionTotal = ref(0)
const sessionCurrentPage = ref(1)
const sessionPageSize = ref(20)
const sessionsLoading = ref(false)

const logs = ref<any[]>([])
const logTotal = ref(0)
const logCurrentPage = ref(1)
const logPageSize = ref(20)
const logsLoading = ref(false)
const autoRefresh = ref(true)
let autoRefreshTimer: ReturnType<typeof setInterval> | null = null

const filters = reactive({
  path: '/v1/chat/completions',
  model: '',
  session_id: '',
  client_ip: '',
  timeRange: null as [string, string] | null,
})

const sortOrder = reactive({ field: 'created_at', dir: 'desc' as 'asc' | 'desc' })

const modalVisible = ref(false)
const modalTitle = ref('')
const modalContent = ref('')
const modalStreamToggle = ref(false)
const modalStreamMode = ref(true)
let modalRawBody = ''

const showClientInfo = ref(false)
const clientInfoLoading = ref(false)
const clientInfoHtml = ref('')
const clientInfoTitle = ref('对外调用说明')

const showAppPicker = ref(false)
const appPickerOptions = ref<string[]>([])
const appPickerSelected = ref('')
let appPickerResolve: ((v: string | null) => void) | null = null

const viewTitle = computed(() => {
  if (currentView.value === 'sessions') return '· 会话列表'
  if (currentView.value === 'logs') return '· 会话日志'
  return '· 应用列表'
})

function refreshCurrent() {
  if (currentView.value === 'apps') loadApps()
  else if (currentView.value === 'sessions') loadSessions()
  else searchLogs()
}

function goBack() {
  if (currentView.value === 'sessions') {
    currentView.value = 'apps'
    selectedApp.value = ''
    router.replace({ query: {} })
    loadApps()
  } else if (currentView.value === 'logs') {
    if (selectedSession.value) {
      currentView.value = 'sessions'
      selectedSession.value = ''
      filters.session_id = ''
      router.replace({ query: { app_id: selectedApp.value } })
      loadSessions()
    } else {
      currentView.value = 'apps'
      selectedApp.value = ''
      router.replace({ query: {} })
      loadApps()
    }
  }
}

async function loadApps() {
  appsLoading.value = true
  try {
    const offset = (appCurrentPage.value - 1) * appPageSize.value
    const data = await apiGet<any>('/logs/apps', { limit: appPageSize.value, offset })
    apps.value = data.items || []
    appTotal.value = data.total || 0
  } catch (e: any) { ElMessage.error(e.message) }
  finally { appsLoading.value = false }
}

async function loadSessions() {
  if (!selectedApp.value) return
  sessionsLoading.value = true
  try {
    const offset = (sessionCurrentPage.value - 1) * sessionPageSize.value
    const data = await apiGet<any>('/logs/sessions', { app_id: selectedApp.value, limit: sessionPageSize.value, offset })
    sessions.value = data.items || []
    sessionTotal.value = data.total || 0
  } catch (e: any) { ElMessage.error(e.message) }
  finally { sessionsLoading.value = false }
}

async function searchLogs() {
  logsLoading.value = true
  try {
    const offset = (logCurrentPage.value - 1) * logPageSize.value
    const params: any = {
      app_id: selectedApp.value,
      limit: logPageSize.value,
      offset,
      order_by: sortOrder.field,
      order_dir: sortOrder.dir,
    }
    const sf = filters.session_id || selectedSession.value
    if (sf) params.session_id = sf
    if (filters.path) params.path = filters.path
    if (filters.model) params.model = filters.model
    if (filters.client_ip) params.client_ip = filters.client_ip
    if (filters.timeRange && filters.timeRange.length === 2) {
      params.start_time = filters.timeRange[0]
      params.end_time = filters.timeRange[1]
    }
    const data = await apiGet<any>('/logs', params)
    logs.value = data.items || []
    logTotal.value = data.total || 0
  } catch (e: any) { ElMessage.error(e.message) }
  finally { logsLoading.value = false }
}

function applyFilters() { logCurrentPage.value = 1; searchLogs() }
function onLogPageSizeChange() { logCurrentPage.value = 1; searchLogs() }
function onLogPageChange() { searchLogs() }
function onAutoRefreshToggle(val: boolean) {
  if (val) { autoRefreshTimer = setInterval(searchLogs, 5000) }
  else { if (autoRefreshTimer) clearInterval(autoRefreshTimer) }
}
function onSortChange({ prop, order }: any) {
  if (!prop) return
  sortOrder.field = prop.replace(/([A-Z])/g, '_$1').toLowerCase()
  sortOrder.dir = order === 'ascending' ? 'asc' : 'desc'
  searchLogs()
}

function selectApp(row: any) {
  selectedApp.value = row.app_id
  sessionCurrentPage.value = 1
  currentView.value = 'sessions'
  router.replace({ query: { app_id: row.app_id } })
  loadSessions()
}

function selectSession(row: any) {
  selectedSession.value = row.session_id
  filters.session_id = row.session_id
  logCurrentPage.value = 1
  currentView.value = 'logs'
  router.replace({ query: { app_id: selectedApp.value, session_id: row.session_id } })
  searchLogs()
}

async function deleteApp(appId: string) {
  try { await ElMessageBox.confirm(`确认删除应用 ${appId} 的所有日志？`, '确认', { type: 'warning' }) } catch { return }
  try { await apiDelete(`/logs/apps/${encodeURIComponent(appId)}`); ElMessage.success('已删除'); loadApps() }
  catch (e: any) { ElMessage.error(e.message) }
}

async function deleteSession(sessionId: string) {
  try { await ElMessageBox.confirm(`确认删除会话 ${sessionId} 的所有日志？`, '确认', { type: 'warning' }) } catch { return }
  try {
    await apiDelete(`/logs/sessions?app_id=${encodeURIComponent(selectedApp.value)}&session_id=${encodeURIComponent(sessionId)}`)
    ElMessage.success('已删除'); loadSessions()
  } catch (e: any) { ElMessage.error(e.message) }
}

async function deleteLog(logId: number) {
  try { await ElMessageBox.confirm(`确认删除日志 #${logId}？`, '确认', { type: 'warning' }) } catch { return }
  try { await apiDelete(`/logs/${logId}`); ElMessage.success('已删除'); searchLogs() }
  catch (e: any) { ElMessage.error(e.message) }
}

function formatBody(body: any): string {
  if (!body) return '(empty)'
  if (typeof body === 'string') {
    try { return JSON.stringify(JSON.parse(body), null, 2) } catch { return body }
  }
  return JSON.stringify(body, null, 2)
}

function buildNonStreamJsonFromSse(sseText: string): string {
  const lines = sseText.split('\n')
  const parts: string[] = []
  for (const line of lines) {
    if (!line.startsWith('data:')) continue
    const c = line.slice(5).trim()
    if (!c || c === '[DONE]') continue
    try {
      const obj = JSON.parse(c)
      for (const choice of (obj.choices || [])) {
        if (choice.delta?.content) parts.push(choice.delta.content)
        if (choice.delta?.reasoning_content) parts.push(choice.delta.reasoning_content)
      }
    } catch { }
  }
  return JSON.stringify({ choices: [{ message: { role: 'assistant', content: parts.join('') } }] }, null, 2)
}

function jsonHighlight(json: string): string {
  return json
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/("(\\u[a-fA-F0-9]{4}|\\[^u]|[^"\\])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
      (m) => {
        let cls = 'json-number'
        if (/^"/.test(m)) { if (/:$/.test(m)) cls = 'json-key'; else cls = 'json-string' }
        else if (/true|false/.test(m)) cls = 'json-boolean'
        else if (/null/.test(m)) cls = 'json-null'
        return `<span class="${cls}">${m}</span>`
      })
}

function openBodyModal(log: any) {
  const raw = typeof log.response_body === 'string' ? log.response_body : JSON.stringify(log.response_body)
  modalRawBody = raw
  if (raw.trim().startsWith('data:')) {
    modalStreamToggle.value = true
    modalStreamMode.value = true
    modalTitle.value = 'Response Body (流式 SSE)'
    modalContent.value = `<pre>${raw.replace(/&/g, '&amp;').replace(/</g, '&lt;')}</pre>`
  } else {
    modalStreamToggle.value = false
    modalTitle.value = 'Response Body'
    modalContent.value = jsonHighlight(formatBody(log.response_body))
  }
  modalVisible.value = true
}

function toggleStreamView() {
  modalStreamMode.value = !modalStreamMode.value
  if (!modalStreamMode.value) {
    modalTitle.value = 'Response Body (转为非流式)'
    modalContent.value = jsonHighlight(buildNonStreamJsonFromSse(modalRawBody))
  } else {
    modalTitle.value = 'Response Body (流式 SSE)'
    modalContent.value = `<pre>${modalRawBody.replace(/&/g, '&amp;').replace(/</g, '&lt;')}</pre>`
  }
}

function openModal(title: string, body: string) {
  modalTitle.value = title
  modalContent.value = jsonHighlight(typeof body === 'string' ? body : JSON.stringify(body, null, 2))
  modalStreamToggle.value = false
  modalVisible.value = true
}

function confirmAppPicker() {
  showAppPicker.value = false
  appPickerResolve?.(appPickerSelected.value)
  appPickerResolve = null
}

function cancelAppPicker() {
  showAppPicker.value = false
  appPickerResolve?.(null)
  appPickerResolve = null
}

function pickApp(): Promise<string | null> {
  return new Promise(async (resolve) => {
    appPickerResolve = resolve
    try {
      const data = await apiGet<any>('/admin/gateway-client-keys')
      appPickerOptions.value = (data.items || []).map((k: any) => k.app_id).filter(Boolean)
      if (!appPickerOptions.value.length) {
        ElMessage.warning('请先在「上游配置」中为应用创建 API Key')
        resolve(null)
        return
      }
      appPickerSelected.value = ''
      showAppPicker.value = true
    } catch (e: any) {
      ElMessage.error(e.message)
      resolve(null)
    }
  })
}

async function loadClientInfo(appId: string) {
  showClientInfo.value = true
  clientInfoLoading.value = true
  clientInfoHtml.value = ''
  clientInfoTitle.value = `对外调用说明 · ${appId}`
  try {
    const data = await apiGet<any>('/admin/client-info', { app_id: appId })
    const key = data.gateway_api_key || '(暂无密钥)'
    clientInfoHtml.value = `
      <p><b>应用 ID</b>: <code>${data.app_id || appId}</code></p>
      <p><b>网关地址</b>: ${data.gateway_base_url}</p>
      <p><b>API Key</b>: <code>${key}</code></p>
      <p><b>Models</b>: <code>${data.v1_models_url}</code></p>
      <p><b>Chat</b>: <code>${data.v1_chat_completions_url}</code></p>
      <el-divider />
      <p><b>curl 示例 - 列表模型:</b></p>
      <pre>curl ${data.v1_models_url} -H "Authorization: Bearer ${key}"</pre>
      <p><b>curl 示例 - 对话:</b></p>
      <pre>curl ${data.v1_chat_completions_url} -H "Content-Type: application/json" -H "Authorization: Bearer ${key}" -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Hello!"}]}'</pre>`
  } catch { clientInfoHtml.value = '<p style="color:red">加载失败</p>' }
  finally { clientInfoLoading.value = false }
}

async function openClientInfoModal() {
  let appId = selectedApp.value
  if (!appId) {
    appId = (await pickApp()) ?? ''
    if (!appId) return
  }
  await loadClientInfo(appId)
}

onMounted(() => {
  const q = route.query
  if (q.app_id && q.session_id) {
    selectedApp.value = String(q.app_id)
    selectedSession.value = String(q.session_id)
    filters.session_id = selectedSession.value
    currentView.value = 'logs'
    searchLogs()
  } else if (q.app_id) {
    selectedApp.value = String(q.app_id)
    currentView.value = 'sessions'
    loadSessions()
  } else {
    loadApps()
  }
  if (autoRefresh.value) autoRefreshTimer = setInterval(searchLogs, 5000)
})

onUnmounted(() => {
  if (autoRefreshTimer) clearInterval(autoRefreshTimer)
})
</script>
