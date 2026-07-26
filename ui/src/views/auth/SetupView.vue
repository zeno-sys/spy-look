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
        <h1>初始化管理员</h1>
        <p>首次部署请设置唯一 Owner 账号，完成后即可进入系统</p>
      </div>

      <el-form :model="form" @submit.prevent="onSubmit" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="form.username" autocomplete="username" placeholder="字母或数字开头" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            autocomplete="new-password"
            placeholder="至少 8 位"
          />
        </el-form-item>
        <el-form-item label="确认密码">
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
        <el-button type="primary" class="auth-submit" :loading="submitting" @click="onSubmit">
          创建并进入
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
const { setup } = useAuth()

const form = reactive({
  username: '',
  password: '',
  confirm: '',
})
const submitting = ref(false)
const error = ref('')

async function onSubmit() {
  error.value = ''
  if (!form.username.trim()) {
    error.value = '请输入用户名'
    return
  }
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
    await setup(form.username.trim(), form.password)
    await router.replace('/')
  } catch (e: any) {
    error.value = e?.message || '初始化失败'
  } finally {
    submitting.value = false
  }
}
</script>

<style src="./auth-shared.css"></style>
