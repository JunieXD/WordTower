<template>
  <div class="flex flex-col p-8 h-screen items-center gap-4">
    <div v-for="item in items" :key="item.name" class="h-auto w-full max-w-md">
      <Card class="rounded-lg gap-1 py-4">
        <CardHeader class="flex flex-row justify-between">
          <CardTitle class="text-md">{{ item.name }}</CardTitle>
          <Badge v-if="item.visibility === 'public'">公开</Badge>
          <Badge v-else-if="item.visibility === 'private'">私有</Badge>
        </CardHeader>
        <CardContent class="text-xs text-gray-500"> {{ item.word_count }} words </CardContent>
        <div class="flex flex-row justify-center gap-8">
          <Button class="w-2/5" variant="outline">选择</Button>
          <Button class="w-2/5" variant="outline">编辑</Button>
        </div>
      </Card>
    </div>
    <div class="flex flex-row justify-center gap-10 w-full">
      <Button class="w-3/7 max-w-sm h-12 rounded-3xl" variant="outline">添加词库</Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import request from '@/utils/request'
import { onMounted, ref } from 'vue'

interface Library {
  id: number
  name: string
  description: string
  creator_id: number
  visibility: 'public' | 'private'
  created_at: string
  word_count: number
  updated_at: string
}

const items = ref<Library[]>([])

onMounted(() => {
  request.get('/api/library/get_libraries').then((res) => {
    items.value = res.data.data as Library[]
    console.log(items.value)
  })
})
</script>
