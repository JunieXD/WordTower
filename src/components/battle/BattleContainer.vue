<template>
  <div class="flex h-full flex-col overflow-hidden">
    <div
      class="h-1/3 shrink-0 bg-cover bg-center sm:bg-contain"
      :style="{ backgroundImage: `url(${dungeonBackground})` }"
    >
      <div class="flex h-full flex-col">
        <div class="px-4 pt-4 text-white">
          <slot name="battle-top">
            <div
              v-if="modeLabel || auxiliaryLabel"
              class="flex items-center justify-between gap-3"
            >
              <div
                v-if="modeLabel"
                class="rounded-full bg-black/30 px-3 py-1 text-xs backdrop-blur-sm"
              >
                {{ modeLabel }}
              </div>
              <div
                v-if="auxiliaryLabel"
                class="rounded-full bg-black/30 px-3 py-1 text-xs backdrop-blur-sm"
              >
                {{ auxiliaryLabel }}
              </div>
            </div>
          </slot>
        </div>

        <div class="flex-1" />

        <div class="flex h-3/10 flex-row">
          <div
            ref="player"
            :class="playerHidden ? 'hidden' : null"
            class="flex w-1/4 flex-col items-center justify-end"
          >
            <div class="flex items-center justify-center gap-1">
              <Icon icon="mdi:cards-heart" class="size-4 text-red-500" />
              <div class="text-sm font-bold text-red-500">{{ safePlayerHp }}</div>
            </div>
            <img :src="currentPlayerAnimation" class="h-full object-contain" />
          </div>

          <div class="w-1/4" />

          <div
            ref="enemy"
            :class="enemyHidden ? 'hidden' : null"
            class="flex w-2/4 flex-col items-center justify-end"
          >
            <div class="flex items-center justify-center gap-1">
              <Icon icon="mdi:cards-heart" class="size-4 text-red-500" />
              <div class="text-sm font-bold text-red-500">{{ safeEnemyHp }}</div>
            </div>
            <img :src="currentEnemyAnimation" class="h-full scale-x-[-1] object-contain" />
          </div>
        </div>

        <div class="h-1/10" />
      </div>
    </div>

    <div class="h-2" />

    <div class="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
      <slot name="summary" />

      <template v-if="showQuestion">
        <component
          :is="currentQuestionComponent"
          :question="question"
          :evaluation-mode="evaluationMode"
          :answer-result="answerResult"
          :is-submitting="isSubmitting"
          @is-correct="emit('isCorrect', $event)"
          @submit="emit('submit', $event)"
          @continue="emit('continue')"
        />
        <slot name="after-question" />
      </template>

      <slot v-else />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Component } from 'vue'
import { Icon } from '@iconify/vue'
import gsap from 'gsap'

import Loading from '@/components/Question/Loading.vue'
import QuestionChoice from '@/components/Question/QuestionChoice.vue'
import QuestionInput from '@/components/Question/QuestionInput.vue'
import QuestionSort from '@/components/Question/QuestionSort.vue'
import dungeonBackground from '@/assets/background/dungeon.jpg'
import playerIdleAnimationSrc from '@/assets/character/Elf/Idle.gif'
import playerWalkAnimationSrc from '@/assets/character/Elf/Walk.gif'
import playerAttackAnimationSrc from '@/assets/character/Elf/Attack.gif'
import playerHurtAnimationSrc from '@/assets/character/Elf/Hurt.gif'
import playerDeathAnimationSrc from '@/assets/character/Elf/Death.gif'
import enemyIdleAnimationSrc from '@/assets/character/DemonKin/Idle.gif'
import enemyWalkAnimationSrc from '@/assets/character/DemonKin/Walk.gif'
import enemyAttackAnimationSrc from '@/assets/character/DemonKin/Attack.gif'
import enemyHurtAnimationSrc from '@/assets/character/DemonKin/Hurt.gif'
import enemyDeathAnimationSrc from '@/assets/character/DemonKin/Death.gif'
import type {
  BattleAnswerEvent,
  BattleContainerHandle,
  BattleEvaluationMode,
  BattleRenderableQuestion,
  BattleSubmitPayload,
} from '@/components/battle/types'
import type { QuestionType } from '@/stores/combat'

const props = withDefaults(
  defineProps<{
    question?: BattleRenderableQuestion | null
    playerHp: number
    enemyHp: number
    showQuestion?: boolean
    isSubmitting?: boolean
    answerResult?: Record<string, unknown> | null
    evaluationMode?: BattleEvaluationMode
    modeLabel?: string
    auxiliaryLabel?: string
  }>(),
  {
    question: null,
    showQuestion: true,
    isSubmitting: false,
    answerResult: null,
    evaluationMode: 'client',
    modeLabel: '',
    auxiliaryLabel: '',
  },
)

const emit = defineEmits<{
  isCorrect: [payload: BattleAnswerEvent]
  submit: [payload: BattleSubmitPayload]
  continue: []
}>()

const componentMap: Record<QuestionType | 'loading', Component> = {
  context_guess: QuestionChoice,
  cloze_test: QuestionSort,
  keyword_translation: QuestionInput,
  loading: Loading,
}

const player = ref<HTMLDivElement | null>(null)
const enemy = ref<HTMLDivElement | null>(null)
const activeBattleTimeline = ref<gsap.core.Timeline | null>(null)
const activeBattleResolve = ref<(() => void) | null>(null)

const playerHidden = ref(false)
const enemyHidden = ref(false)

const currentPlayerAnimation = ref(playerWalkAnimationSrc)
const currentEnemyAnimation = ref(enemyIdleAnimationSrc)

const safePlayerHp = computed(() => Math.max(0, props.playerHp))
const safeEnemyHp = computed(() => Math.max(0, props.enemyHp))

const currentQuestionComponent = computed(() => {
  const type = props.question?.type ?? 'loading'
  return componentMap[type as QuestionType] ?? Loading
})

function resetTransforms() {
  if (activeBattleTimeline.value) {
    activeBattleTimeline.value.kill()
    activeBattleTimeline.value = null
  }
  if (activeBattleResolve.value) {
    const resolve = activeBattleResolve.value
    activeBattleResolve.value = null
    resolve()
  }
  if (player.value) {
    gsap.killTweensOf(player.value)
    gsap.set(player.value, { x: 0 })
  }
  if (enemy.value) {
    gsap.killTweensOf(enemy.value)
    gsap.set(enemy.value, { x: 0 })
  }
}

function cancelActiveAnimation() {
  resetTransforms()
  if (!playerHidden.value) {
    currentPlayerAnimation.value = playerIdleAnimationSrc
  }
  if (!enemyHidden.value) {
    currentEnemyAnimation.value = enemyIdleAnimationSrc
  }
}

function respawnPlayer() {
  playerHidden.value = false
  currentPlayerAnimation.value = playerWalkAnimationSrc
  if (!player.value) return

  gsap.killTweensOf(player.value)
  gsap.fromTo(
    player.value,
    { x: -window.innerWidth * 0.25 },
    {
      x: 0,
      duration: 1,
      ease: 'power1.out',
      onComplete: () => {
        currentPlayerAnimation.value = playerIdleAnimationSrc
      },
    },
  )
}

function respawnEnemy() {
  enemyHidden.value = false
  currentEnemyAnimation.value = enemyWalkAnimationSrc
  if (!enemy.value) return

  gsap.killTweensOf(enemy.value)
  gsap.fromTo(
    enemy.value,
    { x: window.innerWidth * 0.5 },
    {
      x: 0,
      duration: 1,
      ease: 'power1.out',
      onComplete: () => {
        currentEnemyAnimation.value = enemyIdleAnimationSrc
      },
    },
  )
}

function enterBattlefield() {
  resetTransforms()
  respawnPlayer()
  respawnEnemy()
}

function playPlayerAttack(options: { nextEnemyHp: number; enemyDies: boolean }) {
  return new Promise<void>((resolve) => {
    resetTransforms()
    activeBattleResolve.value = () => {
      if (activeBattleResolve.value) {
        activeBattleResolve.value = null
      }
      resolve()
    }
    const timeline = gsap.timeline({
      onComplete: () => {
        if (activeBattleTimeline.value === timeline) {
          activeBattleTimeline.value = null
        }
        if (activeBattleResolve.value) {
          const finish = activeBattleResolve.value
          activeBattleResolve.value = null
          finish()
          return
        }
        resolve()
      },
    })
    activeBattleTimeline.value = timeline

    timeline.call(() => {
      currentPlayerAnimation.value = playerAttackAnimationSrc
    })

    timeline.call(
      () => {
        currentEnemyAnimation.value = enemyHurtAnimationSrc
      },
      undefined,
      0.5,
    )

    timeline.call(
      () => {
        currentPlayerAnimation.value = playerIdleAnimationSrc
      },
      undefined,
      0.8,
    )

    timeline.call(
      () => {
        currentEnemyAnimation.value = options.enemyDies
          ? enemyDeathAnimationSrc
          : enemyIdleAnimationSrc
      },
      undefined,
      0.9,
    )

    if (options.enemyDies) {
      timeline.call(
        () => {
          enemyHidden.value = true
        },
        undefined,
        1.8,
      )
    }
  })
}

function playEnemyAttack(options: { nextPlayerHp: number; playerDies: boolean }) {
  return new Promise<void>((resolve) => {
    resetTransforms()
    activeBattleResolve.value = () => {
      if (activeBattleResolve.value) {
        activeBattleResolve.value = null
      }
      resolve()
    }
    const timeline = gsap.timeline({
      onComplete: () => {
        if (activeBattleTimeline.value === timeline) {
          activeBattleTimeline.value = null
        }
        if (activeBattleResolve.value) {
          const finish = activeBattleResolve.value
          activeBattleResolve.value = null
          finish()
          return
        }
        resolve()
      },
    })
    activeBattleTimeline.value = timeline

    timeline.call(() => {
      currentEnemyAnimation.value = enemyWalkAnimationSrc
    })

    timeline.to(
      enemy.value,
      {
        x: -window.innerWidth * 0.5,
        duration: 0.5,
        ease: 'power1.out',
      },
      0,
    )

    timeline.call(
      () => {
        currentEnemyAnimation.value = enemyAttackAnimationSrc
      },
      undefined,
      0.5,
    )

    timeline.call(
      () => {
        currentPlayerAnimation.value = playerHurtAnimationSrc
      },
      undefined,
      1,
    )

    timeline.call(
      () => {
        currentEnemyAnimation.value = enemyIdleAnimationSrc
        currentPlayerAnimation.value = options.playerDies
          ? playerDeathAnimationSrc
          : playerIdleAnimationSrc
      },
      undefined,
      1.4,
    )

    timeline.to(
      enemy.value,
      {
        x: 0,
        duration: 0.5,
        ease: 'power1.out',
      },
      1.5,
    )

    if (options.playerDies) {
      timeline.call(
        () => {
          playerHidden.value = true
        },
        undefined,
        2.3,
      )
    }
  })
}

defineExpose<BattleContainerHandle>({
  enterBattlefield,
  respawnPlayer,
  respawnEnemy,
  cancelActiveAnimation,
  playPlayerAttack,
  playEnemyAttack,
})
</script>
