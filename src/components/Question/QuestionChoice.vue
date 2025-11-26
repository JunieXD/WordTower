<template>
  <Card class="p-4">
    <p class="text-md" v-html="highlightedStory"></p>
  </Card>
  <Card class="p-4 gap-4">
    <p class="text-md">请选择单词 {{ targetWord }} 的正确释义。</p>
    <Button
      v-for="option in options"
      :key="option"
      class="p-4 justify-start"
      variant="outline"
      :class="getButtonClass(option)"
      @click="handleOptionClick(option)"
      :disabled="isAnswered"
    >
      <p class="text-md">{{ props.question?.content?.options?.[option] }}</p>
    </Button>
  </Card>
  <Card v-if="showExplanation" class="p-4 bg-green-50 gap-2">
    <p class="text-sm font-semibold text-green-800 mb-2">✓ 回答正确！解析：</p>
    <p class="text-md">{{ explanation }}</p>
  </Card>
</template>

<script setup lang="ts">
import { defineProps, computed, ref } from 'vue'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

const props = defineProps({
  question: {
    type: Object,
    required: true,
  },
})

const story = computed(() => {
  return props.question?.content?.story
})

const targetWord = computed(() => {
  return props.question?.content?.target_word
})

const highlightedStory = computed(() => {
  if (!story.value || !targetWord.value) return story.value || ''

  // 使用全局正则表达式匹配所有出现的 targetWord（不区分大小写）
  const regex = new RegExp(`(${targetWord.value})`, 'gi')
  return story.value.replace(regex, '<strong class="underline">$1</strong>')
})

const correct_option = computed(() => {
  return props.question?.content?.correct_option
})

const explanation = computed(() => {
  return props.question?.content?.explanation
})

// 选项列表
const options = ['A', 'B', 'C', 'D'] as const

// 答题状态管理
const selectedOption = ref<string | null>(null)
const isAnswered = ref(false)
const showExplanation = ref(false)

// 处理选项点击
const handleOptionClick = (option: string) => {
  if (isAnswered.value) return

  selectedOption.value = option
  const isCorrect = option === correct_option.value

  if (isCorrect) {
    // 答对：显示绿色背景和解析
    isAnswered.value = true
    showExplanation.value = true
  } else {
    // 答错：显示红色背景，1秒后恢复
    setTimeout(() => {
      selectedOption.value = null
    }, 1000)
  }
}

// 获取按钮样式类
const getButtonClass = (option: string) => {
  if (selectedOption.value !== option) return ''

  const isCorrect = option === correct_option.value
  return isCorrect
    ? 'bg-green-500 hover:bg-green-500 text-white'
    : 'bg-red-500 hover:bg-red-500 text-white'
}
</script>
