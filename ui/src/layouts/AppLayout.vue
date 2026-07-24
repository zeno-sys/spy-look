<template>
  <el-container class="app-shell">
    <el-aside :width="sidebarCollapsed ? '64px' : '232px'" class="app-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-brand">
        <div class="sidebar-logo" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 3L4 8v8l8 5 8-5V8l-8-5z" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>
            <circle cx="12" cy="12" r="2.5" fill="white"/>
          </svg>
        </div>
        <div v-show="!sidebarCollapsed" class="sidebar-brand-text">
          <h2>Spy-Look</h2>
          <span class="sidebar-tagline">个人工具合集</span>
        </div>
      </div>
      <el-menu
        :default-active="activeMenu"
        :default-openeds="['gateway', 'video-tools', 'doc-tools']"
        :collapse="sidebarCollapsed"
        :collapse-transition="false"
        router
        class="sidebar-menu"
      >
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon>
          <template #title>首页</template>
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
      <div class="sidebar-footer">
        <el-menu
          :default-active="activeMenu"
          :collapse="sidebarCollapsed"
          :collapse-transition="false"
          router
          class="sidebar-footer-menu"
        >
          <el-menu-item index="/settings">
            <el-icon><Setting /></el-icon>
            <template #title>设置</template>
          </el-menu-item>
        </el-menu>
        <button
          type="button"
          class="sidebar-collapse-btn"
          :title="sidebarCollapsed ? '展开菜单' : '收起菜单'"
          @click="toggleSidebar"
        >
          <el-icon :size="16">
            <Expand v-if="sidebarCollapsed" />
            <Fold v-else />
          </el-icon>
          <span v-show="!sidebarCollapsed">收起菜单</span>
        </button>
      </div>
    </el-aside>
    <el-main class="app-content">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Expand, Fold, HomeFilled, Setting } from '@element-plus/icons-vue'
import { tools } from '../config/tools'

const SIDEBAR_KEY = 'spy-look-sidebar-collapsed'

const route = useRoute()
const sidebarCollapsed = ref(localStorage.getItem(SIDEBAR_KEY) === '1')

watch(sidebarCollapsed, (v) => {
  localStorage.setItem(SIDEBAR_KEY, v ? '1' : '0')
})

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const activeMenu = computed(() => {
  const path = route.path
  if (path === '/') return '/'
  if (path === '/settings' || path.startsWith('/settings/')) return '/settings'
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
