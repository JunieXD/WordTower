<template>
  <!-- 加载提示 -->
  <div class="text-center mb-4 text-sm text-muted-foreground">
    <p>正在加载题目...</p>
    <p class="text-xs mt-1">首次加载需要10秒左右，请耐心等待</p>
  </div>

  <!-- 题目内容骨架屏 -->
  <Card class="p-4">
    <div class="space-y-3">
      <Skeleton class="h-4 w-full" />
      <Skeleton class="h-4 w-11/12" />
      <Skeleton class="h-4 w-4/5" />
      <Skeleton class="h-4 w-full" />
      <Skeleton class="h-4 w-3/4" />
    </div>
  </Card>

  <!-- 选项骨架屏 -->
  <Card class="p-4 gap-4">
    <Skeleton class="h-5 w-3/5" />
    <Button v-for="i in 4" :key="i" class="p-4 justify-start" variant="outline" disabled>
      <Skeleton class="h-4 w-4/5" />
    </Button>
  </Card>
</template>

<script setup lang="ts">
import type { Question } from '@/stores/combat'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

defineProps<{
  question: Question | null
}>()

defineEmits(['isCorrect', 'continue'])
</script>
