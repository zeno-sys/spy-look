<template>
  <div class="page-container">
    <div class="page-header">
      <div><h3>大模型网关 · 显存计算</h3></div>
    </div>

    <div class="page-body">
      <el-card class="section-card">
        <template #header><span>权重占用</span></template>
        <p class="hint">
          仅考虑参数本身：
          <code>Memory (GB) = 参数量 × 每参数字节数 / 1024³</code>
          · 粗略估算：<code>参数量(B) × 每参数字节数</code>（如 7B FP16 ≈ 14 GB）
        </p>
        <el-form label-position="top">
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="参数量（B）">
                <el-input-number v-model="paramBillions" :min="0.001" :step="0.5" :precision="3" style="width:100%" />
                <p class="field-hint">填模型总参数量，单位十亿。例如 7 表示 7B，27 表示 27B。</p>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="精度">
                <el-select v-model="weightDtype" style="width:100%">
                  <el-option v-for="d in dtypeOptions" :key="d.value" :label="d.label" :value="d.value" />
                </el-select>
                <p class="field-hint">常见推理精度：FP16/BF16 全精度加载；INT4/INT8 为量化权重。</p>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="每参数字节数">
                <el-input-number v-model="weightBytesPerParam" :min="0.5" :step="0.5" :precision="1" style="width:100%" />
                <p class="field-hint">通常与精度一致；混合精度或自定义量化时可手动调整。</p>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="精确值">{{ formatGb(weightMemoryGb) }} GB</el-descriptions-item>
          <el-descriptions-item label="粗略估算">{{ formatGb(weightRoughGb) }} GB</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card class="section-card" style="margin-top:16px">
        <template #header><span>KV Cache（Transformer decoder-only）</span></template>
        <p class="hint">
          每 token KV cache =
          <code>2 × num_layers × (num_kv_heads × head_dim) × dtype_size</code>
          · 序列总量 =
          <code>每 token KV cache × S × B</code>
        </p>
        <el-form label-position="top">
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="层数 (num_layers)">
                <el-input-number v-model="numLayers" :min="1" :step="1" style="width:100%" />
                <p class="field-hint">一般使用模型配置中的 <code>num_hidden_layers</code>。</p>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="KV 头数 (num_kv_heads)">
                <el-input-number v-model="numKvHeads" :min="1" :step="1" style="width:100%" />
                <p class="field-hint">建议使用配置 <code>num_key_value_heads</code>。GQA/MQA 模型小于注意力头数，如 Qwen3.5-27B 可填 4。</p>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="单头维度 (head_dim)">
                <el-input-number v-model="headDim" :min="1" :step="64" style="width:100%" />
                <p class="field-hint">建议使用配置 <code>head_dim</code>；若未给出，可填 <code>hidden_size / num_attention_heads</code>，如 128 / 256。</p>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="KV 精度">
                <el-select v-model="kvDtype" style="width:100%">
                  <el-option v-for="d in dtypeOptions" :key="d.value" :label="d.label" :value="d.value" />
                </el-select>
                <p class="field-hint">推理框架可能将 KV cache 存为 FP16/BF16 或 FP8；与权重精度可不同。</p>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="序列长度 (seq_len)">
                <el-input-number v-model="seqLength" :min="1" :step="512" style="width:100%" />
                <p class="field-hint">测试极限场景可取模型最大上下文，如 <code>max_position_embeddings</code>。</p>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="批大小 (batch_size)">
                <el-input-number v-model="batchSize" :min="1" :step="1" style="width:100%" />
                <p class="field-hint">常见范围：API 服务 1–16；批处理推理 4/8/16/32；单用户对话常用 1。</p>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="每 token KV cache">{{ formatBytes(kvPerTokenBytes) }}</el-descriptions-item>
          <el-descriptions-item label="序列总 KV cache">{{ formatGb(kvTotalGb) }} GB</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card class="section-card summary-card" style="margin-top:16px">
        <template #header><span>合计（权重 + KV Cache）</span></template>
        <div class="summary-total">{{ formatGb(totalGb) }} GB</div>
        <p class="hint">未计入激活值、梯度、优化器状态及框架开销；推理场景下权重与 KV Cache 是主要显存项。</p>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const GB = 1024 ** 3

const dtypeOptions = [
  { label: 'FP32 (4 B)', value: 'fp32', bytes: 4 },
  { label: 'FP16 / BF16 (2 B)', value: 'fp16', bytes: 2 },
  { label: 'FP8 / INT8 (1 B)', value: 'fp8', bytes: 1 },
  { label: 'INT4 (0.5 B)', value: 'int4', bytes: 0.5 },
] as const

type DtypeValue = (typeof dtypeOptions)[number]['value']

function bytesForDtype(value: DtypeValue): number {
  return dtypeOptions.find((d) => d.value === value)?.bytes ?? 2
}

const paramBillions = ref(7)
const weightDtype = ref<DtypeValue>('fp16')
const weightBytesPerParam = ref(2)

watch(weightDtype, (v) => {
  weightBytesPerParam.value = bytesForDtype(v)
})

const numLayers = ref(32)
const numKvHeads = ref(8)
const headDim = ref(128)
const kvDtype = ref<DtypeValue>('fp16')
const kvBytesPerElement = computed(() => bytesForDtype(kvDtype.value))
const seqLength = ref(4096)
const batchSize = ref(1)

const paramCount = computed(() => paramBillions.value * 1e9)

const weightMemoryGb = computed(
  () => (paramCount.value * weightBytesPerParam.value) / GB,
)
const weightRoughGb = computed(() => paramBillions.value * weightBytesPerParam.value)

const kvPerTokenBytes = computed(
  () => 2 * numLayers.value * (numKvHeads.value * headDim.value) * kvBytesPerElement.value,
)
const kvTotalGb = computed(
  () => (kvPerTokenBytes.value * seqLength.value * batchSize.value) / GB,
)

const totalGb = computed(() => weightMemoryGb.value + kvTotalGb.value)

function formatGb(value: number): string {
  if (!Number.isFinite(value)) return '—'
  if (value >= 100) return value.toFixed(1)
  if (value >= 10) return value.toFixed(2)
  return value.toFixed(3)
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes)) return '—'
  if (bytes >= GB) return `${formatGb(bytes / GB)} GB`
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(2)} KB`
  return `${bytes.toFixed(0)} B`
}
</script>

<style scoped>
.field-hint {
  color: var(--sl-text-muted);
  font-size: 12px;
  line-height: 1.55;
  margin: 6px 0 0;
}

.field-hint code {
  background: var(--sl-accent-subtle);
  color: var(--sl-accent);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 11px;
  font-family: ui-monospace, "Cascadia Code", "SF Mono", monospace;
}

:deep(.el-form-item) {
  margin-bottom: 8px;
}

.summary-card :deep(.el-card__body) {
  padding-top: 8px;
}

.summary-total {
  font-size: 2rem;
  font-weight: 600;
  color: var(--el-color-primary);
  line-height: 1.2;
  margin-bottom: 8px;
}
</style>
