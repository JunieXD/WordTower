<script setup lang="ts">
import FooterNav from '@/components/FooterNav.vue'
import AppSidebar from '@/components/AppSidebar.vue'
import { SidebarProvider } from '@/components/ui/sidebar'
</script>

<template>
  <div class="flex min-h-screen">
    <!-- 侧边栏：仅桌面端显示 -->
    <div class="hidden lg:block">
      <SidebarProvider>
        <AppSidebar />
      </SidebarProvider>
    </div>
    <!-- 主区域 -->
    <main class="flex-col flex-1 pb-16 lg:pb-0">
      <router-view />
      <!-- 底部导航栏：仅手机端显示 -->
      <FooterNav class="block lg:hidden" />
    </main>
  </div>
</template>

<style scoped></style>
