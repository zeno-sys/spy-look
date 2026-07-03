<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div><h3>Spy-Look · 模型能力测试</h3></div>
      <div class="header-actions">
        <router-link to="/"><el-button>返回应用列表</el-button></router-link>
      </div>
    </el-header>

    <el-main>
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
      <el-card v-if="report" class="section-card" style="margin-top:16px">
        <template #header>
          <div class="card-header">
            <span>探测报告</span>
            <el-tag :type="allPassed ? 'success' : 'warning'">{{ summaryText }}</el-tag>
          </div>
        </template>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="服务地址">{{ report.uri }}</el-descriptions-item>
          <el-descriptions-item label="请求端点">{{ report.endpoint }}</el-descriptions-item>
          <el-descriptions-item label="模型名称">{{ report.model }}</el-descriptions-item>
          <el-descriptions-item v-if="report.total_elapsed_ms" label="总耗时">{{ report.total_elapsed_ms }}ms</el-descriptions-item>
        </el-descriptions>

        <el-row :gutter="12" style="margin-top:16px">
          <el-col v-for="cap in capabilities" :key="cap.key" :span="12">
            <el-card shadow="hover" style="margin-bottom:12px">
              <template #header>
                <div class="card-header">
                  <span>{{ cap.title }}</span>
                  <el-tag :type="cap.supported ? 'success' : cap.skipped ? 'warning' : 'danger'" size="small">
                    {{ cap.skipped ? '已跳过' : cap.supported ? '支持' : '不支持' }}
                  </el-tag>
                </div>
              </template>
              <p class="hint">{{ cap.desc }}</p>
              <p v-if="cap.item.detail"><b>说明:</b> {{ cap.item.detail }}</p>
              <p v-if="cap.item.error" style="color:red"><b>错误:</b> {{ cap.item.error }}</p>
              <p v-if="cap.item.status_code">HTTP {{ cap.item.status_code }}</p>
              <p v-if="cap.item.finish_reason">结束原因: {{ cap.item.finish_reason }}</p>
              <p v-if="cap.item.content_preview">内容预览: {{ cap.item.content_preview }}</p>
              <el-tag v-if="cap.item.legacy_format" type="warning" size="small">旧版 function_call 格式</el-tag>
              <el-tag v-if="cap.item.param_rejected" type="warning" size="small">服务端拒绝了 json_schema 参数</el-tag>
            </el-card>
          </el-col>
        </el-row>

        <!-- Thinking detail -->
        <el-card v-if="report.thinking" shadow="hover" style="margin-top:8px">
          <template #header>
            <div class="card-header">
              <span>思考模式详情</span>
              <el-tag :type="report.thinking.mode !== 'not_supported' ? 'success' : 'danger'" size="small">{{ report.thinking.mode_label }}</el-tag>
            </div>
          </template>
          <p v-for="(v, k) in report.thinking.summary" :key="k">{{ k }}: {{ v }}</p>
          <p>{{ report.thinking.detail }}</p>
        </el-card>
      </el-card>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { apiGet, apiPost } from '../composables/useApi'

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
    { key: 'chat_completion', title: '基础对话', desc: '能否正常完成 Chat Completions 请求并返回文本' },
    { key: 'tool_calling', title: '工具调用', desc: '是否支持 tools / tool_calls（Function Calling）' },
    { key: 'json_mode', title: '结构化输出', desc: '是否支持 Pydantic parse 等价能力（json_schema + 严格解析）' },
    { key: 'thinking', title: '思考模式', desc: '开/关 thinking 参数后是否可控制思考内容的输出' },
  ]
  return defs.map(d => {
    const item = report.value[d.key] || {}
    return { ...d, item, supported: item.supported, skipped: (item.detail || '').includes('跳过') }
  })
})

const tested = computed(() => capabilities.value.filter(c => !c.skipped))
const allPassed = computed(() => tested.value.length > 0 && tested.value.every(c => c.supported))
const summaryText = computed(() => {
  if (tested.value.length === 0) return '无探测结果'
  return `${tested.value.filter(c => c.supported).length}/${tested.value.length} 通过`
})

async function loadUpstreamOptions() {
  try {
    const d = await apiGet<any>('/admin/model-capability-probe/options')
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
    const d = await apiGet<any>(`/admin/model-capability-probe/models?upstream_id=${selectedUpstreamId.value}`)
    upstreamModels.value = d.models || []
  } catch (e: any) { ElMessage.error(e.message) }
}

function onCustomCredentialsChange() {
  if (debounceTimer) clearTimeout(debounceTimer)
  customModels.value = []; selectedModel.value = ''
  if (!customUri.value.trim() || !customApiKey.value.trim()) return
  debounceTimer = setTimeout(async () => {
    try {
      const d = await apiPost<any>('/admin/model-capability-probe/models/custom', {
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
    report.value = await apiPost('/admin/model-capability-probe', body)
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
