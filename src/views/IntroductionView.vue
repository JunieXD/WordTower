<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Button } from '@/components/ui/button'

const router = useRouter()

const enter = () => {
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="h-screen w-full flex flex-col items-center justify-center bg-white">
    <div class="my-30 text-center flex flex-col gap-4">
      <h1
        class="text-6xl font-bold tracking-tight text-transparent bg-clip-text bg-linear-to-br from-blue-400 via-purple-400 to-pink-400 drop-shadow-sm select-none lg:text-7xl"
      >
        Word Tower
      </h1>
      <p class="text-md text-gray-500 lg:text-xl">一款基于 LLM 和 Roguelike 机制的单词闯塔小游戏</p>
    </div>
    <Button
      class="h-12 w-1/3 min-w-20 max-w-40 text-lg rounded-4xl"
      @click="enter"
      variant="outline"
    >
      Start
    </Button>
    <div class="fixed bottom-2 text-center text-sm text-gray-500">
      Made by <a href="https://juniexd.cn/" target="_blank" class="text-blue-500">JunieXD</a>
    </div>
  </div>
</template>
