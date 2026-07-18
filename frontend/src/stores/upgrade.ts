import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/utils/request'
import { useNotificationStore } from '@/stores/notification'
import { useUserProfileStore } from '@/stores/userProfile'

export interface UpgradeValues {
  upgrade_hp_coins: number
  upgrade_attack_coins: number
  upgrade_crit_rate_coins: number
  upgrade_hp_value: number
  upgrade_attack_value: number
  upgrade_crit_rate_value: number
}

// 升级项配置
export interface UpgradeItem {
  key: 'max_hp' | 'attack' | 'crit_rate'
  name: string
  icon: string
  iconColor: string
  description: string
  currentValue: number
  UpgradeCost: number
  NextValue: number
}

export const useUpgradeStore = defineStore('upgrade', () => {
  const notificationStore = useNotificationStore()
  const userProfileStore = useUserProfileStore()
  const upgradeValues = ref<UpgradeValues | null>(null)
  const isUpgrading = ref(false)

  async function fetchUpgradeValues() {
    try {
      const res = await request.get('/api/upgrade/get_values')
      if (res.data.success && res.data.data) {
        upgradeValues.value = res.data.data
      }
    } catch (error) {
      console.error('获取升级值失败:', error)
      return null
    }
  }

  async function getUpgradeValues() {
    if (!upgradeValues.value) {
      await fetchUpgradeValues()
    }
    return upgradeValues.value
  }

  // 升级处理
  const handleUpgrade = async (item: UpgradeItem) => {
    // 防止重复点击
    if (isUpgrading.value) return

    isUpgrading.value = true
    try {
      const res = await request.post(`/api/upgrade/${item.key}`)

      if (res.data.success) {
        notificationStore.addNotification({
          title: '升级成功',
          description: `${item.name} 已提升至 ${formatValue(item.key, item.NextValue)}`,
          variant: 'default',
          duration: 2000,
        })
        await userProfileStore.getProfile(true)
      } else {
        notificationStore.addNotification({
          title: '升级失败',
          description: res.data.message,
          variant: 'destructive',
          duration: 2000,
        })
      }
    } finally {
      isUpgrading.value = false
    }
  }

  // 是否有足够金币
  const canAfford = (item: UpgradeItem): boolean => {
    const cost = item.UpgradeCost
    return (userProfileStore.profile?.coins ?? 0) >= cost
  }

  // 格式化显示数值
  const formatValue = (key: string, value: number): string => {
    if (key === 'crit_rate') {
      return `${(value * 100).toFixed(1)}%`
    }
    return value.toString()
  }

  return {
    upgradeValues,
    isUpgrading,
    fetchUpgradeValues,
    getUpgradeValues,
    handleUpgrade,
    canAfford,
    formatValue,
  }
})
