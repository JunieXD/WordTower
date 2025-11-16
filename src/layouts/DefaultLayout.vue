<script setup lang="ts">
import FooterNav from '@/components/FooterNav.vue'
import AppSidebar from '@/components/AppSidebar.vue'
import AppHeader from '@/components/AppHeader.vue'
import { SidebarProvider } from '@/components/ui/sidebar'
</script>

<template>
  <div class="flex h-screen overflow-hidden">
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

<style scoped></style>
