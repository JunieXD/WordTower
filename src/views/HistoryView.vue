<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useHistoryStore, type HistoryRunMode, type HistoryRunStatus } from '@/stores/history'

const router = useRouter()
const historyStore = useHistoryStore()

const runs = computed(() => historyStore.runs)

const statusLabelMap: Record<HistoryRunStatus, string> = {
  in_progress: '进行中',
  completed: '已完成',
  failed: '已结束',
}

const statusClassMap: Record<HistoryRunStatus, string> = {
  in_progress: 'bg-blue-50 text-blue-700',
  completed: 'bg-emerald-50 text-emerald-700',
  failed: 'bg-amber-50 text-amber-700',
}

const modeLabelMap: Record<HistoryRunMode, string> = {
  tower: '普通闯塔',
  daily_challenge: '每日挑战',
}

const modeClassMap: Record<HistoryRunMode, string> = {
  tower: 'bg-slate-100 text-slate-700',
  daily_challenge: 'bg-violet-50 text-violet-700',
}

const formatDateTime = (value: string | null) => {
  if (!value) return '未结束'
  return new Date(value).toLocaleString()
}

const formatProgressText = (run: (typeof runs.value)[number]) => {
  if (run.status === 'in_progress' && run.current_floor) {
    return `当前进行到第 ${run.current_floor} 层`
  }
  return `最高到达第 ${run.highest_floor} 层`
}

const formatRunTitle = (run: (typeof runs.value)[number]) => {
  if (run.mode === 'daily_challenge') {
    return run.day_key ? `每日挑战 · ${run.day_key}` : '每日挑战'
  }
  const sequenceNumber = historyStore.getRunSequenceNumber(run.run_ref)
  return sequenceNumber ? `第 ${sequenceNumber} 次闯塔` : '闯塔记录'
}

const openRun = (runRef: string) => {
  router.push({ name: 'history-detail', params: { runId: runRef } })
}

onMounted(() => {
  historyStore.fetchRuns()
})
</script>

<template>
  <div class="flex h-full flex-col overflow-y-auto p-6">
    <div class="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <Card v-if="historyStore.isLoadingRuns">
        <CardContent class="py-4 text-sm text-muted-foreground">正在加载历史记录...</CardContent>
      </Card>

      <Card v-else-if="runs.length === 0">
        <CardContent class="py-4 text-sm text-muted-foreground">还没有任何历史记录。</CardContent>
      </Card>

      <button
        v-for="run in runs"
        :key="run.run_ref"
        type="button"
        class="text-left"
        @click="openRun(run.run_ref)"
      >
        <Card class="transition-colors hover:bg-muted/30">
          <CardContent class="flex flex-col gap-4">
            <div class="flex flex-wrap items-center gap-3">
              <div class="text-lg font-semibold">{{ formatRunTitle(run) }}</div>
              <span class="rounded-full px-2.5 py-1 text-xs font-medium" :class="modeClassMap[run.mode]">
                {{ modeLabelMap[run.mode] }}
              </span>
              <span class="rounded-full px-2.5 py-1 text-xs font-medium" :class="statusClassMap[run.status]">
                {{ statusLabelMap[run.status] }}
              </span>
            </div>

            <div class="grid gap-3 text-sm text-muted-foreground md:grid-cols-2">
              <div>{{ formatProgressText(run) }}</div>
              <div>题目数：{{ run.question_count }}</div>
              <div>开始时间：{{ formatDateTime(run.started_at) }}</div>
              <div>结束时间：{{ formatDateTime(run.ended_at) }}</div>
            </div>

            <div class="flex justify-end">
              <Button variant="outline" class="h-9">查看详情</Button>
            </div>
          </CardContent>
        </Card>
      </button>
    </div>
  </div>
</template>
