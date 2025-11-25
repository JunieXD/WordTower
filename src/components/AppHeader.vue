<script setup lang="ts">
import { useRoute } from 'vue-router'
import { computed } from 'vue'

const route = useRoute()

const headerConfig = computed(() => {
  const routeName = route.name as string

  switch (routeName) {
    case 'home':
      return {
        title: '主页',
        rightAction: null,
      }

    case 'library':
      return {
        title: '词库',
        rightAction: null,
      }

    case 'profile':
      return {
        title: '个人中心',
        rightAction: null,
      }

    case 'leaderboard':
      return {
        title: '排行榜',
        rightAction: null,
      }

    case 'upgrade':
      return {
        title: '升级',
        rightAction: null,
      }

    case 'library-edit':
      return {
        title: '编辑词库',
        rightAction: null,
      }

    case 'combat':
      return {
        title: '战斗',
        rightAction: null,
      }

    default:
      return {
        title: 'WordTower',
        rightAction: null,
      }
  }
})
</script>

<template>
  <header class="flex items-center justify-between px-8 py-4 border-b border-border bg-white">
    <div class="text-md">{{ headerConfig.title }}</div>
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
