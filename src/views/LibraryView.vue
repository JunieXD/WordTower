<template>
  <div class="flex flex-col p-8 h-screen items-center gap-4 overflow-y-auto">
    <!-- 已选择的词库（支持拖拽） -->
    <draggable
      v-model="selectedLibraries"
      @end="handleDragEnd"
      item-key="id"
      handle=".drag-handle"
      class="flex flex-col gap-4 w-full max-w-md"
    >
      <template #item="{ element: item }">
        <Card class="rounded-lg gap-1 py-4">
          <CardHeader class="flex flex-row justify-between items-start">
            <CardTitle class="text-md">{{ item.name }}</CardTitle>
            <div class="flex gap-2 items-center">
              <Badge v-if="item.visibility === 'public'">内置</Badge>
              <GripVertical
                class="drag-handle cursor-move text-gray-400 hover:text-gray-600"
                :size="20"
              />
            </div>
          </CardHeader>
          <CardContent class="text-xs text-gray-500"> 单词数：{{ item.word_count }} </CardContent>
          <div class="flex flex-row justify-center gap-8">
            <Button
              :class="item.visibility === 'private' ? 'w-2/5' : 'w-3/5'"
              variant="default"
              @click="handleToggleLibrary(item.id)"
              >已选择</Button
            >
            <Button
              v-if="item.visibility === 'private'"
              class="w-2/5"
              variant="outline"
              @click="router.push({ name: 'library-edit', params: { id: item.id } })"
              >编辑</Button
            >
          </div>
        </Card>
      </template>
    </draggable>

    <!-- 未选择的词库 -->
    <div v-for="item in unselectedLibraries" :key="item.id" class="h-auto w-full max-w-md">
      <Card class="rounded-lg gap-1 py-4 opacity-60">
        <CardHeader class="flex flex-row justify-between">
          <CardTitle class="text-md">{{ item.name }}</CardTitle>
          <Badge v-if="item.visibility === 'public'">内置</Badge>
        </CardHeader>
        <CardContent class="text-xs text-gray-500"> 单词数：{{ item.word_count }} </CardContent>
        <div class="flex flex-row justify-center gap-8">
          <Button
            :class="item.visibility === 'private' ? 'w-2/5' : 'w-3/5'"
            variant="outline"
            @click="handleToggleLibrary(item.id)"
            >选择</Button
          >
          <Button
            v-if="item.visibility === 'private'"
            class="w-2/5"
            variant="outline"
            @click="router.push({ name: 'library-edit', params: { id: item.id } })"
            >编辑</Button
          >
        </div>
      </Card>
    </div>
    <Dialog v-model:open="open">
      <DialogTrigger as-child>
        <Button class="h-12 rounded-3xl mb-4" variant="outline">添加词库</Button>
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
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import draggable from 'vuedraggable'
import { GripVertical } from 'lucide-vue-next'
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
import { useNotificationStore } from '@/stores/notification'
import type { Library } from '@/stores/library'

const router = useRouter()
const libraryStore = useLibraryStore()
const notificationStore = useNotificationStore()
const open = ref(false)
const name = ref('')
const description = ref('')

// 分离已选择和未选择的词库
const selectedLibraries = computed({
  get: () => libraryStore.libraries.filter((lib) => lib.selected),
  set: (value: Library[]) => {
    // 更新 store 中的顺序
    const unselected = libraryStore.libraries.filter((lib) => !lib.selected)
    libraryStore.libraries = [...value, ...unselected]
  },
})

const unselectedLibraries = computed(() => libraryStore.libraries.filter((lib) => !lib.selected))

async function onSubmit() {
  const res = await libraryStore.createLibrary(name.value, description.value)
  if (res.success) {
    notificationStore.addNotification({
      variant: 'default',
      title: '成功',
      description: res.message,
      duration: 2000,
    })
    open.value = false
    name.value = ''
    description.value = ''
  } else {
    notificationStore.addNotification({
      variant: 'destructive',
      title: '失败',
      description: res.message,
      duration: 4000,
    })
  }
}

async function handleToggleLibrary(libraryId: number) {
  const res = await libraryStore.toggleLibrary(libraryId)
  if (res.success) {
    notificationStore.addNotification({
      variant: 'default',
      title: '成功',
      description: res.message,
      duration: 1000,
    })
  } else {
    notificationStore.addNotification({
      variant: 'destructive',
      title: '失败',
      description: res.message,
      duration: 2000,
    })
  }
}

// 拖拽结束时批量更新所有已选择词库的优先级
async function handleDragEnd() {
  const selected = selectedLibraries.value
  if (selected.length === 0) return

  try {
    // 构建批量更新数据，优先级从 1 开始
    const priorities = selected.map((lib, index) => ({
      library_id: lib.id,
      priority: index + 1,
    }))

    // 一次性批量更新所有优先级
    const res = await libraryStore.batchUpdateLibraryPriorities(priorities)

    if (res.success) {
      notificationStore.addNotification({
        variant: 'default',
        title: '成功',
        description: res.message || '词库优先级更新成功',
        duration: 2000,
      })
    } else {
      notificationStore.addNotification({
        variant: 'destructive',
        title: '失败',
        description: res.message || '词库优先级更新失败',
        duration: 3000,
      })
    }

    // 刷新词库列表
    await libraryStore.getLibraries(true)
  } catch (error) {
    console.error('更新词库优先级时发生错误:', error)
    notificationStore.addNotification({
      variant: 'destructive',
      title: '失败',
      description: '更新词库优先级时发生错误',
      duration: 3000,
    })
  }
}

onMounted(() => {
  libraryStore.getLibraries()
})
</script>
