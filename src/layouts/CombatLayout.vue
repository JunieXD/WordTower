<script setup lang="ts">
import AppHeader from '@/components/AppHeader.vue'
</script>

<template>
  <div class="layout-container">
    <main class="flex flex-col flex-1 overflow-hidden">
      <!-- 顶部栏 -->
      <AppHeader />
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.layout-container {
  display: flex;
  overflow: hidden;
  /* 使用动态视口高度，适配移动浏览器地址栏 */
  height: 100vh; /* 回退方案 */
  height: 100dvh; /* 动态视口高度，推荐 */
}

/* 如果浏览器不支持 dvh，使用 -webkit-fill-available 作为备选 */
@supports (-webkit-touch-callout: none) {
  .layout-container {
    height: -webkit-fill-available;
  }
}
</style>
