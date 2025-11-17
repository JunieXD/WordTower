<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useUserProfileStore } from '@/stores/userProfile'
import { useNotificationStore } from '@/stores/notification'
import request from '@/utils/request'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useUpgradeStore } from '@/stores/upgrade'

const userProfileStore = useUserProfileStore()
const notificationStore = useNotificationStore()
const upgradeStore = useUpgradeStore()

// 升级项配置
interface UpgradeItem {
  key: 'max_hp' | 'attack' | 'crit_rate'
  name: string
  icon: string
  iconColor: string
  description: string
  currentValue: number
  UpgradeCost: number
  NextValue: number
}

const upgradeItems = computed<UpgradeItem[]>(() => [
  {
    key: 'max_hp',
    name: '最大血量',
    icon: 'mdi:heart',
    iconColor: 'text-red-500',
    description: '增加你的生命值上限',
    currentValue: userProfileStore.profile?.max_hp ?? 100,
    UpgradeCost: upgradeStore.upgradeValues?.upgrade_hp_coins ?? 100,
    NextValue:
      (userProfileStore.profile?.max_hp ?? 100) +
      (upgradeStore.upgradeValues?.upgrade_hp_value ?? 0),
  },
  {
    key: 'attack',
    name: '基础攻击力',
    icon: 'mdi:sword',
    iconColor: 'text-black-500',
    description: '提升你的基础伤害',
    currentValue: userProfileStore.profile?.attack ?? 10,
    UpgradeCost: upgradeStore.upgradeValues?.upgrade_attack_coins ?? 100,
    NextValue:
      (userProfileStore.profile?.attack ?? 10) +
      (upgradeStore.upgradeValues?.upgrade_attack_value ?? 0),
  },
  {
    key: 'crit_rate',
    name: '暴击率',
    icon: 'mdi:flash',
    iconColor: 'text-green-500',
    description: '提高造成暴击伤害的概率',
    currentValue: userProfileStore.profile?.crit_rate ?? 0,
    UpgradeCost: upgradeStore.upgradeValues?.upgrade_crit_rate_coins ?? 100,
    NextValue:
      (userProfileStore.profile?.crit_rate ?? 0) +
      (upgradeStore.upgradeValues?.upgrade_crit_rate_value ?? 0),
  },
])

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

// 升级处理
const handleUpgrade = async (item: UpgradeItem) => {
  const res = await request.post(`/api/upgrade/${item.key}`)

  if (res.data.success) {
    notificationStore.addNotification({
      title: '升级成功',
      description: `${item.name} 已提升至 ${formatValue(item.key, item.NextValue)}`,
      variant: 'default',
      duration: 2000,
    })
    await userProfileStore.getProfile(true)
    console.log(userProfileStore.profile)
  } else {
    notificationStore.addNotification({
      title: '升级失败',
      description: res.data.message,
      variant: 'destructive',
      duration: 2000,
    })
  }
}

onMounted(async () => {
  await userProfileStore.getProfile()
  await upgradeStore.getUpgradeValues()
})
</script>

<template>
  <div class="flex flex-col p-6 h-screen items-center gap-4">
    <!-- 金币显示 -->
    <Card class="w-full max-w-md rounded-lg py-2">
      <CardHeader class="gap-0">
        <CardTitle class="flex flex-row items-center gap-2 text-lg">
          <Icon icon="mdi:coin" class="size-5 text-yellow-500" />
          <div class="mr-auto">当前金币</div>
          <div class="text-2xl font-bold text-yellow-600">
            {{ userProfileStore.profile?.coins ?? 0 }}
          </div>
        </CardTitle>
      </CardHeader>
    </Card>

    <!-- 升级项列表 -->
    <div class="flex flex-col gap-4 w-full max-w-md overflow-y-auto grow shrink min-h-0 pb-4">
      <Card v-for="item in upgradeItems" :key="item.key" class="rounded-lg py-4 gap-0">
        <CardHeader>
          <div class="flex items-center justify-between">
            <CardTitle class="flex items-center gap-2 text-md">
              <Icon :icon="item.icon" class="size-5" :class="item.iconColor" />
              {{ item.name }}
            </CardTitle>
            <div class="text-lg font-bold">{{ formatValue(item.key, item.currentValue) }}</div>
          </div>
        </CardHeader>
        <CardContent class="space-y-3">
          <div class="text-xs text-muted-foreground">
            {{ item.description }}
          </div>

          <!-- 升级信息和按钮 -->
          <div class="flex items-center justify-between pt-2">
            <div class="text-sm">
              <div class="text-muted-foreground">下一级</div>
              <div class="font-semibold text-lg">{{ formatValue(item.key, item.NextValue) }}</div>
            </div>
            <Button
              @click="handleUpgrade(item)"
              class="flex items-center gap-1 rounded-3xl"
              :class="
                canAfford(item) ? 'bg-green-500 cursor-pointer' : 'bg-gray-500 cursor-not-allowed'
              "
            >
              <Icon icon="mdi:coin" class="size-4" />
              {{ item.UpgradeCost }}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>
