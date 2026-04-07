<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronLeft } from 'lucide-vue-next'
import { type RouteLocationRaw, useRoute, useRouter } from 'vue-router'

import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useCombatStore } from '@/stores/combat'
import { useDailyChallengeStore } from '@/stores/dailyChallenge'

const route = useRoute()
const router = useRouter()
const confirmRef = ref<InstanceType<typeof ConfirmDialog>>()
const combatStore = useCombatStore()
const dailyChallengeStore = useDailyChallengeStore()

const currentFloorText = computed(() => {
  const floor =
    route.name === 'daily-challenge'
      ? dailyChallengeStore.activeState?.current_floor
      : combatStore.combatInfo?.current_floor

  return floor !== undefined ? `第 ${floor} 层` : ''
})

const handleCombatBack = async () => {
  const isDailyChallenge = route.name === 'daily-challenge'
  const ok = await confirmRef.value?.open({
    title: isDailyChallenge ? '离开每日挑战' : '退出战斗',
    description: isDailyChallenge
      ? '确认要暂时离开每日挑战吗？当前进度会保存在这道题的位置。'
      : '确认要退出战斗吗？进度会保留在当前层。',
    cancelText: '取消',
    actionText: '确定',
  })
  if (!ok) return
  router.push({ name: 'home' })
}

const handleBack = async () => {
  const backTo = route.meta.backTo as RouteLocationRaw | undefined
  router.push(backTo || { name: 'home' })
}

const headerConfig = computed(() => {
  const routeName = route.name as string

  switch (routeName) {
    case 'home':
      return { title: '主页' }
    case 'library':
      return { title: '词库' }
    case 'profile':
      return { title: '个人中心' }
    case 'history':
      return { title: '历史记录', leftAction: 'back' }
    case 'history-detail':
      return { title: '记录详情', leftAction: 'back' }
    case 'social':
      return { title: '社交' }
    case 'social-chat':
      return { title: '聊天', leftAction: 'back' }
    case 'upgrade':
      return { title: '升级' }
    case 'library-edit':
      return { title: '编辑词库' }
    case 'combat':
      return { title: '战斗', leftAction: 'back', middle: currentFloorText.value }
    case 'daily-challenge':
      return { title: '每日挑战', leftAction: 'back', middle: currentFloorText.value }
    case 'checkout':
      return { title: '结算', leftAction: 'back' }
    default:
      return { title: 'WordTower' }
  }
})
</script>

<template>
  <header
    class="grid grid-cols-3 items-center border-b border-border bg-white py-4"
    :class="route.name === 'combat' || route.name === 'daily-challenge' ? 'px-2' : 'px-8'"
  >
    <div class="flex items-center gap-2">
      <button
        v-if="headerConfig.leftAction === 'back'"
        class="rounded-md transition-colors hover:bg-gray-100"
        aria-label="返回"
        @click="
          route.name === 'combat' || route.name === 'daily-challenge'
            ? handleCombatBack()
            : handleBack()
        "
      >
        <ChevronLeft :size="20" class="text-gray-700" />
      </button>
      <div class="text-md">{{ headerConfig.title }}</div>
    </div>
    <div v-if="headerConfig.middle" class="text-center text-md">{{ headerConfig.middle }}</div>
    <div></div>
    <ConfirmDialog ref="confirmRef" />
  </header>
</template>

<style scoped>
header {
  position: sticky;
  top: 0;
  z-index: 10;
}
</style>
