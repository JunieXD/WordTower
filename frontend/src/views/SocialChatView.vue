<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { storeToRefs } from 'pinia'
import { useNotificationStore } from '@/stores/notification'
import { useSocialStore, type ChatMessage, type SocialStatus, type SocialUserSummary } from '@/stores/social'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import { formatChatMessageTime, parseSocialDate } from '@/views/social/socialHelpers'

const route = useRoute()
const router = useRouter()
const notificationStore = useNotificationStore()
const socialStore = useSocialStore()
const { activeChatFriend, chatMessages, hasMoreMessages, isLoadingChat, isLoadingOlderMessages, isSendingMessage } =
  storeToRefs(socialStore)

const messageDraft = ref('')
const detailsOpen = ref(false)
const messagesRef = ref<HTMLElement | null>(null)

const friendId = computed(() => Number(route.params.friendId))

const displayName = (user: SocialUserSummary | null) => (user ? user.nickname || user.username : '聊天')

const statusClassMap: Record<SocialStatus, string> = {
  combat: 'bg-amber-500',
  online: 'bg-emerald-500',
  offline: 'bg-slate-300',
}

const statusTextMap: Record<SocialStatus, string> = {
  combat: '闯塔中',
  online: '在线',
  offline: '离线',
}

function getInitials(user: SocialUserSummary | null) {
  return displayName(user).slice(0, 1).toUpperCase()
}

function formatBubbleTime(value: string) {
  return formatChatMessageTime(value)
}

function formatLastOnline(value: string | null) {
  if (!value) return '暂时没有记录'
  const date = parseSocialDate(value)
  if (!date) return '暂时没有记录'
  const diff = Date.now() - date.getTime()
  if (diff < 60_000) return '刚刚在线'
  if (diff < 3_600_000) return `${Math.max(1, Math.floor(diff / 60_000))} 分钟前在线`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前在线`
  return `最后在线于 ${date.toLocaleString()}`
}

async function scrollToBottom(behavior: ScrollBehavior = 'auto') {
  await nextTick()
  messagesRef.value?.scrollTo({
    top: messagesRef.value.scrollHeight,
    behavior,
  })
}

async function handleSendMessage() {
  if (!friendId.value || Number.isNaN(friendId.value)) return
  const result = await socialStore.sendMessage(friendId.value, messageDraft.value)
  if (!result.success) {
    notificationStore.addNotification({
      title: '发送失败',
      description: result.message,
      variant: 'destructive',
      duration: 3000,
    })
    return
  }

  messageDraft.value = ''
  await scrollToBottom('smooth')
}

function handleTextareaKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    void handleSendMessage()
  }
}

async function handleLoadOlderMessages() {
  await socialStore.fetchOlderMessages()
}

function onVisibilityChange() {
  if (document.visibilityState === 'visible') {
    void socialStore.refreshActiveChat().then(() => socialStore.markActiveChatRead())
  }
}

watch(
  () => chatMessages.value.length,
  async (nextLength, previousLength) => {
    if (nextLength >= previousLength) {
      await scrollToBottom(previousLength > 0 ? 'smooth' : 'auto')
    }
  },
)

onMounted(async () => {
  if (!friendId.value || Number.isNaN(friendId.value)) {
    router.replace({ name: 'social' })
    return
  }

  await socialStore.startChatPolling(friendId.value)
  await scrollToBottom()
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onUnmounted(() => {
  socialStore.clearChatState()
  document.removeEventListener('visibilitychange', onVisibilityChange)
})
</script>

<template>
  <div class="flex h-full flex-col overflow-hidden bg-[linear-gradient(180deg,#eff6ff_0%,#ffffff_18%,#ffffff_100%)]">
    <div class="border-b border-slate-200/80 bg-white/90 px-4 py-3 backdrop-blur">
      <button
        class="flex w-full items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50/90 px-3 py-3 text-left transition hover:border-sky-200 hover:bg-white"
        @click="detailsOpen = true"
      >
        <div class="relative">
          <Avatar class="size-11 ring-2 ring-white">
            <AvatarImage
              v-if="activeChatFriend?.avatar_url"
              :src="activeChatFriend.avatar_url"
              :alt="displayName(activeChatFriend)"
            />
            <AvatarFallback class="bg-sky-100 text-sky-700">
              {{ getInitials(activeChatFriend) }}
            </AvatarFallback>
          </Avatar>
          <span
            v-if="activeChatFriend"
            class="absolute right-0 bottom-0 size-3 rounded-full border-2 border-white"
            :class="statusClassMap[activeChatFriend.social_status]"
          />
        </div>

        <div class="min-w-0 flex-1">
          <div class="truncate font-medium text-slate-900">
            {{ displayName(activeChatFriend) }}
          </div>
          <div class="mt-1 flex items-center gap-2 text-xs text-slate-500">
            <span v-if="activeChatFriend">@{{ activeChatFriend.username }}</span>
            <span v-if="activeChatFriend">Lv.{{ activeChatFriend.level }}</span>
            <span v-if="activeChatFriend">{{ statusTextMap[activeChatFriend.social_status] }}</span>
          </div>
        </div>

        <Icon icon="mdi:chevron-right" class="size-5 text-slate-400" />
      </button>
    </div>

    <div ref="messagesRef" class="flex-1 overflow-y-auto px-4 py-4">
      <div class="mx-auto flex w-full flex-col gap-3">
        <Button
          v-if="hasMoreMessages"
          variant="outline"
          class="mx-auto rounded-full"
          :loading="isLoadingOlderMessages"
          @click="handleLoadOlderMessages"
        >
          加载更早消息
        </Button>

        <div v-if="isLoadingChat && !chatMessages.length" class="py-12 text-center text-sm text-slate-500">
          正在加载聊天记录...
        </div>

        <div
          v-for="message in chatMessages"
          :key="message.id"
          class="flex"
          :class="message.is_mine ? 'justify-end' : 'justify-start'"
        >
          <div
            class="max-w-[78%] rounded-3xl px-4 py-3 shadow-sm"
            :class="
              message.is_mine
                ? 'rounded-br-md bg-sky-500 text-white shadow-sky-100'
                : 'rounded-bl-md border border-slate-200 bg-white text-slate-800'
            "
          >
            <div class="whitespace-pre-wrap wrap-break-word text-sm leading-6">
              {{ message.content }}
            </div>
            <div
              class="mt-2 text-[11px]"
              :class="message.is_mine ? 'text-sky-100' : 'text-slate-400'"
            >
              {{ formatBubbleTime(message.created_at) }}
              <span v-if="'optimistic' in message && message.optimistic"> · 发送中</span>
            </div>
          </div>
        </div>

        <div v-if="!isLoadingChat && !chatMessages.length" class="py-12 text-center text-sm text-slate-500">
          还没有聊天记录，发一条消息开始吧。
        </div>
      </div>
    </div>

    <div class="border-t border-slate-200/80 bg-white/95 px-4 pt-3 pb-[calc(env(safe-area-inset-bottom)+12px)] backdrop-blur">
      <div class="mx-auto flex w-full max-w-3xl items-end gap-3">
        <Textarea
          v-model="messageDraft"
          placeholder="输入消息，回车发送，Shift + 回车换行"
          class="min-h-12 max-h-32 rounded-3xl border-slate-200 bg-slate-50 px-4 py-3"
          @keydown="handleTextareaKeydown"
        />
        <Button
          class="h-12 shrink-0 rounded-2xl px-4"
          :loading="isSendingMessage"
          :disabled="!messageDraft.trim()"
          @click="handleSendMessage"
        >
          <Icon icon="mdi:send-outline" class="size-5" />
        </Button>
      </div>
    </div>

    <Sheet v-model:open="detailsOpen">
      <SheetContent side="bottom" class="rounded-t-2xl px-4 pb-8">
        <SheetHeader class="pt-6 text-left border-b border-gray-300">
          <SheetTitle>好友资料</SheetTitle>
          <SheetDescription>查看当前好友的基础状态与闯塔进度</SheetDescription>
        </SheetHeader>

        <div v-if="activeChatFriend" class="mt-2 space-y-4">
          <div class="flex items-center gap-4">
            <Avatar class="size-16 ring-4 ring-sky-100">
              <AvatarImage
                v-if="activeChatFriend.avatar_url"
                :src="activeChatFriend.avatar_url"
                :alt="displayName(activeChatFriend)"
              />
              <AvatarFallback class="bg-sky-100 text-lg text-sky-700">
                {{ getInitials(activeChatFriend) }}
              </AvatarFallback>
            </Avatar>
            <div class="min-w-0">
              <div class="truncate text-lg font-semibold text-slate-900">
                {{ displayName(activeChatFriend) }}
              </div>
              <div class="mt-1 text-sm text-slate-500">@{{ activeChatFriend.username }}</div>
              <div class="mt-2 flex items-center gap-2">
                <Badge>{{ statusTextMap[activeChatFriend.social_status] }}</Badge>
                <Badge variant="secondary">Lv.{{ activeChatFriend.level }}</Badge>
              </div>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div class="text-xs text-slate-500">最高层数</div>
              <div class="mt-2 text-2xl font-semibold text-slate-900">
                {{ activeChatFriend.max_floor }}
              </div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div class="text-xs text-slate-500">当前等级</div>
              <div class="mt-2 text-2xl font-semibold text-slate-900">
                {{ activeChatFriend.level }}
              </div>
            </div>
          </div>

          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            {{ formatLastOnline(activeChatFriend.last_online_at) }}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  </div>
</template>
