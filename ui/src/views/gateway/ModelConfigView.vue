<template>
  <div class="page-container">
    <div class="page-header">
      <div><h3>大模型网关 · 模型配置</h3></div>
      <div class="header-actions">
        <el-button type="primary" @click="loadAll">刷新列表</el-button>
      </div>
    </div>

    <div class="page-body">
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
          <el-table-column prop="created_at" label="创建时间" width="180">
            <template #default="{ row }">{{ formatBeijingTime(row.created_at) }}</template>
          </el-table-column>
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
          <div class="card-header">
            <span>模型源配置</span>
            <el-button type="primary" @click="openCreateUpstreamDialog">新增模型源</el-button>
          </div>
        </template>
        <p class="hint">配置真实大模型提供商的连接信息；保存前会自动请求上游 <code>/models</code> 测试连通性，通过后方可保存。对外模型通过下方绑定映射到具体模型源。</p>
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
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="testUpstream(row)">探测</el-button>
              <el-button size="small" @click="openEditUpstreamDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="confirmDeleteUpstream(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- Public Models -->
      <el-card class="section-card">
        <template #header>
          <div class="card-header">
            <span>对外模型配置</span>
            <el-button type="primary" @click="openCreatePublicModelDialog">新增对外模型</el-button>
          </div>
        </template>
        <p class="hint">客户端调用 <code>/v1/models</code> 与 <code>/v1/chat/completions</code> 时仅能看到此处配置的对外模型名。</p>
        <el-table :data="publicModels" stripe size="small">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="name" label="对外模型名" min-width="160" />
          <el-table-column prop="bindings_summary" label="绑定" min-width="260" show-overflow-tooltip />
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '启用' : '禁用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openEditPublicModelDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="confirmDeletePublicModel(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

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
    <el-dialog v-model="showUpstreamDialog" :title="editingUpstreamId ? '编辑模型源' : '新增模型源'" width="560px" destroy-on-close center>
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
        <el-form-item :label="editingUpstreamId ? 'API Key (留空不修改)' : 'API Key (可选)'">
          <el-input v-model="upstreamForm.api_key" type="password" show-password placeholder="无需鉴权的模型源可留空" />
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
          <el-button type="primary" @click="saveUpstream" :loading="upstreamSaving">
            {{ upstreamSaving ? '测试连通性中…' : '保存' }}
          </el-button>
          <el-button @click="showUpstreamDialog = false">取消</el-button>
        </el-form-item>
      </el-form>
    </el-dialog>

    <!-- Public Model Dialog -->
    <el-dialog
      v-model="showPublicModelDialog"
      :title="editingPublicModelId ? '编辑对外模型' : '新增对外模型'"
      width="680px"
      destroy-on-close
      center
    >
      <el-form :model="publicModelForm" label-position="top">
        <el-form-item label="对外模型名称">
          <el-input v-model="publicModelForm.name" placeholder="客户端请求时使用的 model 名称" />
        </el-form-item>
        <el-form-item><el-checkbox v-model="publicModelForm.enabled">启用</el-checkbox></el-form-item>

        <div class="route-list-header">
          <span>模型源绑定</span>
          <el-button size="small" @click="addRouteRow">添加绑定</el-button>
        </div>
        <p class="hint">可绑定多个模型源实现负载均衡；同一客户端通过请求头 <code>X-Session-Id</code> 保持会话粘性。</p>

        <div v-for="(route, index) in publicModelForm.routes" :key="index" class="route-row">
          <el-select
            v-model="route.upstream_id"
            placeholder="选择模型源"
            style="width: 180px"
            @change="onRouteUpstreamChange(route)"
          >
            <el-option
              v-for="u in enabledUpstreams"
              :key="u.id"
              :label="u.name"
              :value="u.id"
            />
          </el-select>
          <el-select
            v-model="route.upstream_model"
            placeholder="选择实际模型"
            style="flex: 1"
            filterable
            :loading="route.loading"
            :disabled="!route.upstream_id"
          >
            <el-option v-for="m in route.modelOptions" :key="m" :label="m" :value="m" />
          </el-select>
          <el-button type="danger" text @click="removeRouteRow(index)" :disabled="publicModelForm.routes.length <= 1">删除</el-button>
        </div>

        <el-form-item style="margin-top: 16px">
          <el-button type="primary" @click="savePublicModel" :loading="publicModelSaving">保存</el-button>
          <el-button @click="showPublicModelDialog = false">取消</el-button>
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
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiGet, apiPost, apiPatch, apiDelete } from '../../composables/useApi'
import { formatBeijingTime } from '../../utils/formatTime'

interface RouteFormRow {
  upstream_id: number | null
  upstream_model: string
  modelOptions: string[]
  loading: boolean
}

const clientKeys = ref<any[]>([])
const upstreams = ref<any[]>([])
const publicModels = ref<any[]>([])

const enabledUpstreams = computed(() => upstreams.value.filter((u) => u.enabled))

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

const showPublicModelDialog = ref(false)
const editingPublicModelId = ref(0)
const publicModelSaving = ref(false)
const publicModelForm = reactive({
  name: '',
  enabled: true,
  routes: [] as RouteFormRow[],
})

const showTestDialog = ref(false)
const testResult = ref<any>({})
const testModels = ref<string[]>([])

function emptyRouteRow(): RouteFormRow {
  return { upstream_id: null, upstream_model: '', modelOptions: [], loading: false }
}

async function loadAll() {
  await Promise.all([loadClientKeys(), loadUpstreams(), loadPublicModels()])
}

async function loadClientKeys() {
  try { const d = await apiGet<any>('/gateway/admin/gateway-client-keys'); clientKeys.value = d.items || [] }
  catch (e: any) { ElMessage.error(e.message) }
}

async function loadUpstreams() {
  try { const d = await apiGet<any>('/gateway/admin/upstreams'); upstreams.value = d.items || [] }
  catch (e: any) { ElMessage.error(e.message) }
}

async function loadPublicModels() {
  try { const d = await apiGet<any>('/gateway/admin/public-models'); publicModels.value = d.items || [] }
  catch (e: any) { ElMessage.error(e.message) }
}

async function loadUpstreamModels(upstreamId: number): Promise<string[]> {
  const d = await apiGet<any>(`/gateway/admin/upstreams/${upstreamId}/models`)
  return d.models || []
}

async function generateKey() {
  try { const d = await apiPost<any>('/gateway/admin/gateway-client-keys/generate'); newKeyForm.key = d.gateway_api_key || '' }
  catch (e: any) { ElMessage.error(e.message) }
}

function openCreateKeyDialog() { newKeyForm.app_id = ''; newKeyForm.key = ''; showCreateKeyDialog.value = true; generateKey() }

async function saveClientKey() {
  keySaving.value = true
  try {
    await apiPost('/gateway/admin/gateway-client-keys', { app_id: newKeyForm.app_id, gateway_api_key: newKeyForm.key })
    showCreateKeyDialog.value = false; ElMessage.success('密钥已保存'); await loadClientKeys()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { keySaving.value = false }
}

async function copyKey(keyId: number) {
  try {
    const d = await apiGet<any>(`/gateway/admin/gateway-client-keys/${keyId}`)
    await navigator.clipboard.writeText(d.api_key); ElMessage.success('已复制到剪贴板')
  } catch (e: any) { ElMessage.error(e.message) }
}

function openEditAppIdDialog(row: any) {
  editingKeyId.value = row.id; editingKeyMasked.value = row.api_key_masked; editingAppId.value = row.app_id
  showEditAppIdDialog.value = true
}

async function saveEditAppId() {
  try {
    await apiPatch(`/gateway/admin/gateway-client-keys/${editingKeyId.value}`, { app_id: editingAppId.value })
    showEditAppIdDialog.value = false; ElMessage.success('已更新'); await loadClientKeys()
  } catch (e: any) { ElMessage.error(e.message) }
}

async function confirmDeleteKey(keyId: number) {
  try { await ElMessageBox.confirm('确认删除此 API Key？', '确认', { type: 'warning' }) } catch { return }
  try { await apiDelete(`/gateway/admin/gateway-client-keys/${keyId}`); await loadClientKeys(); ElMessage.success('已删除') }
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
      await apiPatch(`/gateway/admin/upstreams/${editingUpstreamId.value}`, body)
    } else {
      await apiPost('/gateway/admin/upstreams', { ...upstreamForm })
    }
    showUpstreamDialog.value = false; await loadUpstreams(); ElMessage.success(editingUpstreamId.value ? '已更新' : '已创建')
  } catch (e: any) { ElMessage.error(e.message) }
  finally { upstreamSaving.value = false }
}

async function confirmDeleteUpstream(row: any) {
  try {
    const d = await apiGet<any>(`/gateway/admin/upstreams/${row.id}/bindings`)
    if ((d.items || []).length > 0) {
      const summary = d.items
        .map((b: any) => `${b.public_model_name}/${b.upstream_model}`)
        .join('、')
      await ElMessageBox.alert(
        `该模型源「${row.name}」仍被以下对外模型绑定：\n\n${summary}\n\n请先在「对外模型配置」中解除绑定后再删除。`,
        '无法删除',
        { type: 'warning', confirmButtonText: '我知道了' },
      )
      return
    }
  } catch (e: any) {
    ElMessage.error(e.message)
    return
  }
  try { await ElMessageBox.confirm(`确认删除模型源「${row.name}」？`, '确认', { type: 'warning' }) } catch { return }
  try { await apiDelete(`/gateway/admin/upstreams/${row.id}`); await loadUpstreams(); ElMessage.success('已删除') }
  catch (e: any) { ElMessage.error(e.message) }
}

function addRouteRow() {
  publicModelForm.routes.push(emptyRouteRow())
}

function removeRouteRow(index: number) {
  publicModelForm.routes.splice(index, 1)
}

async function onRouteUpstreamChange(route: RouteFormRow) {
  route.upstream_model = ''
  route.modelOptions = []
  if (!route.upstream_id) return
  route.loading = true
  try {
    route.modelOptions = await loadUpstreamModels(route.upstream_id)
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    route.loading = false
  }
}

function openCreatePublicModelDialog() {
  editingPublicModelId.value = 0
  publicModelForm.name = ''
  publicModelForm.enabled = true
  publicModelForm.routes = [emptyRouteRow()]
  showPublicModelDialog.value = true
}

async function openEditPublicModelDialog(row: any) {
  editingPublicModelId.value = row.id
  publicModelForm.name = row.name
  publicModelForm.enabled = row.enabled
  publicModelForm.routes = []
  showPublicModelDialog.value = true
  try {
    const detail = await apiGet<any>(`/gateway/admin/public-models/${row.id}`)
    publicModelForm.routes = await Promise.all(
      (detail.routes || []).map(async (r: any) => {
        const routeRow: RouteFormRow = {
          upstream_id: r.upstream_id,
          upstream_model: r.upstream_model,
          modelOptions: [],
          loading: true,
        }
        try {
          routeRow.modelOptions = await loadUpstreamModels(r.upstream_id)
        } catch {
          routeRow.modelOptions = r.upstream_model ? [r.upstream_model] : []
        } finally {
          routeRow.loading = false
        }
        return routeRow
      }),
    )
    if (!publicModelForm.routes.length) {
      publicModelForm.routes = [emptyRouteRow()]
    }
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

async function savePublicModel() {
  const routes = publicModelForm.routes
    .filter((r) => r.upstream_id && r.upstream_model)
    .map((r) => ({ upstream_id: r.upstream_id, upstream_model: r.upstream_model, enabled: true }))
  if (!publicModelForm.name.trim()) {
    ElMessage.warning('请填写对外模型名称')
    return
  }
  if (!routes.length) {
    ElMessage.warning('请至少配置一条模型源绑定')
    return
  }
  publicModelSaving.value = true
  try {
    const body = { name: publicModelForm.name.trim(), enabled: publicModelForm.enabled, routes }
    if (editingPublicModelId.value) {
      await apiPatch(`/gateway/admin/public-models/${editingPublicModelId.value}`, body)
    } else {
      await apiPost('/gateway/admin/public-models', body)
    }
    showPublicModelDialog.value = false
    await loadPublicModels()
    ElMessage.success(editingPublicModelId.value ? '已更新' : '已创建')
  } catch (e: any) { ElMessage.error(e.message) }
  finally { publicModelSaving.value = false }
}

async function confirmDeletePublicModel(id: number) {
  try { await ElMessageBox.confirm('确认删除此对外模型？', '确认', { type: 'warning' }) } catch { return }
  try { await apiDelete(`/gateway/admin/public-models/${id}`); await loadPublicModels(); ElMessage.success('已删除') }
  catch (e: any) { ElMessage.error(e.message) }
}

async function testUpstream(row: any) {
  showTestDialog.value = true; testResult.value = {}; testModels.value = []
  try {
    const body: any = { base_url: row.base_url, timeout_seconds: row.timeout_seconds, trust_env: row.trust_env, id: row.id }
    const d = await apiPost<any>('/gateway/admin/upstreams/test', body)
    testResult.value = d
    if (d.body?.data) testModels.value = d.body.data.map((m: any) => m.id || m).sort()
  } catch (e: any) { testResult.value = { ok: false, error: e.message } }
}

onMounted(loadAll)
</script>

<style scoped>
.route-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-weight: 600;
}

.route-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
</style>
