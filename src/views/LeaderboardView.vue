<template>
  <div class="flex flex-col h-full overflow-hidden">
    <!-- 顶部筛选栏 -->
    <div class="shrink-0 px-8 py-3">
      <!-- 词库筛选 -->
      <div class="flex gap-1 overflow-x-auto justify-start md:justify-center">
        <Button
          :variant="activeLibrary === library.key ? 'default' : 'outline'"
          v-for="library in libraries"
          :key="library.key"
          @click="activeLibrary = library.key"
          class="rounded-full text-sm font-medium shrink-0"
        >
          {{ library.label }}
        </Button>
      </div>
    </div>

    <!-- 排行榜内容区域 - 可滚动 -->
    <div ref="scrollContainer" class="flex-1 overflow-y-auto px-8 py-4 pb-24 lg:pb-4">
      <!-- 前三名特殊展示 -->
      <div class="mb-6 space-y-4">
        <TopRankCard v-for="user in topThree" :key="user.rank" :user="user" :rank="user.rank" />
      </div>

      <!-- 其他排名（4名及以后） -->
      <div class="space-y-2">
        <div
          v-for="user in displayedUsers"
          :key="user.rank"
          class="bg-white rounded-lg p-3 shadow-sm hover:shadow-md transition-shadow border border-slate-200"
        >
          <div class="flex items-center gap-3">
            <!-- 排名 -->
            <div
              class="min-w-8 flex items-center justify-center font-bold text-slate-600 text-sm shrink-0"
            >
              #{{ user.rank }}
            </div>

            <!-- 头像 -->
            <div
              class="w-10 h-10 sm:w-11 sm:h-11 rounded-full bg-linear-to-br from-blue-400 to-blue-500 flex items-center justify-center text-white font-semibold shadow shrink-0"
            >
              <img
                v-if="user.avatarUrl"
                :src="user.avatarUrl"
                :alt="user.name"
                class="w-full h-full rounded-full object-cover"
              />
              <span v-else class="text-sm sm:text-base">{{ user.name.charAt(0) }}</span>
            </div>

            <!-- 用户信息 -->
            <div class="flex-1 min-w-0">
              <div class="font-semibold text-slate-800 text-sm sm:text-base truncate">
                {{ user.name }}
              </div>
              <div class="flex items-center gap-2 sm:gap-3 text-xs text-slate-600 mt-0.5">
                <span class="flex items-center gap-1 shrink-0">
                  <Icon icon="ph:stack-fill" class="w-3 h-3 sm:w-3.5 sm:h-3.5" />
                  {{ user.floor }}层
                </span>
                <span class="flex items-center gap-1 shrink-0">
                  <Icon icon="ph:target-fill" class="w-3 h-3 sm:w-3.5 sm:h-3.5" />
                  {{ user.acc }}%
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- 加载更多指示器 -->
        <div v-if="isLoading" class="flex justify-center py-4">
          <div class="animate-spin rounded-full size-8 sm:size-10 border-b-2 border-blue-500"></div>
        </div>

        <!-- 没有更多数据提示 -->
        <div
          v-if="!hasMore && displayedUsers.length > 0"
          class="text-center py-4 text-slate-500 text-sm"
        >
          已显示全部排名
        </div>
      </div>
    </div>

    <!-- 底部固定：当前用户排名 -->
    <div
      class="fixed bottom-16 lg:bottom-0 left-0 lg:left-64 right-0 bg-white border-t-2 border-white-500 z-10"
    >
      <div class="px-4 py-3">
        <div v-if="currentUser" class="flex items-center gap-3">
          <!-- 排名 -->
          <div class="text-lg font-semibold">#{{ currentUser.rank }}</div>

          <!-- 头像 -->
          <div
            class="w-12 h-12 sm:w-14 sm:h-14 rounded-full bg-linear-to-br from-blue-500 to-blue-600 flex items-center justify-center text-white font-bold shadow-lg border-2 border-white shrink-0"
          >
            <img
              v-if="currentUser.avatarUrl"
              :src="currentUser.avatarUrl"
              :alt="currentUser.name"
              class="w-full h-full rounded-full object-cover"
            />
            <span v-else class="text-lg sm:text-xl">{{ currentUser.name.charAt(0) }}</span>
          </div>

          <!-- 用户信息 -->
          <div class="flex-1 min-w-0">
            <div class="font-bold text-slate-800 text-sm sm:text-base truncate">
              {{ currentUser.name }} <span class="text-blue-500">(你)</span>
            </div>
            <div
              class="flex flex-row md:items-center gap-4 md:gap-4 text-xs md:text-md text-slate-600 mt-1"
            >
              <span class="flex items-center gap-1 shrink-0">
                <Icon icon="ph:stack-fill" class="w-3 h-3 md:w-4 md:h-4" />
                层数: {{ currentUser.floor }}
              </span>
              <span class="flex items-center gap-1 shrink-0">
                <Icon icon="ph:target-fill" class="w-3 h-3 md:w-4 md:h-4" />
                准确率: {{ currentUser.acc }}%
              </span>
            </div>
          </div>
        </div>

        <div v-else class="text-center text-slate-500 py-2">暂无个人排名数据</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, nextTick } from 'vue'
import TopRankCard from '@/components/TopRankCard.vue'
import { Button } from '@/components/ui/button'

// 词库筛选选项
const libraries = [
  { key: 'all', label: '全部' },
  { key: 'cet4', label: 'CET-4' },
  { key: 'cet6', label: 'CET-6' },
  { key: 'toefl', label: 'TOEFL' },
  { key: 'ielts', label: 'IELTS' },
]

const activeLibrary = ref('all')
const isLoading = ref(false)
const hasMore = ref(true)
const pageSize = 20 // 每次加载20条
const currentPage = ref(1)

// 模拟排行榜数据
const allUsers = ref([
  { rank: 1, name: 'Nova', floor: 58, acc: 93, avatarUrl: '', isCurrent: false },
  { rank: 2, name: 'Orion', floor: 54, acc: 90, avatarUrl: '', isCurrent: false },
  { rank: 3, name: 'Lyra', floor: 51, acc: 88, avatarUrl: '', isCurrent: false },
  { rank: 4, name: 'Vega', floor: 49, acc: 86, avatarUrl: '', isCurrent: false },
  { rank: 5, name: 'Artemis', floor: 47, acc: 85, avatarUrl: '', isCurrent: false },
  { rank: 6, name: 'Zephyr', floor: 46, acc: 83, avatarUrl: '', isCurrent: false },
  { rank: 7, name: 'Phoenix', floor: 45, acc: 82, avatarUrl: '', isCurrent: false },
  { rank: 8, name: 'Atlas', floor: 44, acc: 81, avatarUrl: '', isCurrent: false },
  { rank: 9, name: 'Cassio', floor: 43, acc: 80, avatarUrl: '', isCurrent: false },
  { rank: 10, name: 'Diana', floor: 42, acc: 79, avatarUrl: '', isCurrent: false },
  // 添加更多用户以测试滚动加载
  ...Array.from({ length: 40 }, (_, i) => ({
    rank: 11 + i,
    name: `Player${11 + i}`,
    floor: 41 - i,
    acc: Math.max(60, 78 - i),
    avatarUrl: '',
    isCurrent: false,
  })),
  { rank: 51, name: '你', floor: 25, acc: 75, avatarUrl: '', isCurrent: true },
])

// 前三名
const topThree = computed(() => allUsers.value.filter((p) => p.rank <= 3))

// 其他用户（排除前三名和当前用户）
const otherUsers = computed(() => allUsers.value.filter((p) => p.rank > 3 && !p.isCurrent))

// 当前显示的用户列表（分页加载）
const displayedUsers = computed(() => {
  const endIndex = currentPage.value * pageSize
  return otherUsers.value.slice(0, endIndex)
})

// 当前用户
const currentUser = computed(() => allUsers.value.find((p) => p.isCurrent))

// 滚动容器引用
const scrollContainer = ref<HTMLElement | null>(null)

// 滚动加载处理（使用容器滚动事件）
const handleScroll = async () => {
  if (isLoading.value || !hasMore.value || !scrollContainer.value) return

  const { scrollTop, scrollHeight, clientHeight } = scrollContainer.value

  // 当滚动到距离底部200px时触发加载
  if (scrollTop + clientHeight >= scrollHeight - 200) {
    await loadMore()
  }
}

// 加载更多数据
const loadMore = async () => {
  if (isLoading.value || !hasMore.value) return

  isLoading.value = true

  // 模拟网络延迟
  await new Promise((resolve) => setTimeout(resolve, 500))

  currentPage.value++

  // 检查是否还有更多数据
  if (displayedUsers.value.length >= otherUsers.value.length) {
    hasMore.value = false
  }

  isLoading.value = false
}

// 初始化
onMounted(async () => {
  await nextTick()
  // 添加滚动事件监听到容器
  if (scrollContainer.value) {
    scrollContainer.value.addEventListener('scroll', handleScroll)
  }
  // 可以在这里添加从后端获取数据的逻辑
})

// 组件卸载时移除监听器
onUnmounted(() => {
  if (scrollContainer.value) {
    scrollContainer.value.removeEventListener('scroll', handleScroll)
  }
})
</script>
