<script setup lang="ts">
import request from '@/utils/request'
import { onMounted, ref } from 'vue'
import {
  Item,
  ItemContent,
  ItemDescription,
  ItemTitle,
  ItemMedia,
  ItemGroup,
  ItemSeparator,
} from '@/components/ui/item'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Progress } from '@/components/ui/progress'
import { Button } from '@/components/ui/button'
import { ChevronRight } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import { useNotificationStore } from '@/stores/notification'

const authStore = useAuthStore()
const router = useRouter()
const notificationStore = useNotificationStore()

const logout = async () => {
  try {
    const res = await request.post('/api/auth/logout')
    if (res.data.code === 0) {
      authStore.clearToken()
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

interface UserProfile {
  id: number
  nickname: string | null
  username: string
  email: string | null
  avatarUrl: string | null
  exp: number
  coins: number
  createdAt: string
  lastLogin: string
  status: string
  maxHp: number
  attack: number
  critRate: number
  role: string
}

const profile = ref<UserProfile | null>(null)
const loading = ref(false)

const getProfile = async () => {
  loading.value = true
  try {
    const res = await request.get('/api/auth/profile')
    if (res.data.code === 0) {
      profile.value = res.data.data
    }
  } catch (error) {
    console.error('获取用户信息失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  getProfile()
})
</script>

<template>
  <div class="flex flex-col gap-6 m-4 h-screen rounded-lg items-center">
    <Item variant="muted" class="m-2 mt-4 w-full max-w-md">
      <ItemMedia class="self-center!">
        <Avatar class="size-12">
          <AvatarImage :src="profile?.avatarUrl ?? ''" />
          <AvatarFallback><Icon icon="mdi:account-circle" class="size-12" /></AvatarFallback>
        </Avatar>
      </ItemMedia>
      <ItemContent>
        <ItemTitle>
          {{ profile?.nickname ?? profile?.username ?? '用户名' }}
        </ItemTitle>
        <div class="flex flex-row gap-10">
          <ItemDescription> 等级：{{ profile?.exp ?? 0 }} </ItemDescription>
          <ItemDescription> 金币：{{ profile?.coins ?? 0 }} </ItemDescription>
        </div>
        <Progress
          :model-value="profile?.exp ?? 0"
          :label="`${profile?.exp ?? 0} / 100`"
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
