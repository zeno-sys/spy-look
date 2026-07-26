<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-brand">
        <div class="auth-logo" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 3L4 8v8l8 5 8-5V8l-8-5z" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>
            <circle cx="12" cy="12" r="2.5" fill="white"/>
          </svg>
        </div>
        <h1>本机重置 Owner 密码</h1>
        <p>仅可通过本机地址（127.0.0.1 / localhost）访问。成功后需重新登录。</p>
      </div>

      <el-form :model="form" @submit.prevent="onSubmit" label-position="top">
        <el-form-item label="新密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            autocomplete="new-password"
            placeholder="至少 8 位"
          />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input
            v-model="form.confirm"
            type="password"
            show-password
            autocomplete="new-password"
            placeholder="再次输入密码"
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="auth-error" />
        <el-alert
          v-if="success"
          title="密码已重置，请使用新密码登录"
          type="success"
          show-icon
          :closable="false"
          class="auth-error"
        />
        <el-button type="primary" class="auth-submit" :loading="submitting" @click="onSubmit">
          重置密码
        </el-button>
        <el-button class="auth-link" text type="primary" @click="goLogin">返回登录</el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../../composables/useAuth'

const router = useRouter()
const { localResetOwner } = useAuth()

const form = reactive({
  password: '',
  confirm: '',
})
const submitting = ref(false)
const error = ref('')
const success = ref(false)

async function onSubmit() {
  error.value = ''
  success.value = false
  if (form.password.length < 8) {
    error.value = '密码至少 8 位'
    return
  }
  if (form.password !== form.confirm) {
    error.value = '两次输入的密码不一致'
    return
  }
  submitting.value = true
  try {
    await localResetOwner(form.password)
    success.value = true
    form.password = ''
    form.confirm = ''
  } catch (e: any) {
    error.value = e?.message || '重置失败'
  } finally {
    submitting.value = false
  }
}

function goLogin() {
  router.push('/login')
}
</script>

<style src="./auth-shared.css"></style>
<style scoped>
.auth-link {
  width: 100%;
  margin-top: 8px;
}
</style>
