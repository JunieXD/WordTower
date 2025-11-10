<script setup lang="ts">
import request from '@/utils/request'
import { onMounted } from 'vue'
import {
  Item,
  ItemContent,
  ItemDescription,
  ItemTitle,
  ItemMedia,
  ItemGroup,
  ItemSeparator,
  ItemActions,
} from '@/components/ui/item'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Progress } from '@/components/ui/progress'
import { Button } from '@/components/ui/button'
import { ChevronRight } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import { useNotificationStore } from '@/stores/notification'
import { useUserProfileStore } from '@/stores/userProfile'

const authStore = useAuthStore()
const router = useRouter()
const notificationStore = useNotificationStore()
const userProfileStore = useUserProfileStore()

const logout = async () => {
  try {
    const res = await request.post('/api/auth/logout')
    if (res.data.code === 0) {
      authStore.clearToken()
      userProfileStore.clearProfile()
      notificationStore.addNotification({
        title: '退出登录',
        description: '您已成功退出登录。',
        variant: 'default',
        duration: 2000,
      })
    }
  } catch (error) {
    console.error('退出登录失败:', error)
  } finally {
    router.push({ name: 'login' })
  }
}

const items = [{ name: '退出登录', icon: 'mdi:logout', func: logout }]

onMounted(async () => {
  // 从 store 获取用户资料（会先显示缓存，然后从后端更新）
  await userProfileStore.getProfile()
})
</script>

<template>
  <div class="flex flex-col gap-6 m-4 h-screen rounded-lg items-center">
    <Item variant="muted" class="m-2 mt-4 w-full max-w-md">
      <ItemMedia class="self-center!">
        <Avatar class="size-12">
          <AvatarImage :src="userProfileStore.profile?.avatarUrl ?? ''" />
          <AvatarFallback><Icon icon="mdi:account-circle" class="size-12" /></AvatarFallback>
        </Avatar>
      </ItemMedia>
      <ItemContent>
        <ItemTitle>
          {{ userProfileStore.profile?.nickname ?? userProfileStore.profile?.username ?? '用户名' }}
        </ItemTitle>
        <div class="flex flex-row gap-10">
          <ItemDescription> 等级：{{ userProfileStore.profile?.exp ?? 0 }} </ItemDescription>
          <ItemDescription> 金币：{{ userProfileStore.profile?.coins ?? 0 }} </ItemDescription>
        </div>
        <Progress
          :model-value="userProfileStore.profile?.exp ?? 0"
          :label="`${userProfileStore.profile?.exp ?? 0} / 100`"
          show-label
        />
      </ItemContent>
      <ItemActions>
        <Button variant="ghost" size="icon" class="rounded-full">
          <ChevronRight />
        </Button>
      </ItemActions>
    </Item>
    <ItemGroup
      class="flex flex-col w-full max-w-md border border-border rounded-lg overflow-y-auto grow shrink min-h-0 mb-32"
    >
      <template v-for="item in items" :key="item.name">
        <Item
          class="p-2 pl-4 cursor-pointer hover:bg-accent/50 active:bg-accent transition-all select-none"
          @click="item.func?.()"
        >
          <ItemMedia>
            <Icon :icon="item.icon" class="size-4" />
          </ItemMedia>
          <ItemContent>
            <ItemTitle>{{ item.name }}</ItemTitle>
          </ItemContent>
          <ItemActions>
            <Button variant="ghost" size="icon" class="rounded-full">
              <ChevronRight v-if="item.name !== '退出登录'" />
            </Button>
          </ItemActions>
        </Item>
        <ItemSeparator />
      </template>
    </ItemGroup>
  </div>
</template>
