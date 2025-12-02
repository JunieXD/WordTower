<template>
  <div class="flex flex-col h-full p-6 items-center justify-center gap-8">
    <!-- 结果标题 -->
    <div class="text-center">
      <div
        class="text-5xl font-bold mb-2 text-transparent bg-clip-text bg-linear-to-br from-blue-500 via-purple-500 to-pink-500"
      >
        第 {{ checkoutInfo?.current_floor ?? 0 }} 层
      </div>
      <div class="text-lg text-gray-500">本次闯塔结算</div>
    </div>

    <!-- 结算卡片 -->
    <Card class="w-full max-w-sm p-6">
      <div class="space-y-4">
        <!-- 经验值 -->
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <Icon icon="mdi:star-four-points" class="text-yellow-500 size-6" />
            <span class="text-md">获得经验</span>
          </div>
          <span class="text-xl font-bold text-yellow-500">
            +{{ checkoutInfo?.exp_gained ?? 0 }}
          </span>
        </div>

        <!-- 金币 -->
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <Icon icon="mdi:currency-usd" class="text-amber-500 size-6" />
            <span class="text-md">获得金币</span>
          </div>
          <span class="text-xl font-bold text-amber-500">
            +{{ checkoutInfo?.coins_gained ?? 0 }}
          </span>
        </div>
      </div>
    </Card>

    <!-- 返回按钮 -->
    <Button class="w-full max-w-sm" @click="handleBack">返回主页</Button>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { onBeforeUnmount } from 'vue'
import { storeToRefs } from 'pinia'
import { Icon } from '@iconify/vue'
import { useCombatStore } from '@/stores/combat'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

const router = useRouter()
const combatStore = useCombatStore()
const { checkoutInfo } = storeToRefs(combatStore)

const handleBack = () => {
  router.push({ name: 'home' })
}

onBeforeUnmount(() => {
  combatStore.clearCheckout()
})
</script>
