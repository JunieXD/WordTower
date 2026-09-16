<script setup lang="ts">
import { requestRecovery } from '@/utils/reliableRequest'
</script>

<template>
  <Transition name="recovery">
    <div
      v-if="requestRecovery"
      role="status"
      aria-live="polite"
      class="fixed inset-x-4 bottom-24 z-50 mx-auto max-w-md rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-center text-sm text-amber-950 shadow-lg"
    >
      {{ requestRecovery }}
    </div>
  </Transition>
</template>

<style scoped>
.recovery-enter-active,
.recovery-leave-active {
  transition: opacity 180ms ease;
}
.recovery-enter-from,
.recovery-leave-to {
  opacity: 0;
}
</style>
