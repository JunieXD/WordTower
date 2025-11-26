<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { computed, ref } from 'vue'
import { ChevronLeft } from 'lucide-vue-next'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useCombatStore } from '@/stores/combat'

const route = useRoute()
const router = useRouter()
const confirmRef = ref<InstanceType<typeof ConfirmDialog>>()
const combatStore = useCombatStore()

const handleBack = async () => {
  const ok = await confirmRef.value?.open({
    title: '退出战斗',
    description: '确认要退出战斗吗？进度会保存到当前层。',
    cancelText: '取消',
    actionText: '确定',
  })
  if (!ok) return
  router.push({ name: 'home' })
}

const headerConfig = computed(() => {
  const routeName = route.name as string

  switch (routeName) {
    case 'home':
      return {
        title: '主页',
      }

    case 'library':
      return {
        title: '词库',
      }

    case 'profile':
      return {
        title: '个人中心',
      }

    case 'leaderboard':
      return {
        title: '排行榜',
      }

    case 'upgrade':
      return {
        title: '升级',
      }

    case 'library-edit':
      return {
        title: '编辑词库',
      }

    case 'combat':
      return {
        title: '战斗',
        leftAction: 'back',
        middle: '第 ' + combatStore.combatInfo?.current_floor + ' 层',
      }

    default:
      return {
        title: 'WordTower',
      }
  }
})
</script>

<template>
  <header class="grid grid-cols-3 items-center px-8 py-4 border-b border-border bg-white">
    <div class="flex items-center gap-3">
      <button
        v-if="headerConfig.leftAction === 'back' && route.name !== 'home'"
        @click="handleBack"
        class="hover:bg-gray-100 rounded-md transition-colors"
        aria-label="返回"
      >
        <ChevronLeft :size="20" class="text-gray-700" />
      </button>
      <div class="text-md">{{ headerConfig.title }}</div>
    </div>
    <div v-if="headerConfig.middle" class="text-md text-center">{{ headerConfig.middle }}</div>
    <div></div>
    <ConfirmDialog ref="confirmRef" />
  </header>
</template>

<style scoped>
/* 顶部栏固定在顶部 */
header {
  position: sticky;
  top: 0;
  z-index: 10;
}
</style>
