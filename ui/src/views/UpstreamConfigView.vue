<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div><h3>Spy-Look · 上游配置</h3></div>
      <div class="header-actions">
        <router-link to="/"><el-button>返回日志</el-button></router-link>
        <el-button type="primary" @click="loadAll">刷新列表</el-button>
      </div>
    </el-header>

    <el-main>
      <!-- Client Keys -->
      <el-card class="section-card">
        <template #header>
          <div class="card-header">
            <span>对外服务 API Key</span>
            <el-button type="primary" @click="openCreateKeyDialog">新增密钥</el-button>
          </div>
        </template>
        <p class="hint">客户端调用本网关需在请求头 <code>Authorization: Bearer ...</code> 中匹配下列任意一条密钥。</p>
        <el-table :data="clientKeys" stripe size="small">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="app_id" label="App ID" min-width="140" />
          <el-table-column prop="api_key_masked" label="密钥(脱敏)" min-width="200" />
          <el-table-column prop="created_at" label="创建时间" width="170" />
          <el-table-column label="操作" width="240">
            <template #default="{ row }">
              <el-button size="small" @click="copyKey(row.id)">复制</el-button>
              <el-button size="small" @click="openEditAppIdDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="confirmDeleteKey(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- Upstreams -->
      <el-card class="section-card">
        <template #header>
          <div class="card-header"><span>已配置上游</span>
            <el-button type="primary" @click="openCreateUpstreamDialog">新增上游</el-button>
          </div>
        </template>
        <p class="hint">连接失败或超时时，将按列表顺序（默认优先）尝试其它已启用上游。</p>
        <el-table :data="upstreams" stripe size="small">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="name" label="名称" width="120" />
          <el-table-column prop="base_url" label="Base URL" min-width="200" show-overflow-tooltip />
          <el-table-column prop="api_key_masked" label="Key" width="140" />
          <el-table-column prop="timeout_seconds" label="超时(s)" width="80" />
          <el-table-column label="代理" width="70">
            <template #default="{ row }">{{ row.trust_env ? '是' : '否' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '启用' : '禁用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="对外服务" width="90">
            <template #default="{ row }">
              <el-tag v-if="row.is_default" type="warning" size="small">对外服务</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="280" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="testUpstream(row)">探测</el-button>
              <el-button size="small" @click="openEditUpstreamDialog(row)">编辑</el-button>
              <el-button v-if="!row.is_default && row.enabled" size="small" @click="setDefaultUpstream(row.id)">切为对外</el-button>
              <el-button size="small" type="danger" @click="confirmDeleteUpstream(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-main>

    <!-- Create Key Dialog -->
    <el-dialog v-model="showCreateKeyDialog" title="新增对外 API Key" width="500px" destroy-on-close center>
      <el-form :model="newKeyForm" label-position="top" @submit.prevent="saveClientKey">
        <el-form-item label="App ID">
          <el-input v-model="newKeyForm.app_id" placeholder="例如 billing-service" />
        </el-form-item>
        <p class="hint">以字母或数字开头，可含字母、数字、点、下划线、连字符，长度 1–64。</p>
        <el-form-item label="API Key（服务端自动生成）">
          <el-input v-model="newKeyForm.key" readonly>
            <template #append><el-button @click="generateKey">重新生成</el-button></template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveClientKey" :loading="keySaving">保存</el-button>
          <el-button @click="showCreateKeyDialog = false">取消</el-button>
        </el-form-item>
      </el-form>
    </el-dialog>

    <!-- Edit App ID Dialog -->
    <el-dialog v-model="showEditAppIdDialog" title="修改 App ID" width="450px" destroy-on-close center>
      <el-form label-position="top">
        <p class="hint">Key: {{ editingKeyMasked }}</p>
        <el-form-item label="App ID">
          <el-input v-model="editingAppId" placeholder="新的 app_id" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveEditAppId">保存</el-button>
          <el-button @click="showEditAppIdDialog = false">取消</el-button>
        </el-form-item>
      </el-form>
    </el-dialog>

    <!-- Upstream Dialog -->
    <el-dialog v-model="showUpstreamDialog" :title="editingUpstreamId ? '编辑上游' : '新增上游'" width="560px" destroy-on-close center>
      <el-form :model="upstreamForm" label-position="top">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="名称">
              <el-input v-model="upstreamForm.name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Base URL（含 /v1）">
              <el-input v-model="upstreamForm.base_url" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item :label="'API Key' + (editingUpstreamId ? ' (留空不修改)' : '')">
          <el-input v-model="upstreamForm.api_key" type="password" show-password />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="超时(秒)">
              <el-input-number v-model="upstreamForm.timeout_seconds" :min="5" :step="1" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label=" "><el-checkbox v-model="upstreamForm.trust_env">trust_env（走系统代理）</el-checkbox></el-form-item>
          </el-col>
        </el-row>
        <el-form-item><el-checkbox v-model="upstreamForm.enabled">启用</el-checkbox></el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveUpstream" :loading="upstreamSaving">保存</el-button>
          <el-button @click="showUpstreamDialog = false">取消</el-button>
        </el-form-item>
      </el-form>
    </el-dialog>

    <!-- Test Result Dialog -->
    <el-dialog v-model="showTestDialog" title="可用模型" width="560px" destroy-on-close center>
      <div v-if="testResult.ok !== undefined">
        <el-alert :type="testResult.ok ? 'success' : 'error'" :closable="false" show-icon>
          <template #title>
            {{ testResult.ok ? '连通成功' : '连通失败' }}
            <span v-if="testResult.upstream_status_code">HTTP {{ testResult.upstream_status_code }}</span>
            <span v-if="testResult.latency_ms">| {{ testResult.latency_ms }}ms</span>
          </template>
        </el-alert>
        <p v-if="testResult.error" style="color:red">{{ testResult.error }}</p>
        <div v-if="testModels.length" style="margin-top:12px">
          <p>共 {{ testModels.length }} 个模型:</p>
          <el-tag v-for="m in testModels" :key="m" style="margin:2px" size="small">{{ m }}</el-tag>
        </div>
      </div>
    </el-dialog>
  </el-container>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiGet, apiPost, apiPatch, apiDelete } from '../composables/useApi'

const clientKeys = ref<any[]>([])
const upstreams = ref<any[]>([])

const showCreateKeyDialog = ref(false)
const newKeyForm = reactive({ app_id: '', key: '' })
const keySaving = ref(false)

const showEditAppIdDialog = ref(false)
const editingKeyId = ref(0)
const editingKeyMasked = ref('')
const editingAppId = ref('')

const showUpstreamDialog = ref(false)
const editingUpstreamId = ref(0)
const upstreamSaving = ref(false)
const upstreamForm = reactive({
  name: '', base_url: '', api_key: '', timeout_seconds: 60,
  trust_env: false, enabled: true,
})

const showTestDialog = ref(false)
const testResult = ref<any>({})
const testModels = ref<string[]>([])

async function loadAll() { await Promise.all([loadClientKeys(), loadUpstreams()]) }

async function loadClientKeys() {
  try { const d = await apiGet<any>('/admin/gateway-client-keys'); clientKeys.value = d.items || [] }
  catch (e: any) { ElMessage.error(e.message) }
}

async function loadUpstreams() {
  try { const d = await apiGet<any>('/admin/upstreams'); upstreams.value = d.items || [] }
  catch (e: any) { ElMessage.error(e.message) }
}

async function generateKey() {
  try { const d = await apiPost<any>('/admin/gateway-client-keys/generate'); newKeyForm.key = d.gateway_api_key || '' }
  catch (e: any) { ElMessage.error(e.message) }
}

function openCreateKeyDialog() { newKeyForm.app_id = ''; newKeyForm.key = ''; showCreateKeyDialog.value = true; generateKey() }

async function saveClientKey() {
  keySaving.value = true
  try {
    await apiPost('/admin/gateway-client-keys', { app_id: newKeyForm.app_id, gateway_api_key: newKeyForm.key })
    showCreateKeyDialog.value = false; ElMessage.success('密钥已保存'); await loadClientKeys()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { keySaving.value = false }
}

async function copyKey(keyId: number) {
  try {
    const d = await apiGet<any>(`/admin/gateway-client-keys/${keyId}`)
    await navigator.clipboard.writeText(d.api_key); ElMessage.success('已复制到剪贴板')
  } catch (e: any) { ElMessage.error(e.message) }
}

function openEditAppIdDialog(row: any) {
  editingKeyId.value = row.id; editingKeyMasked.value = row.api_key_masked; editingAppId.value = row.app_id
  showEditAppIdDialog.value = true
}

async function saveEditAppId() {
  try {
    await apiPatch(`/admin/gateway-client-keys/${editingKeyId.value}`, { app_id: editingAppId.value })
    showEditAppIdDialog.value = false; ElMessage.success('已更新'); await loadClientKeys()
  } catch (e: any) { ElMessage.error(e.message) }
}

async function confirmDeleteKey(keyId: number) {
  try { await ElMessageBox.confirm('确认删除此 API Key？', '确认', { type: 'warning' }) } catch { return }
  try { await apiDelete(`/admin/gateway-client-keys/${keyId}`); await loadClientKeys(); ElMessage.success('已删除') }
  catch (e: any) { ElMessage.error(e.message) }
}

function openCreateUpstreamDialog() {
  editingUpstreamId.value = 0
  upstreamForm.name = ''; upstreamForm.base_url = ''; upstreamForm.api_key = ''
  upstreamForm.timeout_seconds = 60; upstreamForm.trust_env = false; upstreamForm.enabled = true
  showUpstreamDialog.value = true
}

function openEditUpstreamDialog(row: any) {
  editingUpstreamId.value = row.id
  upstreamForm.name = row.name; upstreamForm.base_url = row.base_url; upstreamForm.api_key = ''
  upstreamForm.timeout_seconds = row.timeout_seconds; upstreamForm.trust_env = row.trust_env
  upstreamForm.enabled = row.enabled
  showUpstreamDialog.value = true
}

async function saveUpstream() {
  upstreamSaving.value = true
  try {
    if (editingUpstreamId.value) {
      const body: any = { name: upstreamForm.name, base_url: upstreamForm.base_url, trust_env: upstreamForm.trust_env, timeout_seconds: upstreamForm.timeout_seconds, enabled: upstreamForm.enabled }
      if (upstreamForm.api_key) body.api_key = upstreamForm.api_key
      await apiPatch(`/admin/upstreams/${editingUpstreamId.value}`, body)
    } else {
      await apiPost('/admin/upstreams', { ...upstreamForm })
    }
    showUpstreamDialog.value = false; await loadUpstreams(); ElMessage.success(editingUpstreamId.value ? '已更新' : '已创建')
  } catch (e: any) { ElMessage.error(e.message) }
  finally { upstreamSaving.value = false }
}

async function confirmDeleteUpstream(id: number) {
  try { await ElMessageBox.confirm('确认删除此上游？', '确认', { type: 'warning' }) } catch { return }
  try { await apiDelete(`/admin/upstreams/${id}`); await loadUpstreams(); ElMessage.success('已删除') }
  catch (e: any) { ElMessage.error(e.message) }
}

async function setDefaultUpstream(id: number) {
  try { await apiPost(`/admin/upstreams/${id}/set-default`); await loadUpstreams(); ElMessage.success('已设为对外服务') }
  catch (e: any) { ElMessage.error(e.message) }
}

async function testUpstream(row: any) {
  showTestDialog.value = true; testResult.value = {}; testModels.value = []
  try {
    const body: any = { base_url: row.base_url, timeout_seconds: row.timeout_seconds, trust_env: row.trust_env, id: row.id }
    const d = await apiPost<any>('/admin/upstreams/test', body)
    testResult.value = d
    if (d.body?.data) testModels.value = d.body.data.map((m: any) => m.id || m).sort()
  } catch (e: any) { testResult.value = { ok: false, error: e.message } }
}

onMounted(loadAll)
</script>
