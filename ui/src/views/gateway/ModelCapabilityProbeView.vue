<template>
  <div class="page-container">
    <div class="page-header">
      <div><h3>大模型网关 · 模型能力测试</h3></div>
    </div>

    <div class="page-body">
      <el-card class="section-card">
        <template #header><span>探测配置</span></template>
        <el-alert type="warning" :closable="false" show-icon style="margin-bottom:12px"
          title="将向上游发起多轮 HTTP 请求，可能消耗配额；单次探测通常需数分钟。" />

        <el-radio-group v-model="mode" @change="onModeChange">
          <el-radio-button value="upstream">选择上游</el-radio-button>
          <el-radio-button value="custom">自定义连接</el-radio-button>
        </el-radio-group>

        <div style="margin-top:16px">
          <!-- Upstream Mode -->
          <el-row v-if="mode === 'upstream'" :gutter="12">
            <el-col :span="12">
              <el-form-item label="上游">
                <el-select v-model="selectedUpstreamId" @change="onUpstreamChange" style="width:100%">
                  <el-option v-for="o in upstreamOptions" :key="o.id" :label="o.name + ' (' + o.base_url + ')'" :value="o.id" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="模型">
                <el-select v-model="selectedModel" filterable :disabled="!selectedUpstreamId" style="width:100%" placeholder="请先选择上游">
                  <el-option v-for="m in upstreamModels" :key="m" :label="m" :value="m" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <!-- Custom Mode -->
          <template v-if="mode === 'custom'">
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="API 地址 (uri)">
                  <el-input v-model="customUri" placeholder="https://api.example.com/v1" @input="onCustomCredentialsChange" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="API Key">
                  <el-input v-model="customApiKey" type="password" show-password placeholder="sk-..." @input="onCustomCredentialsChange" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="模型">
              <el-select v-model="selectedModel" filterable :disabled="!customModels.length" style="width:100%" placeholder="请先填写 API 地址与 Key">
                <el-option v-for="m in customModels" :key="m" :label="m" :value="m" />
              </el-select>
            </el-form-item>
          </template>

          <el-button type="primary" :loading="probing" :disabled="!selectedModel" @click="runProbe" style="margin-top:12px">
            {{ probing ? '探测中...' : '开始探测' }}
          </el-button>
        </div>
      </el-card>

      <!-- Report -->
      <el-card v-if="report" class="section-card probe-report" style="margin-top:16px">
        <template #header>
          <div class="card-header">
            <span>探测报告</span>
            <el-tag :type="allPassed ? 'success' : 'warning'" size="large">{{ summaryText }}</el-tag>
          </div>
        </template>

        <el-descriptions :column="2" border size="small" class="probe-meta">
          <el-descriptions-item label="服务地址">{{ report.uri }}</el-descriptions-item>
          <el-descriptions-item label="请求端点">{{ report.endpoint }}</el-descriptions-item>
          <el-descriptions-item label="模型名称">{{ report.model }}</el-descriptions-item>
          <el-descriptions-item v-if="report.total_elapsed_ms" label="总耗时">
            {{ (report.total_elapsed_ms / 1000).toFixed(2) }} s
          </el-descriptions-item>
        </el-descriptions>

        <el-row :gutter="12" class="probe-summary">
          <el-col v-for="cap in capabilities" :key="cap.key" :span="6">
            <div class="probe-stat" :class="capStatClass(cap)">
              <div class="probe-stat__title">{{ cap.title }}</div>
              <div class="probe-stat__status">{{ capStatusLabel(cap) }}</div>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" class="probe-cards">
          <el-col v-for="cap in capabilities" :key="cap.key" :span="12">
            <el-card shadow="hover" class="cap-card" :class="capCardClass(cap)">
              <template #header>
                <div class="card-header">
                  <span>{{ cap.title }}</span>
                  <el-tag :type="capTagType(cap)" size="small">{{ capStatusLabel(cap) }}</el-tag>
                </div>
              </template>

              <p class="cap-desc">{{ cap.desc }}</p>

              <el-alert
                v-if="cap.skipped"
                type="info"
                :closable="false"
                show-icon
                title="已跳过"
                :description="formatCapabilityDetail(cap.key, cap.item)"
              />

              <el-alert
                v-else-if="cap.item.error"
                type="error"
                :closable="false"
                show-icon
                title="请求失败"
              >
                <pre class="cap-error">{{ formatErrorText(cap.item.error) }}</pre>
              </el-alert>

              <template v-else>
                <div class="cap-result" :class="cap.item.supported ? 'cap-result--ok' : 'cap-result--fail'">
                  <div class="cap-result__label">探测结论</div>
                  <div class="cap-result__text">{{ formatCapabilityDetail(cap.key, cap.item) }}</div>
                </div>

                <el-descriptions
                  v-if="cap.key === 'json_mode' && cap.item.parsed"
                  :column="2"
                  border
                  size="small"
                  class="cap-parsed"
                >
                  <el-descriptions-item label="姓名">{{ cap.item.parsed.name }}</el-descriptions-item>
                  <el-descriptions-item label="年龄">{{ cap.item.parsed.age }}</el-descriptions-item>
                  <el-descriptions-item label="城市">{{ cap.item.parsed.city }}</el-descriptions-item>
                  <el-descriptions-item label="爱好">{{ (cap.item.parsed.hobbies || []).join('、') }}</el-descriptions-item>
                </el-descriptions>

                <div v-if="cap.item.content_preview" class="cap-preview">
                  <div class="cap-preview__label">响应预览</div>
                  <pre class="cap-preview__text">{{ cap.item.content_preview }}</pre>
                </div>
              </template>

              <div v-if="capMetaTags(cap).length" class="cap-tags">
                <el-tag
                  v-for="tag in capMetaTags(cap)"
                  :key="tag.label"
                  size="small"
                  :type="tag.type || 'info'"
                >
                  {{ tag.label }}
                </el-tag>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <el-card v-if="report.thinking" shadow="never" class="thinking-card">
          <template #header>
            <div class="card-header">
              <span>思考模式详情</span>
              <el-tag :type="report.thinking.supported ? 'success' : 'info'" size="small">
                {{ report.thinking.mode_label }}
              </el-tag>
            </div>
          </template>

          <p class="thinking-conclusion">{{ report.thinking.detail }}</p>

          <el-table :data="thinkingProbeRows" size="small" border class="thinking-table">
            <el-table-column prop="label" label="探测场景" width="140" />
            <el-table-column prop="thinking" label="思考内容" width="120">
              <template #default="{ row }">
                <el-tag :type="row.thinking === '有思考' ? 'warning' : 'info'" size="small">{{ row.thinking }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="signal" label="检测说明" min-width="200" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { apiGet, apiPost } from '../../composables/useApi'

const mode = ref<'upstream' | 'custom'>('upstream')
const selectedUpstreamId = ref(0)
const selectedModel = ref('')
const customUri = ref('')
const customApiKey = ref('')
const probing = ref(false)
const report = ref<any>(null)

const upstreamOptions = ref<any[]>([])
const upstreamModels = ref<string[]>([])
const customModels = ref<string[]>([])
let debounceTimer: ReturnType<typeof setTimeout> | null = null

const capabilities = computed(() => {
  if (!report.value) return []
  const defs = [
    { key: 'chat_completion', title: '基础对话', desc: '发送简单对话请求，检查模型能否正常返回文本回复' },
    { key: 'tool_calling', title: '工具调用', desc: '检查模型是否支持 Function Calling（tools / tool_calls）' },
    { key: 'json_mode', title: '结构化输出', desc: '检查模型是否支持 json_schema 严格结构化输出并可解析' },
    { key: 'thinking', title: '思考模式', desc: '对比开启/关闭思考参数后，模型是否输出可控制的思考内容' },
  ]
  return defs.map(d => {
    const item = report.value[d.key] || {}
    return { ...d, item, supported: item.supported, skipped: (item.detail || '').includes('跳过') }
  })
})

const thinkingProbeRows = computed(() => {
  const thinking = report.value?.thinking
  if (!thinking) return []
  return [
    {
      label: '开启思考参数',
      thinking: thinking.summary?.['开启思考参数'] || '-',
      signal: thinking.enabled?.detail || '-',
    },
    {
      label: '关闭思考参数',
      thinking: thinking.summary?.['关闭思考参数'] || '-',
      signal: thinking.disabled?.detail || '-',
    },
  ]
})

function truncateText(text: string, max = 120): string {
  const t = String(text || '').trim()
  if (t.length <= max) return t
  return `${t.slice(0, max)}…`
}

function formatErrorText(error: string): string {
  const text = String(error || '').trim()
  try {
    const parsed = JSON.parse(text)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return truncateText(text, 600)
  }
}

function formatCapabilityDetail(key: string, item: any): string {
  if (!item) return '暂无探测结果'
  const detail = String(item.detail || '').trim()

  if (detail.includes('跳过')) {
    return '基础对话未通过，后续能力项未执行探测'
  }

  switch (key) {
    case 'chat_completion':
      if (item.supported) return `模型返回了有效文本：「${truncateText(detail, 80)}」`
      if (detail === '响应无有效 content') return '请求已成功，但响应中未包含可用的文本内容'
      return detail || '未能完成基础对话'

    case 'tool_calling': {
      if (item.supported) {
        const match = detail.match(/(?:tool_calls|function_call):\s*(\S+)/)
        const toolName = match?.[1] || '未知工具'
        return item.legacy_format
          ? `模型通过旧版 function_call 格式调用了工具「${toolName}」`
          : `模型通过 tool_calls 调用了工具「${toolName}」`
      }
      if (detail === '请求成功但未返回 tool_calls / function_call') {
        return '请求已成功，但模型返回了普通文本，未触发工具调用'
      }
      return detail || '工具调用探测未通过'
    }

    case 'json_mode':
      if (item.supported && item.parsed) {
        const hobbies = (item.parsed.hobbies || []).join('、')
        return `返回内容符合 UserInfo schema，已成功解析为结构化数据（爱好：${hobbies || '无'}）`
      }
      if (detail.startsWith('Pydantic 解析失败')) {
        return '模型返回了文本，但无法按 UserInfo schema 严格解析（等价于 SDK 的 message.parsed 不可用）'
      }
      if (detail === '响应无 content') return '请求已成功，但响应中缺少可用于解析的文本内容'
      if (item.param_rejected) return '上游拒绝了 json_schema / response_format 参数，可能不支持结构化输出'
      return detail || '结构化输出探测未通过'

    case 'thinking':
      return detail || '未能判定思考模式行为'

    default:
      return detail || (item.supported ? '探测通过' : '探测未通过')
  }
}

function capStatusLabel(cap: { skipped?: boolean; supported?: boolean }): string {
  if (cap.skipped) return '已跳过'
  if (cap.supported) return '支持'
  return '不支持'
}

function capTagType(cap: { skipped?: boolean; supported?: boolean }): 'success' | 'warning' | 'danger' | 'info' {
  if (cap.skipped) return 'warning'
  if (cap.supported) return 'success'
  return 'danger'
}

function capStatClass(cap: { skipped?: boolean; supported?: boolean }): string {
  if (cap.skipped) return 'probe-stat--skip'
  if (cap.supported) return 'probe-stat--ok'
  return 'probe-stat--fail'
}

function capCardClass(cap: { skipped?: boolean; supported?: boolean }): string {
  if (cap.skipped) return 'cap-card--skip'
  if (cap.supported) return 'cap-card--ok'
  return 'cap-card--fail'
}

function capMetaTags(cap: { key: string; item: any }) {
  const item = cap.item || {}
  const tags: { label: string; type?: 'success' | 'warning' | 'info' | 'danger' }[] = []
  if (item.status_code) tags.push({ label: `HTTP ${item.status_code}` })
  if (item.finish_reason) tags.push({ label: `结束原因：${item.finish_reason}` })
  if (item.legacy_format) tags.push({ label: '旧版 function_call', type: 'warning' })
  if (item.param_rejected) tags.push({ label: '不支持 json_schema', type: 'warning' })
  if (cap.key === 'json_mode' && item.mode === 'pydantic_parse') {
    tags.push({ label: 'Pydantic 严格解析', type: 'info' })
  }
  return tags
}

const tested = computed(() => capabilities.value.filter(c => !c.skipped))
const allPassed = computed(() => tested.value.length > 0 && tested.value.every(c => c.supported))
const summaryText = computed(() => {
  if (tested.value.length === 0) return '无探测结果'
  return `${tested.value.filter(c => c.supported).length}/${tested.value.length} 通过`
})

async function loadUpstreamOptions() {
  try {
    const d = await apiGet<any>('/gateway/admin/model-capability-probe/options')
    upstreamOptions.value = d.upstreams || []
    if (upstreamOptions.value.length > 0) {
      selectedUpstreamId.value = upstreamOptions.value[0].id
      onUpstreamChange()
    }
  } catch (e: any) { ElMessage.error(e.message) }
}

async function onUpstreamChange() {
  if (!selectedUpstreamId.value) return
  upstreamModels.value = []; selectedModel.value = ''
  try {
    const d = await apiGet<any>(`/gateway/admin/model-capability-probe/models?upstream_id=${selectedUpstreamId.value}`)
    upstreamModels.value = d.models || []
  } catch (e: any) { ElMessage.error(e.message) }
}

function onCustomCredentialsChange() {
  if (debounceTimer) clearTimeout(debounceTimer)
  customModels.value = []; selectedModel.value = ''
  if (!customUri.value.trim() || !customApiKey.value.trim()) return
  debounceTimer = setTimeout(async () => {
    try {
      const d = await apiPost<any>('/gateway/admin/model-capability-probe/models/custom', {
        uri: customUri.value.trim(), api_key: customApiKey.value.trim(),
      })
      customModels.value = d.models || []
    } catch { }
  }, 500)
}

async function runProbe() {
  probing.value = true; report.value = null
  try {
    const body: any = mode.value === 'upstream'
      ? { mode: 'upstream', upstream_id: selectedUpstreamId.value, model: selectedModel.value }
      : { mode: 'custom', uri: customUri.value.trim(), api_key: customApiKey.value.trim(), model: selectedModel.value }
    report.value = await apiPost('/gateway/admin/model-capability-probe', body)
  } catch (e: any) { ElMessage.error(e.message) }
  finally { probing.value = false }
}

function onModeChange() {
  selectedModel.value = ''
  if (mode.value === 'upstream' && upstreamOptions.value.length > 0) {
    selectedUpstreamId.value = upstreamOptions.value[0].id
    onUpstreamChange()
  }
}

onMounted(loadUpstreamOptions)
</script>

<style scoped>
.probe-meta {
  margin-bottom: 16px;
}

.probe-summary {
  margin-bottom: 16px;
}

.probe-stat {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 12px 14px;
  background: var(--el-fill-color-blank);
}

.probe-stat__title {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}

.probe-stat__status {
  font-size: 18px;
  font-weight: 600;
}

.probe-stat--ok .probe-stat__status {
  color: var(--el-color-success);
}

.probe-stat--fail .probe-stat__status {
  color: var(--el-color-danger);
}

.probe-stat--skip .probe-stat__status {
  color: var(--el-color-warning);
}

.probe-cards :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cap-card {
  margin-bottom: 12px;
  border-left: 3px solid var(--el-border-color);
}

.cap-card--ok {
  border-left-color: var(--el-color-success);
}

.cap-card--fail {
  border-left-color: var(--el-color-danger);
}

.cap-card--skip {
  border-left-color: var(--el-color-warning);
}

.cap-desc {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}

.cap-result {
  border-radius: 8px;
  padding: 10px 12px;
  background: var(--el-fill-color-light);
}

.cap-result--ok {
  background: var(--el-color-success-light-9);
}

.cap-result--fail {
  background: var(--el-color-danger-light-9);
}

.cap-result__label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}

.cap-result__text {
  font-size: 14px;
  line-height: 1.7;
  color: var(--el-text-color-primary);
  word-break: break-word;
}

.cap-parsed {
  margin-top: 4px;
}

.cap-preview__label,
.cap-result__label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}

.cap-preview__text,
.cap-error {
  margin: 0;
  padding: 10px 12px;
  border-radius: 6px;
  background: var(--el-fill-color-darker);
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 160px;
  overflow: auto;
  font-family: ui-monospace, "Cascadia Code", "SF Mono", monospace;
}

.cap-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.thinking-card {
  margin-top: 4px;
  border: 1px dashed var(--el-border-color);
}

.thinking-conclusion {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--el-fill-color-light);
  line-height: 1.7;
  color: var(--el-text-color-primary);
}

.thinking-table {
  margin-top: 4px;
}
</style>
