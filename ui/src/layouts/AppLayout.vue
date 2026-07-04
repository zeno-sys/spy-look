<template>
  <el-container class="app-shell">
    <el-aside width="232px" class="app-sidebar">
      <div class="sidebar-brand">
        <div class="sidebar-logo" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 3L4 8v8l8 5 8-5V8l-8-5z" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>
            <circle cx="12" cy="12" r="2.5" fill="white"/>
          </svg>
        </div>
        <div class="sidebar-brand-text">
          <h2>Spy-Look</h2>
          <span class="sidebar-tagline">个人工具合集</span>
        </div>
      </div>
      <el-menu
        :default-active="activeMenu"
        :default-openeds="['gateway', 'video-tools']"
        router
        class="sidebar-menu"
      >
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon>
          <span>首页</span>
        </el-menu-item>
        <el-sub-menu v-for="tool in tools" :key="tool.id" :index="tool.id">
          <template #title>
            <el-icon><component :is="tool.icon" /></el-icon>
            <span>{{ tool.title }}</span>
          </template>
          <el-menu-item
            v-for="item in tool.menuItems"
            :key="item.path"
            :index="item.path"
          >
            {{ item.title }}
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>
    <el-main class="app-content">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { HomeFilled } from '@element-plus/icons-vue'
import { tools } from '../config/tools'

const route = useRoute()

const activeMenu = computed(() => {
  const path = route.path
  if (path === '/') return '/'
  for (const tool of tools) {
    for (const item of tool.menuItems) {
      if (path === item.path || path.startsWith(item.path + '/')) {
        return item.path
      }
    }
  }
  return path
})
</script>
