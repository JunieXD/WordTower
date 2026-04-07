<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { Icon } from '@iconify/vue'

import { Input } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useDailyChallengeStore } from '@/stores/dailyChallenge'
import { useNotificationStore } from '@/stores/notification'
import { useSocialStore } from '@/stores/social'
import SocialFriendsSubview from '@/views/social/SocialFriendsSubview.vue'
import SocialLeaderboardSubview from '@/views/social/SocialLeaderboardSubview.vue'

const router = useRouter()
const route = useRoute()
const notificationStore = useNotificationStore()
const socialStore = useSocialStore()
const dailyChallengeStore = useDailyChallengeStore()

const {
  friends,
  incomingRequests,
  searchResults,
  isLoadingFriends,
  isLoadingRequests,
  isSearchingUsers,
} = storeToRefs(socialStore)

const {
  leaderboard: dailyLeaderboard,
  leaderboardDayKey,
  currentUserRank,
  currentUserEntry,
  isLoadingLeaderboard,
} = storeToRefs(dailyChallengeStore)

const activeTab = ref(route.query.tab === 'leaderboard' ? 'leaderboard' : 'friends')
const searchQuery = ref('')
let searchTimer: ReturnType<typeof setTimeout> | null = null

const filteredFriends = computed(() => {
  const query = searchQuery.value.trim().toLocaleLowerCase()
  if (!query) return friends.value
  return friends.value.filter((item) => {
    const nickname = item.friend.nickname?.toLocaleLowerCase() ?? ''
    const username = item.friend.username.toLocaleLowerCase()
    return nickname.includes(query) || username.includes(query)
  })
})

async function refreshSearchResults() {
  if (searchQuery.value.trim()) {
    await socialStore.searchUsers(searchQuery.value)
  } else {
    searchResults.value = []
  }
}

async function refreshDailyLeaderboard() {
  await dailyChallengeStore.fetchLeaderboard()
}

async function handleSendFriendRequest(userId: number) {
  const result = await socialStore.sendFriendRequest(userId)
  notificationStore.addNotification({
    title: result.success ? '好友申请' : '发送失败',
    description: result.message,
    variant: result.success ? 'default' : 'destructive',
    duration: 3000,
  })
  await refreshSearchResults()
}

async function handleAcceptRequest(requestId: number) {
  const result = await socialStore.acceptRequest(requestId)
  notificationStore.addNotification({
    title: result.success ? '好友申请' : '处理失败',
    description: result.message,
    variant: result.success ? 'default' : 'destructive',
    duration: 3000,
  })
  await refreshSearchResults()
}

async function handleRejectRequest(requestId: number) {
  const result = await socialStore.rejectRequest(requestId)
  notificationStore.addNotification({
    title: result.success ? '好友申请' : '处理失败',
    description: result.message,
    variant: result.success ? 'default' : 'destructive',
    duration: 3000,
  })
  await refreshSearchResults()
}

function openChat(friendId: number) {
  router.push({ name: 'social-chat', params: { friendId } })
}

function onVisibilityChange() {
  if (document.visibilityState !== 'visible') return
  void socialStore.refreshSocialOverview()
  void refreshSearchResults()
  if (activeTab.value === 'leaderboard') {
    void refreshDailyLeaderboard()
  }
}

watch(
  searchQuery,
  (value) => {
    if (searchTimer) clearTimeout(searchTimer)
    searchTimer = setTimeout(() => {
      void socialStore.searchUsers(value)
    }, 300)
  },
  { flush: 'post' },
)

watch(activeTab, (value) => {
  if (route.query.tab !== value) {
    void router.replace({
      name: 'social',
      query: value === 'leaderboard' ? { ...route.query, tab: 'leaderboard' } : {},
    })
  }
  if (value === 'leaderboard') {
    void refreshDailyLeaderboard()
  }
})

watch(
  () => route.query.tab,
  (value) => {
    const nextTab = value === 'leaderboard' ? 'leaderboard' : 'friends'
    if (activeTab.value !== nextTab) {
      activeTab.value = nextTab
    }
  },
)

onMounted(() => {
  void socialStore.startSocialPolling()
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onUnmounted(() => {
  socialStore.stopSocialPolling()
  document.removeEventListener('visibilitychange', onVisibilityChange)
  if (searchTimer) clearTimeout(searchTimer)
})
</script>

<template>
  <div class="flex h-full flex-col overflow-hidden bg-linear-to-b from-slate-50 via-white to-sky-50">
    <div class="sticky top-0 z-10 border-b border-slate-200/80 bg-white/95 px-4 py-4 backdrop-blur">
      <div class="relative">
        <Icon
          icon="mdi:magnify"
          class="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-slate-400"
        />
        <Input
          v-model="searchQuery"
          placeholder="搜索好友、用户名或昵称"
          class="h-11 rounded-2xl border-slate-200 bg-slate-50 pl-10 pr-4 shadow-none"
        />
      </div>
      <div class="mt-3">
        <Tabs v-model="activeTab" class="w-full">
          <TabsList class="grid h-10 w-full grid-cols-2 rounded-2xl bg-slate-100">
            <TabsTrigger value="friends" class="rounded-xl">好友</TabsTrigger>
            <TabsTrigger value="leaderboard" class="rounded-xl">排行榜</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
    </div>

    <SocialFriendsSubview
      v-if="activeTab === 'friends'"
      :search-query="searchQuery"
      :filtered-friends="filteredFriends"
      :incoming-requests="incomingRequests"
      :search-results="searchResults"
      :is-loading-friends="isLoadingFriends"
      :is-loading-requests="isLoadingRequests"
      :is-searching-users="isSearchingUsers"
      @send-friend-request="handleSendFriendRequest"
      @accept-request="handleAcceptRequest"
      @reject-request="handleRejectRequest"
      @open-chat="openChat"
    />

    <SocialLeaderboardSubview
      v-else
      :daily-leaderboard="dailyLeaderboard"
      :leaderboard-day-key="leaderboardDayKey"
      :current-user-rank="currentUserRank"
      :current-user-entry="currentUserEntry"
      :is-loading-leaderboard="isLoadingLeaderboard"
      @refresh="refreshDailyLeaderboard"
    />
  </div>
</template>
