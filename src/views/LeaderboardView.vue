<template>
  <div class="flex flex-col h-full overflow-hidden bg-linear-to-b from-slate-50 to-slate-100">
    <!-- 顶部筛选栏 -->
    <div class="shrink-0 bg-white shadow-sm border-b border-slate-200 px-4 py-3">
      <!-- 词库筛选 -->
      <div class="flex gap-1 overflow-x-auto scrollbar-hide">
        <button
          v-for="library in libraries"
          :key="library.key"
          @click="activeLibrary = library.key"
          :class="[
            'px-2 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-all flex-shrink-0',
            activeLibrary === library.key
              ? 'bg-blue-500 text-white shadow-md'
              : 'bg-slate-200 text-slate-700 hover:bg-slate-300',
          ]"
        >
          {{ library.label }}
        </button>
      </div>
    </div>

    <!-- 排行榜内容区域 - 可滚动 -->
    <div ref="scrollContainer" class="flex-1 overflow-y-auto px-4 py-4 pb-24 lg:pb-4">
      <!-- 前三名特殊展示 -->
      <div class="mb-6 space-y-4">
        <!-- 第一名 -->
        <div
          v-if="topThree[0]"
          class="relative bg-linear-to-br from-yellow-50 to-amber-100 rounded-2xl p-4 shadow-lg border-2 border-yellow-400"
        >
          <div class="flex items-center gap-3 sm:gap-4">
            <!-- 奖杯图标 -->
            <div class="relative flex-shrink-0">
              <Icon icon="noto:trophy" class="w-12 h-12 sm:w-16 sm:h-16" />
              <div
                class="absolute -top-0.5 -right-0.5 sm:-top-1 sm:-right-1 bg-yellow-500 text-white text-xs font-bold rounded-full w-5 h-5 sm:w-6 sm:h-6 flex items-center justify-center"
              >
                1
              </div>
            </div>

            <!-- 头像 -->
            <div class="relative flex-shrink-0">
              <div
                class="w-12 h-12 sm:w-16 sm:h-16 rounded-full bg-linear-to-br from-yellow-400 to-amber-500 flex items-center justify-center text-white text-xl sm:text-2xl font-bold shadow-lg"
              >
                <img
                  v-if="topThree[0].avatarUrl"
                  :src="topThree[0].avatarUrl"
                  :alt="topThree[0].name"
                  class="w-full h-full rounded-full object-cover"
                />
                <span v-else>{{ topThree[0].name.charAt(0) }}</span>
              </div>
              <div
                class="absolute -bottom-0.5 -right-0.5 sm:-bottom-1 sm:-right-1 bg-yellow-500 rounded-full p-0.5 sm:p-1"
              >
                <Icon icon="ph:crown-fill" class="w-3 h-3 sm:w-4 sm:h-4 text-white" />
              </div>
            </div>

            <!-- 用户信息 -->
            <div class="flex-1 min-w-0">
              <div class="text-base sm:text-lg font-bold text-slate-800 truncate">
                {{ topThree[0].name }}
              </div>
              <div
                class="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-3 text-xs sm:text-sm text-slate-600 mt-1"
              >
                <span class="flex items-center gap-1 flex-shrink-0">
                  <Icon icon="ph:stack-fill" class="w-3 h-3 sm:w-4 sm:h-4" />
                  层数: {{ topThree[0].floor }}
                </span>
                <span class="flex items-center gap-1 flex-shrink-0">
                  <Icon icon="ph:target-fill" class="w-3 h-3 sm:w-4 sm:h-4" />
                  准确率: {{ topThree[0].acc }}%
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- 第二名 -->
        <div
          v-if="topThree[1]"
          class="relative bg-linear-to-br from-slate-100 to-slate-200 rounded-2xl p-4 shadow-lg border-2 border-slate-300"
        >
          <div class="flex items-center gap-3 sm:gap-4">
            <!-- 奖牌图标 -->
            <div class="relative flex-shrink-0">
              <Icon icon="noto:2nd-place-medal" class="w-12 h-12 sm:w-16 sm:h-16" />
              <div
                class="absolute -top-0.5 -right-0.5 sm:-top-1 sm:-right-1 bg-slate-500 text-white text-xs font-bold rounded-full w-5 h-5 sm:w-6 sm:h-6 flex items-center justify-center"
              >
                2
              </div>
            </div>

            <!-- 头像 -->
            <div class="relative flex-shrink-0">
              <div
                class="w-12 h-12 sm:w-16 sm:h-16 rounded-full bg-linear-to-br from-slate-300 to-slate-400 flex items-center justify-center text-white text-xl sm:text-2xl font-bold shadow-lg"
              >
                <img
                  v-if="topThree[1].avatarUrl"
                  :src="topThree[1].avatarUrl"
                  :alt="topThree[1].name"
                  class="w-full h-full rounded-full object-cover"
                />
                <span v-else>{{ topThree[1].name.charAt(0) }}</span>
              </div>
              <div
                class="absolute -bottom-0.5 -right-0.5 sm:-bottom-1 sm:-right-1 bg-slate-500 rounded-full p-0.5 sm:p-1"
              >
                <Icon icon="ph:medal-fill" class="w-3 h-3 sm:w-4 sm:h-4 text-white" />
              </div>
            </div>

            <!-- 用户信息 -->
            <div class="flex-1 min-w-0">
              <div class="text-base sm:text-lg font-bold text-slate-800 truncate">
                {{ topThree[1].name }}
              </div>
              <div
                class="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-3 text-xs sm:text-sm text-slate-600 mt-1"
              >
                <span class="flex items-center gap-1 flex-shrink-0">
                  <Icon icon="ph:stack-fill" class="w-3 h-3 sm:w-4 sm:h-4" />
                  层数: {{ topThree[1].floor }}
                </span>
                <span class="flex items-center gap-1 flex-shrink-0">
                  <Icon icon="ph:target-fill" class="w-3 h-3 sm:w-4 sm:h-4" />
                  准确率: {{ topThree[1].acc }}%
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- 第三名 -->
        <div
          v-if="topThree[2]"
          class="relative bg-linear-to-br from-orange-50 to-orange-100 rounded-2xl p-4 shadow-lg border-2 border-orange-300"
        >
          <div class="flex items-center gap-3 sm:gap-4">
            <!-- 奖牌图标 -->
            <div class="relative flex-shrink-0">
              <Icon icon="noto:3rd-place-medal" class="w-12 h-12 sm:w-16 sm:h-16" />
              <div
                class="absolute -top-0.5 -right-0.5 sm:-top-1 sm:-right-1 bg-orange-600 text-white text-xs font-bold rounded-full w-5 h-5 sm:w-6 sm:h-6 flex items-center justify-center"
              >
                3
              </div>
            </div>

            <!-- 头像 -->
            <div class="relative flex-shrink-0">
              <div
                class="w-12 h-12 sm:w-16 sm:h-16 rounded-full bg-linear-to-br from-orange-300 to-orange-400 flex items-center justify-center text-white text-xl sm:text-2xl font-bold shadow-lg"
              >
                <img
                  v-if="topThree[2].avatarUrl"
                  :src="topThree[2].avatarUrl"
                  :alt="topThree[2].name"
                  class="w-full h-full rounded-full object-cover"
                />
                <span v-else>{{ topThree[2].name.charAt(0) }}</span>
              </div>
              <div
                class="absolute -bottom-0.5 -right-0.5 sm:-bottom-1 sm:-right-1 bg-orange-600 rounded-full p-0.5 sm:p-1"
              >
                <Icon icon="ph:medal-fill" class="w-3 h-3 sm:w-4 sm:h-4 text-white" />
              </div>
            </div>

            <!-- 用户信息 -->
            <div class="flex-1 min-w-0">
              <div class="text-base sm:text-lg font-bold text-slate-800 truncate">
                {{ topThree[2].name }}
              </div>
              <div
                class="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-3 text-xs sm:text-sm text-slate-600 mt-1"
              >
                <span class="flex items-center gap-1 flex-shrink-0">
                  <Icon icon="ph:stack-fill" class="w-3 h-3 sm:w-4 sm:h-4" />
                  层数: {{ topThree[2].floor }}
                </span>
                <span class="flex items-center gap-1 flex-shrink-0">
                  <Icon icon="ph:target-fill" class="w-3 h-3 sm:w-4 sm:h-4" />
                  准确率: {{ topThree[2].acc }}%
                </span>
              </div>
            </div>
          </div>
        </div>
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
      class="fixed bottom-16 lg:bottom-0 left-0 right-0 bg-white border-t-2 border-white-500 z-10"
    >
      <div class="px-4 py-3">
        <div v-if="currentUser" class="flex items-center gap-3">
          <!-- 排名 -->
          <div
            class="w-11 h-11 sm:w-12 sm:h-12 flex items-center justify-center font-bold text-white bg-blue-500 rounded-full shadow-md shrink-0 text-sm sm:text-base"
          >
            #{{ currentUser.rank }}
          </div>

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
              class="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-3 text-xs sm:text-sm text-slate-600 mt-0.5"
            >
              <span class="flex items-center gap-1 shrink-0">
                <Icon icon="ph:stack-fill" class="w-3 h-3 sm:w-3.5 sm:h-3.5" />
                层数: {{ currentUser.floor }}
              </span>
              <span class="flex items-center gap-1 shrink-0">
                <Icon icon="ph:target-fill" class="w-3 h-3 sm:w-3.5 sm:h-3.5" />
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

// 监听词库切换（这里可以添加API调用逻辑）
// watch(activeLibrary, (newLibrary) => {
//   console.log('切换到词库:', newLibrary)
//   // 重置分页
//   currentPage.value = 1
//   hasMore.value = true
//   // 从后端获取对应词库的排行榜数据
// })
</script>

<style scoped>
/* 隐藏滚动条 */
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}

.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

/* 平滑滚动 */
.overflow-y-auto {
  scroll-behavior: smooth;
}
</style>
