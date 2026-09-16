<script setup lang="ts">
import NotificationContainer from '@/components/NotificationContainer.vue'
import PWAInstallPrompt from '@/components/PWAInstallPrompt.vue'
import RequestRecoveryNotice from '@/components/RequestRecoveryNotice.vue'
</script>

<template>
  <PWAInstallPrompt />
  <NotificationContainer />
  <RequestRecoveryNotice />
  <router-view />
</template>

<style>
body {
  /* 防止双击缩放 */
  touch-action: manipulation;
}
</style>
