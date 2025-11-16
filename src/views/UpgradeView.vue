<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useUserProfileStore } from '@/stores/userProfile'
import { useNotificationStore } from '@/stores/notification'
import request from '@/utils/request'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

const userProfileStore = useUserProfileStore()
const notificationStore = useNotificationStore()
const confirmRef = ref<InstanceType<typeof ConfirmDialog>>()

// 升级项配置
interface UpgradeItem {
  key: 'maxHp' | 'attack' | 'critRate'
  name: string
  icon: string
  description: string
  currentValue: number
  maxLevel: number
  getUpgradeCost: (level: number) => number
  getNextValue: (currentValue: number) => number
}

const upgradeItems = computed<UpgradeItem[]>(() => [
  {
    key: 'maxHp',
    name: '最大血量',
    icon: 'mdi:heart',
    description: '增加你的生命值上限',
    currentValue: userProfileStore.profile?.maxHp ?? 100,
    maxLevel: 50,
    getUpgradeCost: (level: number) => Math.floor(100 * Math.pow(1.15, level)),
    getNextValue: (current: number) => current + 10,
  },
  {
    key: 'attack',
    name: '基础攻击力',
    icon: 'mdi:sword',
    description: '提升你的基础伤害',
    currentValue: userProfileStore.profile?.attack ?? 10,
    maxLevel: 50,
    getUpgradeCost: (level: number) => Math.floor(80 * Math.pow(1.2, level)),
    getNextValue: (current: number) => current + 2,
  },
  {
    key: 'critRate',
    name: '暴击率',
    icon: 'mdi:flash',
    description: '提高造成暴击伤害的概率',
    currentValue: userProfileStore.profile?.critRate ?? 5,
    maxLevel: 50,
    getUpgradeCost: (level: number) => Math.floor(120 * Math.pow(1.25, level)),
    getNextValue: (current: number) => Math.min(current + 1, 100),
  },
])

// 当前升级等级（基于当前值推算）
const getCurrentLevel = (item: UpgradeItem): number => {
  if (item.key === 'maxHp') {
    return Math.floor((item.currentValue - 100) / 10)
  } else if (item.key === 'attack') {
    return Math.floor((item.currentValue - 10) / 2)
  } else if (item.key === 'critRate') {
    return item.currentValue - 5
  }
  return 0
}

// 是否达到最大等级
const isMaxLevel = (item: UpgradeItem): boolean => {
  return getCurrentLevel(item) >= item.maxLevel
}

// 是否有足够金币
const canAfford = (item: UpgradeItem): boolean => {
  const cost = item.getUpgradeCost(getCurrentLevel(item))
  return (userProfileStore.profile?.coins ?? 0) >= cost
}

// 升级处理
const handleUpgrade = async (item: UpgradeItem) => {
  const res = await request.post('/api/user/upgrade', {
    attribute: item.key,
  })

  if (res.data.success) {
    notificationStore.addNotification({
      title: '升级成功',
      description: `${item.name}已提升至 ${item.getNextValue(item.currentValue)}`,
      variant: 'default',
      duration: 2000,
    })
    await userProfileStore.getProfile(true)
  }
}

onMounted(async () => {
  await userProfileStore.getProfile()
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
    <div class="flex flex-col gap-4 w-full max-w-md overflow-y-auto grow shrink min-h-0 pb-28">
      <Card
        v-for="item in upgradeItems"
        :key="item.key"
        class="rounded-lg py-4 gap-4"
        :class="{ 'opacity-60': isMaxLevel(item) }"
      >
        <CardHeader>
          <div class="flex items-center justify-between">
            <CardTitle class="flex items-center gap-2 text-md">
              <Icon :icon="item.icon" class="size-5" />
              {{ item.name }}
            </CardTitle>
            <div class="text-lg font-bold">{{ item.currentValue }}</div>
            <div
              v-if="isMaxLevel(item)"
              class="text-xs bg-primary/10 text-primary px-2 py-1 rounded"
            >
              已满级
            </div>
          </div>
        </CardHeader>
        <CardContent class="space-y-3">
          <div class="text-xs text-muted-foreground">
            {{ item.description }}
          </div>

          <!-- 进度 -->
          <div class="space-y-1">
            <Progress
              :model-value="(getCurrentLevel(item) / item.maxLevel) * 100"
              :label="`等级 ${getCurrentLevel(item)} / ${item.maxLevel}`"
              show-label
              class="h-3"
            />
          </div>

          <!-- 升级信息和按钮 -->
          <div v-if="!isMaxLevel(item)" class="flex items-center justify-between pt-2">
            <div class="text-sm">
              <div class="text-muted-foreground">下一级</div>
              <div class="font-semibold text-lg">{{ item.getNextValue(item.currentValue) }}</div>
            </div>
            <Button
              @click="handleUpgrade(item)"
              :disabled="!canAfford(item)"
              class="flex items-center gap-1"
            >
              <Icon icon="mdi:coin" class="size-4" />
              {{ item.getUpgradeCost(getCurrentLevel(item)) }}
            </Button>
          </div>
          <div v-else class="text-center text-sm text-muted-foreground py-2">
            该属性已达到最大等级
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
  <ConfirmDialog ref="confirmRef" />
</template>
