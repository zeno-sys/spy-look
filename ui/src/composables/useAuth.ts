import { computed, ref } from 'vue'
import { apiGet, apiPost } from './useApi'

export interface AuthUser {
  id: number
  username: string
  role: 'owner' | 'admin' | string
  disabled: boolean
  locked: boolean
  created_at?: string | null
  updated_at?: string | null
}

export interface AuthStatus {
  initialized: boolean
  user: AuthUser | null
}

const status = ref<AuthStatus | null>(null)
const loading = ref(false)

export function useAuth() {
  const user = computed(() => status.value?.user ?? null)
  const initialized = computed(() => status.value?.initialized ?? false)
  const isOwner = computed(() => user.value?.role === 'owner')
  const isLoggedIn = computed(() => !!user.value)

  async function refreshStatus(): Promise<AuthStatus> {
    loading.value = true
    try {
      const data = await apiGet<AuthStatus>('/auth/status')
      status.value = data
      return data
    } finally {
      loading.value = false
    }
  }

  async function setup(username: string, password: string) {
    const data = await apiPost<{ ok: boolean; user: AuthUser }>('/auth/setup', {
      username,
      password,
    })
    status.value = { initialized: true, user: data.user }
    return data
  }

  async function login(username: string, password: string, remember: boolean) {
    const data = await apiPost<{ ok: boolean; user: AuthUser }>('/auth/login', {
      username,
      password,
      remember,
    })
    status.value = { initialized: true, user: data.user }
    return data
  }

  async function logout() {
    try {
      await apiPost('/auth/logout')
    } finally {
      if (status.value) {
        status.value = { initialized: status.value.initialized, user: null }
      } else {
        status.value = { initialized: true, user: null }
      }
    }
  }

  async function changePassword(currentPassword: string, newPassword: string) {
    return apiPost('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
  }

  async function localResetOwner(newPassword: string) {
    return apiPost('/auth/local-reset-owner', { new_password: newPassword })
  }

  return {
    status,
    loading,
    user,
    initialized,
    isOwner,
    isLoggedIn,
    refreshStatus,
    setup,
    login,
    logout,
    changePassword,
    localResetOwner,
  }
}
