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
        <h1>Spy-Look</h1>
        <p>登录以继续使用管理台</p>
      </div>

      <el-form :model="form" @submit.prevent="onSubmit" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="form.username" autocomplete="username" placeholder="用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            autocomplete="current-password"
            placeholder="密码"
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="form.remember">记住我（30 天）</el-checkbox>
        </el-form-item>
        <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="auth-error" />
        <el-button type="primary" class="auth-submit" :loading="submitting" @click="onSubmit">
          登录
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../../composables/useAuth'

const router = useRouter()
const { login } = useAuth()

const form = reactive({
  username: '',
  password: '',
  remember: false,
})
const submitting = ref(false)
const error = ref('')

async function onSubmit() {
  error.value = ''
  if (!form.username.trim() || !form.password) {
    error.value = '请输入用户名和密码'
    return
  }
  submitting.value = true
  try {
    await login(form.username.trim(), form.password, form.remember)
    await router.replace('/')
  } catch (e: any) {
    error.value = e?.message || '登录失败'
  } finally {
    submitting.value = false
  }
}
</script>

<style src="./auth-shared.css"></style>
