<template>
  <div class="flex flex-col p-8 h-screen items-center gap-4 overflow-y-auto">
    <div v-for="item in libraryStore.libraries" :key="item.name" class="h-auto w-full max-w-md">
      <Card class="rounded-lg gap-1 py-4">
        <CardHeader class="flex flex-row justify-between">
          <CardTitle class="text-md">{{ item.name }}</CardTitle>
          <Badge v-if="item.visibility === 'public'">内置</Badge>
        </CardHeader>
        <CardContent class="text-xs text-gray-500"> 单词数：{{ item.word_count }} </CardContent>
        <div class="flex flex-row justify-center gap-8">
          <Button :class="item.visibility === 'private' ? 'w-2/5' : 'w-3/5'" variant="outline"
            >选择</Button
          >
          <Button v-if="item.visibility === 'private'" class="w-2/5" variant="outline">编辑</Button>
        </div>
      </Card>
    </div>
    <Dialog v-model:open="open">
      <DialogTrigger as-child>
        <Button class="h-12 rounded-3xl" variant="outline">添加词库</Button>
      </DialogTrigger>
      <DialogContent class="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>新建词库</DialogTitle>
          <DialogDescription>填写词库信息并保存。</DialogDescription>
        </DialogHeader>
        <form @submit.prevent="onSubmit" class="grid gap-4">
          <div class="grid gap-3">
            <Label for="library-name">词库名*</Label>
            <Input id="library-name" name="name" v-model="name" />
          </div>
          <div class="grid gap-3">
            <Label for="library-desc">描述</Label>
            <Input id="library-desc" name="description" v-model="description" />
          </div>
          <DialogFooter>
            <DialogClose as-child>
              <Button variant="outline">取消</Button>
            </DialogClose>
            <Button type="submit" :disabled="!name.trim()">保存</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useLibraryStore } from '@/stores/library'

const libraryStore = useLibraryStore()
const open = ref(false)
const name = ref('')
const description = ref('')

async function onSubmit() {
  await libraryStore.createLibrary(name.value, description.value)
  open.value = false
  name.value = ''
  description.value = ''
}

onMounted(() => {
  libraryStore.getLibraries()
})
</script>
