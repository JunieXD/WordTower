import { defineStore } from 'pinia'
import { ref } from 'vue'

import { useNotificationStore } from '@/stores/notification'
import request from '@/utils/request'

export type HistoryRunStatus = 'in_progress' | 'completed' | 'failed'
export type HistoryRunMode = 'tower' | 'daily_challenge'

export interface HistoryRunSummary {
  run_ref: string
  run_id: number
  mode: HistoryRunMode
  status: HistoryRunStatus
  day_key: string | null
  started_at: string | null
  ended_at: string | null
  highest_floor: number
  current_floor: number | null
  total_exp: number
  total_coins: number
  question_count: number
  last_hp: number | null
}

export interface HistoryAnswer {
  id: number
  answered_at: string | null
  correct: boolean | null
  answer_detail: Record<string, unknown> | null
  rating: number | null
  report: string | null
}

export interface HistoryQuestion {
  question_id: number
  order_index: number
  floor: number
  question_index: number | null
  level_id: number | null
  question_type: string | null
  content: Record<string, unknown> | null
  first_answer: HistoryAnswer | null
}

export interface HistoryRunDetail {
  run: HistoryRunSummary
  questions: HistoryQuestion[]
}

export const useHistoryStore = defineStore('history', () => {
  const notificationStore = useNotificationStore()

  const runs = ref<HistoryRunSummary[]>([])
  const currentRunDetail = ref<HistoryRunDetail | null>(null)
  const isLoadingRuns = ref(false)
  const isLoadingDetail = ref(false)

  async function fetchRuns() {
    isLoadingRuns.value = true
    try {
      const res = await request.get('/api/history/runs')
      if (res.data.success) {
        runs.value = res.data.data as HistoryRunSummary[]
      }
    } catch (error) {
      console.error('获取历史记录失败:', error)
      notificationStore.addNotification({
        title: '获取失败',
        description: '历史记录加载失败，请稍后重试',
        variant: 'destructive',
        duration: 3000,
      })
    } finally {
      isLoadingRuns.value = false
    }
  }

  async function fetchRunDetail(runRef: string) {
    isLoadingDetail.value = true
    currentRunDetail.value = null
    try {
      const res = await request.get(`/api/history/runs/${runRef}`)
      if (res.data.success) {
        currentRunDetail.value = res.data.data as HistoryRunDetail
      }
    } catch (error) {
      console.error('获取历史记录详情失败:', error)
      notificationStore.addNotification({
        title: '获取失败',
        description: '历史记录详情加载失败，请稍后重试',
        variant: 'destructive',
        duration: 3000,
      })
    } finally {
      isLoadingDetail.value = false
    }
  }

  function getRunSequenceNumber(runRef: string) {
    const towerRuns = runs.value.filter((run) => run.mode === 'tower')
    const index = towerRuns.findIndex((run) => run.run_ref === runRef)
    if (index === -1) {
      return null
    }
    return towerRuns.length - index
  }

  return {
    runs,
    currentRunDetail,
    isLoadingRuns,
    isLoadingDetail,
    fetchRuns,
    fetchRunDetail,
    getRunSequenceNumber,
  }
})
