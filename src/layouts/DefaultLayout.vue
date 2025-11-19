<script setup lang="ts">
import FooterNav from '@/components/FooterNav.vue'
import AppSidebar from '@/components/AppSidebar.vue'
import AppHeader from '@/components/AppHeader.vue'
import { SidebarProvider } from '@/components/ui/sidebar'
</script>

<template>
  <div class="layout-container">
    <!-- 侧边栏：仅桌面端显示 -->
    <div class="hidden lg:block">
      <SidebarProvider>
        <AppSidebar />
      </SidebarProvider>
    </div>
    <!-- 主区域 -->
    <main class="flex flex-col flex-1 overflow-hidden">
      <!-- 顶部栏：所有页面显示 -->
      <AppHeader />
      <RouterView class="flex-1 overflow-hidden pb-16 lg:pb-0" />
      <!-- 底部导航栏：仅手机端显示 -->
      <FooterNav class="block lg:hidden" />
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
