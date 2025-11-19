<script setup lang="ts">
import NotificationContainer from '@/components/NotificationContainer.vue'
// import PWAInstallPrompt from '@/components/PWAInstallPrompt.vue'
</script>

<template>
  <!-- <PWAInstallPrompt /> -->
  <NotificationContainer />
  <router-view />
</template>

<style>
body {
  /* 防止双击缩放 */
  touch-action: manipulation;
}
</style>
