<template>
  <div class="flex flex-col h-full">
    <!-- 战斗区域 -->
    <div
      class="h-1/3 flex flex-col bg-[url('/src/assets/background/dungeon.png')] bg-cover sm:bg-contain bg-center"
    >
      <div class="h-6/10"></div>
      <div class="h-3/10 flex flex-row">
        <div class="w-1/4 flex flex-row justify-center items-center">
          <img
            ref="player"
            :src="currentPlayerAnimation"
            class="object-contain h-full"
            :class="playerHide"
          />
        </div>
        <div class="w-1/4"></div>
        <div class="w-2/4 flex flex-row justify-center items-center">
          <img
            ref="enemy"
            :src="currentEnemyAnimation"
            class="object-contain h-full transform scale-x-[-1]"
            :class="enemyHide"
          />
        </div>
      </div>
      <div class="h-1/10"></div>
    </div>
    <div class="h-2"></div>
    <!-- 答题区域 -->
    <div class="flex-1 flex flex-col p-4 gap-4 overflow-auto mb-16">
      <component
        :is="conponentMap[combatStore.currentQuestion?.type ?? 'loading']"
        :question="combatStore.currentQuestion"
      ></component>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeMount } from 'vue'
import type { Component } from 'vue'
import gsap from 'gsap'
import { useCombatStore, type QuestionType } from '@/stores/combat'
import QuestionChoice from '@/components/Question/QuestionChoice.vue'
import QuestionInput from '@/components/Question/QuestionInput.vue'
import QuestionSort from '@/components/Question/QuestionSort.vue'
import Loading from '@/components/Question/Loading.vue'

const conponentMap: Record<QuestionType | 'loading', Component> = {
  context_guess: QuestionChoice,
  cloze_test: QuestionInput,
  keyword_translation: QuestionSort,
  loading: Loading,
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
  currentPlayerAnimation.value = playerAttackAnimation
  setTimeout(() => {
    currentPlayerAnimation.value = playerIdleAnimation
  }, 700)
}

const playerHurt = () => {
  currentPlayerAnimation.value = playerHurtAnimation
  setTimeout(() => {
    currentPlayerAnimation.value = playerIdleAnimation
  }, 400)
}

const playerDeath = () => {
  currentPlayerAnimation.value = playerDeathAnimation
  setTimeout(() => {
    playerHide.value = 'hidden'
  }, 800)
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
  currentEnemyAnimation.value = enemyAttackAnimation
  setTimeout(() => {
    currentEnemyAnimation.value = enemyIdleAnimation
  }, 1100)
}

const enemyHurt = () => {
  currentEnemyAnimation.value = enemyHurtAnimation
  setTimeout(() => {
    currentEnemyAnimation.value = enemyIdleAnimation
  }, 400)
}

const enemyDeath = () => {
  currentEnemyAnimation.value = enemyDeathAnimation
  setTimeout(() => {
    enemyHide.value = 'hidden'
  }, 800)
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

onBeforeMount(() => {
  // 只有当 store 中没有数据时才初始化，防止刷新重复初始化
  if (!combatStore.combatInfo) {
    combatStore.initCombatInfo()
  }
})

onMounted(() => {
  playerInit()
  enemyInit()
})
</script>
