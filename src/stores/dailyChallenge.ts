import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import request from '@/utils/request'
import type {
  AnswerDetail,
  QuestionContent0,
  QuestionContent1,
  QuestionContent2,
  QuestionType,
} from '@/stores/combat'

export type DailyChallengeStatus = 'in_progress' | 'dead' | 'completed_exhausted'
export type DailyChallengeUserStatus = 'not_started' | 'in_progress' | 'ended'

export interface DailyChallengeQuestion {
  question_id: number
  floor: number
  question_index: number
  type: QuestionType
  content: QuestionContent0 | QuestionContent1 | QuestionContent2
}

export interface DailyChallengeAnswerResult {
  is_correct: boolean
  detail: Record<string, unknown>
}

export interface DailyChallengeState {
  run_id: number
  day_key: string
  status: DailyChallengeStatus
  current_floor: number
  current_question_index: number
  current_hp: number
  current_enemy_hp: number
  player_max_hp: number
  player_attack: number
  enemy_max_hp: number
  enemy_attack: number
  heal_every_floors: number
  heal_amount: number
  best_floor: number
  best_floor_reached_at: string
  started_at: string
  ended_at: string | null
  question: DailyChallengeQuestion | null
  answer_result: DailyChallengeAnswerResult | null
}

export interface DailyChallengeLeaderboardEntry {
  rank: number
  user_id: number
  username: string
  nickname: string | null
  avatar_url: string | null
  best_floor: number
  best_floor_reached_at: string | null
  started_at: string
  status: DailyChallengeStatus
  is_current_user: boolean
}

export interface DailyChallengeOverview {
  day_key: string
  opens_at: string
  closes_at: string
  seconds_until_reset: number
  user_status: DailyChallengeUserStatus
  today_best_floor: number | null
  active_run: DailyChallengeState | null
  leaderboard: DailyChallengeLeaderboardEntry[]
  current_user_rank: number | null
  current_user_entry: DailyChallengeLeaderboardEntry | null
}

type CountdownTimer = ReturnType<typeof setInterval> | null

function cloneQuestion(question: DailyChallengeQuestion | null | undefined): DailyChallengeQuestion | null {
  if (!question) return null
  return JSON.parse(JSON.stringify(question)) as DailyChallengeQuestion
}

export const useDailyChallengeStore = defineStore('dailyChallenge', () => {
  const overview = ref<DailyChallengeOverview | null>(null)
  const leaderboard = ref<DailyChallengeLeaderboardEntry[]>([])
  const leaderboardDayKey = ref<string | null>(null)
  const currentUserRank = ref<number | null>(null)
  const currentUserEntry = ref<DailyChallengeLeaderboardEntry | null>(null)

  const activeState = ref<DailyChallengeState | null>(null)
  const displayedQuestion = ref<DailyChallengeQuestion | null>(null)
  const answerResult = ref<DailyChallengeAnswerResult | null>(null)
  const pendingState = ref<DailyChallengeState | null>(null)
  const secondsUntilReset = ref(0)

  const isLoadingOverview = ref(false)
  const isLoadingLeaderboard = ref(false)
  const isStartingChallenge = ref(false)
  const isSubmittingAnswer = ref(false)

  const countdownTimer = ref<CountdownTimer>(null)

  const hasActiveRun = computed(() => activeState.value?.status === 'in_progress')
  const canContinueCurrentQuestion = computed(() => answerResult.value !== null)
  const isEnded = computed(
    () =>
      activeState.value?.status === 'dead' || activeState.value?.status === 'completed_exhausted',
  )

  function stopCountdown() {
    if (countdownTimer.value) {
      clearInterval(countdownTimer.value)
      countdownTimer.value = null
    }
  }

  function startCountdown(seconds: number) {
    stopCountdown()
    secondsUntilReset.value = Math.max(0, seconds)
    countdownTimer.value = setInterval(() => {
      secondsUntilReset.value = Math.max(0, secondsUntilReset.value - 1)
    }, 1000)
  }

  function hydrateOverview(data: DailyChallengeOverview) {
    overview.value = data
    leaderboard.value = data.leaderboard ?? []
    leaderboardDayKey.value = data.day_key
    currentUserRank.value = data.current_user_rank
    currentUserEntry.value = data.current_user_entry
    startCountdown(data.seconds_until_reset ?? 0)
  }

  function applyFreshState(state: DailyChallengeState | null) {
    activeState.value = state
    displayedQuestion.value = cloneQuestion(state?.question)
    answerResult.value = null
    pendingState.value = null
  }

  async function refreshLeaderboardInBackground() {
    try {
      await fetchLeaderboard()
    } catch (error) {
      console.error('刷新每日挑战排行榜失败:', error)
    }
  }

  async function fetchOverview() {
    isLoadingOverview.value = true
    try {
      const res = await request.get('/api/daily-challenge/overview', { timeout: 10000 })
      if (res.data.success) {
        const data = res.data.data as DailyChallengeOverview
        hydrateOverview(data)
        if (data.active_run) {
          applyFreshState(data.active_run)
        } else if (!pendingState.value) {
          activeState.value = null
          displayedQuestion.value = null
          answerResult.value = null
          pendingState.value = null
        }
      }
      return res.data
    } finally {
      isLoadingOverview.value = false
    }
  }

  async function fetchLeaderboard() {
    isLoadingLeaderboard.value = true
    try {
      const res = await request.get('/api/daily-challenge/leaderboard', { timeout: 10000 })
      if (res.data.success) {
        const data = res.data.data as {
          day_key: string
          items: DailyChallengeLeaderboardEntry[]
          current_user_rank: number | null
          current_user_entry: DailyChallengeLeaderboardEntry | null
        }
        leaderboard.value = data.items ?? []
        leaderboardDayKey.value = data.day_key
        currentUserRank.value = data.current_user_rank
        currentUserEntry.value = data.current_user_entry
      }
      return res.data
    } finally {
      isLoadingLeaderboard.value = false
    }
  }

  async function startOrResume() {
    isStartingChallenge.value = true
    try {
      const res = await request.post('/api/daily-challenge/start', null, { timeout: 30000 })
      if (res.data.success) {
        const state = res.data.data as DailyChallengeState
        applyFreshState(state)
        if (overview.value) {
          overview.value.active_run = state
          overview.value.user_status = state.status === 'in_progress' ? 'in_progress' : 'ended'
          overview.value.today_best_floor = state.best_floor
        }
      }
      return {
        success: Boolean(res.data.success),
        message: String(res.data.message ?? ''),
        state: res.data.success ? (res.data.data as DailyChallengeState) : null,
      }
    } finally {
      isStartingChallenge.value = false
    }
  }

  async function submitAnswer(payload: {
    selected_option?: string
    selected_sequence?: string[]
    user_input?: string
    is_correct?: boolean
    answer_detail?: AnswerDetail
  }) {
    if (!displayedQuestion.value || isSubmittingAnswer.value) {
      return { success: false, message: '当前没有可提交的题目' }
    }

    isSubmittingAnswer.value = true
    try {
      const res = await request.post('/api/daily-challenge/answer', {
        question_id: displayedQuestion.value.question_id,
        ...payload,
      }, { timeout: 30000 })

      if (res.data.success) {
        const next = res.data.data as DailyChallengeState
        activeState.value = next
        answerResult.value = next.answer_result
        pendingState.value = next
        if (overview.value) {
          overview.value.active_run = next.status === 'in_progress' ? next : null
          overview.value.user_status = next.status === 'in_progress' ? 'in_progress' : 'ended'
          overview.value.today_best_floor = next.best_floor
        }
        void refreshLeaderboardInBackground()
      }

      return {
        success: Boolean(res.data.success),
        message: String(res.data.message ?? ''),
      }
    } finally {
      isSubmittingAnswer.value = false
    }
  }

  function continueAfterAnswer() {
    const next = pendingState.value
    if (!next) return
    displayedQuestion.value = cloneQuestion(next.question)
    answerResult.value = null
    pendingState.value = null
  }

  function clearActiveRun() {
    activeState.value = null
    displayedQuestion.value = null
    answerResult.value = null
    pendingState.value = null
  }

  return {
    overview,
    leaderboard,
    leaderboardDayKey,
    currentUserRank,
    currentUserEntry,
    activeState,
    displayedQuestion,
    answerResult,
    pendingState,
    secondsUntilReset,
    isLoadingOverview,
    isLoadingLeaderboard,
    isStartingChallenge,
    isSubmittingAnswer,
    hasActiveRun,
    canContinueCurrentQuestion,
    isEnded,
    stopCountdown,
    fetchOverview,
    fetchLeaderboard,
    startOrResume,
    submitAnswer,
    continueAfterAnswer,
    clearActiveRun,
  }
})
