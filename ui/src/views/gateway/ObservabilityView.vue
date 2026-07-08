<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h3>大模型网关</h3>
        <span class="subtitle">{{ viewTitle }}</span>
      </div>
      <div class="header-actions">
        <el-button v-if="currentView !== 'apps'" @click="goBack">返回</el-button>
        <el-button @click="openClientInfoModal">对外调用</el-button>
        <el-button type="primary" :icon="Refresh" @click="refreshCurrent">刷新</el-button>
      </div>
    </div>

    <!-- Apps View -->
    <div v-show="currentView === 'apps'" class="page-body">
      <section class="gw-dashboard" v-loading="dashboardLoading">
        <div class="gw-dash-kpis">
          <div class="gw-dash-kpi">
            <span class="gw-dash-kpi-value">{{ formatCompactNumber(dashboardSummary.app_count) }}</span>
            <span class="gw-dash-kpi-label">应用数</span>
          </div>
          <div class="gw-dash-kpi">
            <span class="gw-dash-kpi-value">{{ formatCompactNumber(dashboardSummary.log_count) }}</span>
            <span class="gw-dash-kpi-label">请求总数</span>
          </div>
          <div class="gw-dash-kpi gw-dash-kpi--in">
            <span class="gw-dash-kpi-value">{{ formatCompactNumber(dashboardSummary.total_input_tokens) }}</span>
            <span class="gw-dash-kpi-label">输入 Token</span>
          </div>
          <div class="gw-dash-kpi gw-dash-kpi--out">
            <span class="gw-dash-kpi-value">{{ formatCompactNumber(dashboardSummary.total_output_tokens) }}</span>
            <span class="gw-dash-kpi-label">输出 Token</span>
          </div>
          <div class="gw-dash-kpi gw-dash-kpi--total">
            <span class="gw-dash-kpi-value">{{ formatCompactNumber(dashboardSummary.total_total_tokens) }}</span>
            <span class="gw-dash-kpi-label">总 Token</span>
          </div>
        </div>

        <div v-if="dashboardSummary.total_total_tokens" class="gw-dash-token-mix">
          <span class="gw-dash-token-mix-label">Token 构成</span>
          <div class="gw-dash-token-mix-bar">
            <div
              class="gw-dash-token-mix-in"
              :style="{ width: tokenMixInPercent + '%' }"
              :title="`输入 ${formatCompactNumber(dashboardSummary.total_input_tokens)}`"
            />
            <div
              class="gw-dash-token-mix-out"
              :style="{ width: tokenMixOutPercent + '%' }"
              :title="`输出 ${formatCompactNumber(dashboardSummary.total_output_tokens)}`"
            />
          </div>
          <span class="gw-dash-token-mix-legend">
            <span class="log-token log-token--in">输入 {{ tokenMixInPercent }}%</span>
            <span class="log-token-sep">·</span>
            <span class="log-token log-token--out">输出 {{ tokenMixOutPercent }}%</span>
          </span>
        </div>

        <div class="gw-dash-charts">
          <el-card class="gw-dash-card" shadow="never">
            <template #header><span>各应用请求量 Top {{ dashboardByApp.length }}</span></template>
            <div v-if="dashboardByApp.length" class="gw-dash-bars">
              <div v-for="item in dashboardByApp" :key="item.app_id" class="gw-dash-bar-row">
                <span class="gw-dash-bar-label" :title="item.app_id">{{ item.app_id }}</span>
                <div class="gw-dash-bar-track">
                  <div
                    class="gw-dash-bar-fill gw-dash-bar-fill--logs"
                    :style="{ width: barPercent(item.log_count, maxAppLogCount) + '%' }"
                  />
                </div>
                <span class="gw-dash-bar-value">{{ formatCompactNumber(item.log_count) }}</span>
              </div>
            </div>
            <p v-else class="hint">暂无请求数据</p>
          </el-card>

          <el-card class="gw-dash-card" shadow="never">
            <template #header><span>各应用 Token 用量</span></template>
            <div v-if="dashboardByApp.length" class="gw-dash-bars">
              <div v-for="item in dashboardByApp" :key="`${item.app_id}-tokens`" class="gw-dash-bar-row">
                <span class="gw-dash-bar-label" :title="item.app_id">{{ item.app_id }}</span>
                <div class="gw-dash-bar-track">
                  <div
                    class="gw-dash-stack"
                    :style="{ width: barPercent(item.total_total_tokens, maxAppTotalTokens) + '%' }"
                  >
                    <div class="gw-dash-stack-in" :style="{ width: tokenInShare(item) + '%' }" />
                    <div class="gw-dash-stack-out" :style="{ width: (100 - tokenInShare(item)) + '%' }" />
                  </div>
                </div>
                <span class="gw-dash-bar-value gw-dash-bar-value--tokens">
                  <span class="log-token log-token--in">{{ formatCompactNumber(item.total_input_tokens) }}</span>
                  <span class="log-token-sep">/</span>
                  <span class="log-token log-token--out">{{ formatCompactNumber(item.total_output_tokens) }}</span>
                </span>
              </div>
            </div>
            <p v-else class="hint">暂无 Token 数据</p>
          </el-card>
        </div>

        <el-card class="gw-dash-card gw-dash-timeline" shadow="never">
          <template #header><span>近 14 天请求趋势</span></template>
          <div v-if="dashboardTimeline.length" class="gw-dash-spark">
            <div v-for="day in dashboardTimeline" :key="day.date" class="gw-dash-spark-col">
              <span class="gw-dash-spark-value">{{ day.log_count || '' }}</span>
              <div class="gw-dash-spark-bar-wrap">
                <div
                  class="gw-dash-spark-bar"
                  :class="{ 'gw-dash-spark-bar--empty': !day.log_count }"
                  :style="{ height: sparkBarHeight(day.log_count) }"
                  :title="`${day.date} · ${day.log_count} 次 · ${formatCompactNumber(day.total_total_tokens)} tokens`"
                />
              </div>
              <span class="gw-dash-spark-label">{{ formatTimelineLabel(day.date) }}</span>
            </div>
          </div>
          <p v-else class="hint">暂无趋势数据</p>
        </el-card>
      </section>

      <h4 class="gw-section-title">应用明细</h4>
      <el-table :data="apps" highlight-current-row @row-click="selectApp" v-loading="appsLoading" stripe size="small">
        <el-table-column prop="app_id" label="应用 ID" min-width="160" />
        <el-table-column prop="log_count" label="日志数" width="100" />
        <el-table-column prop="total_input_tokens" label="输入 Token" width="120" />
        <el-table-column prop="total_output_tokens" label="输出 Token" width="120" />
        <el-table-column prop="total_total_tokens" label="总 Token" width="120" />
        <el-table-column prop="first_created_at" label="首次" width="180">
          <template #default="{ row }">{{ formatBeijingTime(row.first_created_at) }}</template>
        </el-table-column>
        <el-table-column prop="last_created_at" label="最近" width="180">
          <template #default="{ row }">{{ formatBeijingTime(row.last_created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="danger" size="small" text @click.stop="deleteApp(row.app_id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-if="appTotal > appPageSize" class="pagination" background layout="total, sizes, prev, pager, next"
        :total="appTotal" v-model:page-size="appPageSize" v-model:current-page="appCurrentPage"
        @size-change="loadApps" @current-change="loadApps" />
    </div>

    <!-- Sessions View -->
    <div v-show="currentView === 'sessions'" class="page-body">
      <div class="context-bar"><el-tag>{{ selectedApp }}</el-tag></div>
      <el-table :data="sessions" highlight-current-row @row-click="selectSession" v-loading="sessionsLoading" stripe size="small">
        <el-table-column prop="session_id" label="会话 ID" min-width="160" />
        <el-table-column prop="log_count" label="日志数" width="100" />
        <el-table-column prop="total_input_tokens" label="输入 Token" width="120" />
        <el-table-column prop="total_output_tokens" label="输出 Token" width="120" />
        <el-table-column prop="total_total_tokens" label="总 Token" width="120" />
        <el-table-column prop="first_created_at" label="首次" width="180">
          <template #default="{ row }">{{ formatBeijingTime(row.first_created_at) }}</template>
        </el-table-column>
        <el-table-column prop="last_created_at" label="最近" width="180">
          <template #default="{ row }">{{ formatBeijingTime(row.last_created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="danger" size="small" text @click.stop="deleteSession(row.session_id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-if="sessionTotal > sessionPageSize" class="pagination" background layout="total, sizes, prev, pager, next"
        :total="sessionTotal" v-model:page-size="sessionPageSize" v-model:current-page="sessionCurrentPage"
        @size-change="loadSessions" @current-change="loadSessions" />
    </div>

    <!-- Logs View -->
    <div v-show="currentView === 'logs'" class="page-body">
      <div class="context-bar">
        <el-tag type="primary">{{ selectedApp }}</el-tag>
        <el-tag>{{ selectedSession }}</el-tag>
      </div>
      <el-form :inline="true" :model="filters" size="small" class="filter-form">
        <el-form-item label="Model">
          <el-select
            v-model="filters.model"
            placeholder="全部"
            clearable
            filterable
            style="width:200px"
          >
            <el-option v-for="m in logModelOptions" :key="m" :label="m" :value="m" />
          </el-select>
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
        <el-table-column prop="model" label="Model" min-width="120" />
        <el-table-column label="源模型" width="100" align="center">
          <template #default="{ row }">
            <el-button
              v-if="row.upstream_model"
              size="small"
              text
              type="primary"
              @click="openUpstreamModelModal(row)"
            >查看</el-button>
            <span v-else class="log-upstream-model-empty">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="status_code" label="Status" width="80" sortable="custom">
          <template #default="{ row }">
            <el-tag :type="row.status_code === 200 ? 'success' : 'danger'" size="small">{{ row.status_code }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="latency_ms" label="耗时(s)" width="100" sortable="custom">
          <template #default="{ row }">{{ formatLatencySeconds(row.latency_ms) }}</template>
        </el-table-column>
        <el-table-column prop="client_ip" label="IP" width="130" />
        <el-table-column label="Tokens(in/out/total)" width="200">
          <template #default="{ row }">
            <span class="log-tokens">
              <span class="log-token log-token--in" title="输入">{{ formatToken(row.input_tokens) }}</span>
              <span class="log-token-sep">/</span>
              <span class="log-token log-token--out" title="输出">{{ formatToken(row.output_tokens) }}</span>
              <span class="log-token-sep">/</span>
              <span class="log-token log-token--total" title="总计">{{ formatToken(row.total_tokens) }}</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="180" sortable="custom">
          <template #default="{ row }">{{ formatBeijingTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="请求" width="80" align="center">
          <template #default="{ row }">
            <el-button size="small" @click="openModal('请求体', formatBody(row.request_body))">请求</el-button>
          </template>
        </el-table-column>
        <el-table-column label="响应" width="80" align="center">
          <template #default="{ row }">
            <el-button size="small" @click="openBodyModal(row)">响应</el-button>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click.stop="openReplayDialog(row)">重放</el-button>
            <el-button size="small" type="danger" text @click.stop="deleteLog(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-if="logTotal > logPageSize" class="pagination" background layout="total, sizes, prev, pager, next"
        :total="logTotal" v-model:page-size="logPageSize" v-model:current-page="logCurrentPage"
        @size-change="onLogPageSizeChange" @current-change="onLogPageChange" />
    </div>

    <!-- Body Modal -->
    <el-dialog v-model="modalVisible" :title="modalTitle" :width="modalWidth" destroy-on-close center class="log-json-dialog">
      <div class="log-json-toolbar">
        <el-button size="small" @click="copyModalContent">复制</el-button>
        <el-button v-if="modalStreamToggle" size="small" @click="toggleStreamView">
          {{ modalStreamMode ? '转为非流式' : '转为流式视图' }}
        </el-button>
      </div>
      <div class="json-preview" v-html="modalContent"></div>
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
    <el-dialog
      v-model="showClientInfo"
      :title="clientInfoTitle"
      width="680px"
      destroy-on-close
      center
      class="client-info-dialog"
    >
      <div v-if="clientInfoLoading" class="client-info-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>加载中...</span>
      </div>
      <div v-else-if="clientInfoError" class="client-info-error">加载失败，请稍后重试</div>
      <div v-else-if="clientInfoData" class="client-info">
        <section class="client-info-section">
          <h4 class="client-info-heading">连接信息</h4>
          <dl class="client-info-meta">
            <div class="client-info-meta-row">
              <dt>应用 ID</dt>
              <dd><code>{{ clientInfoData.app_id }}</code></dd>
            </div>
            <div class="client-info-meta-row">
              <dt>网关地址</dt>
              <dd><code>{{ clientInfoData.gateway_base_url }}</code></dd>
            </div>
            <div class="client-info-meta-row">
              <dt>API Key</dt>
              <dd><code class="client-info-key">{{ clientInfoData.gateway_api_key }}</code></dd>
            </div>
            <div class="client-info-meta-row">
              <dt>Models</dt>
              <dd><code>{{ clientInfoData.v1_models_url }}</code></dd>
            </div>
            <div class="client-info-meta-row">
              <dt>Chat</dt>
              <dd><code>{{ clientInfoData.v1_chat_completions_url }}</code></dd>
            </div>
          </dl>
        </section>

        <section class="client-info-section">
          <h4 class="client-info-heading">X-Session-Id</h4>
          <div class="client-info-callout">
            <p>
              在 <code>POST /v1/chat/completions</code> 请求头中可选携带
              <code>X-Session-Id</code>，用于观测页按「应用 → 会话 → 日志」分组追踪。
            </p>
            <ul>
              <li>不传时默认为 <code>default</code></li>
              <li>同时用于网关路由的会话粘性（一致性哈希选源）</li>
              <li>建议按业务语义命名，如 <code>user-42-chat-1</code>、<code>thread-9</code></li>
            </ul>
          </div>
        </section>

        <section class="client-info-section">
          <h4 class="client-info-heading">curl 示例</h4>
          <div class="client-info-example">
            <div class="client-info-example-head">
              <span class="client-info-example-label">列表模型</span>
              <el-button size="small" text @click="copyClientInfoCurl(clientInfoCurlModels)">复制</el-button>
            </div>
            <pre>{{ clientInfoCurlModels }}</pre>
          </div>
          <div class="client-info-example">
            <div class="client-info-example-head">
              <span class="client-info-example-label">对话（含 X-Session-Id）</span>
              <el-button size="small" text @click="copyClientInfoCurl(clientInfoCurlChat)">复制</el-button>
            </div>
            <pre>{{ clientInfoCurlChat }}</pre>
          </div>
        </section>
      </div>
    </el-dialog>

    <!-- Replay Dialog -->
    <el-dialog v-model="showReplayDialog" title="重放请求" width="560px" destroy-on-close center>
      <p class="hint">使用当前日志的请求体，通过所选上游与模型重新调用一次（不会写入新日志）。</p>
      <el-form label-position="top" size="small">
        <el-form-item label="上游">
          <el-select v-model="replayUpstreamId" filterable style="width:100%" placeholder="选择上游" @change="onReplayUpstreamChange">
            <el-option v-for="o in replayUpstreamOptions" :key="o.id" :label="`${o.name} (${o.base_url})`" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型">
          <el-select v-model="replayModel" filterable :disabled="!replayUpstreamId" style="width:100%" placeholder="请先选择上游">
            <el-option v-for="m in replayModels" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showReplayDialog = false">取消</el-button>
        <el-button type="primary" :loading="replayLoading" :disabled="!replayUpstreamId || !replayModel" @click="runReplay">
          开始重放
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Refresh, Loading } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiGet, apiDelete, apiPost } from '../../composables/useApi'
import { formatBeijingTime } from '../../utils/formatTime'

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
const dashboardLoading = ref(false)
const dashboardStats = ref<any>(null)

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
  model: '',
  client_ip: '',
  timeRange: null as [string, string] | null,
})

const logModelOptions = ref<string[]>([])

const sortOrder = reactive({ field: 'created_at', dir: 'desc' as 'asc' | 'desc' })

const modalVisible = ref(false)
const modalTitle = ref('')
const modalContent = ref('')
const modalCopyText = ref('')
const modalWidth = ref('1024px')
const modalStreamToggle = ref(false)
const modalStreamMode = ref(true)
let modalRawBody = ''

interface ClientInfoData {
  app_id: string
  gateway_base_url: string
  gateway_api_key: string
  v1_models_url: string
  v1_chat_completions_url: string
}

const showClientInfo = ref(false)
const clientInfoLoading = ref(false)
const clientInfoError = ref(false)
const clientInfoData = ref<ClientInfoData | null>(null)
const clientInfoTitle = ref('对外调用说明')

const clientInfoCurlModels = computed(() => {
  const d = clientInfoData.value
  if (!d) return ''
  return `curl ${d.v1_models_url} -H "Authorization: Bearer ${d.gateway_api_key}"`
})

const clientInfoCurlChat = computed(() => {
  const d = clientInfoData.value
  if (!d) return ''
  return `curl ${d.v1_chat_completions_url} -H "Content-Type: application/json" -H "Authorization: Bearer ${d.gateway_api_key}" -H "X-Session-Id: user-42-chat-1" -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Hello!"}]}'`
})

const showAppPicker = ref(false)
const appPickerOptions = ref<string[]>([])
const appPickerSelected = ref('')
let appPickerResolve: ((v: string | null) => void) | null = null

const showReplayDialog = ref(false)
const replayLogId = ref(0)
const replayUpstreamId = ref(0)
const replayModel = ref('')
const replayUpstreamOptions = ref<any[]>([])
const replayModels = ref<string[]>([])
const replayLoading = ref(false)

const viewTitle = computed(() => {
  if (currentView.value === 'sessions') return '· 会话列表'
  if (currentView.value === 'logs') return '· 会话日志'
  return '· 应用列表 · 仪表盘'
})

const dashboardSummary = computed(() => dashboardStats.value?.summary || {})
const dashboardByApp = computed(() => dashboardStats.value?.by_app || [])
const dashboardTimeline = computed(() => dashboardStats.value?.timeline || [])

const maxAppLogCount = computed(() => {
  const values = dashboardByApp.value.map((item: any) => Number(item.log_count) || 0)
  return Math.max(...values, 1)
})

const maxAppTotalTokens = computed(() => {
  const values = dashboardByApp.value.map((item: any) => Number(item.total_total_tokens) || 0)
  return Math.max(...values, 1)
})

const maxTimelineLogCount = computed(() => {
  const values = dashboardTimeline.value.map((item: any) => Number(item.log_count) || 0)
  return Math.max(...values, 1)
})

const tokenMixInPercent = computed(() => {
  const total = Number(dashboardSummary.value.total_total_tokens) || 0
  if (!total) return 0
  return Math.round((Number(dashboardSummary.value.total_input_tokens) || 0) / total * 100)
})

const tokenMixOutPercent = computed(() => {
  const total = Number(dashboardSummary.value.total_total_tokens) || 0
  if (!total) return 0
  return Math.round((Number(dashboardSummary.value.total_output_tokens) || 0) / total * 100)
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

async function loadAppDashboard() {
  dashboardLoading.value = true
  try {
    dashboardStats.value = await apiGet<any>('/gateway/logs/apps/stats', { top_n: 10, timeline_days: 14 })
  } catch (e: any) { ElMessage.error(e.message) }
  finally { dashboardLoading.value = false }
}

async function loadApps() {
  appsLoading.value = true
  try {
    const offset = (appCurrentPage.value - 1) * appPageSize.value
    const data = await apiGet<any>('/gateway/logs/apps', { limit: appPageSize.value, offset })
    apps.value = data.items || []
    appTotal.value = data.total || 0
  } catch (e: any) { ElMessage.error(e.message) }
  finally { appsLoading.value = false }
  await loadAppDashboard()
}

async function loadSessions() {
  if (!selectedApp.value) return
  sessionsLoading.value = true
  try {
    const offset = (sessionCurrentPage.value - 1) * sessionPageSize.value
    const data = await apiGet<any>('/gateway/logs/sessions', { app_id: selectedApp.value, limit: sessionPageSize.value, offset })
    sessions.value = data.items || []
    sessionTotal.value = data.total || 0
  } catch (e: any) { ElMessage.error(e.message) }
  finally { sessionsLoading.value = false }
}

async function loadLogModelOptions() {
  if (!selectedApp.value || !selectedSession.value) {
    logModelOptions.value = []
    return
  }
  try {
    const data = await apiGet<any>('/gateway/logs/models', {
      app_id: selectedApp.value,
      session_id: selectedSession.value,
    })
    logModelOptions.value = data.items || []
    if (filters.model && !logModelOptions.value.includes(filters.model)) {
      logModelOptions.value = [filters.model, ...logModelOptions.value]
    }
  } catch (e: any) {
    ElMessage.error(e.message)
  }
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
    if (selectedSession.value) params.session_id = selectedSession.value
    if (filters.model) params.model = filters.model
    if (filters.client_ip) params.client_ip = filters.client_ip
    if (filters.timeRange && filters.timeRange.length === 2) {
      params.start_time = filters.timeRange[0]
      params.end_time = filters.timeRange[1]
    }
    const data = await apiGet<any>('/gateway/logs', params)
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
  logCurrentPage.value = 1
  filters.model = ''
  currentView.value = 'logs'
  router.replace({ query: { app_id: selectedApp.value, session_id: row.session_id } })
  loadLogModelOptions()
  searchLogs()
}

async function deleteApp(appId: string) {
  try { await ElMessageBox.confirm(`确认删除应用 ${appId} 的所有日志？`, '确认', { type: 'warning' }) } catch { return }
  try {
    await apiDelete(`/gateway/logs/apps/${encodeURIComponent(appId)}`)
    ElMessage.success('已删除')
    await loadApps()
  }
  catch (e: any) { ElMessage.error(e.message) }
}

async function deleteSession(sessionId: string) {
  try { await ElMessageBox.confirm(`确认删除会话 ${sessionId} 的所有日志？`, '确认', { type: 'warning' }) } catch { return }
  try {
    await apiDelete(`/gateway/logs/sessions?app_id=${encodeURIComponent(selectedApp.value)}&session_id=${encodeURIComponent(sessionId)}`)
    ElMessage.success('已删除'); loadSessions()
  } catch (e: any) { ElMessage.error(e.message) }
}

async function deleteLog(logId: number) {
  try { await ElMessageBox.confirm(`确认删除日志 #${logId}？`, '确认', { type: 'warning' }) } catch { return }
  try { await apiDelete(`/gateway/logs/${logId}`); ElMessage.success('已删除'); searchLogs() }
  catch (e: any) { ElMessage.error(e.message) }
}

async function loadReplayUpstreamOptions() {
  try {
    const d = await apiGet<any>('/gateway/admin/model-capability-probe/options')
    replayUpstreamOptions.value = d.upstreams || []
    if (replayUpstreamOptions.value.length > 0) {
      replayUpstreamId.value = replayUpstreamOptions.value[0].id
      await onReplayUpstreamChange()
    }
  } catch (e: any) { ElMessage.error(e.message) }
}

async function onReplayUpstreamChange() {
  replayModels.value = []
  replayModel.value = ''
  if (!replayUpstreamId.value) return
  try {
    const d = await apiGet<any>(`/gateway/admin/model-capability-probe/models?upstream_id=${replayUpstreamId.value}`)
    replayModels.value = d.models || []
  } catch (e: any) { ElMessage.error(e.message) }
}

async function openReplayDialog(row: any) {
  replayLogId.value = row.id
  replayUpstreamId.value = 0
  replayModel.value = ''
  replayModels.value = []
  showReplayDialog.value = true
  await loadReplayUpstreamOptions()
}

async function runReplay() {
  if (!replayLogId.value || !replayUpstreamId.value || !replayModel.value) return
  replayLoading.value = true
  try {
    const data = await apiPost<any>(`/gateway/logs/${replayLogId.value}/replay`, {
      upstream_id: replayUpstreamId.value,
      model: replayModel.value,
    })
    showReplayDialog.value = false
    const title = `重放结果 · HTTP ${data.status_code} · ${data.latency_ms}ms · ${data.model}`
    if (data.ok) {
      ElMessage.success(`重放成功 (${data.latency_ms}ms)`)
    } else {
      ElMessage.warning(`重放完成，上游返回 HTTP ${data.status_code}`)
    }
    openModal(title, formatBody(data.response_body))
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    replayLoading.value = false
  }
}

function formatLatencySeconds(ms: number | null | undefined): string {
  if (ms == null || Number.isNaN(Number(ms))) return '-'
  return (Number(ms) / 1000).toFixed(2)
}

function formatToken(value: number | null | undefined): string {
  if (value == null) return '-'
  return String(value)
}

function formatCompactNumber(value: number | null | undefined): string {
  const n = Number(value ?? 0)
  if (Number.isNaN(n)) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`
  if (n >= 10_000) return `${(n / 1_000).toFixed(1).replace(/\.0$/, '')}K`
  return n.toLocaleString('zh-CN')
}

function barPercent(value: number | null | undefined, max: number): number {
  const n = Number(value ?? 0)
  if (!max || Number.isNaN(n) || n <= 0) return 0
  return Math.max(4, Math.round((n / max) * 100))
}

function tokenInShare(item: any): number {
  const total = Number(item.total_total_tokens) || 0
  if (!total) return 50
  return (Number(item.total_input_tokens) || 0) / total * 100
}

function formatTimelineLabel(date: string): string {
  if (!date) return ''
  const parts = date.split('-')
  return parts.length >= 3 ? `${parts[1]}/${parts[2]}` : date
}

function sparkBarHeight(value: number | null | undefined): string {
  const n = Number(value ?? 0)
  if (!n) return '4px'
  const pct = barPercent(n, maxTimelineLogCount.value)
  return `${Math.max(8, Math.round(pct * 0.88))}px`
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

function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function setModalJson(text: string) {
  modalCopyText.value = text
  modalContent.value = jsonHighlight(text)
}

function openBodyModal(log: any) {
  const raw = typeof log.response_body === 'string' ? log.response_body : JSON.stringify(log.response_body)
  modalRawBody = raw
  if (raw.trim().startsWith('data:')) {
    modalStreamToggle.value = true
    modalStreamMode.value = true
    modalTitle.value = 'Response Body (流式 SSE)'
    modalCopyText.value = raw
    modalContent.value = escapeHtml(raw)
  } else {
    modalStreamToggle.value = false
    modalTitle.value = 'Response Body'
    setModalJson(formatBody(log.response_body))
  }
  modalVisible.value = true
}

function toggleStreamView() {
  modalStreamMode.value = !modalStreamMode.value
  if (!modalStreamMode.value) {
    modalTitle.value = 'Response Body (转为非流式)'
    setModalJson(buildNonStreamJsonFromSse(modalRawBody))
  } else {
    modalTitle.value = 'Response Body (流式 SSE)'
    modalCopyText.value = modalRawBody
    modalContent.value = escapeHtml(modalRawBody)
  }
}

function openUpstreamModelModal(row: any) {
  const upstreamModel = String(row.upstream_model || '').trim()
  if (!upstreamModel) return
  modalTitle.value = `源模型 · 日志 #${row.id}`
  modalCopyText.value = upstreamModel
  modalContent.value = escapeHtml(upstreamModel)
  modalStreamToggle.value = false
  modalVisible.value = true
}

function openModal(title: string, body: string) {
  modalTitle.value = title
  setModalJson(typeof body === 'string' ? body : JSON.stringify(body, null, 2))
  modalStreamToggle.value = false
  modalVisible.value = true
}

async function copyModalContent() {
  if (!modalCopyText.value) return
  try {
    await navigator.clipboard.writeText(modalCopyText.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

async function copyClientInfoCurl(text: string) {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
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
      const data = await apiGet<any>('/gateway/admin/gateway-client-keys')
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
  clientInfoData.value = null
  clientInfoError.value = false
  clientInfoTitle.value = `对外调用说明 · ${appId}`
  try {
    const data = await apiGet<any>('/gateway/admin/client-info', { app_id: appId })
    clientInfoData.value = {
      app_id: data.app_id || appId,
      gateway_base_url: data.gateway_base_url,
      gateway_api_key: data.gateway_api_key || '(暂无密钥)',
      v1_models_url: data.v1_models_url,
      v1_chat_completions_url: data.v1_chat_completions_url,
    }
  } catch {
    clientInfoError.value = true
  } finally {
    clientInfoLoading.value = false
  }
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
    currentView.value = 'logs'
    loadLogModelOptions()
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

<style scoped>
.log-tokens {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-variant-numeric: tabular-nums;
  font-family: ui-monospace, "Cascadia Code", "SF Mono", monospace;
  font-size: 12px;
}

.log-token {
  font-weight: 600;
}

.log-token--in {
  color: #2563eb;
}

.log-token--out {
  color: #16a34a;
}

.log-token--total {
  color: #9333ea;
}

.log-token-sep {
  color: var(--sl-text-faint);
  font-weight: 400;
  margin: 0 1px;
}

.log-json-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}

.gw-section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--sl-text);
  margin: 8px 0 12px;
}

.gw-dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 8px;
}

.gw-dash-kpis {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.gw-dash-kpi {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px;
  border-radius: var(--sl-radius-md);
  border: 1px solid var(--sl-border);
  background: var(--sl-bg-elevated);
  box-shadow: var(--sl-shadow-sm);
}

.gw-dash-kpi-value {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--sl-accent);
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}

.gw-dash-kpi-label {
  font-size: 12px;
  color: var(--sl-text-muted);
}

.gw-dash-kpi--in .gw-dash-kpi-value { color: #2563eb; }
.gw-dash-kpi--out .gw-dash-kpi-value { color: #16a34a; }
.gw-dash-kpi--total .gw-dash-kpi-value { color: #9333ea; }

.gw-dash-token-mix {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px 16px;
  border-radius: var(--sl-radius-md);
  border: 1px solid var(--sl-border);
  background: var(--sl-bg-elevated);
}

.gw-dash-token-mix-label {
  font-size: 12px;
  color: var(--sl-text-muted);
  flex-shrink: 0;
}

.gw-dash-token-mix-bar {
  flex: 1;
  min-width: 160px;
  height: 10px;
  display: flex;
  border-radius: 999px;
  overflow: hidden;
  background: var(--sl-border);
}

.gw-dash-token-mix-in {
  background: #2563eb;
}

.gw-dash-token-mix-out {
  background: #16a34a;
}

.gw-dash-token-mix-legend {
  font-size: 12px;
  flex-shrink: 0;
}

.gw-dash-charts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.gw-dash-card :deep(.el-card__header) {
  padding: 12px 16px;
  font-size: 13px;
  font-weight: 600;
}

.gw-dash-card :deep(.el-card__body) {
  padding: 12px 16px 16px;
}

.gw-dash-bars {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.gw-dash-bar-row {
  display: grid;
  grid-template-columns: minmax(72px, 120px) 1fr minmax(56px, 88px);
  gap: 10px;
  align-items: center;
}

.gw-dash-bar-label {
  font-size: 12px;
  color: var(--sl-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.gw-dash-bar-track {
  height: 10px;
  background: #faf6ee;
  border-radius: 999px;
  overflow: hidden;
}

.gw-dash-bar-fill {
  height: 100%;
  border-radius: 999px;
  min-width: 4px;
}

.gw-dash-bar-fill--logs {
  background: linear-gradient(90deg, #eab308, var(--sl-accent));
}

.gw-dash-stack {
  display: flex;
  height: 100%;
  min-width: 4px;
  border-radius: 999px;
  overflow: hidden;
}

.gw-dash-stack-in {
  background: #2563eb;
}

.gw-dash-stack-out {
  background: #16a34a;
}

.gw-dash-bar-value {
  font-size: 12px;
  font-weight: 600;
  color: var(--sl-text);
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.gw-dash-bar-value--tokens {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 1px;
  font-size: 11px;
}

.gw-dash-spark {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  min-height: 140px;
  padding-top: 8px;
}

.gw-dash-spark-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.gw-dash-spark-value {
  font-size: 10px;
  color: var(--sl-text-muted);
  min-height: 14px;
  font-variant-numeric: tabular-nums;
}

.gw-dash-spark-bar-wrap {
  width: 100%;
  height: 88px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.gw-dash-spark-bar {
  width: 100%;
  max-width: 28px;
  border-radius: 6px 6px 4px 4px;
  background: linear-gradient(180deg, #fde68a, var(--sl-accent));
  min-height: 4px;
  transition: height 0.25s ease;
}

.gw-dash-spark-bar--empty {
  background: var(--sl-border);
  opacity: 0.6;
}

.gw-dash-spark-label {
  font-size: 10px;
  color: var(--sl-text-faint);
  white-space: nowrap;
}

@media (max-width: 1100px) {
  .gw-dash-kpis {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .gw-dash-charts {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .gw-dash-kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .gw-dash-bar-row {
    grid-template-columns: 72px 1fr 52px;
  }
}

.client-info-dialog :deep(.el-dialog__body) {
  padding-top: 8px;
  padding-bottom: 24px;
}

.client-info-loading,
.client-info-error {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px 16px;
  color: var(--sl-text-muted);
}

.client-info-error {
  color: #dc2626;
}

.client-info {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.client-info-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.client-info-heading {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--sl-text);
  letter-spacing: 0.02em;
}

.client-info-meta {
  margin: 0;
  padding: 14px 16px;
  border-radius: var(--sl-radius-md);
  border: 1px solid var(--sl-border);
  background: var(--sl-bg);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.client-info-meta-row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.client-info-meta-row dt {
  margin: 0;
  font-size: 12px;
  font-weight: 500;
  color: var(--sl-text-muted);
  line-height: 1.6;
}

.client-info-meta-row dd {
  margin: 0;
  font-size: 13px;
  color: var(--sl-text);
  line-height: 1.6;
  word-break: break-all;
}

.client-info-meta-row code {
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 6px;
  background: var(--sl-accent-subtle);
  border: 1px solid var(--sl-border);
}

.client-info-key {
  display: inline-block;
  max-width: 100%;
}

.client-info-callout {
  padding: 14px 16px 14px 18px;
  border-radius: var(--sl-radius-md);
  border: 1px solid var(--sl-accent-border);
  border-left: 3px solid var(--sl-accent);
  background: var(--sl-accent-subtle);
}

.client-info-callout p {
  margin: 0 0 10px;
  font-size: 13px;
  line-height: 1.65;
  color: var(--sl-text-secondary);
}

.client-info-callout p:last-child {
  margin-bottom: 0;
}

.client-info-callout ul {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.65;
  color: var(--sl-text-secondary);
}

.client-info-callout li + li {
  margin-top: 4px;
}

.client-info-callout code {
  font-size: 12px;
  padding: 1px 5px;
  border-radius: 5px;
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid var(--sl-border);
}

.client-info-example {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.client-info-example + .client-info-example {
  margin-top: 4px;
}

.client-info-example-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.client-info-example-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--sl-text-muted);
}

.client-info-example pre {
  margin: 0;
  padding: 12px 14px;
  border-radius: var(--sl-radius-sm);
  border: 1px solid var(--sl-border);
  background: #f0eeea;
  color: var(--sl-text-secondary);
  font-size: 11px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-all;
  overflow-x: auto;
  font-family: ui-monospace, "Cascadia Code", "SF Mono", monospace;
}
</style>
