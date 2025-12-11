<script setup lang="ts">
import { Icon } from '@iconify/vue'
const items = [
  { title: '主页', url: 'home', icon: 'mdi:home-variant-outline' },
  { title: '词库', url: 'library', icon: 'mdi:bookshelf' },
  { title: '升级', url: 'upgrade', icon: 'mdi:arrow-up-circle-outline' },
  { title: '排行榜', url: 'leaderboard', icon: 'mdi:chart-box-outline' },
  { title: '我的', url: 'profile', icon: 'mdi:account' },
]
</script>
<template>
  <nav
    class="fixed inset-x-0 bottom-0 z-10 flex h-16 items-center justify-around border-t border-gray-200 bg-white pb-[env(safe-area-inset-bottom)] text-gray-600"
  >
    <RouterLink
      v-for="item in items"
      :key="item.url"
      :to="'/' + item.url"
      replace
      custom
      v-slot="{ navigate, isExactActive }"
    >
      <button
        @click="navigate"
        :class="[
          'flex flex-col items-center cursor-pointer',
          isExactActive ? 'text-blue-600' : 'text-gray-600',
        ]"
      >
        <Icon :icon="item.icon" class="size-8" /> <span class="text-xs">{{ item.title }}</span>
      </button>
    </RouterLink>
  </nav>
</template>
