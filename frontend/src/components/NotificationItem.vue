<script setup lang="ts">
import { computed } from 'vue'
import { BadgeInfo, BadgeAlert, X } from 'lucide-vue-next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import type { Notification } from '@/stores/notification'

// 导入 Alert 组件的 props 类型
type AlertVariant = 'default' | 'destructive' | undefined

const props = defineProps<{
  notification: Notification
}>()

const emit = defineEmits<{
  (e: 'close', id: number): void
}>()

const alertProps = computed((): { variant?: AlertVariant } => {
  // 如果 variant 是 'destructive'，返回包含 variant 的对象
  if (props.notification.variant === 'destructive') {
    return { variant: 'destructive' }
  }
  return {}
})

// 根据 variant 渲染不同的图标
const IconComponent = computed(() => {
  return props.notification.variant === 'destructive' ? BadgeAlert : BadgeInfo
})
</script>

<template>
  <Alert v-bind="alertProps" class="relative w-full max-w-sm">
    <component :is="IconComponent" class="h-4 w-4" />

    <AlertTitle>{{ notification.title }}</AlertTitle>

    <AlertDescription>
      {{ notification.description }}
    </AlertDescription>

    <button
      @click="emit('close', notification.id)"
      class="absolute top-2 right-2 p-1 opacity-70 transition-opacity hover:opacity-100 rounded-sm"
      aria-label="Close"
    >
      <X class="h-4 w-4" />
    </button>
  </Alert>
</template>
