<script setup lang="ts">
import request from '@/utils/request'
import { computed, onMounted, ref } from 'vue'
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
import { Progress } from '@/components/ui/progress'
import { Button } from '@/components/ui/button'
import { ChevronRight } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { useNotificationStore } from '@/stores/notification'
import { useUserProfileStore } from '@/stores/userProfile'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

const confirmRef = ref<InstanceType<typeof ConfirmDialog>>()
const router = useRouter()
const notificationStore = useNotificationStore()
const userProfileStore = useUserProfileStore()

const level = computed(() => {
  const exp = userProfileStore.profile?.exp ?? 0
  return Math.floor(exp / 100)
})

const currentLevelExp = computed(() => {
  const exp = userProfileStore.profile?.exp ?? 0
  return exp % 100
})

const logout = async () => {
  try {
    const ok = await confirmRef.value?.open({
      title: '退出登录',
      description: '确定要退出登录吗？',
      cancelText: '取消',
      actionText: '确定',
    })
    if (!ok) return
    const res = await request.post('/api/auth/logout')
    if (res.data.success) {
      userProfileStore.clearProfile()
      notificationStore.addNotification({
        title: '退出登录',
        description: '您已成功退出登录。',
        variant: 'default',
        duration: 2000,
      })
    }
    router.push({ name: 'login' })
  } catch (error) {
    console.error('退出登录失败:', error)
  }
}

const goToHistory = () => {
  router.push({ name: 'history' })
}

const items = [
  { name: '历史记录', icon: 'mdi:history', func: goToHistory },
  { name: '退出登录', icon: 'mdi:logout', func: logout },
]

onMounted(async () => {
  // 从 store 获取用户资料（会先显示缓存，然后从后端更新）
  await userProfileStore.getProfile()
})
</script>

<template>
  <div class="flex flex-col gap-6 p-8 h-screen rounded-lg justify-center items-center">
    <Item variant="muted" class="m-2 mt-4 w-full max-w-md">
      <ItemMedia class="self-center!">
        <div
          class="w-12 h-12 rounded-full bg-linear-to-br from-blue-400 to-blue-500 flex items-center justify-center text-white font-semibold shadow shrink-0"
        >
          <img
            v-if="userProfileStore.profile?.avatar_url"
            :src="userProfileStore.profile.avatar_url"
            :alt="
              userProfileStore.profile?.nickname ?? userProfileStore.profile?.username ?? '用户名'
            "
            class="w-full h-full rounded-full object-cover"
          />
          <span v-else class="text-base">
            {{
              (
                userProfileStore.profile?.nickname ??
                userProfileStore.profile?.username ??
                '用户名'
              )?.charAt(0)
            }}
          </span>
        </div>
      </ItemMedia>
      <ItemContent>
        <ItemTitle class="font-bold">
          {{ userProfileStore.profile?.nickname ?? userProfileStore.profile?.username ?? '用户名' }}
        </ItemTitle>
        <div class="flex flex-row gap-10">
          <ItemDescription> 等级：{{ level }} </ItemDescription>
          <ItemDescription> 金币：{{ userProfileStore.profile?.coins ?? 0 }} </ItemDescription>
        </div>
        <Progress :model-value="currentLevelExp" :label="`${currentLevelExp} / 100`" show-label />
      </ItemContent>
      <ItemActions>
        <Button variant="ghost" size="icon" class="rounded-full">
          <ChevronRight />
        </Button>
      </ItemActions>
    </Item>
    <ItemGroup
      class="flex flex-col w-full max-w-md border border-border rounded-lg overflow-y-auto grow shrink min-h-0 mb-16"
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
    <ConfirmDialog ref="confirmRef" />
  </div>
</template>
