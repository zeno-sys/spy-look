<template>
  <div class="page-container">
    <div class="page-header">
      <div><h3>大模型网关 · 能力测试</h3></div>
    </div>

    <div class="page-body">
      <el-tabs v-model="activeTab" class="probe-tabs">
        <!-- ========== 大语言模型能力测试 ========== -->
        <el-tab-pane label="大语言模型能力测试" name="llm">
          <el-card class="section-card">
            <template #header><span>探测配置</span></template>
            <el-alert type="warning" :closable="false" show-icon style="margin-bottom:12px"
              title="将向上游发起多轮 HTTP 请求，可能消耗配额；单次探测通常需数分钟。" />

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

              <el-button type="primary" :loading="probing" :disabled="!selectedModel" @click="runProbe" style="margin-top:12px">
                {{ probing ? '探测中...' : '开始探测' }}
              </el-button>
            </div>
          </el-card>

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
        </el-tab-pane>

        <!-- ========== 嵌入模型能力测试 ========== -->
        <el-tab-pane label="嵌入模型能力测试" name="embedding">
          <el-card class="section-card">
            <template #header><span>测试配置</span></template>
            <el-alert type="info" :closable="false" show-icon style="margin-bottom:12px"
              title="将调用上游 /embeddings 接口对两段文本生成向量并计算余弦相似度。" />

            <el-radio-group v-model="embMode" @change="onEmbModeChange">
              <el-radio-button value="upstream">选择上游</el-radio-button>
              <el-radio-button value="custom">自定义连接</el-radio-button>
            </el-radio-group>

            <div style="margin-top:16px">
              <el-row v-if="embMode === 'upstream'" :gutter="12">
                <el-col :span="12">
                  <el-form-item label="上游">
                    <el-select v-model="embUpstreamId" @change="onEmbUpstreamChange" style="width:100%">
                      <el-option v-for="o in upstreamOptions" :key="o.id" :label="o.name + ' (' + o.base_url + ')'" :value="o.id" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="模型">
                    <el-select v-model="embModel" filterable :disabled="!embUpstreamId" style="width:100%" placeholder="请先选择上游">
                      <el-option v-for="m in embUpstreamModels" :key="m" :label="m" :value="m" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>

              <template v-if="embMode === 'custom'">
                <el-row :gutter="12">
                  <el-col :span="12">
                    <el-form-item label="API 地址 (uri)">
                      <el-input v-model="embCustomUri" placeholder="https://api.example.com/v1" @input="onEmbCustomCredentialsChange" />
                    </el-form-item>
                  </el-col>
                  <el-col :span="12">
                    <el-form-item label="API Key">
                      <el-input v-model="embCustomApiKey" type="password" show-password placeholder="sk-..." @input="onEmbCustomCredentialsChange" />
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-form-item label="模型">
                  <el-select v-model="embModel" filterable :disabled="!embCustomModels.length" style="width:100%" placeholder="请先填写 API 地址与 Key">
                    <el-option v-for="m in embCustomModels" :key="m" :label="m" :value="m" />
                  </el-select>
                </el-form-item>
              </template>

              <el-row :gutter="12" style="margin-top:8px">
                <el-col :span="12">
                  <el-form-item label="文本 A">
                    <el-input
                      v-model="embTextA"
                      type="textarea"
                      :rows="4"
                      placeholder="请输入第一段文本"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="文本 B">
                    <el-input
                      v-model="embTextB"
                      type="textarea"
                      :rows="4"
                      placeholder="请输入第二段文本"
                    />
                  </el-form-item>
                </el-col>
              </el-row>

              <div class="probe-actions">
                <el-button :loading="embGenerating" @click="generateEmbeddingTexts">
                  {{ embGenerating ? '生成中...' : '一键生成测试文本' }}
                </el-button>
                <el-button
                  type="primary"
                  :loading="embProbing"
                  :disabled="!canRunEmbeddingProbe"
                  @click="runEmbeddingProbe"
                >
                  {{ embProbing ? '测试中...' : '开始测试' }}
                </el-button>
              </div>
            </div>
          </el-card>
        </el-tab-pane>

        <!-- ========== 重排序模型能力测试 ========== -->
        <el-tab-pane label="重排序模型能力测试" name="rerank">
          <el-card class="section-card">
            <template #header><span>测试配置</span></template>
            <el-alert type="info" :closable="false" show-icon style="margin-bottom:12px"
              title="将调用上游 /rerank 接口，对查询与多条候选结果进行重排序。" />

            <el-radio-group v-model="rrMode" @change="onRrModeChange">
              <el-radio-button value="upstream">选择上游</el-radio-button>
              <el-radio-button value="custom">自定义连接</el-radio-button>
            </el-radio-group>

            <div style="margin-top:16px">
              <el-row v-if="rrMode === 'upstream'" :gutter="12">
                <el-col :span="12">
                  <el-form-item label="上游">
                    <el-select v-model="rrUpstreamId" @change="onRrUpstreamChange" style="width:100%">
                      <el-option v-for="o in upstreamOptions" :key="o.id" :label="o.name + ' (' + o.base_url + ')'" :value="o.id" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="模型">
                    <el-select v-model="rrModel" filterable :disabled="!rrUpstreamId" style="width:100%" placeholder="请先选择上游">
                      <el-option v-for="m in rrUpstreamModels" :key="m" :label="m" :value="m" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>

              <template v-if="rrMode === 'custom'">
                <el-row :gutter="12">
                  <el-col :span="12">
                    <el-form-item label="API 地址 (uri)">
                      <el-input v-model="rrCustomUri" placeholder="https://api.example.com/v1" @input="onRrCustomCredentialsChange" />
                    </el-form-item>
                  </el-col>
                  <el-col :span="12">
                    <el-form-item label="API Key">
                      <el-input v-model="rrCustomApiKey" type="password" show-password placeholder="sk-..." @input="onRrCustomCredentialsChange" />
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-form-item label="模型">
                  <el-select v-model="rrModel" filterable :disabled="!rrCustomModels.length" style="width:100%" placeholder="请先填写 API 地址与 Key">
                    <el-option v-for="m in rrCustomModels" :key="m" :label="m" :value="m" />
                  </el-select>
                </el-form-item>
              </template>

              <el-form-item label="查询 (query)" style="margin-top:8px">
                <el-input
                  v-model="rrQuery"
                  type="textarea"
                  :rows="3"
                  placeholder="请输入查询文本"
                />
              </el-form-item>

              <div class="rr-docs-header">
                <span>候选结果 (documents)</span>
                <el-button type="primary" link @click="addRrDocument">添加结果</el-button>
              </div>
              <div v-for="(doc, idx) in rrDocuments" :key="idx" class="rr-doc-row">
                <el-input
                  v-model="rrDocuments[idx]"
                  type="textarea"
                  :rows="2"
                  :placeholder="`结果 ${idx + 1}`"
                />
                <el-button
                  type="danger"
                  link
                  :disabled="rrDocuments.length <= 2"
                  @click="removeRrDocument(idx)"
                >
                  删除
                </el-button>
              </div>

              <div class="probe-actions">
                <el-button :loading="rrGenerating" @click="generateRerankTexts">
                  {{ rrGenerating ? '生成中...' : '一键生成测试文本' }}
                </el-button>
                <el-button
                  type="primary"
                  :loading="rrProbing"
                  :disabled="!canRunRerankProbe"
                  @click="runRerankProbe"
                >
                  {{ rrProbing ? '测试中...' : '开始测试' }}
                </el-button>
              </div>
            </div>
          </el-card>
        </el-tab-pane>
      </el-tabs>

      <el-dialog
        v-model="embReportVisible"
        title="嵌入模型测试报告"
        width="640px"
        destroy-on-close
        center
        class="emb-report-dialog"
      >
        <template v-if="embReport">
          <div class="card-header" style="margin-bottom:16px">
            <span>测试结果</span>
            <el-tag :type="embReport.supported ? 'success' : 'danger'" size="large">
              {{ embReport.supported ? '成功' : '失败' }}
            </el-tag>
          </div>

          <el-descriptions :column="2" border size="small" class="probe-meta">
            <el-descriptions-item label="服务地址">{{ embReport.uri }}</el-descriptions-item>
            <el-descriptions-item label="请求端点">{{ embReport.endpoint }}</el-descriptions-item>
            <el-descriptions-item label="模型名称">{{ embReport.model }}</el-descriptions-item>
            <el-descriptions-item v-if="embReport.dimensions" label="向量维度">{{ embReport.dimensions }}</el-descriptions-item>
            <el-descriptions-item v-if="embReport.total_elapsed_ms" label="总耗时">
              {{ (embReport.total_elapsed_ms / 1000).toFixed(2) }} s
            </el-descriptions-item>
            <el-descriptions-item v-if="embReport.status_code" label="HTTP 状态">{{ embReport.status_code }}</el-descriptions-item>
          </el-descriptions>

          <div
            v-if="embReport.supported && embReport.cosine_similarity != null"
            class="emb-similarity"
          >
            <div class="emb-similarity__label">余弦相似度</div>
            <div class="emb-similarity__value">{{ formatSimilarity(embReport.cosine_similarity) }}</div>
            <div class="emb-similarity__raw">原始值：{{ embReport.cosine_similarity }}</div>
          </div>

          <el-alert
            v-else-if="embReport.error"
            type="error"
            :closable="false"
            show-icon
            :title="embReport.detail || '测试失败'"
            style="margin-top:12px"
          >
            <pre class="cap-error">{{ formatErrorText(embReport.error) }}</pre>
          </el-alert>

          <el-alert
            v-else-if="embReport.detail"
            type="info"
            :closable="false"
            show-icon
            :title="embReport.detail"
            style="margin-top:12px"
          />
        </template>
        <template #footer>
          <el-button type="primary" @click="embReportVisible = false">关闭</el-button>
        </template>
      </el-dialog>

      <el-dialog
        v-model="rrReportVisible"
        title="重排序模型测试报告"
        width="760px"
        destroy-on-close
        center
      >
        <template v-if="rrReport">
          <div class="card-header" style="margin-bottom:16px">
            <span>测试结果</span>
            <el-tag :type="rrReport.supported ? 'success' : 'danger'" size="large">
              {{ rrReport.supported ? '成功' : '失败' }}
            </el-tag>
          </div>

          <el-descriptions :column="2" border size="small" class="probe-meta">
            <el-descriptions-item label="服务地址">{{ rrReport.uri }}</el-descriptions-item>
            <el-descriptions-item label="请求端点">{{ rrReport.endpoint }}</el-descriptions-item>
            <el-descriptions-item label="模型名称">{{ rrReport.model }}</el-descriptions-item>
            <el-descriptions-item v-if="rrReport.document_count" label="候选数量">{{ rrReport.document_count }}</el-descriptions-item>
            <el-descriptions-item v-if="rrReport.total_elapsed_ms" label="总耗时">
              {{ (rrReport.total_elapsed_ms / 1000).toFixed(2) }} s
            </el-descriptions-item>
            <el-descriptions-item v-if="rrReport.status_code" label="HTTP 状态">{{ rrReport.status_code }}</el-descriptions-item>
            <el-descriptions-item label="查询" :span="2">{{ rrReport.query }}</el-descriptions-item>
          </el-descriptions>

          <el-table
            v-if="rrReport.supported && rrReport.results?.length"
            :data="rrReport.results"
            size="small"
            border
            style="margin-top:12px"
          >
            <el-table-column prop="rank" label="排序" width="70" />
            <el-table-column prop="index" label="原索引" width="80" />
            <el-table-column label="相关度" width="120">
              <template #default="{ row }">
                {{ formatSimilarity(row.relevance_score) }}
                <div class="rr-score-raw">{{ row.relevance_score }}</div>
              </template>
            </el-table-column>
            <el-table-column prop="document" label="文档内容" min-width="280" show-overflow-tooltip />
          </el-table>

          <el-alert
            v-else-if="rrReport.error"
            type="error"
            :closable="false"
            show-icon
            :title="rrReport.detail || '测试失败'"
            style="margin-top:12px"
          >
            <pre class="cap-error">{{ formatErrorText(rrReport.error) }}</pre>
          </el-alert>

          <el-alert
            v-else-if="rrReport.detail"
            type="info"
            :closable="false"
            show-icon
            :title="rrReport.detail"
            style="margin-top:12px"
          />
        </template>
        <template #footer>
          <el-button type="primary" @click="rrReportVisible = false">关闭</el-button>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { apiGet, apiPost } from '../../composables/useApi'

const activeTab = ref<'llm' | 'embedding' | 'rerank'>('llm')

// ---- LLM probe state ----
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

// ---- Embedding probe state (independent) ----
const embMode = ref<'upstream' | 'custom'>('upstream')
const embUpstreamId = ref(0)
const embModel = ref('')
const embCustomUri = ref('')
const embCustomApiKey = ref('')
const embTextA = ref('')
const embTextB = ref('')
const embProbing = ref(false)
const embGenerating = ref(false)
const embReport = ref<any>(null)
const embReportVisible = ref(false)
const embUpstreamModels = ref<string[]>([])
const embCustomModels = ref<string[]>([])
let embDebounceTimer: ReturnType<typeof setTimeout> | null = null

// ---- Rerank probe state (independent) ----
const rrMode = ref<'upstream' | 'custom'>('upstream')
const rrUpstreamId = ref(0)
const rrModel = ref('')
const rrCustomUri = ref('')
const rrCustomApiKey = ref('')
const rrQuery = ref('')
const rrDocuments = ref<string[]>(['', ''])
const rrProbing = ref(false)
const rrGenerating = ref(false)
const rrReport = ref<any>(null)
const rrReportVisible = ref(false)
const rrUpstreamModels = ref<string[]>([])
const rrCustomModels = ref<string[]>([])
let rrDebounceTimer: ReturnType<typeof setTimeout> | null = null

const canRunEmbeddingProbe = computed(() =>
  !!embModel.value
  && !!embTextA.value.trim()
  && !!embTextB.value.trim(),
)

const canRunRerankProbe = computed(() =>
  !!rrModel.value
  && !!rrQuery.value.trim()
  && rrDocuments.value.filter(d => d.trim()).length >= 2,
)

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

function formatSimilarity(value: number): string {
  const n = Number(value)
  if (Number.isNaN(n)) return '-'
  return `${(n * 100).toFixed(2)}%`
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
      const firstId = upstreamOptions.value[0].id
      selectedUpstreamId.value = firstId
      embUpstreamId.value = firstId
      rrUpstreamId.value = firstId
      onUpstreamChange()
      onEmbUpstreamChange()
      onRrUpstreamChange()
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

async function onEmbUpstreamChange() {
  if (!embUpstreamId.value) return
  embUpstreamModels.value = []; embModel.value = ''
  try {
    const d = await apiGet<any>(`/gateway/admin/model-capability-probe/models?upstream_id=${embUpstreamId.value}`)
    embUpstreamModels.value = d.models || []
  } catch (e: any) { ElMessage.error(e.message) }
}

function onEmbCustomCredentialsChange() {
  if (embDebounceTimer) clearTimeout(embDebounceTimer)
  embCustomModels.value = []; embModel.value = ''
  if (!embCustomUri.value.trim() || !embCustomApiKey.value.trim()) return
  embDebounceTimer = setTimeout(async () => {
    try {
      const d = await apiPost<any>('/gateway/admin/model-capability-probe/models/custom', {
        uri: embCustomUri.value.trim(), api_key: embCustomApiKey.value.trim(),
      })
      embCustomModels.value = d.models || []
    } catch { }
  }, 500)
}

function onEmbModeChange() {
  embModel.value = ''
  if (embMode.value === 'upstream' && upstreamOptions.value.length > 0) {
    embUpstreamId.value = upstreamOptions.value[0].id
    onEmbUpstreamChange()
  }
}

async function generateEmbeddingTexts() {
  embGenerating.value = true
  try {
    const d = await apiPost<{ text_a?: string; text_b?: string }>(
      '/settings/admin/llm/generate-probe-texts',
      { kind: 'embedding' },
    )
    embTextA.value = d.text_a || ''
    embTextB.value = d.text_b || ''
    if (!embTextA.value || !embTextB.value) {
      ElMessage.warning('生成结果不完整，请重试')
      return
    }
    ElMessage.success('占位文本已生成')
  } catch (e: any) {
    ElMessage.error(e.message || '生成失败，请先在设置中配置全局大模型')
  } finally {
    embGenerating.value = false
  }
}

async function runEmbeddingProbe() {
  if (!embTextA.value.trim() || !embTextB.value.trim()) {
    ElMessage.warning('请填写两段文本')
    return
  }
  embProbing.value = true
  embReport.value = null
  embReportVisible.value = false
  try {
    const body: any = embMode.value === 'upstream'
      ? {
          mode: 'upstream',
          upstream_id: embUpstreamId.value,
          model: embModel.value,
          text_a: embTextA.value.trim(),
          text_b: embTextB.value.trim(),
        }
      : {
          mode: 'custom',
          uri: embCustomUri.value.trim(),
          api_key: embCustomApiKey.value.trim(),
          model: embModel.value,
          text_a: embTextA.value.trim(),
          text_b: embTextB.value.trim(),
        }
    embReport.value = await apiPost('/gateway/admin/embedding-capability-probe', body)
    embReportVisible.value = true
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    embProbing.value = false
  }
}

async function onRrUpstreamChange() {
  if (!rrUpstreamId.value) return
  rrUpstreamModels.value = []; rrModel.value = ''
  try {
    const d = await apiGet<any>(`/gateway/admin/model-capability-probe/models?upstream_id=${rrUpstreamId.value}`)
    rrUpstreamModels.value = d.models || []
  } catch (e: any) { ElMessage.error(e.message) }
}

function onRrCustomCredentialsChange() {
  if (rrDebounceTimer) clearTimeout(rrDebounceTimer)
  rrCustomModels.value = []; rrModel.value = ''
  if (!rrCustomUri.value.trim() || !rrCustomApiKey.value.trim()) return
  rrDebounceTimer = setTimeout(async () => {
    try {
      const d = await apiPost<any>('/gateway/admin/model-capability-probe/models/custom', {
        uri: rrCustomUri.value.trim(), api_key: rrCustomApiKey.value.trim(),
      })
      rrCustomModels.value = d.models || []
    } catch { }
  }, 500)
}

function onRrModeChange() {
  rrModel.value = ''
  if (rrMode.value === 'upstream' && upstreamOptions.value.length > 0) {
    rrUpstreamId.value = upstreamOptions.value[0].id
    onRrUpstreamChange()
  }
}

async function generateRerankTexts() {
  rrGenerating.value = true
  try {
    const count = Math.max(2, Math.min(8, rrDocuments.value.length || 3))
    const d = await apiPost<{ query?: string; documents?: string[] }>(
      '/settings/admin/llm/generate-probe-texts',
      { kind: 'rerank', document_count: count < 3 ? 3 : count },
    )
    rrQuery.value = d.query || ''
    const docs = (d.documents || []).map(x => String(x || '').trim()).filter(Boolean)
    if (!rrQuery.value || docs.length < 2) {
      ElMessage.warning('生成结果不完整，请重试')
      return
    }
    rrDocuments.value = docs
    ElMessage.success('占位文本已生成')
  } catch (e: any) {
    ElMessage.error(e.message || '生成失败，请先在设置中配置全局大模型')
  } finally {
    rrGenerating.value = false
  }
}

function addRrDocument() {
  rrDocuments.value.push('')
}

function removeRrDocument(idx: number) {
  if (rrDocuments.value.length <= 2) return
  rrDocuments.value.splice(idx, 1)
}

async function runRerankProbe() {
  const docs = rrDocuments.value.map(d => d.trim()).filter(Boolean)
  if (!rrQuery.value.trim()) {
    ElMessage.warning('请填写查询文本')
    return
  }
  if (docs.length < 2) {
    ElMessage.warning('请至少填写 2 条候选结果')
    return
  }
  rrProbing.value = true
  rrReport.value = null
  rrReportVisible.value = false
  try {
    const body: any = rrMode.value === 'upstream'
      ? {
          mode: 'upstream',
          upstream_id: rrUpstreamId.value,
          model: rrModel.value,
          query: rrQuery.value.trim(),
          documents: docs,
        }
      : {
          mode: 'custom',
          uri: rrCustomUri.value.trim(),
          api_key: rrCustomApiKey.value.trim(),
          model: rrModel.value,
          query: rrQuery.value.trim(),
          documents: docs,
        }
    rrReport.value = await apiPost('/gateway/admin/rerank-capability-probe', body)
    rrReportVisible.value = true
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    rrProbing.value = false
  }
}

onMounted(loadUpstreamOptions)
</script>

<style scoped>
.probe-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

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

.emb-similarity {
  margin-top: 8px;
  padding: 24px 20px;
  border-radius: 10px;
  text-align: center;
  background: var(--el-color-success-light-9);
  border: 1px solid var(--el-color-success-light-5);
}

.emb-similarity__label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.emb-similarity__value {
  font-size: 36px;
  font-weight: 700;
  color: var(--el-color-success);
  line-height: 1.2;
  letter-spacing: 0.02em;
}

.emb-similarity__raw {
  margin-top: 8px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  font-family: ui-monospace, "Cascadia Code", "SF Mono", monospace;
}

.rr-docs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 8px 0 10px;
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.probe-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
}

.rr-doc-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 10px;
}

.rr-doc-row .el-input {
  flex: 1;
}

.rr-score-raw {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-family: ui-monospace, "Cascadia Code", "SF Mono", monospace;
}
</style>
