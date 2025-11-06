<script setup lang="ts">
import NotificationContainer from '@/components/NotificationContainer.vue'
</script>

<template>
  <NotificationContainer />
  <router-view />
</template>

<style>
body {
  /* 防止页面内容超出视口 */
  width: 100%;
  height: 100%;
  /* 隐藏掉溢出的内容，特别是水平方向的 */
  overflow-x: hidden;
  overflow-y: hidden;
  /* 防止双击缩放 */
  touch-action: manipulation;
}
</style>
