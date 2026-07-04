<template>
  <div class="page-container">
    <div class="page-header">
      <div><h3>视频工具 · 工具配置</h3></div>
      <div class="header-actions">
        <el-button type="primary" @click="loadConfig">刷新</el-button>
      </div>
    </div>

    <div class="page-body">
      <el-card class="section-card" v-loading="loading">
        <template #header><span>FFmpeg 与 VAD</span></template>
        <el-form :model="form" label-position="top">
          <el-form-item>
            <template #label>
              <ConfigFieldLabel label="FFmpeg 路径" :tip="tips.ffmpeg_path" />
            </template>
            <el-input v-model="form.ffmpeg_path" placeholder="ffmpeg 可执行文件绝对路径" />
          </el-form-item>
          <el-divider content-position="left">VAD 静音切分</el-divider>
          <el-row :gutter="12">
            <el-col :span="8">
              <el-form-item>
                <template #label>
                  <ConfigFieldLabel label="noise_db" :tip="tips.noise_db" />
                </template>
                <el-input-number v-model="form.vad.noise_db" :step="1" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item>
                <template #label>
                  <ConfigFieldLabel label="min_duration (s)" :tip="tips.min_duration" />
                </template>
                <el-input-number v-model="form.vad.min_duration" :step="0.05" :min="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item>
                <template #label>
                  <ConfigFieldLabel label="min_silence_sec (s)" :tip="tips.min_silence_sec" />
                </template>
                <el-input-number v-model="form.vad.min_silence_sec" :step="0.05" :min="0" style="width:100%" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="12">
            <el-col :span="8">
              <el-form-item>
                <template #label>
                  <ConfigFieldLabel label="search_window (s)" :tip="tips.search_window" />
                </template>
                <el-input-number v-model="form.vad.search_window" :min="1" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item>
                <template #label>
                  <ConfigFieldLabel label="sample_rate" :tip="tips.sample_rate" />
                </template>
                <el-input-number v-model="form.vad.sample_rate" :min="8000" :step="1000" style="width:100%" />
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </el-card>

      <el-card class="section-card" style="margin-top:16px" v-loading="loading">
        <template #header><span>ASR 语音识别</span></template>
        <el-form :model="form" label-position="top">
          <el-form-item>
            <template #label>
              <ConfigFieldLabel label="Base URL" :tip="tips.base_url" />
            </template>
            <el-input v-model="form.asr.base_url" placeholder="https://api.siliconflow.cn/v1" />
          </el-form-item>
          <el-form-item>
            <template #label>
              <ConfigFieldLabel label="API Key" :tip="tips.api_key" />
            </template>
            <el-input
              v-model="form.asr.api_key"
              type="password"
              show-password
              :placeholder="apiKeyPlaceholder"
            />
            <p class="hint">留空表示不修改已保存的密钥。</p>
          </el-form-item>
          <el-form-item>
            <template #label>
              <ConfigFieldLabel label="Model" :tip="tips.model" />
            </template>
            <el-input v-model="form.asr.model" placeholder="FunAudioLLM/SenseVoiceSmall" />
          </el-form-item>
          <el-row :gutter="12">
            <el-col :span="8">
              <el-form-item>
                <template #label>
                  <ConfigFieldLabel label="max_chunk_sec" :tip="tips.max_chunk_sec" />
                </template>
                <el-input-number v-model="form.asr.max_chunk_sec" :min="30" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item>
                <template #label>
                  <ConfigFieldLabel label="max_file_bytes" :tip="tips.max_file_bytes" />
                </template>
                <el-input-number v-model="form.asr.max_file_bytes" :min="1048576" :step="1048576" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item>
                <template #label>
                  <ConfigFieldLabel label="parallel_workers" :tip="tips.parallel_workers" />
                </template>
                <el-input-number v-model="form.asr.parallel_workers" :min="1" :max="16" style="width:100%" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="12">
            <el-col :span="8">
              <el-form-item>
                <template #label>
                  <ConfigFieldLabel label="max_retries" :tip="tips.max_retries" />
                </template>
                <el-input-number v-model="form.asr.max_retries" :min="1" :max="10" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item>
                <template #label>
                  <ConfigFieldLabel label="request_timeout_sec" :tip="tips.request_timeout_sec" />
                </template>
                <el-input-number v-model="form.asr.request_timeout_sec" :min="30" style="width:100%" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item>
            <el-button type="primary" :loading="saving" @click="saveConfig">保存配置</el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiGet, apiPatch } from '../../composables/useApi'
import ConfigFieldLabel from './ConfigFieldLabel.vue'

const tips = {
  ffmpeg_path:
    'FFmpeg 可执行文件的完整路径。用于视频转音频、音频归一化与 VAD 切分，请填写本机 ffmpeg.exe 的绝对路径。',
  noise_db:
    '静音检测能量阈值（分贝）。低于该值的片段视为静音。切分点落在句中时可调低（如 -40）；切得太碎时可调高（如 -30）。默认 -35。',
  min_duration:
    '最短静音时长（秒）。只有连续静音达到该长度才记为可切分点，用于过滤短促换气。默认 0.35 秒。',
  min_silence_sec:
    '可作为切分点的最短静音长度（秒）。与 min_duration 配合，决定句间停顿的识别灵敏度。',
  search_window:
    '选取切分点时的搜索窗口（秒）。接近单段上限时，在此范围内寻找最长静音作为切点。默认 60 秒。',
  sample_rate:
    'ASR 归一化目标采样率（Hz）。长音频切分前会转为该采样率的单声道 PCM。默认 16000，一般无需修改。',
  base_url:
    '语音识别 API 的基础地址，需兼容 OpenAI 格式的 /audio/transcriptions 接口。硅基流动默认 https://api.siliconflow.cn/v1。',
  api_key: '调用 ASR 服务的 API 密钥（Bearer Token）。保存时留空表示不修改已存密钥。',
  model: '语音识别模型名称，如 FunAudioLLM/SenseVoiceSmall。需与 ASR 服务商支持的模型一致。',
  max_chunk_sec:
    '单段音频最大时长（秒）。超过后会触发 VAD 静音切分再并行识别。默认 240 秒（4 分钟），需符合上游 API 限制。',
  max_file_bytes:
    '单段音频最大文件体积（字节）。与 max_chunk_sec 共同决定是否切分。默认 20971520（20MB）。',
  parallel_workers:
    '多段并行 ASR 请求的并发数。数值越大处理越快，但可能触发 API 限流。默认 3。',
  max_retries:
    '单段 ASR 请求失败时的最大重试次数，主要针对服务端 5xx 与网络错误。默认 3 次。',
  request_timeout_sec:
    '单次 ASR HTTP 请求的超时时间（秒）。段落较长或网络较慢时可适当增大。默认 300 秒。',
} as const

const loading = ref(false)
const saving = ref(false)
const maskedApiKey = ref('')

const defaultForm = () => ({
  ffmpeg_path: '',
  vad: {
    noise_db: -35,
    min_duration: 0.35,
    min_silence_sec: 0.35,
    search_window: 60,
    sample_rate: 16000,
  },
  asr: {
    base_url: 'https://api.siliconflow.cn/v1',
    api_key: '',
    model: 'FunAudioLLM/SenseVoiceSmall',
    max_chunk_sec: 240,
    max_file_bytes: 20971520,
    parallel_workers: 3,
    max_retries: 3,
    request_timeout_sec: 300,
  },
})

const form = reactive(defaultForm())

const apiKeyPlaceholder = computed(() =>
  maskedApiKey.value ? `已保存: ${maskedApiKey.value}` : 'sk-...',
)

async function loadConfig() {
  loading.value = true
  try {
    const data = await apiGet('/video-tools/admin/config')
    form.ffmpeg_path = data.ffmpeg_path ?? ''
    Object.assign(form.vad, data.vad ?? {})
    Object.assign(form.asr, data.asr ?? {})
    form.asr.api_key = ''
    maskedApiKey.value = data.asr?.api_key ?? ''
  } catch (e: any) {
    ElMessage.error(e.message || '加载配置失败')
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      ffmpeg_path: form.ffmpeg_path,
      vad: { ...form.vad },
      asr: { ...form.asr },
    }
    if (!form.asr.api_key.trim()) {
      delete (payload.asr as Record<string, unknown>).api_key
    }
    const data = await apiPatch('/video-tools/admin/config', payload)
    form.asr.api_key = ''
    maskedApiKey.value = data.asr?.api_key ?? ''
    ElMessage.success('配置已保存')
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadConfig)
</script>

<style scoped>
.hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
