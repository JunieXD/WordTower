<script setup lang="ts">
import { ref, reactive } from 'vue'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'

interface OpenOptions {
  title?: string
  description?: string
  cancelText?: string
  actionText?: string
}

const openState = ref(false)
const state = reactive<Required<OpenOptions>>({
  title: '提示',
  description: '',
  cancelText: '取消',
  actionText: '确定',
})

let resolver: ((value: boolean) => void) | null = null

function open(options: OpenOptions = {}): Promise<boolean> {
  state.title = options.title ?? '提示'
  state.description = options.description ?? ''
  state.cancelText = options.cancelText ?? '取消'
  state.actionText = options.actionText ?? '确定'
  openState.value = true
  return new Promise<boolean>((resolve) => {
    resolver = resolve
  })
}

function handleCancel() {
  openState.value = false
  resolver?.(false)
  resolver = null
}

function handleAction() {
  openState.value = false
  resolver?.(true)
  resolver = null
}

defineExpose({ open })
</script>

<template>
  <AlertDialog v-model:open="openState">
    <AlertDialogContent>
      <AlertDialogHeader>
        <AlertDialogTitle>{{ state.title }}</AlertDialogTitle>
        <AlertDialogDescription v-if="state.description">
          {{ state.description }}
        </AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter>
        <AlertDialogCancel as-child>
          <Button variant="outline" @click="handleCancel">{{ state.cancelText }}</Button>
        </AlertDialogCancel>
        <AlertDialogAction as-child>
          <Button @click="handleAction">{{ state.actionText }}</Button>
        </AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
</template>
