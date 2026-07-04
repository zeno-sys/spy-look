<template>
  <el-tooltip :content="tip" placement="top" :show-after="300" :max-width="360">
    <span class="config-label">{{ label }}</span>
  </el-tooltip>
</template>

<script setup lang="ts">
defineProps<{
  label: string
  tip: string
}>()
</script>

<style scoped>
.config-label {
  cursor: help;
  border-bottom: 1px dashed var(--el-border-color);
}
</style>
