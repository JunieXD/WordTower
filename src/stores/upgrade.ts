import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/utils/request'

export interface UpgradeValues {
  upgrade_hp_coins: number
  upgrade_attack_coins: number
  upgrade_crit_rate_coins: number
  upgrade_hp_value: number
  upgrade_attack_value: number
  upgrade_crit_rate_value: number
}

export const useUpgradeStore = defineStore('upgrade', () => {
  const upgradeValues = ref<UpgradeValues | null>(null)

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

  return {
    upgradeValues,
    fetchUpgradeValues,
    getUpgradeValues,
  }
})
