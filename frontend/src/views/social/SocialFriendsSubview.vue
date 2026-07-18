<script setup lang="ts">
import { Icon } from '@iconify/vue'

import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { FriendConversation, FriendRequest, RelationStatus, SocialSearchResult, SocialUserSummary } from '@/stores/social'
import {
  displayName,
  formatMessagePreview,
  formatShortTime,
  getInitials,
  relationTextMap,
  statusClassMap,
  statusTextMap,
} from '@/views/social/socialHelpers'

defineProps<{
  searchQuery: string
  filteredFriends: FriendConversation[]
  incomingRequests: FriendRequest[]
  searchResults: SocialSearchResult[]
  isLoadingFriends: boolean
  isLoadingRequests: boolean
  isSearchingUsers: boolean
}>()

const emit = defineEmits<{
  sendFriendRequest: [userId: number]
  acceptRequest: [requestId: number]
  rejectRequest: [requestId: number]
  openChat: [friendId: number]
}>()

function handleSendFriendRequest(userId: number) {
  emit('sendFriendRequest', userId)
}

function handleAcceptRequest(requestId: number) {
  emit('acceptRequest', requestId)
}

function handleRejectRequest(requestId: number) {
  emit('rejectRequest', requestId)
}

function handleOpenChat(friendId: number) {
  emit('openChat', friendId)
}

function relationLabel(status: RelationStatus) {
  return relationTextMap[status]
}

function nameOf(user: SocialUserSummary) {
  return displayName(user)
}
</script>

<template>
  <div class="mt-0 flex flex-1 flex-col overflow-y-auto px-4 pb-6">
    <section
      v-if="incomingRequests.length || isLoadingRequests"
      class="mt-4 rounded-3xl border border-slate-200/80 bg-white/90 p-4 shadow-[0_10px_35px_rgba(15,23,42,0.06)]"
    >
      <div class="mb-3 flex items-center justify-between">
        <div>
          <div class="text-sm font-semibold text-slate-900">好友申请</div>
          <div class="text-xs text-slate-500">收到的申请会显示在这里</div>
        </div>
        <Badge variant="secondary">{{ incomingRequests.length }}</Badge>
      </div>

      <div v-if="isLoadingRequests" class="py-4 text-center text-sm text-slate-500">
        正在加载好友申请...
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="request in incomingRequests"
          :key="request.request_id"
          class="rounded-2xl border border-slate-200 bg-slate-50/90 p-3"
        >
          <div class="flex items-center gap-3">
            <Avatar class="size-11 ring-2 ring-white">
              <AvatarImage
                v-if="request.requester.avatar_url"
                :src="request.requester.avatar_url"
                :alt="nameOf(request.requester)"
              />
              <AvatarFallback class="bg-sky-100 text-sky-700">
                {{ getInitials(request.requester) }}
              </AvatarFallback>
            </Avatar>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="truncate font-medium text-slate-900">
                  {{ nameOf(request.requester) }}
                </span>
                <span
                  class="inline-flex size-2 shrink-0 rounded-full"
                  :class="statusClassMap[request.requester.social_status]"
                />
                <span class="text-xs text-slate-500">
                  {{ statusTextMap[request.requester.social_status] }}
                </span>
              </div>
              <div class="mt-1 text-xs text-slate-500">
                @{{ request.requester.username }} · {{ formatShortTime(request.created_at) }}
              </div>
            </div>
          </div>

          <div class="mt-3 flex gap-2">
            <Button class="flex-1 rounded-xl" @click="handleAcceptRequest(request.request_id)">
              同意
            </Button>
            <Button
              variant="outline"
              class="flex-1 rounded-xl"
              @click="handleRejectRequest(request.request_id)"
            >
              拒绝
            </Button>
          </div>
        </div>
      </div>
    </section>

    <section
      v-if="searchQuery.trim()"
      class="mt-4 rounded-3xl border border-slate-200/80 bg-white/90 p-4 shadow-[0_10px_35px_rgba(15,23,42,0.06)]"
    >
      <div class="mb-3 flex items-center justify-between">
        <div>
          <div class="text-sm font-semibold text-slate-900">发现用户</div>
          <div class="text-xs text-slate-500">可以搜索用户名或昵称来加好友</div>
        </div>
        <Icon
          v-if="isSearchingUsers"
          icon="mdi:loading"
          class="size-5 animate-spin text-slate-400"
        />
      </div>

      <div v-if="!searchResults.length && !isSearchingUsers" class="py-4 text-center text-sm text-slate-500">
        没有找到匹配的用户
      </div>

      <div class="space-y-3">
        <div
          v-for="result in searchResults"
          :key="result.user.id"
          class="rounded-2xl border border-slate-200 bg-slate-50/90 p-3"
        >
          <div class="flex items-center gap-3">
            <Avatar class="size-11 ring-2 ring-white">
              <AvatarImage
                v-if="result.user.avatar_url"
                :src="result.user.avatar_url"
                :alt="nameOf(result.user)"
              />
              <AvatarFallback class="bg-violet-100 text-violet-700">
                {{ getInitials(result.user) }}
              </AvatarFallback>
            </Avatar>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="truncate font-medium text-slate-900">
                  {{ nameOf(result.user) }}
                </span>
                <Badge variant="outline">{{ relationLabel(result.relation_status) }}</Badge>
              </div>
              <div class="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span>@{{ result.user.username }}</span>
                <span>Lv.{{ result.user.level }}</span>
                <span>{{ statusTextMap[result.user.social_status] }}</span>
              </div>
            </div>
          </div>

          <div class="mt-3 flex gap-2">
            <Button
              v-if="result.relation_status === 'none'"
              class="flex-1 rounded-xl"
              @click="handleSendFriendRequest(result.user.id)"
            >
              <Icon icon="mdi:account-plus-outline" class="size-4" />
              添加好友
            </Button>
            <Button
              v-else-if="result.relation_status === 'accepted'"
              variant="outline"
              class="flex-1 rounded-xl"
              @click="handleOpenChat(result.user.id)"
            >
              <Icon icon="mdi:message-text-outline" class="size-4" />
              发消息
            </Button>
            <Button
              v-else-if="result.relation_status === 'outgoing_pending'"
              variant="outline"
              class="flex-1 rounded-xl"
              disabled
            >
              已发送申请
            </Button>
            <template v-else-if="result.relation_status === 'incoming_pending'">
              <Button
                class="flex-1 rounded-xl"
                @click="result.request_id && handleAcceptRequest(result.request_id)"
              >
                同意
              </Button>
              <Button
                variant="outline"
                class="flex-1 rounded-xl"
                @click="result.request_id && handleRejectRequest(result.request_id)"
              >
                拒绝
              </Button>
            </template>
          </div>
        </div>
      </div>
    </section>

    <section
      class="mt-4 flex-1 rounded-2xl border border-slate-200/80 bg-white/90 p-4 shadow-[0_10px_35px_rgba(15,23,42,0.06)]"
    >
      <div class="mb-3 flex items-center justify-between">
        <div>
          <div class="text-sm font-semibold text-slate-900">好友聊天</div>
          <div class="text-xs text-slate-500">最近的会话和在线状态</div>
        </div>
        <Badge variant="secondary">{{ filteredFriends.length }}</Badge>
      </div>

      <div v-if="isLoadingFriends" class="py-10 text-center text-sm text-slate-500">
        正在同步好友列表...
      </div>

      <div
        v-else-if="!filteredFriends.length"
        class="flex h-full min-h-64 flex-col items-center justify-center text-center text-slate-500"
      >
        <Icon icon="mdi:chat-processing-outline" class="mb-3 size-12 text-slate-300" />
        <div class="text-sm font-medium text-slate-600">还没有匹配的好友会话</div>
        <div class="mt-1 text-xs">
          {{
            searchQuery.trim()
              ? '试试搜索其他用户昵称或用户名'
              : '从上方搜索栏添加好友，开始聊天'
          }}
        </div>
      </div>

      <div v-else class="space-y-3">
        <button
          v-for="item in filteredFriends"
          :key="item.friend.id"
          class="flex w-full items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50/90 p-3 text-left transition hover:-translate-y-0.5 hover:border-sky-200 hover:bg-white hover:shadow-[0_10px_25px_rgba(59,130,246,0.08)]"
          @click="handleOpenChat(item.friend.id)"
        >
          <div class="relative">
            <Avatar class="size-12 ring-2 ring-white">
              <AvatarImage
                v-if="item.friend.avatar_url"
                :src="item.friend.avatar_url"
                :alt="nameOf(item.friend)"
              />
              <AvatarFallback class="bg-slate-200 text-slate-700">
                {{ getInitials(item.friend) }}
              </AvatarFallback>
            </Avatar>
            <span
              class="absolute bottom-0 right-0 size-3 rounded-full border-2 border-white"
              :class="statusClassMap[item.friend.social_status]"
            />
          </div>

          <div class="min-w-0 flex-1">
            <div class="flex items-center justify-between gap-3">
              <div class="truncate font-medium text-slate-900">
                {{ nameOf(item.friend) }}
              </div>
              <div class="shrink-0 text-xs text-slate-400">
                {{ formatShortTime(item.last_message?.created_at || item.friend.last_online_at) }}
              </div>
            </div>

            <div class="mt-1 flex items-center gap-2 text-xs text-slate-500">
              <span>@{{ item.friend.username }}</span>
              <span>Lv.{{ item.friend.level }}</span>
              <span>{{ statusTextMap[item.friend.social_status] }}</span>
            </div>

            <div class="mt-2 flex items-center justify-between gap-3">
              <div class="truncate text-sm text-slate-600">
                {{ formatMessagePreview(item.last_message?.content) }}
              </div>
              <span
                v-if="item.unread_count > 0"
                class="inline-flex min-w-6 items-center justify-center rounded-full bg-rose-500 px-2 text-xs font-semibold leading-6 text-white"
              >
                {{ item.unread_count > 99 ? '99+' : item.unread_count }}
              </span>
            </div>
          </div>
        </button>
      </div>
    </section>
  </div>
</template>
