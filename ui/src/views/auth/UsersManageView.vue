<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h3>用户管理</h3>
        <p class="page-subtitle">仅 Owner 可见。可创建 Admin、禁用、重置密码与强制下线。</p>
      </div>
      <div class="header-actions">
        <el-button @click="loadUsers" :loading="loading">刷新</el-button>
        <el-button type="primary" @click="openCreate">新建 Admin</el-button>
      </div>
    </div>

    <div class="page-body">
      <el-table :data="users" v-loading="loading" stripe>
        <el-table-column prop="username" label="用户名" min-width="140" />
        <el-table-column label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="row.role === 'owner' ? 'warning' : 'info'" size="small">
              {{ row.role === 'owner' ? 'Owner' : 'Admin' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.disabled" type="danger" size="small">已禁用</el-tag>
            <el-tag v-else-if="row.locked" type="warning" size="small">已锁定</el-tag>
            <el-tag v-else type="success" size="small">正常</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="320" fixed="right">
          <template #default="{ row }">
            <template v-if="row.role !== 'owner'">
              <el-button link type="primary" @click="openReset(row)">重置密码</el-button>
              <el-button link type="primary" @click="revokeSessions(row)">强制下线</el-button>
              <el-button
                link
                :type="row.disabled ? 'success' : 'warning'"
                @click="toggleDisabled(row)"
              >
                {{ row.disabled ? '启用' : '禁用' }}
              </el-button>
              <el-button link type="danger" @click="removeUser(row)">删除</el-button>
            </template>
            <span v-else class="muted">唯一 Owner</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="createVisible" title="新建 Admin" width="420px" destroy-on-close>
      <el-form :model="createForm" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="createForm.username" placeholder="字母或数字开头" />
        </el-form-item>
        <el-form-item label="初始密码">
          <el-input v-model="createForm.password" type="password" show-password placeholder="至少 8 位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="createUser">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetVisible" title="重置密码" width="420px" destroy-on-close>
      <p class="hint" style="margin-bottom: 12px">为用户 <strong>{{ resetTarget?.username }}</strong> 设置新密码</p>
      <el-form :model="resetForm" label-position="top">
        <el-form-item label="新密码">
          <el-input v-model="resetForm.password" type="password" show-password placeholder="至少 8 位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="resetPassword">确认重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiDelete, apiGet, apiPost } from '../../composables/useApi'
import type { AuthUser } from '../../composables/useAuth'
import { formatBeijingTime as formatTime } from '../../utils/formatTime'

const users = ref<AuthUser[]>([])
const loading = ref(false)
const acting = ref(false)

const createVisible = ref(false)
const createForm = reactive({ username: '', password: '' })

const resetVisible = ref(false)
const resetTarget = ref<AuthUser | null>(null)
const resetForm = reactive({ password: '' })

async function loadUsers() {
  loading.value = true
  try {
    const data = await apiGet<{ items: AuthUser[] }>('/auth/users')
    users.value = data.items || []
  } catch (e: any) {
    ElMessage.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  createForm.username = ''
  createForm.password = ''
  createVisible.value = true
}

async function createUser() {
  if (!createForm.username.trim() || createForm.password.length < 8) {
    ElMessage.warning('请填写有效用户名与至少 8 位密码')
    return
  }
  acting.value = true
  try {
    await apiPost('/auth/users', {
      username: createForm.username.trim(),
      password: createForm.password,
    })
    ElMessage.success('已创建')
    createVisible.value = false
    await loadUsers()
  } catch (e: any) {
    ElMessage.error(e?.message || '创建失败')
  } finally {
    acting.value = false
  }
}

function openReset(row: AuthUser) {
  resetTarget.value = row
  resetForm.password = ''
  resetVisible.value = true
}

async function resetPassword() {
  if (!resetTarget.value) return
  if (resetForm.password.length < 8) {
    ElMessage.warning('密码至少 8 位')
    return
  }
  acting.value = true
  try {
    await apiPost(`/auth/users/${resetTarget.value.id}/reset-password`, {
      new_password: resetForm.password,
    })
    ElMessage.success('密码已重置，该用户需重新登录')
    resetVisible.value = false
  } catch (e: any) {
    ElMessage.error(e?.message || '重置失败')
  } finally {
    acting.value = false
  }
}

async function toggleDisabled(row: AuthUser) {
  const next = !row.disabled
  const action = next ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(`确定要${action}用户「${row.username}」吗？`, '确认', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await apiPost(`/auth/users/${row.id}/disabled`, { disabled: next })
    ElMessage.success(`已${action}`)
    await loadUsers()
  } catch (e: any) {
    ElMessage.error(e?.message || `${action}失败`)
  }
}

async function revokeSessions(row: AuthUser) {
  try {
    await ElMessageBox.confirm(`强制下线「${row.username}」的所有会话？`, '确认', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    const data = await apiPost<{ revoked: number }>(`/auth/users/${row.id}/revoke-sessions`)
    ElMessage.success(`已作废 ${data.revoked ?? 0} 个会话`)
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  }
}

async function removeUser(row: AuthUser) {
  try {
    await ElMessageBox.confirm(`确定删除用户「${row.username}」？此操作不可恢复。`, '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
    })
  } catch {
    return
  }
  try {
    await apiDelete(`/auth/users/${row.id}`)
    ElMessage.success('已删除')
    await loadUsers()
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败')
  }
}

onMounted(loadUsers)
</script>

<style scoped>
.muted {
  color: var(--sl-text-muted);
  font-size: 13px;
}
.hint {
  color: var(--sl-text-secondary);
  font-size: 13px;
}
</style>
