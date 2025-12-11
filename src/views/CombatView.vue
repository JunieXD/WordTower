<template>
  <div class="flex flex-col h-full overflow-hidden">
    <!-- 战斗区域 -->
    <div
      class="h-1/3 shrink-0 flex flex-col bg-cover sm:bg-contain bg-center"
      :style="{ backgroundImage: `url(${dungeonBackground})` }"
    >
      <div class="h-6/10"></div>
      <div class="h-3/10 flex flex-row">
        <div ref="player" :class="playerHide" class="w-1/4 flex flex-col justify-end items-center">
          <div class="flex flex-row justify-center items-center">
            <Icon icon="mdi:cards-heart" class="text-red-500 size-4"></Icon>
            <div class="text-sm text-red-500 font-bold">
              {{
                (combatStore.combatInfo?.player_hp ?? 0) < 0 ? 0 : combatStore.combatInfo?.player_hp
              }}
            </div>
          </div>
          <img :src="currentPlayerAnimation" class="object-contain h-full" />
        </div>
        <div class="w-1/4"></div>
        <div ref="enemy" :class="enemyHide" class="w-2/4 flex flex-col justify-end items-center">
          <div class="flex flex-row justify-center items-center">
            <Icon icon="mdi:cards-heart" class="text-red-500 size-4"></Icon>
            <div class="text-sm text-red-500 font-bold">
              {{
                (combatStore.combatInfo?.enemy_hp ?? 0) < 0 ? 0 : combatStore.combatInfo?.enemy_hp
              }}
            </div>
          </div>
          <img :src="currentEnemyAnimation" class="object-contain h-full transform scale-x-[-1]" />
        </div>
      </div>
      <div class="h-1/10"></div>
    </div>
    <div class="h-2"></div>
    <!-- 答题区域 -->
    <div class="flex-1 min-h-0 flex flex-col p-4 gap-4 overflow-y-auto">
      <component
        :is="conponentMap[combatStore.currentQuestion?.type ?? 'loading']"
        :question="combatStore.currentQuestion"
        @is-correct="handleIsCorrect"
        @continue="handleContinue"
      ></component>
      <!--反馈区域-->
      <div
        v-if="combatStore.currentQuestion"
        class="mt-2 pt-2 border-t border-gray-700/30 flex flex-col gap-2"
      >
        <div class="flex items-center justify-between px-2">
          <div class="flex gap-1" title="评分">
            <Icon
              v-for="i in 5"
              :key="i"
              :icon="i <= userRating ? 'mdi:star' : 'mdi:star-outline'"
              class="size-6 cursor-pointer text-yellow-500 hover:scale-110 transition-transform"
              @click="rateQuestion(i)"
            />
          </div>
          <button
            @click="showFeedback = !showFeedback"
            class="text-sm text-gray-500 cursor-pointer"
          >
            {{ showFeedback ? '取消' : '反馈' }}
          </button>
        </div>

        <div
          v-if="showFeedback"
          class="flex gap-2 px-2 pb-2 animate-in slide-in-from-top-2 fade-in duration-200"
        >
          <input
            v-model="feedbackContent"
            type="text"
            placeholder="请输入反馈..."
            class="flex-1 rounded-lg px-2 py-1 text-sm text-black border border-gray-400 focus:outline-none transition-colors"
            @keyup.enter="submitFeedback"
          />
          <Button @click="submitFeedback" variant="outline" class="rounded-lg">提交</Button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { ref, onMounted, onBeforeMount, watch } from 'vue'
import type { Component } from 'vue'
import gsap from 'gsap'
import { useRouter } from 'vue-router'
import { useCombatStore, type QuestionType } from '@/stores/combat'
import QuestionChoice from '@/components/Question/QuestionChoice.vue'
import QuestionInput from '@/components/Question/QuestionInput.vue'
import QuestionSort from '@/components/Question/QuestionSort.vue'
import Loading from '@/components/Question/Loading.vue'
import { Button } from '@/components/ui/button'
import dungeonBackground from '@/assets/background/dungeon.jpg'
import { useNotificationStore } from '@/stores/notification'

// 角色动画资源使用 import，确保在构建时被打包
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

const conponentMap: Record<QuestionType | 'loading', Component> = {
  context_guess: QuestionChoice,
  cloze_test: QuestionSort,
  keyword_translation: QuestionInput,
  loading: Loading,
}

const player = ref<HTMLImageElement | null>(null)
const playerIdleAnimation = playerIdleAnimationSrc
const playerWalkAnimation = playerWalkAnimationSrc
const playerAttackAnimation = playerAttackAnimationSrc
const playerHurtAnimation = playerHurtAnimationSrc
const playerDeathAnimation = playerDeathAnimationSrc
const playerHide = ref<string | null>(null)
const currentPlayerAnimation = ref(playerWalkAnimation)

const enemy = ref<HTMLImageElement | null>(null)
const enemyIdleAnimation = enemyIdleAnimationSrc
const enemyWalkAnimation = enemyWalkAnimationSrc
const enemyAttackAnimation = enemyAttackAnimationSrc
const enemyHurtAnimation = enemyHurtAnimationSrc
const enemyDeathAnimation = enemyDeathAnimationSrc
const enemyHide = ref<string | null>(null)
const currentEnemyAnimation = ref(enemyIdleAnimation)

const combatStore = useCombatStore()
const router = useRouter()
const notificationStore = useNotificationStore()

const userRating = ref(0)
const showFeedback = ref(false)
const feedbackContent = ref('')

watch(
  () => combatStore.currentQuestion?.id,
  () => {
    userRating.value = 0
    showFeedback.value = false
    feedbackContent.value = ''
  },
)

const rateQuestion = async (rating: number) => {
  userRating.value = rating
  if (combatStore.currentQuestion) {
    await combatStore.ratingQuestion(combatStore.currentQuestion.id, rating)
    notificationStore.addNotification({
      title: '评分成功',
      description: '感谢您的反馈！',
    })
  }
}

const submitFeedback = async () => {
  if (!feedbackContent.value.trim() || !combatStore.currentQuestion) return
  await combatStore.reportQuestion(combatStore.currentQuestion.id, feedbackContent.value)
  showFeedback.value = false
  feedbackContent.value = ''
  notificationStore.addNotification({
    title: '提交成功',
    description: '感谢您的反馈！',
  })
}

const handleIsCorrect = async (isCorrect: boolean) => {
  if (combatStore.currentQuestion) {
    void combatStore.answerQuestion(combatStore.currentQuestion.id, isCorrect)
  }

  if (isCorrect) {
    playerAttack()
  } else {
    await enemyAttack()
    if (combatStore.combatInfo) {
      if (combatStore.combatInfo.player_hp <= 0) {
        await combatStore.EndCombat()
        router.push({ name: 'checkout' })
      }
    }
  }
}

const handleContinue = async () => {
  if (combatStore.combatInfo) {
    if (combatStore.combatInfo.enemy_hp <= 0) {
      // 完成本次挑战，继续下一层
      await combatStore.CompleteCombat()
      await combatStore.StartCombat()
      playerInit()
      enemyInit()
    }
  }
  combatStore.fetchQuestion()
}

const playerInit = () => {
  playerHide.value = null
  currentPlayerAnimation.value = playerWalkAnimation
  gsap.from(player.value, {
    x: -window.innerWidth * 0.25,
    duration: 1,
    ease: 'power1.out',
    onComplete: () => {
      currentPlayerAnimation.value = playerIdleAnimation
    },
  })
}

const playerAttack = () => {
  const tl = gsap.timeline()
  // 玩家攻击开始
  tl.call(
    () => {
      currentPlayerAnimation.value = playerAttackAnimation
    },
    undefined,
    0,
  )
  // 敌人受伤开始
  tl.call(
    () => {
      currentEnemyAnimation.value = enemyHurtAnimation
      if (combatStore.combatInfo) {
        combatStore.combatInfo.enemy_hp -= combatStore.combatInfo.player_attack
      }
    },
    undefined,
    0.5,
  )
  // 玩家攻击结束
  tl.call(
    () => {
      currentPlayerAnimation.value = playerIdleAnimation
    },
    undefined,
    0.8,
  )
  // 敌人受伤结束
  tl.call(
    () => {
      currentEnemyAnimation.value = enemyIdleAnimation
    },
    undefined,
    0.9,
  )
  // 敌人死亡开始
  tl.call(
    () => {
      if ((combatStore.combatInfo?.enemy_hp ?? 100) <= 0) {
        currentEnemyAnimation.value = enemyDeathAnimation
      }
    },
    undefined,
    1,
  )
  // 敌人死亡结束
  tl.call(
    () => {
      if ((combatStore.combatInfo?.enemy_hp ?? 100) <= 0) {
        enemyHide.value = 'hidden'
      }
    },
    undefined,
    1.8,
  )
}

const enemyInit = () => {
  enemyHide.value = null
  currentEnemyAnimation.value = enemyWalkAnimation
  gsap.from(enemy.value, {
    x: window.innerWidth * 0.5,
    duration: 1,
    ease: 'power1.out',
    onComplete: () => {
      currentEnemyAnimation.value = enemyIdleAnimation
    },
  })
}

const enemyAttack = () => {
  return new Promise<void>((resolve) => {
    const tl = gsap.timeline({ onComplete: resolve })
    // 敌人变更为走路状态，同时开始移动
    tl.call(
      () => {
        currentEnemyAnimation.value = enemyWalkAnimation
      },
      undefined,
      0,
    )
    tl.to(
      enemy.value,
      {
        x: -window.innerWidth * 0.5,
        duration: 0.5,
        ease: 'power1.out',
      },
      0,
    )
    // 移动刚结束，立即切换攻击动作
    tl.call(
      () => {
        currentEnemyAnimation.value = enemyAttackAnimation
      },
      undefined,
      0.5,
    )
    // 玩家显示受伤
    tl.call(
      () => {
        currentPlayerAnimation.value = playerHurtAnimation
        if (combatStore.combatInfo) {
          combatStore.combatInfo.player_hp -= combatStore.combatInfo.enemy_attack
        }
      },
      undefined,
      1,
    )
    // 攻击动作完成，双方恢复待机
    tl.call(
      () => {
        currentEnemyAnimation.value = enemyIdleAnimation
      },
      undefined,
      1.4,
    )
    tl.call(
      () => {
        currentPlayerAnimation.value = playerIdleAnimation
      },
      undefined,
      1.4,
    )
    // 稍微停顿0.1秒后，敌人跑回原位
    tl.to(
      enemy.value,
      {
        x: 0,
        duration: 0.5,
        ease: 'power1.out',
      },
      1.5,
    )
    // 玩家死亡动画开始
    tl.call(
      () => {
        if (combatStore.combatInfo) {
          if (combatStore.combatInfo.player_hp <= 0) {
            currentPlayerAnimation.value = playerDeathAnimation
          }
        }
      },
      undefined,
      2,
    )
    // 玩家死亡动画结束
    tl.call(
      () => {
        if (combatStore.combatInfo) {
          if (combatStore.combatInfo.player_hp <= 0) {
            playerHide.value = 'hidden'
          }
        }
      },
      undefined,
      2.8,
    )
  })
}

onBeforeMount(() => {
  combatStore.StartCombat()
  if (!combatStore.currentQuestion) {
    combatStore.fetchQuestion()
  }
})

onMounted(() => {
  playerInit()
  enemyInit()
})
</script>
