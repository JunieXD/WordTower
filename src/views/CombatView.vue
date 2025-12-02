<template>
  <div class="flex flex-col h-full overflow-hidden">
    <!-- 战斗区域 -->
    <div
      class="h-1/3 shrink-0 flex flex-col bg-[url('/src/assets/background/dungeon.png')] bg-cover sm:bg-contain bg-center"
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
      ></component>
      <!-- 继续按钮 -->
      <Button v-if="showContinueButton" @click="handleContinue" variant="outline"> 继续 </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { ref, onMounted, onBeforeMount } from 'vue'
import type { Component } from 'vue'
import gsap from 'gsap'
import { useRouter } from 'vue-router'
import { useCombatStore, type QuestionType } from '@/stores/combat'
import QuestionChoice from '@/components/Question/QuestionChoice.vue'
import QuestionInput from '@/components/Question/QuestionInput.vue'
import QuestionSort from '@/components/Question/QuestionSort.vue'
import Loading from '@/components/Question/Loading.vue'
import { Button } from '@/components/ui/button'

const conponentMap: Record<QuestionType | 'loading', Component> = {
  context_guess: QuestionChoice,
  cloze_test: QuestionInput,
  keyword_translation: QuestionSort,
  loading: Loading,
}

const player = ref<HTMLImageElement | null>(null)
const playerIdleAnimation = '/src/assets/character/Elf/Idle.gif'
const playerWalkAnimation = '/src/assets/character/Elf/Walk.gif'
const playerAttackAnimation = '/src/assets/character/Elf/Attack.gif'
const playerHurtAnimation = '/src/assets/character/Elf/Hurt.gif'
const playerDeathAnimation = '/src/assets/character/Elf/Death.gif'
const playerHide = ref<string | null>(null)
const currentPlayerAnimation = ref(playerWalkAnimation)

const enemy = ref<HTMLImageElement | null>(null)
const enemyIdleAnimation = '/src/assets/character/DemonKin/Idle.gif'
const enemyWalkAnimation = '/src/assets/character/DemonKin/Walk.gif'
const enemyAttackAnimation = '/src/assets/character/DemonKin/Attack.gif'
const enemyHurtAnimation = '/src/assets/character/DemonKin/Hurt.gif'
const enemyDeathAnimation = '/src/assets/character/DemonKin/Death.gif'
const enemyHide = ref<string | null>(null)
const currentEnemyAnimation = ref(enemyIdleAnimation)

const combatStore = useCombatStore()
const showContinueButton = ref(false)
const router = useRouter()

const handleIsCorrect = async (isCorrect: boolean) => {
  if (isCorrect) {
    playerAttack()
    showContinueButton.value = true
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
  showContinueButton.value = false
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
