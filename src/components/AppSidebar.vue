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
    title: 'home',
    url: 'home',
    icon: 'mdi:home-variant-outline',
  },
  {
    title: 'library',
    url: 'library',
    icon: 'mdi:bookshelf',
  },
  {
    title: 'profile',
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
                <SidebarMenuButton asChild class="my-1 h-10" @click="navigate">
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
