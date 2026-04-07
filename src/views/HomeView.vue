<template>
  <div class="flex h-screen flex-col items-center p-8 gap-6">
    <Card class="border-dashed py-2 w-full max-w-md">
        <CardContent class="space-y-3 p-4">
          <div class="flex items-center justify-between">
            <div>
              <div class="font-medium">每日挑战</div>
              <div class="text-sm text-muted-foreground">
                {{
                  dailyOverview?.active_run
                    ? '存在进行中的每日挑战，可随时继续'
                    : dailyOverview?.user_status === 'ended'
                      ? '今天的机会已经用完，明早 6 点刷新'
                      : '成绩计入今日榜单'
                }}
              </div>
            </div>
            <Badge variant="outline" class="p-2 rounded-lg">
              {{
                dailyOverview?.active_run
                  ? '进行中'
                  : dailyOverview?.user_status === 'ended'
                    ? '已结束'
                    : '未开始'
              }}
            </Badge>
          </div>

          <div class="grid grid-cols-2 gap-3 text-sm">
            <div class="rounded-lg border px-3 py-2">
              <div class="text-muted-foreground">今日最佳</div>
              <div class="mt-1 font-medium">第 {{ dailyOverview?.today_best_floor ?? 0 }} 层</div>
            </div>
            <div class="rounded-lg border px-3 py-2">
              <div class="text-muted-foreground">距离刷新</div>
              <div class="mt-1 font-medium">{{ countdownText }}</div>
            </div>
          </div>

          <Button
            class="w-full"
            :disabled="isDailyDisabled"
            @click="$router.push({ name: 'daily-challenge' })"
          >
            {{ dailyActionText }}
          </Button>
          <Button
            variant="outline"
            class="w-full"
            @click="$router.push({ name: 'social', query: { tab: 'leaderboard' } })"
          >
            查看排行榜
          </Button>
        </CardContent>
      </Card>
    <div class="w-full max-w-md select-none rounded-lg">
      <Card class="h-auto">
        <CardHeader>
          <CardTitle
            class="bg-linear-to-br from-blue-500 via-purple-500 to-pink-500 bg-clip-text text-center text-6xl font-bold text-transparent"
          >
            {{ profile?.max_floor ?? 0 }}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p class="text-center text-lg">最高层数</p>
        </CardContent>
      </Card>
    </div>

    <div class="mt-8 flex w-full max-w-md flex-1 flex-col justify-center gap-4">
      <Button variant="outline" class="h-12 w-full text-md" @click="$router.push({ name: 'combat' })">
        开始闯塔
      </Button>


    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useDailyChallengeStore } from '@/stores/dailyChallenge'
import { useUserProfileStore } from '@/stores/userProfile'
import { preloadHomeCriticalAssets } from '@/utils/assetPreloader'

const userProfileStore = useUserProfileStore()
const dailyChallengeStore = useDailyChallengeStore()

const { profile } = storeToRefs(userProfileStore)
const { overview: dailyOverview, secondsUntilReset } = storeToRefs(dailyChallengeStore)

const countdownText = computed(() => {
  const total = secondsUntilReset.value
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  return [hours, minutes, seconds].map((value) => String(value).padStart(2, '0')).join(':')
})

const isDailyDisabled = computed(() => {
  return dailyOverview.value?.user_status === 'ended' && !dailyOverview.value?.active_run
})

const dailyActionText = computed(() => {
  if (dailyOverview.value?.active_run) return '继续每日挑战'
  if (dailyOverview.value?.user_status === 'ended') return '今日已结束，明早 6 点刷新'
  return '开始每日挑战'
})

onMounted(() => {
  preloadHomeCriticalAssets()
  userProfileStore.getProfile()
  void dailyChallengeStore.fetchOverview()
})
</script>
