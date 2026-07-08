<template>
  <div class="page-container">
    <div class="page-header">
      <div><h3>大模型网关 · Token 测试</h3></div>
    </div>

    <div class="page-body">
      <!-- 体验区 -->
      <el-card class="section-card">
        <template #header><span>Token 生成速度体验</span></template>
        <p class="hint">
          用内置文本模拟不同生成速度下的对话输出效果，直观感受 tokens/s 的差异。
          粗略换算：1 个中文字符 ≈ 0.6 个 token，1 个英文字符 ≈ 0.3 个 token。
          不同模型的分词方式不同，实际换算比例会有差异。
        </p>

        <el-row :gutter="16" align="middle">
          <el-col :span="8">
            <el-form-item label="模拟速度 (tokens/s)">
              <el-slider v-model="demoSpeed" :min="5" :max="200" :step="5" show-input />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="预设">
              <el-radio-group v-model="demoSpeed" size="small">
                <el-radio-button :value="10">慢速 10</el-radio-button>
                <el-radio-button :value="30">一般 30</el-radio-button>
                <el-radio-button :value="60">较快 60</el-radio-button>
                <el-radio-button :value="120">高速 120</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-button type="primary" :disabled="demoPlaying" @click="startDemo">
              {{ demoPlaying ? '播放中...' : '开始体验' }}
            </el-button>
            <el-button :disabled="!demoPlaying && !demoDisplayed" @click="resetDemo">重置</el-button>
          </el-col>
        </el-row>

        <div class="demo-output">
          <div class="demo-label">AI 回复</div>
          <div class="demo-text">
            <span>{{ demoDisplayed }}</span>
            <span v-if="demoPlaying" class="demo-cursor">▍</span>
          </div>
          <div v-if="demoPlaying || demoDisplayed" class="demo-stats">
            已输出约 {{ demoTokenCount.toFixed(1) }} tokens · 当前速度 {{ demoSpeed }} tokens/s
          </div>
        </div>
      </el-card>

      <!-- 测速区 -->
      <el-card class="section-card" style="margin-top:16px">
        <template #header><span>Token 生成速度测试</span></template>
        <el-alert type="info" :closable="false" show-icon style="margin-bottom:12px"
          title="使用中文提示词向上游发起流式请求：预热 1 次后串行测试 3 次取平均，输出 tokens/s 估计值。" />

        <el-radio-group v-model="mode" @change="onModeChange">
          <el-radio-button value="upstream">选择上游</el-radio-button>
          <el-radio-button value="custom">自定义连接</el-radio-button>
        </el-radio-group>

        <div style="margin-top:16px">
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

          <el-button type="primary" :loading="testing" :disabled="!selectedModel" @click="runTest" style="margin-top:12px">
            {{ testing ? '测试中...' : '开始测速' }}
          </el-button>
        </div>

        <div v-if="testing" class="test-progress">
          <el-progress :percentage="testPercent" :stroke-width="10" striped striped-flow />
          <p class="test-progress-message">{{ testProgressMessage }}</p>
          <ul v-if="testSteps.length" class="test-steps">
            <li v-for="(step, idx) in testSteps" :key="idx" :class="{ done: step.done, active: step.active }">
              {{ step.text }}
            </li>
          </ul>
        </div>
      </el-card>

      <!-- 测速报告 -->
      <el-card v-if="report" class="section-card" style="margin-top:16px">
        <template #header>
          <div class="card-header">
            <span>测速报告</span>
            <el-tag v-if="report.average?.ok" type="success">
              平均 {{ report.average.tokens_per_sec }} tokens/s
            </el-tag>
            <el-tag v-else type="danger">测试失败</el-tag>
          </div>
        </template>

        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="服务地址">{{ report.uri }}</el-descriptions-item>
          <el-descriptions-item label="模型">{{ report.model }}</el-descriptions-item>
          <el-descriptions-item label="测试提示词" :span="2">{{ report.prompt }}</el-descriptions-item>
          <el-descriptions-item v-if="report.total_elapsed_ms" label="总耗时">{{ report.total_elapsed_ms }} ms</el-descriptions-item>
        </el-descriptions>

        <el-row :gutter="12" style="margin-top:16px">
          <el-col :span="8">
            <el-statistic title="平均生成速度" :value="report.average?.tokens_per_sec ?? 0" suffix="tokens/s" :precision="1" />
          </el-col>
          <el-col :span="8">
            <el-statistic title="平均首 token 延迟" :value="report.average?.ttft_ms ?? 0" suffix="ms" />
          </el-col>
          <el-col :span="8">
            <el-statistic title="平均输出 tokens" :value="report.average?.completion_tokens ?? 0" :precision="0" />
          </el-col>
        </el-row>

        <el-table :data="allRuns" size="small" style="margin-top:16px" border>
          <el-table-column prop="label" label="轮次" width="100" />
          <el-table-column prop="completion_tokens" label="输出 tokens" width="120" />
          <el-table-column prop="ttft_ms" label="首 token (ms)" width="130" />
          <el-table-column label="生成耗时 (s)" width="130">
            <template #default="{ row }">{{ formatGenerationSeconds(row.generation_ms) }}</template>
          </el-table-column>
          <el-table-column prop="tokens_per_sec" label="速度 (tokens/s)" width="140" />
          <el-table-column prop="status" label="状态" />
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { apiGet, apiPost, apiStreamPost } from '../../composables/useApi'

const DEMO_TEXT =
  '人工智能正在深刻改变我们的生活方式。从智能手机上的语音助手，到自动驾驶汽车，再到医疗诊断辅助系统，AI 技术已经渗透到社会的各个角落。' +
  '未来，随着大语言模型能力的不断提升，人机协作将变得更加自然流畅。我们有望看到更多个性化教育、科学发现和创意生产的突破。' +
  '与此同时，也需要关注 AI 安全、隐私保护和伦理规范，确保技术发展惠及所有人。'

const TOKENS_PER_CHINESE = 0.6
const TOKENS_PER_ENGLISH = 0.3

function estimateCharTokens(char: string): number {
  if (/[\u4e00-\u9fff]/.test(char)) return TOKENS_PER_CHINESE
  if (/[a-zA-Z]/.test(char)) return TOKENS_PER_ENGLISH
  return TOKENS_PER_ENGLISH
}

const demoSpeed = ref(30)
const demoPlaying = ref(false)
const demoDisplayed = ref('')
const demoTokenCount = ref(0)
let demoTimer: ReturnType<typeof setInterval> | null = null
let demoIndex = 0
let demoTokenBudget = 0

const mode = ref<'upstream' | 'custom'>('upstream')
const selectedUpstreamId = ref(0)
const selectedModel = ref('')
const customUri = ref('')
const customApiKey = ref('')
const testing = ref(false)
const report = ref<any>(null)
const testPercent = ref(0)
const testProgressMessage = ref('')
const testSteps = ref<{ text: string; done: boolean; active: boolean }[]>([])

function resetTestProgress() {
  testPercent.value = 0
  testProgressMessage.value = '准备开始测速...'
  testSteps.value = [
    { text: '预热（不计入统计）', done: false, active: false },
    { text: '第 1 轮测试', done: false, active: false },
    { text: '第 2 轮测试', done: false, active: false },
    { text: '第 3 轮测试', done: false, active: false },
  ]
}

function updateTestSteps(stage: string, message: string, percent: number, run?: number) {
  testProgressMessage.value = message
  testPercent.value = percent
  if (stage === 'warmup') {
    if (percent >= 25) {
      testSteps.value[0] = { text: message, done: true, active: false }
    } else {
      testSteps.value[0] = { text: message, done: false, active: true }
    }
    return
  }
  if (stage === 'run' && run) {
    const idx = run
    if (percent >= 25 + run * 25) {
      testSteps.value[idx] = { text: message, done: true, active: false }
    } else {
      testSteps.value[idx] = { text: message, done: false, active: true }
    }
  }
  if (stage === 'complete') {
    testPercent.value = 100
    testProgressMessage.value = message
  }
}

const upstreamOptions = ref<any[]>([])
const upstreamModels = ref<string[]>([])
const customModels = ref<string[]>([])
let debounceTimer: ReturnType<typeof setTimeout> | null = null

function formatGenerationSeconds(ms: number | string | null | undefined): string {
  if (ms === '-' || ms == null) return '-'
  const n = Number(ms)
  if (Number.isNaN(n)) return String(ms)
  return (n / 1000).toFixed(2)
}

const allRuns = computed(() => {
  if (!report.value) return []
  const rows: any[] = []
  const warmup = report.value.warmup
  if (warmup) {
    rows.push({
      label: '预热',
      completion_tokens: warmup.completion_tokens ?? '-',
      ttft_ms: warmup.ttft_ms ?? '-',
      generation_ms: warmup.generation_ms ?? '-',
      tokens_per_sec: warmup.tokens_per_sec ?? '-',
      status: warmup.ok ? '成功' : (warmup.error || '失败'),
    })
  }
  for (const r of report.value.runs || []) {
    rows.push({
      label: `第 ${r.run} 轮`,
      completion_tokens: r.completion_tokens ?? '-',
      ttft_ms: r.ttft_ms ?? '-',
      generation_ms: r.generation_ms ?? '-',
      tokens_per_sec: r.tokens_per_sec ?? '-',
      status: r.ok ? '成功' : (r.error || '失败'),
    })
  }
  return rows
})

function clearDemoTimer() {
  if (demoTimer) {
    clearInterval(demoTimer)
    demoTimer = null
  }
}

function resetDemo() {
  clearDemoTimer()
  demoPlaying.value = false
  demoDisplayed.value = ''
  demoTokenCount.value = 0
  demoIndex = 0
  demoTokenBudget = 0
}

function startDemo() {
  resetDemo()
  demoPlaying.value = true
  const tickMs = 20
  demoTimer = setInterval(() => {
    demoTokenBudget += demoSpeed.value * (tickMs / 1000)
    while (demoIndex < DEMO_TEXT.length) {
      const cost = estimateCharTokens(DEMO_TEXT[demoIndex])
      if (demoTokenBudget < cost) break
      demoDisplayed.value += DEMO_TEXT[demoIndex]
      demoTokenCount.value += cost
      demoTokenBudget -= cost
      demoIndex += 1
    }
    if (demoIndex >= DEMO_TEXT.length) {
      clearDemoTimer()
      demoPlaying.value = false
    }
  }, tickMs)
}

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

async function runTest() {
  testing.value = true
  report.value = null
  resetTestProgress()
  try {
    const body: any = mode.value === 'upstream'
      ? { mode: 'upstream', upstream_id: selectedUpstreamId.value, model: selectedModel.value }
      : { mode: 'custom', uri: customUri.value.trim(), api_key: customApiKey.value.trim(), model: selectedModel.value }

    await apiStreamPost('/gateway/admin/token-speed-test/stream', body, (event, data) => {
      if (event === 'progress') {
        const stage = typeof data.stage === 'string' ? data.stage : ''
        const message = typeof data.message === 'string' ? data.message : '测速进行中...'
        const percent = typeof data.percent === 'number' ? data.percent : testPercent.value
        const run = typeof data.run === 'number' ? data.run : undefined
        updateTestSteps(stage, message, percent, run)
      } else if (event === 'done') {
        report.value = data
        testPercent.value = 100
        testProgressMessage.value = '测速完成'
        if (!data.average?.ok) {
          ElMessage.warning(data.average?.error || '测速未成功完成')
        }
      } else if (event === 'error') {
        const detail = typeof data.detail === 'string' ? data.detail : '测速失败'
        testProgressMessage.value = detail
        ElMessage.error(detail)
      }
    })
  } catch (e: any) {
    testProgressMessage.value = e.message || '请求失败'
    ElMessage.error(e.message)
  } finally {
    testing.value = false
  }
}

function onModeChange() {
  selectedModel.value = ''
  if (mode.value === 'upstream' && upstreamOptions.value.length > 0) {
    selectedUpstreamId.value = upstreamOptions.value[0].id
    onUpstreamChange()
  }
}

onMounted(loadUpstreamOptions)
onUnmounted(clearDemoTimer)
</script>

<style scoped>
.demo-output {
  margin-top: 16px;
  padding: 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  min-height: 120px;
}
.demo-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}
.demo-text {
  font-size: 15px;
  line-height: 1.8;
  color: var(--el-text-color-primary);
  white-space: pre-wrap;
}
.demo-cursor {
  animation: blink 1s step-end infinite;
  color: var(--el-color-primary);
}
.demo-stats {
  margin-top: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
@keyframes blink {
  50% { opacity: 0; }
}
.test-progress {
  margin-top: 16px;
  padding: 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}
.test-progress-message {
  margin: 10px 0 0;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.test-steps {
  margin: 12px 0 0;
  padding-left: 20px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.test-steps li {
  margin-bottom: 4px;
}
.test-steps li.active {
  color: var(--el-color-primary);
  font-weight: 500;
}
.test-steps li.done {
  color: var(--el-color-success);
}
</style>
