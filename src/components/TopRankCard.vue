<template>
  <div
    :class="[
      'relative rounded-2xl p-4 shadow-lg border-2',
      rank === 1
        ? 'bg-linear-to-br from-yellow-50 to-amber-100 border-yellow-400'
        : rank === 2
          ? 'bg-linear-to-br from-slate-100 to-slate-200 border-slate-300'
          : 'bg-linear-to-br from-orange-50 to-orange-100 border-orange-300',
    ]"
  >
    <div class="flex items-center gap-3 sm:gap-4">
      <!-- 奖杯/奖牌图标 -->
      <div class="relative shrink-0">
        <Icon :icon="medalIcon" class="size-10 md:size-16" />
      </div>

      <!-- 头像 -->
      <div class="relative shrink-0">
        <div
          :class="[
            'rounded-full flex items-center justify-center text-white text-xl sm:text-2xl font-bold shadow-lg size-12 md:size-16',
            avatarBgClass,
          ]"
        >
          <img
            v-if="user.avatarUrl"
            :src="user.avatarUrl"
            :alt="user.name"
            class="w-full h-full rounded-full object-cover"
          />
          <span v-else>{{ user.name.charAt(0) }}</span>
        </div>
        <div
          :class="[
            'absolute -bottom-0.5 -right-0.5 md:-bottom-1 md:-right-1 rounded-full p-0.5 md:p-1',
            badgeBgClass,
          ]"
        >
          <Icon :icon="badgeIcon" class="w-3 h-3 md:w-4 md:h-4 text-white" />
        </div>
      </div>

      <!-- 用户信息 -->
      <div class="flex-1 min-w-0">
        <div class="text-base md:text-lg font-bold text-slate-800 truncate">
          {{ user.name }}
        </div>
        <div
          class="flex flex-row md:items-center gap-4 md:gap-4 text-xs md:text-md text-slate-600 mt-1"
        >
          <span class="flex items-center gap-1 shrink-0">
            <Icon icon="ph:stack-fill" class="w-3 h-3 md:w-4 md:h-4" />
            层数: {{ user.floor }}
          </span>
          <span class="flex items-center gap-1 shrink-0">
            <Icon icon="ph:target-fill" class="w-3 h-3 md:w-4 md:h-4" />
            准确率: {{ user.acc }}%
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  user: {
    rank: number
    name: string
    floor: number
    acc: number
    avatarUrl?: string
  }
  rank: number
}

const props = defineProps<Props>()

// 将 rank 约束为 1|2|3（若越界则回退为 3）
const rankKey = computed<1 | 2 | 3>(() => {
  return props.rank === 1 || props.rank === 2 || props.rank === 3 ? props.rank : 3
})

// 奖牌图标配置
const medalIcon = computed(() => {
  const icons = {
    1: 'noto:trophy',
    2: 'noto:2nd-place-medal',
    3: 'noto:3rd-place-medal',
  }
  return icons[rankKey.value]
})

// 头像背景渐变
const avatarBgClass = computed(() => {
  const classes = {
    1: 'bg-linear-to-br from-yellow-400 to-amber-500',
    2: 'bg-linear-to-br from-slate-300 to-slate-400',
    3: 'bg-linear-to-br from-orange-300 to-orange-400',
  }
  return classes[rankKey.value]
})

// 徽章图标
const badgeIcon = computed(() => {
  return props.rank === 1 ? 'ph:crown-fill' : 'ph:medal-fill'
})

// 徽章背景色
const badgeBgClass = computed(() => {
  const classes = {
    1: 'bg-yellow-500',
    2: 'bg-slate-500',
    3: 'bg-orange-600',
  }
  return classes[rankKey.value]
})
</script>
