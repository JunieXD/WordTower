<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'
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
  <Sidebar>
    <SidebarContent>
      <SidebarGroup>
        <SidebarGroupContent>
          <SidebarMenu>
            <SidebarMenuItem v-for="item in items" :key="item.title">
              <RouterLink :to="'/' + item.url" replace custom v-slot="{ navigate }">
                <SidebarMenuButton
                  asChild
                  class="my-1 h-10 cursor-pointer select-none hover:bg-accent/50 active:bg-accent transition-all"
                  @click="navigate"
                >
                  <div class="flex items-center gap-2">
                    <Icon :icon="item.icon" />
                    <span>{{ item.title }}</span>
                    <span
                      v-if="item.url === 'social' && socialUnreadText"
                      class="rounded-full bg-rose-500 px-2 py-0.5 text-[11px] font-semibold text-white"
                    >
                      {{ socialUnreadText }}
                    </span>
                  </div>
                </SidebarMenuButton>
              </RouterLink>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>
    </SidebarContent>
  </Sidebar>
</template>
