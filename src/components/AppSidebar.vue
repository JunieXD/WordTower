<script setup lang="ts">
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'

// Menu items.
const items = [
  {
    title: '主页',
    url: 'home',
    icon: 'mdi:home-variant-outline',
  },
  {
    title: '词库',
    url: 'library',
    icon: 'mdi:bookshelf',
  },
  {
    title: '我的',
    url: 'profile',
    icon: 'mdi:account',
  },
]
</script>

<template>
  <Sidebar>
    <SidebarContent>
      <SidebarGroup>
        <SidebarGroupContent>
          <SidebarMenu>
            <SidebarMenuItem v-for="item in items" :key="item.title">
              <RouterLink :to="'/' + item.url" custom v-slot="{ navigate }">
                <SidebarMenuButton
                  asChild
                  class="my-1 h-10 cursor-pointer select-none hover:bg-accent/50 active:bg-accent transition-all"
                  @click="navigate"
                >
                  <div class="flex items-center gap-2">
                    <Icon :icon="item.icon" />
                    <span>{{ item.title }}</span>
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
