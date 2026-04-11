<template>
  <BattleContainer
    ref="battleContainer"
    :question="combatStore.currentQuestion"
    :player-hp="displayPlayerHp"
    :enemy-hp="displayEnemyHp"
    :evaluation-mode="currentAnswerResult ? 'server' : 'client'"
    :answer-result="currentAnswerResult"
    @is-correct="handleAnswer"
    @continue="handleContinue"
  >
    <template #after-question>
      <div
        v-if="combatStore.currentQuestion"
        class="mt-2 flex flex-col gap-2 border-t border-gray-700/30 pt-2"
      >
        <div class="flex items-center justify-between px-2">
          <div class="flex gap-1" title="评分">
            <Icon
              v-for="star in 5"
              :key="star"
              :icon="star <= userRating ? 'mdi:star' : 'mdi:star-outline'"
              class="size-6 cursor-pointer text-yellow-500 transition-transform hover:scale-110"
              @click="rateQuestion(star)"
            />
          </div>
          <button
            class="cursor-pointer text-sm text-gray-500"
            @click="showFeedback = !showFeedback"
          >
            {{ showFeedback ? '取消' : '反馈' }}
          </button>
        </div>

        <div
          v-if="showFeedback"
          class="animate-in slide-in-from-top-2 fade-in flex gap-2 px-2 pb-2 duration-200"
        >
          <input
            v-model="feedbackContent"
            type="text"
            placeholder="请输入反馈..."
            class="flex-1 rounded-lg border border-gray-400 px-2 py-1 text-sm text-black transition-colors focus:outline-none"
            @keyup.enter="submitFeedback"
          />
          <Button class="rounded-lg" variant="outline" @click="submitFeedback">提交</Button>
        </div>
      </div>
    </template>
  </BattleContainer>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { useRouter } from 'vue-router'

import BattleContainer from '@/components/battle/BattleContainer.vue'
import type { BattleAnswerEvent, BattleContainerHandle } from '@/components/battle/types'
import { Button } from '@/components/ui/button'
import {
  useCombatStore,
  type AnswerDetail,
  type AnswerQuestionMeta,
  type CombatInfo,
  type Question,
  type QuestionContent0,
  type QuestionContent1,
  type QuestionContent2,
} from '@/stores/combat'
import { useNotificationStore } from '@/stores/notification'

const COMBAT_PENDING_SNAPSHOT_KEY = 'wordtower:combat-pending-snapshot'

const battleContainer = ref<BattleContainerHandle | null>(null)
const combatStore = useCombatStore()
const notificationStore = useNotificationStore()
const router = useRouter()

const displayPlayerHp = ref(0)
const displayEnemyHp = ref(0)
const isAnimatingTransition = ref(false)
const currentAnswerResult = ref<Record<string, unknown> | null>(null)

const userRating = ref(0)
const showFeedback = ref(false)
const feedbackContent = ref('')

interface PendingCombatSnapshot {
  levelId: number
  currentFloor: number
  combatInfo: CombatInfo
  question: Question
  answerResult: Record<string, unknown>
}

watch(
  () => combatStore.currentQuestion?.id,
  () => {
    userRating.value = 0
    showFeedback.value = false
    feedbackContent.value = ''
  },
)

watch(
  () => [combatStore.combatInfo?.player_hp, combatStore.combatInfo?.enemy_hp],
  () => {
    if (!isAnimatingTransition.value) {
      syncDisplayedHealth()
    }
  },
)

function syncDisplayedHealth() {
  displayPlayerHp.value = Math.max(0, combatStore.combatInfo?.player_hp ?? 0)
  displayEnemyHp.value = Math.max(0, combatStore.combatInfo?.enemy_hp ?? 0)
}

function normalizeAnswerEvent(payload: BattleAnswerEvent) {
  if (typeof payload === 'boolean') {
    return { isCorrect: payload, answerDetail: undefined }
  }

  return {
    isCorrect: payload.isCorrect,
    answerDetail: payload.answerDetail,
  }
}

function clearPendingSnapshot() {
  sessionStorage.removeItem(COMBAT_PENDING_SNAPSHOT_KEY)
}

function persistPendingSnapshot() {
  if (!combatStore.combatInfo || !combatStore.currentQuestion || !currentAnswerResult.value) return

  const snapshot: PendingCombatSnapshot = {
    levelId: combatStore.combatInfo.level_id,
    currentFloor: combatStore.combatInfo.current_floor,
    combatInfo: JSON.parse(JSON.stringify(combatStore.combatInfo)) as CombatInfo,
    question: JSON.parse(JSON.stringify(combatStore.currentQuestion)) as Question,
    answerResult: JSON.parse(JSON.stringify(currentAnswerResult.value)) as Record<string, unknown>,
  }
  sessionStorage.setItem(COMBAT_PENDING_SNAPSHOT_KEY, JSON.stringify(snapshot))
}

function restorePendingSnapshot(): boolean {
  if (!combatStore.combatInfo) return false

  const raw = sessionStorage.getItem(COMBAT_PENDING_SNAPSHOT_KEY)
  if (!raw) return false

  try {
    const snapshot = JSON.parse(raw) as PendingCombatSnapshot
    if (
      !snapshot ||
      snapshot.levelId !== combatStore.combatInfo.level_id ||
      snapshot.currentFloor !== combatStore.combatInfo.current_floor ||
      !snapshot.question ||
      !snapshot.answerResult
    ) {
      clearPendingSnapshot()
      return false
    }

    combatStore.combatInfo = snapshot.combatInfo
    combatStore.currentQuestion = snapshot.question
    currentAnswerResult.value = snapshot.answerResult
    syncDisplayedHealth()
    return true
  } catch {
    clearPendingSnapshot()
    return false
  }
}

function buildLocalAnswerResult(
  question: Question,
  isCorrect: boolean,
  answerDetail?: AnswerDetail,
): Record<string, unknown> {
  switch (question.type) {
    case 'context_guess': {
      const content = question.content as QuestionContent0
      const correctOption = String(answerDetail?.correct_option ?? content.correct_option ?? '')
      return {
        is_correct: isCorrect,
        detail: {
          ...answerDetail,
          correct_option: correctOption,
          correct_text:
            typeof answerDetail?.correct_text === 'string'
              ? answerDetail.correct_text
              : content.options?.[correctOption as keyof typeof content.options] ?? '',
          explanation:
            typeof answerDetail?.explanation === 'string'
              ? answerDetail.explanation
              : content.explanation ?? '',
        },
      }
    }
    case 'cloze_test': {
      const content = question.content as QuestionContent1
      return {
        is_correct: isCorrect,
        detail: {
          ...answerDetail,
          correct_sequence:
            Array.isArray(answerDetail?.correct_sequence) && answerDetail.correct_sequence.length > 0
              ? answerDetail.correct_sequence
              : content.correct_sequence ?? [],
          chinese_translation:
            typeof answerDetail?.chinese_translation === 'string'
              ? answerDetail.chinese_translation
              : content.chinese_translation ?? '',
        },
      }
    }
    case 'keyword_translation': {
      const content = question.content as QuestionContent2
      return {
        is_correct: isCorrect,
        detail: {
          ...answerDetail,
          reference_answer:
            typeof answerDetail?.reference_answer === 'string'
              ? answerDetail.reference_answer
              : content.reference_answer ?? '',
        },
      }
    }
    default:
      return {
        is_correct: isCorrect,
        detail: answerDetail ?? {},
      }
  }
}

function attachReviewHintToAnswerResult(question: Question, meta: AnswerQuestionMeta | null) {
  if (question.type !== 'context_guess' || !meta) return
  if (typeof meta.next_review_days !== 'number' || !Number.isFinite(meta.next_review_days)) return
  if (!currentAnswerResult.value) return

  const current = currentAnswerResult.value as { detail?: Record<string, unknown> }
  currentAnswerResult.value = {
    ...current,
    detail: {
      ...(current.detail ?? {}),
      next_review_days: meta.next_review_days,
      target_word:
        typeof meta.target_word === 'string' && meta.target_word.trim()
          ? meta.target_word
          : (question.content as QuestionContent0).target_word,
    },
  }
}

async function rateQuestion(rating: number) {
  userRating.value = rating
  if (!combatStore.currentQuestion) return

  await combatStore.ratingQuestion(combatStore.currentQuestion.id, rating)
  notificationStore.addNotification({
    title: '评分成功',
    description: '感谢你的反馈。',
  })
}

async function submitFeedback() {
  if (!feedbackContent.value.trim() || !combatStore.currentQuestion) return

  await combatStore.reportQuestion(combatStore.currentQuestion.id, feedbackContent.value)
  showFeedback.value = false
  feedbackContent.value = ''
  notificationStore.addNotification({
    title: '提交成功',
    description: '感谢你的反馈。',
  })
}

async function handleAnswer(payload: BattleAnswerEvent) {
  if (!combatStore.currentQuestion || !combatStore.combatInfo || isAnimatingTransition.value) {
    return
  }

  const { isCorrect, answerDetail } = normalizeAnswerEvent(payload)
  currentAnswerResult.value = buildLocalAnswerResult(
    combatStore.currentQuestion,
    isCorrect,
    answerDetail as AnswerDetail | undefined,
  )

  const answerMeta = await combatStore.answerQuestion(
    combatStore.currentQuestion.id,
    isCorrect,
    answerDetail as AnswerDetail | undefined,
  )
  attachReviewHintToAnswerResult(combatStore.currentQuestion, answerMeta)

  isAnimatingTransition.value = true

  if (isCorrect) {
    const nextEnemyHp = combatStore.combatInfo.enemy_hp - combatStore.combatInfo.player_attack
    const enemyDies = nextEnemyHp <= 0

    combatStore.combatInfo.enemy_hp = nextEnemyHp
    displayEnemyHp.value = Math.max(0, nextEnemyHp)
    persistPendingSnapshot()

    await battleContainer.value?.playPlayerAttack({
      nextEnemyHp,
      enemyDies,
    })
  } else {
    const nextPlayerHp = combatStore.combatInfo.player_hp - combatStore.combatInfo.enemy_attack
    const playerDies = nextPlayerHp <= 0

    combatStore.combatInfo.player_hp = nextPlayerHp
    displayPlayerHp.value = Math.max(0, nextPlayerHp)
    persistPendingSnapshot()

    await battleContainer.value?.playEnemyAttack({
      nextPlayerHp,
      playerDies,
    })

    if (playerDies) {
      clearPendingSnapshot()
      currentAnswerResult.value = null
      await combatStore.EndCombat()
      await router.push({ name: 'checkout' })
      isAnimatingTransition.value = false
      return
    }
  }

  isAnimatingTransition.value = false
  syncDisplayedHealth()
}

async function handleContinue() {
  if (!combatStore.combatInfo) return

  battleContainer.value?.cancelActiveAnimation()
  isAnimatingTransition.value = false

  const enemyDefeated = combatStore.combatInfo.enemy_hp <= 0
  clearPendingSnapshot()
  currentAnswerResult.value = null

  if (enemyDefeated) {
    await combatStore.CompleteCombat()
    await combatStore.StartCombat()
  }

  await combatStore.fetchQuestion()
  syncDisplayedHealth()
  await nextTick()

  if (enemyDefeated) {
    battleContainer.value?.respawnEnemy()
  }
}

async function initializeCombat() {
  await combatStore.StartCombat()
  if (!restorePendingSnapshot()) {
    currentAnswerResult.value = null
    syncDisplayedHealth()
    await combatStore.fetchQuestion()
  }
  await nextTick()
  battleContainer.value?.enterBattlefield()
}

onMounted(() => {
  void initializeCombat()
})
</script>
