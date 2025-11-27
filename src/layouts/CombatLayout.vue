<script setup lang="ts">
import AppHeader from '@/components/AppHeader.vue'
</script>

<template>
  <div
    class="flex overflow-hidden h-screen supports-[height:100dvh]:h-dvh supports-[(-webkit-touch-callout:none)]:h-[-webkit-fill-available]"
  >
    <main class="flex flex-col flex-1 overflow-hidden">
      <!-- 顶部栏 -->
      <AppHeader />
      <RouterView />
    </main>
  </div>
</template>
