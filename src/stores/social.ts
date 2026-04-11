import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/utils/request'
import { useUserProfileStore } from '@/stores/userProfile'
import { getSocialTimestamp } from '@/views/social/socialHelpers'

export type SocialStatus = 'offline' | 'online' | 'combat'
export type RelationStatus = 'none' | 'accepted' | 'outgoing_pending' | 'incoming_pending'

export interface SocialUserSummary {
  id: number
  username: string
  nickname: string | null
  avatar_url: string | null
  exp: number
  level: number
  max_floor: number
  social_status: SocialStatus
  last_online_at: string | null
}

export interface FriendMessagePreview {
  id: number
  sender_id: number
  recipient_id: number
  content: string
  created_at: string
  read_at: string | null
}

export interface FriendConversation {
  relation_id: number
  friend: SocialUserSummary
  unread_count: number
  last_message: FriendMessagePreview | null
}

export interface FriendRequest {
  request_id: number
  created_at: string
  requester: SocialUserSummary
}

export interface SocialSearchResult {
  user: SocialUserSummary
  relation_status: RelationStatus
  request_id: number | null
}

export interface ChatMessage {
  id: number | string
  sender_id: number
  recipient_id: number
  content: string
  created_at: string
  read_at: string | null
  is_mine: boolean
  optimistic?: boolean
}

type SocialTimer = ReturnType<typeof setInterval> | null

const SOCIAL_POLL_MS = 15000
const CHAT_POLL_MS = 5000

function normalizeMessages(messages: ChatMessage[]): ChatMessage[] {
  const map = new Map<number | string, ChatMessage>()
  for (const message of messages) {
    map.set(message.id, message)
  }
  return [...map.values()].sort((a, b) => {
    const aTime = getSocialTimestamp(a.created_at) ?? 0
    const bTime = getSocialTimestamp(b.created_at) ?? 0
    return aTime - bTime
  })
}

function sortFriends(items: FriendConversation[]): FriendConversation[] {
  const statusPriority: Record<SocialStatus, number> = {
    combat: 0,
    online: 1,
    offline: 2,
  }

  return [...items].sort((a, b) => {
    const aTime = a.last_message ? getSocialTimestamp(a.last_message.created_at) : null
    const bTime = b.last_message ? getSocialTimestamp(b.last_message.created_at) : null

    if (aTime !== null && bTime !== null && aTime !== bTime) {
      return bTime - aTime
    }
    if (aTime !== null && bTime === null) return -1
    if (aTime === null && bTime !== null) return 1

    const statusDiff = statusPriority[a.friend.social_status] - statusPriority[b.friend.social_status]
    if (statusDiff !== 0) return statusDiff

    const aName = (a.friend.nickname || a.friend.username).toLocaleLowerCase()
    const bName = (b.friend.nickname || b.friend.username).toLocaleLowerCase()
    return aName.localeCompare(bName)
  })
}

export const useSocialStore = defineStore('social', () => {
  const friends = ref<FriendConversation[]>([])
  const incomingRequests = ref<FriendRequest[]>([])
  const searchResults = ref<SocialSearchResult[]>([])
  const totalUnread = ref(0)
  const activeChatFriend = ref<SocialUserSummary | null>(null)
  const chatMessages = ref<ChatMessage[]>([])
  const hasMoreMessages = ref(false)
  const activeChatFriendId = ref<number | null>(null)

  const isLoadingFriends = ref(false)
  const isLoadingRequests = ref(false)
  const isSearchingUsers = ref(false)
  const isLoadingChat = ref(false)
  const isLoadingOlderMessages = ref(false)
  const isSendingMessage = ref(false)

  const socialPollTimer = ref<SocialTimer>(null)
  const chatPollTimer = ref<SocialTimer>(null)
  const searchRequestToken = ref(0)

  async function fetchUnreadSummary() {
    try {
      const res = await request.get('/api/social/unread-summary')
      if (res.data.success) {
        totalUnread.value = Number(res.data.data?.total ?? 0)
      }
    } catch (error) {
      console.error('获取未读汇总失败:', error)
    }
    return totalUnread.value
  }

  async function fetchFriends() {
    isLoadingFriends.value = true
    try {
      const res = await request.get('/api/social/friends')
      if (res.data.success) {
        friends.value = sortFriends((res.data.data ?? []) as FriendConversation[])
      } else {
        friends.value = []
      }
    } catch (error) {
      console.error('获取好友列表失败:', error)
      friends.value = []
    } finally {
      isLoadingFriends.value = false
    }
    return friends.value
  }

  async function fetchIncomingRequests() {
    isLoadingRequests.value = true
    try {
      const res = await request.get('/api/social/requests')
      if (res.data.success) {
        incomingRequests.value = (res.data.data ?? []) as FriendRequest[]
      } else {
        incomingRequests.value = []
      }
    } catch (error) {
      console.error('获取好友申请失败:', error)
      incomingRequests.value = []
    } finally {
      isLoadingRequests.value = false
    }
    return incomingRequests.value
  }

  async function searchUsers(query: string) {
    const trimmedQuery = query.trim()
    const currentToken = ++searchRequestToken.value

    if (!trimmedQuery) {
      searchResults.value = []
      return searchResults.value
    }

    isSearchingUsers.value = true
    try {
      const res = await request.get('/api/social/search', {
        params: { q: trimmedQuery },
      })
      if (currentToken !== searchRequestToken.value) return searchResults.value
      searchResults.value = res.data.success ? ((res.data.data ?? []) as SocialSearchResult[]) : []
    } catch (error) {
      if (currentToken === searchRequestToken.value) {
        console.error('搜索社交用户失败:', error)
        searchResults.value = []
      }
    } finally {
      if (currentToken === searchRequestToken.value) {
        isSearchingUsers.value = false
      }
    }
    return searchResults.value
  }

  async function refreshSocialOverview() {
    await Promise.all([fetchFriends(), fetchIncomingRequests(), fetchUnreadSummary()])
  }

  function stopSocialPolling() {
    if (socialPollTimer.value) {
      clearInterval(socialPollTimer.value)
      socialPollTimer.value = null
    }
  }

  async function startSocialPolling() {
    stopSocialPolling()
    await refreshSocialOverview()
    socialPollTimer.value = setInterval(() => {
      if (document.visibilityState === 'visible') {
        void refreshSocialOverview()
      }
    }, SOCIAL_POLL_MS)
  }

  function mergeMessages(messages: ChatMessage[]) {
    chatMessages.value = normalizeMessages([...chatMessages.value, ...messages])
  }

  async function fetchChat(friendId: number) {
    isLoadingChat.value = true
    activeChatFriendId.value = friendId
    try {
      const res = await request.get(`/api/social/chats/${friendId}`)
      if (res.data.success) {
        const data = res.data.data as {
          friend: SocialUserSummary
          messages: ChatMessage[]
          has_more: boolean
        }
        activeChatFriend.value = data.friend
        chatMessages.value = normalizeMessages(data.messages ?? [])
        hasMoreMessages.value = Boolean(data.has_more)
      }
    } catch (error) {
      console.error('获取聊天初始化数据失败:', error)
      throw error
    } finally {
      isLoadingChat.value = false
    }
  }

  async function refreshActiveChat() {
    if (!activeChatFriendId.value) return
    try {
      const res = await request.get(`/api/social/chats/${activeChatFriendId.value}`)
      if (res.data.success) {
        const data = res.data.data as {
          friend: SocialUserSummary
          messages: ChatMessage[]
          has_more: boolean
        }
        activeChatFriend.value = data.friend
        hasMoreMessages.value = hasMoreMessages.value || Boolean(data.has_more)
        mergeMessages(data.messages ?? [])
      }
    } catch (error) {
      console.error('刷新聊天数据失败:', error)
    }
  }

  async function fetchOlderMessages() {
    if (!activeChatFriendId.value || !hasMoreMessages.value || !chatMessages.value.length) return
    isLoadingOlderMessages.value = true
    try {
      const before = chatMessages.value[0]?.created_at
      const res = await request.get(`/api/social/chats/${activeChatFriendId.value}/messages`, {
        params: { before, limit: 30 },
      })
      if (res.data.success) {
        const data = res.data.data as { messages: ChatMessage[]; has_more: boolean }
        chatMessages.value = normalizeMessages([...(data.messages ?? []), ...chatMessages.value])
        hasMoreMessages.value = Boolean(data.has_more)
      }
    } catch (error) {
      console.error('加载更早消息失败:', error)
    } finally {
      isLoadingOlderMessages.value = false
    }
  }

  async function markActiveChatRead() {
    if (!activeChatFriendId.value) return
    try {
      const friendId = activeChatFriendId.value
      await request.post(`/api/social/chats/${friendId}/read`)
      friends.value = friends.value.map((item) =>
        item.friend.id === friendId ? { ...item, unread_count: 0 } : item,
      )
      await fetchUnreadSummary()
    } catch (error) {
      console.error('标记消息已读失败:', error)
    }
  }

  function stopChatPolling() {
    if (chatPollTimer.value) {
      clearInterval(chatPollTimer.value)
      chatPollTimer.value = null
    }
  }

  async function startChatPolling(friendId: number) {
    stopChatPolling()
    await fetchChat(friendId)
    await markActiveChatRead()
    chatPollTimer.value = setInterval(() => {
      if (document.visibilityState === 'visible') {
        void refreshActiveChat().then(() => markActiveChatRead())
      }
    }, CHAT_POLL_MS)
  }

  function clearChatState() {
    activeChatFriend.value = null
    activeChatFriendId.value = null
    chatMessages.value = []
    hasMoreMessages.value = false
    stopChatPolling()
  }

  async function sendFriendRequest(userId: number) {
    const res = await request.post('/api/social/requests', { user_id: userId })
    if (res.data.success) {
      await Promise.all([fetchFriends(), fetchIncomingRequests(), fetchUnreadSummary()])
    }
    return { success: res.data.success, message: res.data.message as string }
  }

  async function acceptRequest(requestId: number) {
    const res = await request.post(`/api/social/requests/${requestId}/accept`)
    if (res.data.success) {
      await Promise.all([fetchFriends(), fetchIncomingRequests(), fetchUnreadSummary()])
    }
    return { success: res.data.success, message: res.data.message as string }
  }

  async function rejectRequest(requestId: number) {
    const res = await request.post(`/api/social/requests/${requestId}/reject`)
    if (res.data.success) {
      await fetchIncomingRequests()
    }
    return { success: res.data.success, message: res.data.message as string }
  }

  async function removeFriend(friendId: number) {
    const res = await request.delete(`/api/social/friends/${friendId}`)
    if (res.data.success) {
      await Promise.all([fetchFriends(), fetchUnreadSummary()])
    }
    return { success: res.data.success, message: res.data.message as string }
  }

  async function sendMessage(friendId: number, content: string) {
    const trimmedContent = content.trim()
    if (!trimmedContent || isSendingMessage.value) {
      return { success: false, message: '消息内容不能为空' }
    }

    const userProfileStore = useUserProfileStore()
    const optimisticId = `temp-${Date.now()}`
    const optimisticMessage: ChatMessage = {
      id: optimisticId,
      sender_id: userProfileStore.profile?.id ?? -1,
      recipient_id: friendId,
      content: trimmedContent,
      created_at: new Date().toISOString(),
      read_at: null,
      is_mine: true,
      optimistic: true,
    }
    mergeMessages([optimisticMessage])

    isSendingMessage.value = true
    try {
      const res = await request.post(`/api/social/chats/${friendId}/messages`, {
        content: trimmedContent,
      })
      if (!res.data.success) {
        chatMessages.value = chatMessages.value.filter((message) => message.id !== optimisticId)
        return { success: false, message: res.data.message as string }
      }

      const savedMessage = res.data.data as ChatMessage
      chatMessages.value = normalizeMessages(
        chatMessages.value.map((message) => (message.id === optimisticId ? savedMessage : message)),
      )
      await Promise.all([fetchFriends(), fetchUnreadSummary()])
      return { success: true, message: res.data.message as string }
    } catch (error) {
      console.error('发送消息失败:', error)
      chatMessages.value = chatMessages.value.filter((message) => message.id !== optimisticId)
      return { success: false, message: '发送失败，请稍后重试' }
    } finally {
      isSendingMessage.value = false
    }
  }

  return {
    friends,
    incomingRequests,
    searchResults,
    totalUnread,
    activeChatFriend,
    chatMessages,
    hasMoreMessages,
    isLoadingFriends,
    isLoadingRequests,
    isSearchingUsers,
    isLoadingChat,
    isLoadingOlderMessages,
    isSendingMessage,
    fetchUnreadSummary,
    fetchFriends,
    fetchIncomingRequests,
    searchUsers,
    refreshSocialOverview,
    startSocialPolling,
    stopSocialPolling,
    fetchChat,
    refreshActiveChat,
    fetchOlderMessages,
    markActiveChatRead,
    startChatPolling,
    stopChatPolling,
    clearChatState,
    sendFriendRequest,
    acceptRequest,
    rejectRequest,
    removeFriend,
    sendMessage,
  }
})
