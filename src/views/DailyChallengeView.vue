<template>
  <BattleContainer
    ref="battleContainer"
    :question="questionForRender"
    :player-hp="displayPlayerHp"
    :enemy-hp="displayEnemyHp"
    :show-question="showQuestionPanel"
    :evaluation-mode="'server'"
    :answer-result="answerResultForRender"
    :is-submitting="isSubmittingAnswer"
    @submit="handleSubmit"
    @continue="handleContinue"
  >
    <template #battle-top>
      <div class="flex items-center justify-between gap-3">
        <div class="rounded-full bg-black/30 px-3 py-1 text-xs backdrop-blur-sm">每日挑战</div>
        <div class="rounded-full bg-black/30 px-3 py-1 text-xs backdrop-blur-sm">
          距刷新 {{ countdownText }}
        </div>
      </div>
    </template>

    <Card v-if="isBootstrapping || isLoadingOverview || isStartingChallenge">
      <CardContent class="flex min-h-48 items-center justify-center text-sm text-muted-foreground">
        正在加载每日挑战...
      </CardContent>
    </Card>

    <Card v-else-if="loadErrorMessage">
      <CardContent class="flex min-h-56 flex-col items-center justify-center gap-4 text-center">
        <div class="text-lg font-semibold">加载失败</div>
        <p class="max-w-md text-sm text-muted-foreground">{{ loadErrorMessage }}</p>
        <div class="flex gap-3">
          <Button variant="outline" @click="bootstrapDailyChallenge">重新加载</Button>
          <Button @click="router.push({ name: 'home' })">返回首页</Button>
        </div>
      </CardContent>
    </Card>

    <Card v-else-if="!displayedQuestion && !canContinueCurrentQuestion">
      <CardContent class="flex min-h-56 flex-col items-center justify-center gap-4 text-center">
        <div class="text-lg font-semibold">{{ statusLabel }}</div>
        <p class="max-w-md text-sm text-muted-foreground">
          {{
            canStartFromEndedState
              ? '当前没有可继续的题目，请返回首页重新进入每日挑战。'
              : '你今天的每日挑战已经结束，明日 6 点会刷新新的题组。'
          }}
        </p>
        <Button @click="router.push({ name: 'home' })">返回首页</Button>
      </CardContent>
    </Card>

    <template v-else-if="canContinueCurrentQuestion && !displayedQuestion">
      <Card>
        <CardContent class="flex flex-col items-center justify-center gap-4 py-10 text-center">
          <div class="text-lg font-semibold">{{ statusLabel }}</div>
          <p class="text-sm text-muted-foreground">
            {{
              activeState?.status === 'completed_exhausted'
                ? '今日题目已经全部打通。'
                : '本次每日挑战已经结束，成绩已计入今日榜单。'
            }}
          </p>
          <Button @click="router.push({ name: 'home' })">返回首页</Button>
        </CardContent>
      </Card>
    </template>
  </BattleContainer>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'

import BattleContainer from '@/components/battle/BattleContainer.vue'
import type { BattleContainerHandle, BattleSubmitPayload } from '@/components/battle/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { useDailyChallengeStore } from '@/stores/dailyChallenge'
import { useNotificationStore } from '@/stores/notification'
import type { QuestionContent0, QuestionContent1 } from '@/stores/combat'

const battleContainer = ref<BattleContainerHandle | null>(null)
const router = useRouter()
const notificationStore = useNotificationStore()
const dailyChallengeStore = useDailyChallengeStore()

const {
  overview,
  activeState,
  displayedQuestion,
  answerResult,
  pendingState,
  secondsUntilReset,
  isLoadingOverview,
  isStartingChallenge,
  isSubmittingAnswer,
  canContinueCurrentQuestion,
} = storeToRefs(dailyChallengeStore)

const isBootstrapping = ref(true)
const loadErrorMessage = ref('')
const isAnimatingTransition = ref(false)
const optimisticAnswerResult = ref<Record<string, unknown> | null>(null)

const displayPlayerHp = ref(100)
const displayEnemyHp = ref(30)

const healEveryFloors = computed(() => activeState.value?.heal_every_floors ?? 5)
const healAmount = computed(() => activeState.value?.heal_amount ?? 50)

const questionForRender = computed(() => displayedQuestion.value ?? undefined)
const answerResultForRender = computed(
  () => answerResult.value ?? optimisticAnswerResult.value ?? undefined,
)
const showQuestionPanel = computed(() => {
  if (isBootstrapping.value || isLoadingOverview.value || isStartingChallenge.value) return false
  if (loadErrorMessage.value) return false
  if (!displayedQuestion.value && !canContinueCurrentQuestion.value) return false
  if (canContinueCurrentQuestion.value && !displayedQuestion.value) return false
  return true
})

const statusLabel = computed(() => {
  if (activeState.value?.status === 'dead') return '今日已结束'
  if (activeState.value?.status === 'completed_exhausted') return '今日已通关'
  if (activeState.value?.status === 'in_progress') return '挑战进行中'
  if (overview.value?.user_status === 'ended') return '今日已结束'
  return '准备开始'
})

const canStartFromEndedState = computed(() => {
  if (!overview.value) return false
  return overview.value.user_status !== 'ended' || Boolean(overview.value.active_run)
})

const countdownText = computed(() => {
  const total = secondsUntilReset.value
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  return [hours, minutes, seconds].map((value) => String(value).padStart(2, '0')).join(':')
})

const questionIdentity = computed(
  () =>
    `${displayedQuestion.value?.question_id ?? 'none'}-${displayedQuestion.value?.floor ?? 0}-${displayedQuestion.value?.question_index ?? 0}`,
)

function syncDisplayedHealth() {
  displayPlayerHp.value = Math.max(0, activeState.value?.current_hp ?? 0)
  displayEnemyHp.value = Math.max(0, activeState.value?.current_enemy_hp ?? 0)
}

function predictObjectiveAnswer(payload: BattleSubmitPayload) {
  if (!activeState.value || !displayedQuestion.value) return null

  if (displayedQuestion.value.type === 'context_guess') {
    const content = displayedQuestion.value.content as QuestionContent0
    const selectedOption = (payload.selected_option ?? '').trim().toUpperCase()
    const correctOption = String(content.correct_option ?? '').trim().toUpperCase()
    const isCorrect = selectedOption === correctOption

    if (isCorrect) {
      const nextEnemyHp = Math.max(0, activeState.value.current_enemy_hp - activeState.value.player_attack)
      return {
        isCorrect: true,
        nextEnemyHp,
        enemyDies: nextEnemyHp <= 0,
        answerDetail: {
          selected_option: selectedOption,
          selected_text: content.options?.[selectedOption as keyof typeof content.options] ?? '',
          correct_option: correctOption,
          correct_text: content.options?.[correctOption as keyof typeof content.options] ?? '',
          explanation: content.explanation ?? '',
        },
        answerResult: {
          is_correct: true,
          detail: {
            selected_option: selectedOption,
            selected_text: content.options?.[selectedOption as keyof typeof content.options] ?? '',
            correct_option: correctOption,
            correct_text: content.options?.[correctOption as keyof typeof content.options] ?? '',
            explanation: content.explanation ?? '',
          },
        },
      } as const
    }

    const nextPlayerHp = Math.max(0, activeState.value.current_hp - activeState.value.enemy_attack)
    return {
      isCorrect: false,
      nextPlayerHp,
      playerDies: nextPlayerHp <= 0,
      answerDetail: {
        selected_option: selectedOption,
        selected_text: content.options?.[selectedOption as keyof typeof content.options] ?? '',
        correct_option: correctOption,
        correct_text: content.options?.[correctOption as keyof typeof content.options] ?? '',
        explanation: content.explanation ?? '',
      },
      answerResult: {
        is_correct: false,
        detail: {
          selected_option: selectedOption,
          selected_text: content.options?.[selectedOption as keyof typeof content.options] ?? '',
          correct_option: correctOption,
          correct_text: content.options?.[correctOption as keyof typeof content.options] ?? '',
          explanation: content.explanation ?? '',
        },
      },
    } as const
  }

  if (displayedQuestion.value.type === 'cloze_test') {
    const content = displayedQuestion.value.content as QuestionContent1
    const selectedSequence = payload.selected_sequence ?? []
    const correctSequence = content.correct_sequence ?? []
    const isCorrect =
      selectedSequence.length === correctSequence.length &&
      selectedSequence.every((word, index) => word === correctSequence[index])

    if (isCorrect) {
      const nextEnemyHp = Math.max(0, activeState.value.current_enemy_hp - activeState.value.player_attack)
      return {
        isCorrect: true,
        nextEnemyHp,
        enemyDies: nextEnemyHp <= 0,
        answerDetail: {
          selected_sequence: selectedSequence,
          correct_sequence: correctSequence,
          shuffled_options: content.shuffled_options ?? [],
          chinese_translation: content.chinese_translation ?? '',
        },
        answerResult: {
          is_correct: true,
          detail: {
            selected_sequence: selectedSequence,
            correct_sequence: correctSequence,
            chinese_translation: content.chinese_translation ?? '',
          },
        },
      } as const
    }

    const nextPlayerHp = Math.max(0, activeState.value.current_hp - activeState.value.enemy_attack)
    return {
      isCorrect: false,
      nextPlayerHp,
      playerDies: nextPlayerHp <= 0,
      answerDetail: {
        selected_sequence: selectedSequence,
        correct_sequence: correctSequence,
        shuffled_options: content.shuffled_options ?? [],
        chinese_translation: content.chinese_translation ?? '',
      },
      answerResult: {
        is_correct: false,
        detail: {
          selected_sequence: selectedSequence,
          correct_sequence: correctSequence,
          chinese_translation: content.chinese_translation ?? '',
        },
      },
    } as const
  }

  return null
}

async function bootstrapDailyChallenge() {
  isBootstrapping.value = true
  loadErrorMessage.value = ''

  try {
    await dailyChallengeStore.fetchOverview()

    if (!activeState.value && overview.value?.user_status !== 'ended') {
      const result = await dailyChallengeStore.startOrResume()
      if (!result.success && result.message) {
        loadErrorMessage.value = result.message
        notificationStore.addNotification({
          title: '每日挑战',
          description: result.message,
          variant: 'destructive',
          duration: 3000,
        })
      }
    }

    syncDisplayedHealth()
    await nextTick()
    if (displayedQuestion.value) {
      battleContainer.value?.enterBattlefield()
    }
  } catch (error) {
    console.error('加载每日挑战失败:', error)
    loadErrorMessage.value = '每日挑战加载失败，请稍后重试'
    notificationStore.addNotification({
      title: '每日挑战',
      description: loadErrorMessage.value,
      variant: 'destructive',
      duration: 3000,
    })
  } finally {
    isBootstrapping.value = false
  }
}

async function handleSubmit(payload: BattleSubmitPayload) {
  if (!activeState.value || isAnimatingTransition.value) return

  const beforeFloor = activeState.value.current_floor
  const predictedObjectiveResult = predictObjectiveAnswer(payload)

  let optimisticAnimation: Promise<void> | null = null
  if (predictedObjectiveResult) {
    optimisticAnswerResult.value = predictedObjectiveResult.answerResult
    isAnimatingTransition.value = true

    if (predictedObjectiveResult.isCorrect) {
      displayEnemyHp.value = predictedObjectiveResult.nextEnemyHp
      optimisticAnimation =
        battleContainer.value?.playPlayerAttack({
          nextEnemyHp: predictedObjectiveResult.nextEnemyHp,
          enemyDies: predictedObjectiveResult.enemyDies,
        }) ?? null
    } else {
      displayPlayerHp.value = predictedObjectiveResult.nextPlayerHp
      optimisticAnimation =
        battleContainer.value?.playEnemyAttack({
          nextPlayerHp: predictedObjectiveResult.nextPlayerHp,
          playerDies: predictedObjectiveResult.playerDies,
        }) ?? null
    }
  }

  const submitPayload = predictedObjectiveResult
    ? {
        ...payload,
        is_correct: predictedObjectiveResult.isCorrect,
        answer_detail: predictedObjectiveResult.answerDetail,
      }
    : payload

  const result = await dailyChallengeStore.submitAnswer(submitPayload)

  if (!result.success) {
    optimisticAnswerResult.value = null
    isAnimatingTransition.value = false
    syncDisplayedHealth()
    notificationStore.addNotification({
      title: '提交失败',
      description: result.message || '请稍后重试',
      variant: 'destructive',
      duration: 3000,
    })
    return
  }

  if (!answerResult.value || !pendingState.value) return

  if (optimisticAnimation) {
    await optimisticAnimation
    optimisticAnswerResult.value = null
    isAnimatingTransition.value = false
    syncDisplayedHealth()
    return
  }

  isAnimatingTransition.value = true

  if (answerResult.value.is_correct) {
    const enemyDies =
      pendingState.value.status === 'completed_exhausted' ||
      pendingState.value.current_floor > beforeFloor

    displayEnemyHp.value = enemyDies ? 0 : pendingState.value.current_enemy_hp

    await battleContainer.value?.playPlayerAttack({
      nextEnemyHp: displayEnemyHp.value,
      enemyDies,
    })
  } else {
    const playerDies = pendingState.value.status === 'dead'
    displayPlayerHp.value = playerDies ? 0 : pendingState.value.current_hp

    await battleContainer.value?.playEnemyAttack({
      nextPlayerHp: displayPlayerHp.value,
      playerDies,
    })
  }

  isAnimatingTransition.value = false
  syncDisplayedHealth()
}

async function handleContinue() {
  battleContainer.value?.cancelActiveAnimation()
  isAnimatingTransition.value = false

  optimisticAnswerResult.value = null
  const previousFloor = displayedQuestion.value?.floor
  dailyChallengeStore.continueAfterAnswer()
  await nextTick()

  if (!displayedQuestion.value) return

  syncDisplayedHealth()

  if (previousFloor !== activeState.value?.current_floor) {
    battleContainer.value?.respawnEnemy()
  }
}

watch(questionIdentity, async () => {
  if (isBootstrapping.value || answerResult.value || isAnimatingTransition.value) return
  optimisticAnswerResult.value = null
  await nextTick()
  syncDisplayedHealth()
})

onMounted(() => {
  void bootstrapDailyChallenge()
})
</script>
