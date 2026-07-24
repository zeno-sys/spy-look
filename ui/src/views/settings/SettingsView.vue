<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h3>设置</h3>
        <p class="page-subtitle">全局配置；后续可在此扩展更多设置项。</p>
      </div>
      <div class="header-actions">
        <el-button @click="loadConfig" :loading="loading">刷新</el-button>
      </div>
    </div>

    <div class="page-body">
      <el-tabs v-model="activeTab" class="settings-tabs">
        <el-tab-pane label="大模型" name="llm">
          <el-card class="section-card" v-loading="loading">
            <template #header><span>全局大模型</span></template>
            <p class="hint" style="margin-bottom:16px">
              配置应用内共用的大模型连接。可从网关已有模型源选用，或自行填写 URL / API Key。
              <code>extra_params</code> 对应 SDK 的 <code>extra_body</code>，会合并进 chat completions 请求体。
            </p>

            <el-form :model="form" label-position="top">
              <el-form-item label="配置方式">
                <el-radio-group v-model="form.mode" @change="onModeChange">
                  <el-radio-button value="upstream">从网关模型源选择</el-radio-button>
                  <el-radio-button value="custom">自定义连接</el-radio-button>
                </el-radio-group>
              </el-form-item>

              <template v-if="form.mode === 'upstream'">
                <el-form-item label="模型源">
                  <el-select
                    v-model="form.upstream_id"
                    filterable
                    clearable
                    placeholder="选择网关中的模型源"
                    style="width:100%"
                    @change="onUpstreamChange"
                  >
                    <el-option
                      v-for="u in upstreamOptions"
                      :key="u.id"
                      :label="`${u.name} (${u.base_url})`"
                      :value="u.id"
                    />
                  </el-select>
                  <p v-if="!upstreamOptions.length" class="hint">
                    暂无可用模型源，请先到「大模型网关 · 模型配置」添加。
                  </p>
                </el-form-item>
                <el-form-item label="Base URL">
                  <el-input :model-value="selectedUpstream?.base_url || ''" disabled placeholder="由模型源决定" />
                </el-form-item>
                <el-form-item label="API Key">
                  <el-input
                    :model-value="selectedUpstream?.api_key_masked || '（使用模型源密钥）'"
                    disabled
                  />
                </el-form-item>
              </template>

              <template v-else>
                <el-form-item label="Base URL">
                  <el-input v-model="form.base_url" placeholder="https://api.example.com/v1" @change="onCustomCredentialsChange" />
                </el-form-item>
                <el-form-item label="API Key">
                  <el-input
                    v-model="form.api_key"
                    type="password"
                    show-password
                    :placeholder="apiKeyPlaceholder"
                    @change="onCustomCredentialsChange"
                  />
                  <p class="hint">留空表示不修改已保存的密钥。</p>
                </el-form-item>
              </template>

              <el-form-item label="模型">
                <el-select
                  v-model="form.model"
                  filterable
                  allow-create
                  default-first-option
                  :disabled="modelSelectDisabled"
                  style="width:100%"
                  :placeholder="modelPlaceholder"
                  :loading="modelsLoading"
                >
                  <el-option v-for="m in modelOptions" :key="m" :label="m" :value="m" />
                </el-select>
                <p class="hint">可从列表选择，也可直接输入模型名。</p>
              </el-form-item>

              <el-form-item label="extra_params（JSON）">
                <el-input
                  v-model="extraParamsText"
                  type="textarea"
                  :rows="6"
                  placeholder='例如：{"enable_thinking": false, "thinking_budget": 1024}'
                  :class="{ 'is-error-input': extraParamsError }"
                />
                <p v-if="extraParamsError" class="hint hint-error">{{ extraParamsError }}</p>
                <p v-else class="hint">可选。等价于 SDK 的 extra_body 参数；请勿覆盖 model / messages。</p>
              </el-form-item>

              <el-form-item>
                <el-button type="primary" :loading="saving" @click="saveConfig">保存</el-button>
                <el-button :loading="testing" @click="testConnectivity">连通性测试</el-button>
              </el-form-item>
            </el-form>
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog
      v-model="testDialogVisible"
      :title="testResult?.ok ? '连通成功' : '连通失败'"
      width="720px"
      destroy-on-close
    >
      <el-descriptions v-if="testResult" :column="2" border size="small" style="margin-bottom:12px">
        <el-descriptions-item label="结果">
          <el-tag :type="testResult.ok ? 'success' : 'danger'" size="small">
            {{ testResult.ok ? '成功' : '失败' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item v-if="testResult.latency_ms != null" label="耗时">
          {{ testResult.latency_ms }} ms
        </el-descriptions-item>
        <el-descriptions-item v-if="testResult.upstream_status_code" label="HTTP 状态">
          {{ testResult.upstream_status_code }}
        </el-descriptions-item>
        <el-descriptions-item v-if="testResult.request_url" label="请求地址" :span="2">
          {{ testResult.request_url }}
        </el-descriptions-item>
        <el-descriptions-item v-if="testResult.error" label="错误" :span="2">
          {{ testResult.error }}
        </el-descriptions-item>
      </el-descriptions>
      <el-tabs v-model="testDialogTab" class="test-result-tabs">
        <el-tab-pane label="请求体" name="request">
          <pre class="test-body-preview">{{ testRequestBodyText }}</pre>
        </el-tab-pane>
        <el-tab-pane label="响应体" name="response">
          <pre class="test-body-preview">{{ testBodyText }}</pre>
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button type="primary" @click="testDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { apiGet, apiPatch, apiPost } from '../../composables/useApi'

interface UpstreamOption {
  id: number
  name: string
  base_url: string
  api_key_masked?: string
  enabled?: boolean
}

interface TestResult {
  ok: boolean
  error?: string
  latency_ms?: number
  upstream_status_code?: number
  request_url?: string
  request_body?: unknown
  body?: unknown
}

const activeTab = ref('llm')
const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const modelsLoading = ref(false)
const maskedApiKey = ref('')
const upstreamOptions = ref<UpstreamOption[]>([])
const modelOptions = ref<string[]>([])
const extraParamsText = ref('{}')
const extraParamsError = ref('')
const testDialogVisible = ref(false)
const testDialogTab = ref<'request' | 'response'>('response')
const testResult = ref<TestResult | null>(null)

function formatJson(value: unknown): string {
  if (value == null) return ''
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

const testRequestBodyText = computed(() => {
  const result = testResult.value
  if (!result) return ''
  return formatJson(result.request_body) || '（无）'
})

const testBodyText = computed(() => {
  const result = testResult.value
  if (!result) return ''
  if (result.error && result.body == null) return String(result.error)
  return formatJson(result.body ?? result)
})

const form = reactive({
  mode: 'custom' as 'upstream' | 'custom',
  upstream_id: null as number | null,
  base_url: '',
  api_key: '',
  model: '',
})

const selectedUpstream = computed(() =>
  upstreamOptions.value.find((u) => u.id === form.upstream_id) || null,
)

const apiKeyPlaceholder = computed(() =>
  maskedApiKey.value ? `已保存: ${maskedApiKey.value}` : 'sk-...',
)

const modelSelectDisabled = computed(() => {
  if (form.mode === 'upstream') return !form.upstream_id
  return false
})

const modelPlaceholder = computed(() => {
  if (form.mode === 'upstream' && !form.upstream_id) return '请先选择模型源'
  return '选择或输入模型名'
})

function parseExtraParams(): Record<string, unknown> | null {
  const raw = extraParamsText.value.trim() || '{}'
  try {
    const parsed = JSON.parse(raw)
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
      extraParamsError.value = 'extra_params 必须是 JSON 对象'
      return null
    }
    extraParamsError.value = ''
    return parsed as Record<string, unknown>
  } catch {
    extraParamsError.value = 'extra_params JSON 格式无效'
    return null
  }
}

watch(extraParamsText, () => {
  if (extraParamsError.value) parseExtraParams()
})

async function loadUpstreamOptions() {
  try {
    const d = await apiGet<{ upstreams: UpstreamOption[] }>('/settings/admin/llm/upstream-options')
    upstreamOptions.value = d.upstreams || []
  } catch (e: any) {
    ElMessage.error(e.message || '加载模型源失败')
  }
}

async function loadUpstreamModels(upstreamId: number) {
  modelsLoading.value = true
  try {
    const d = await apiGet<{ models: string[] }>(
      `/gateway/admin/model-capability-probe/models?upstream_id=${upstreamId}`,
    )
    modelOptions.value = d.models || []
  } catch {
    modelOptions.value = []
  } finally {
    modelsLoading.value = false
  }
}

async function loadCustomModels() {
  const uri = form.base_url.trim()
  if (!uri) {
    modelOptions.value = []
    return
  }
  const key = form.api_key.trim() || undefined
  modelsLoading.value = true
  try {
    const d = await apiPost<{ models: string[] }>('/gateway/admin/model-capability-probe/models/custom', {
      uri,
      api_key: key || '',
    })
    modelOptions.value = d.models || []
  } catch {
    modelOptions.value = []
  } finally {
    modelsLoading.value = false
  }
}

function onModeChange() {
  modelOptions.value = []
  if (form.mode === 'upstream') {
    form.base_url = ''
    form.api_key = ''
    if (form.upstream_id) void loadUpstreamModels(form.upstream_id)
  } else {
    form.upstream_id = null
    void loadCustomModels()
  }
}

function onUpstreamChange() {
  form.model = ''
  if (form.upstream_id) void loadUpstreamModels(form.upstream_id)
  else modelOptions.value = []
}

let customModelsTimer: ReturnType<typeof setTimeout> | null = null
function onCustomCredentialsChange() {
  if (customModelsTimer) clearTimeout(customModelsTimer)
  customModelsTimer = setTimeout(() => {
    void loadCustomModels()
  }, 400)
}

async function loadConfig() {
  loading.value = true
  try {
    await loadUpstreamOptions()
    const data = await apiGet<any>('/settings/admin/config')
    const llm = data.llm || {}
    form.mode = llm.mode === 'upstream' ? 'upstream' : 'custom'
    form.upstream_id = llm.upstream_id ?? null
    form.base_url = llm.base_url || ''
    form.api_key = ''
    form.model = llm.model || ''
    maskedApiKey.value = typeof llm.api_key === 'string' ? llm.api_key : ''
    const extra = llm.extra_params && typeof llm.extra_params === 'object' ? llm.extra_params : {}
    extraParamsText.value = JSON.stringify(extra, null, 2)
    extraParamsError.value = ''

    if (form.mode === 'upstream' && form.upstream_id) {
      await loadUpstreamModels(form.upstream_id)
    } else if (form.mode === 'custom' && form.base_url) {
      await loadCustomModels()
    }
  } catch (e: any) {
    ElMessage.error(e.message || '加载设置失败')
  } finally {
    loading.value = false
  }
}

function buildLlmPayload(forTest = false) {
  const extra = parseExtraParams()
  if (extra === null) return null

  const payload: Record<string, unknown> = {
    mode: form.mode,
    model: form.model.trim(),
    extra_params: extra,
  }

  if (form.mode === 'upstream') {
    payload.upstream_id = form.upstream_id
  } else {
    payload.base_url = form.base_url.trim()
    if (form.api_key.trim()) {
      payload.api_key = form.api_key.trim()
    } else if (forTest) {
      payload.use_saved_api_key = true
    }
  }
  return payload
}

async function saveConfig() {
  const llm = buildLlmPayload(false)
  if (!llm) {
    ElMessage.error(extraParamsError.value || 'extra_params 无效')
    return
  }
  if (form.mode === 'upstream' && !form.upstream_id) {
    ElMessage.warning('请选择模型源')
    return
  }
  if (form.mode === 'custom' && !form.base_url.trim()) {
    ElMessage.warning('请填写 Base URL')
    return
  }
  if (!form.model.trim()) {
    ElMessage.warning('请填写模型')
    return
  }

  saving.value = true
  try {
    const data = await apiPatch<any>('/settings/admin/config', { llm })
    form.api_key = ''
    maskedApiKey.value = data.llm?.api_key || ''
    ElMessage.success('设置已保存')
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function testConnectivity() {
  const llm = buildLlmPayload(true)
  if (!llm) {
    ElMessage.error(extraParamsError.value || 'extra_params 无效')
    return
  }
  if (form.mode === 'upstream' && !form.upstream_id) {
    ElMessage.warning('请选择模型源')
    return
  }
  if (form.mode === 'custom' && !form.base_url.trim()) {
    ElMessage.warning('请填写 Base URL')
    return
  }
  if (!form.model.trim()) {
    ElMessage.warning('请填写模型')
    return
  }

  testing.value = true
  try {
    const d = await apiPost<TestResult>('/settings/admin/llm/test', llm)
    testResult.value = d
    testDialogTab.value = 'response'
    testDialogVisible.value = true
  } catch (e: any) {
    testResult.value = {
      ok: false,
      error: e.message || '连通性测试失败',
      body: { detail: e.message || '连通性测试失败' },
    }
    testDialogTab.value = 'response'
    testDialogVisible.value = true
  } finally {
    testing.value = false
  }
}

onMounted(loadConfig)
</script>

<style scoped>
.page-subtitle {
  margin-top: 4px;
  font-size: 13px;
  color: var(--sl-text-muted);
}

.hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.hint-error {
  color: var(--el-color-danger);
}

.is-error-input :deep(.el-textarea__inner) {
  border-color: var(--el-color-danger);
}

.settings-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

.test-result-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

.test-body-preview {
  margin: 0;
  max-height: 420px;
  overflow: auto;
  padding: 12px;
  border-radius: 8px;
  background: #f7f5f0;
  border: 1px solid var(--sl-border);
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: ui-monospace, "Cascadia Code", "SF Mono", Consolas, monospace;
}
</style>
