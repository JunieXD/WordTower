<script setup lang="ts">
import { useNotificationStore } from '@/stores/notification'
import NotificationItem from './NotificationItem.vue'

const store = useNotificationStore()

const handleClose = (id: number) => {
  store.removeNotification(id)
}
</script>

<template>
  <div class="fixed top-4 right-4 z-1000 w-1/2 max-w-sm pointer-events-none">
    <TransitionGroup name="notification" tag="div" class="space-y-2">
      <NotificationItem
        v-for="alert in store.alerts"
        :key="alert.id"
        :notification="alert"
        @close="handleClose"
        class="pointer-events-auto"
      />
    </TransitionGroup>
  </div>
</template>

<style>
/* 定义进入和离开时的过渡效果 */
.notification-enter-active,
.notification-leave-active {
  transition: all 0.5s ease-in-out;
}

/* 解决列表元素变化时平滑移动的问题 */
.notification-move {
  transition: transform 0.5s ease-in-out;
}

/* 初始状态（进入前）和结束状态（离开后） */
.notification-enter-from,
.notification-leave-to {
  opacity: 0;
  /* 从右侧滑入/滑出 */
  transform: translateX(100%);
}

/* 确保离开的元素不会影响布局，当它正在离开时 */
.notification-leave-active {
  position: absolute;
}
</style>
