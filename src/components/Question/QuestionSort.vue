<template>
  <!-- 题干区域：展示含有占位符的英文短文 -->
  <Card class="p-4 gap-2">
    <p class="text-md mb-2">请将下面的单词按正确顺序填入文章中的空格。</p>
    <p class="text-md text-gray-800" v-html="renderedClozeText"></p>
  </Card>

  <!-- 选词与顺序区域 -->
  <Card class="p-4 gap-4">
    <p class="text-md">点击下面的单词，按照第 1 空、第 2 空……的顺序依次选择。</p>

    <!-- 当前已选择顺序预览 -->
    <div class="flex flex-wrap gap-2">
      <span
        v-for="(word, index) in selectedWords"
        :key="index"
        class="px-2 py-1 rounded bg-blue-50 text-blue-700 text-sm border border-blue-200"
      >
        {{ index + 1 }}. {{ word }}
      </span>
      <span v-if="selectedWords.length === 0" class="text-sm text-gray-500">
        还没有选择任何单词
      </span>
    </div>

    <!-- 备选单词按钮 -->
    <div class="flex flex-wrap gap-2">
      <Button
        v-for="(word, index) in shuffledOptions"
        :key="index"
        size="sm"
        variant="outline"
        class="px-3 py-1"
        :disabled="isAnswered || isOptionUsed(index)"
        @click="handleOptionClick(index)"
      >
        {{ word }}
      </Button>
    </div>

    <!-- 操作按钮与错误提示 -->
    <div class="flex flex-wrap items-center gap-3 mt-2">
      <Button
        variant="outline"
        size="sm"
        :disabled="isAnswered || selectedOptionIndices.length === 0"
        @click="handleReset"
      >
        重置选择
      </Button>
      <Button
        variant="outline"
        size="sm"
        :disabled="isAnswered || selectedOptionIndices.length !== correctSequence.length"
        @click="handleSubmit"
      >
        提交答案
      </Button>
      <p v-if="errorMessage" class="text-sm text-red-500">
        {{ errorMessage }}
      </p>
    </div>
  </Card>

  <!-- 结果与中文译文：无论对错都展示 -->
  <Card v-if="isAnswered" class="p-4 gap-2" :class="isCorrect ? 'bg-green-50' : 'bg-yellow-50'">
    <p class="text-sm font-semibold mb-1">
      {{ isCorrect ? '✓ 答案正确！' : '✗ 答案有误。' }}
    </p>
    <p class="text-md">中文译文：{{ chineseTranslation }}</p>
    <!-- 如果做错了，额外展示正确的英文填空结果 -->
    <p v-if="isCorrect === false" class="text-md mt-1">
      正确英文：
      <span v-html="correctFilledText"></span>
    </p>
    <Button class="self-start mt-2" variant="outline" @click="handleContinue">继续</Button>
  </Card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import type { QuestionContent1 } from '@/stores/combat'

const props = defineProps({
  question: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['isCorrect', 'continue'])

// 将 Question.content 视为 完形填空 类型的内容
const content = computed<QuestionContent1 | null>(() => {
  return (props.question?.content as QuestionContent1) ?? null
})

const clozeText = computed(() => content.value?.cloze_text ?? '')
const shuffledOptions = computed(() => content.value?.shuffled_options ?? [])
const correctSequence = computed(() => content.value?.correct_sequence ?? [])
const chineseTranslation = computed(() => content.value?.chinese_translation ?? '')

// 用户选择状态：存储被选择的 shuffledOptions 下标
const selectedOptionIndices = ref<number[]>([])
const isAnswered = ref(false)
const isCorrect = ref<boolean | null>(null)
const errorMessage = ref('')

// 当前已选择的单词序列（用于展示）
const selectedWords = computed(() =>
  selectedOptionIndices.value.map((idx) => shuffledOptions.value[idx] ?? ''),
)

// 判断某个选项是否已经被使用
const isOptionUsed = (index: number) => {
  return selectedOptionIndices.value.includes(index)
}

// 将文章中的 ____[n]____ 占位符替换为当前选择的单词（如果有）
const renderedClozeText = computed(() => {
  if (!clozeText.value) return ''

  const regex = /____\[(\d+)]____/g
  return clozeText.value.replace(regex, (match, indexStr) => {
    const placeholderIndex = Number(indexStr) - 1
    const optionIndex = selectedOptionIndices.value[placeholderIndex]
    if (optionIndex == null) {
      return `<span class="px-1 font-semibold text-blue-600">____[${indexStr}]____</span>`
    }
    const word = shuffledOptions.value[optionIndex] ?? ''
    return `<span class="px-1 border-b border-dashed border-blue-500">${word}</span>`
  })
})

// 使用正确答案序列填充占位符，用于展示“正确英文”
const correctFilledText = computed(() => {
  if (!clozeText.value) return ''

  const regex = /____\[(\d+)]____/g
  return clozeText.value.replace(regex, (match, indexStr) => {
    const idx = Number(indexStr) - 1
    const word = correctSequence.value[idx]
    if (!word) return match
    return `<span class="px-1 border-b border-dashed border-green-600">${word}</span>`
  })
})

// 选中一个单词，按顺序填入下一个空
const handleOptionClick = (index: number) => {
  if (isAnswered.value) return
  if (isOptionUsed(index)) return
  if (selectedOptionIndices.value.length >= correctSequence.value.length) return

  selectedOptionIndices.value.push(index)
  errorMessage.value = ''
}

// 重置当前选择
const handleReset = () => {
  if (isAnswered.value) return
  selectedOptionIndices.value = []
  errorMessage.value = ''
}

// 提交答案，前端根据 correct_sequence 判断正误
const handleSubmit = () => {
  if (isAnswered.value) return

  if (selectedOptionIndices.value.length !== correctSequence.value.length) {
    errorMessage.value = '请先按顺序选完所有单词。'
    return
  }

  const userSequence = selectedOptionIndices.value.map((idx) => shuffledOptions.value[idx] ?? '')

  const correct = userSequence.every((word, i) => word === (correctSequence.value[i] ?? ''))

  isCorrect.value = correct
  isAnswered.value = true
  emit('isCorrect', correct)
}

const handleContinue = () => {
  emit('continue')
}
</script>
