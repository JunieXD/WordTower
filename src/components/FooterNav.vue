<script setup lang="ts">
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
    class="fixed bottom-0 left-0 right-0 bg-white border-t flex justify-around items-center h-16 text-gray-600 z-10"
  >
    <RouterLink
      v-for="item in items"
      :key="item.url"
      :to="'/' + item.url"
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
