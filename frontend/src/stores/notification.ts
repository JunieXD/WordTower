import { defineStore } from 'pinia'
import { ref } from 'vue'

// 定义通知的类型
export interface Notification {
  id: number
  title: string
  description: string
  variant?: 'default' | 'destructive'
  duration?: number // 自动关闭的时间，单位毫秒
}

export const useNotificationStore = defineStore('notification', () => {
  // 通知队列
  const alerts = ref<Notification[]>([])
  let nextId = 0

  /**
   * 添加一个新通知
   */
  function addNotification(notification: Omit<Notification, 'id'>) {
    const newAlert: Notification = {
      id: nextId++,
      ...notification,
    }

    // 使用 unshift 将新通知放在数组开头，使其显示在其他通知的上方
    alerts.value.unshift(newAlert)

    // 设置自动关闭
    const duration = notification.duration ?? 3000 // 默认 3 秒

    if (duration > 0) {
      setTimeout(() => {
        removeNotification(newAlert.id)
      }, duration)
    }
  }

  /**
   * 根据 ID 移除通知
   */
  function removeNotification(id: number) {
    alerts.value = alerts.value.filter((alert) => alert.id !== id)
  }

  return {
    alerts,
    addNotification,
    removeNotification,
  }
})
