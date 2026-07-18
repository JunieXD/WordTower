<script setup lang="ts">
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { DailyChallengeLeaderboardEntry } from '@/stores/dailyChallenge'
import {
  formatLeaderboardStatus,
  formatShortTime,
  getInitials,
} from '@/views/social/socialHelpers'

defineProps<{
  dailyLeaderboard: DailyChallengeLeaderboardEntry[]
  leaderboardDayKey: string | null
  currentUserRank: number | null
  currentUserEntry: DailyChallengeLeaderboardEntry | null
  isLoadingLeaderboard: boolean
}>()

const emit = defineEmits<{
  refresh: []
}>()

function handleRefresh() {
  emit('refresh')
}
</script>

<template>
  <div class="mt-0 flex flex-1 flex-col overflow-y-auto px-4 pb-6">
    <section
      class="mt-4 rounded-3xl border border-slate-200/80 bg-white/90 p-4 shadow-[0_10px_35px_rgba(15,23,42,0.06)]"
    >
      <div class="flex items-center justify-between gap-3">
        <div>
          <div class="text-sm font-semibold text-slate-900">今日每日挑战排行榜</div>
          <div class="text-xs text-slate-500">
            {{ leaderboardDayKey ? `${leaderboardDayKey} 的挑战榜单` : '正在同步今日榜单' }}
          </div>
        </div>
        <Button variant="outline" class="rounded-xl" @click="handleRefresh">
          刷新
        </Button>
      </div>

      <div class="mt-4 rounded-2xl border border-slate-200 bg-slate-50/90 p-3">
        <div class="text-xs text-slate-500">我的成绩</div>
        <div v-if="currentUserEntry" class="mt-2 flex items-center justify-between gap-3">
          <div>
            <div class="font-medium text-slate-900">
              第 {{ currentUserRank ?? currentUserEntry.rank }} 名 · 第
              {{ currentUserEntry.best_floor }} 层
            </div>
            <div class="mt-1 text-xs text-slate-500">
              {{ currentUserEntry.nickname || currentUserEntry.username }} ·
              {{ formatLeaderboardStatus(currentUserEntry.status) }}
            </div>
          </div>
          <Badge variant="outline">{{ formatLeaderboardStatus(currentUserEntry.status) }}</Badge>
        </div>
        <div v-else class="mt-2 text-sm text-slate-500">今天还没有上榜成绩。</div>
      </div>

      <div v-if="isLoadingLeaderboard" class="py-10 text-center text-sm text-slate-500">
        正在加载今日榜单...
      </div>

      <div
        v-else-if="!dailyLeaderboard.length"
        class="py-10 text-center text-sm text-slate-500"
      >
        今天还没有人开始每日挑战。
      </div>

      <div v-else class="mt-4 space-y-3">
        <div
          v-for="entry in dailyLeaderboard"
          :key="entry.user_id"
          class="flex items-center gap-3 rounded-2xl border p-3"
          :class="
            entry.is_current_user ? 'border-sky-200 bg-sky-50/80' : 'border-slate-200 bg-slate-50/80'
          "
        >
          <div
            class="flex size-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold"
            :class="entry.rank <= 3 ? 'bg-amber-100 text-amber-700' : 'bg-slate-200 text-slate-700'"
          >
            {{ entry.rank }}
          </div>

          <Avatar class="size-11 ring-2 ring-white">
            <AvatarImage
              v-if="entry.avatar_url"
              :src="entry.avatar_url"
              :alt="entry.nickname || entry.username"
            />
            <AvatarFallback class="bg-slate-200 text-slate-700">
              {{ getInitials(entry) }}
            </AvatarFallback>
          </Avatar>

          <div class="min-w-0 flex-1">
            <div class="truncate font-medium text-slate-900">
              {{ entry.nickname || entry.username }}
            </div>
            <div class="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span>@{{ entry.username }}</span>
              <span>{{ formatLeaderboardStatus(entry.status) }}</span>
              <span>{{ formatShortTime(entry.best_floor_reached_at) }}</span>
            </div>
          </div>

          <div class="text-right">
            <div class="text-sm font-semibold text-slate-900">第 {{ entry.best_floor }} 层</div>
            <div v-if="entry.is_current_user" class="mt-1 text-xs text-sky-600">我</div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
