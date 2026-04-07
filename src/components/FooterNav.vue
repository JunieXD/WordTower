<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useSocialStore } from '@/stores/social'

const items = [
  { title: '主页', url: 'home', icon: 'mdi:home-variant-outline' },
  { title: '词库', url: 'library', icon: 'mdi:bookshelf' },
  { title: '升级', url: 'upgrade', icon: 'mdi:arrow-up-circle-outline' },
  { title: '社交', url: 'social', icon: 'mdi:person-supervisor' },
  { title: '我的', url: 'profile', icon: 'mdi:account' },
]

const socialStore = useSocialStore()
const { totalUnread } = storeToRefs(socialStore)
const socialUnreadText = computed(() => {
  if (totalUnread.value <= 0) return null
  return totalUnread.value > 99 ? '99+' : String(totalUnread.value)
})

onMounted(() => {
  void socialStore.fetchUnreadSummary()
})
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
          'relative flex flex-col items-center cursor-pointer',
          isExactActive ? 'text-blue-600' : 'text-gray-600',
        ]"
      >
        <span
          v-if="item.url === 'social' && socialUnreadText"
          class="absolute top-0 left-1/2 min-w-5 -translate-x-1 rounded-full bg-rose-500 px-1.5 text-[10px] font-semibold leading-5 text-white"
        >
          {{ socialUnreadText }}
        </span>
        <Icon :icon="item.icon" class="size-8" /> <span class="text-xs">{{ item.title }}</span>
      </button>
    </RouterLink>
  </nav>
</template>
