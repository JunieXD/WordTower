<template>
  <div class="flex flex-col p-8 h-screen items-center gap-4">
    <div v-for="item in items" :key="item.title" class="h-auto w-full max-w-md">
      <Card class="rounded-lg gap-1 py-4">
        <CardHeader class="flex flex-row justify-between">
          <CardTitle class="text-md">{{ item.title }}</CardTitle>
          <Badge v-if="item.built_in">Built-in</Badge>
        </CardHeader>
        <CardContent class="text-xs text-gray-500"> {{ item.wordcount }} words </CardContent>
        <div class="flex flex-row justify-center gap-8">
          <Button class="w-2/5" variant="outline">选择</Button>
          <Button class="w-2/5" variant="outline">编辑</Button>
        </div>
      </Card>
    </div>
    <div class="flex flex-row justify-center gap-10 w-full">
      <Button class="w-3/7 h-12 rounded-3xl" variant="outline">添加词库</Button>
    </div>
  </div>
</template>

<script setup lang="ts">
const items = [
  { title: 'CET-4', built_in: true, wordcount: 1000 },
  { title: 'CET-6', built_in: true, wordcount: 2000 },
]
</script>
