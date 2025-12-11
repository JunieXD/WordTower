<template>
  <Card class="p-4">
    <p class="text-md" v-html="highlightedStory"></p>
  </Card>
  <Card class="p-4 gap-4">
    <p class="text-md">请选择单词 {{ targetWord }} 最符合上下文的正确释义。</p>
    <Button
      v-for="option in options"
      :key="option"
      class="p-4 justify-start"
      variant="outline"
      :class="getButtonClass(option)"
      @click="handleOptionClick(option)"
      :disabled="isAnswered || isInCooldown"
    >
      <p class="text-md">{{ props.question?.content?.options?.[option] }}</p>
    </Button>
  </Card>
  <Card v-if="showExplanation" class="p-4 bg-green-50 gap-2">
    <p class="text-sm font-semibold text-green-800 mb-2">✓ 回答正确！解析：</p>
    <p class="text-md">{{ explanation }}</p>
    <Button class="self-start mt-2" variant="outline" @click="handleContinue"> 继续 </Button>
  </Card>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

const props = defineProps({
  question: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['isCorrect', 'continue'])

const story = computed(() => {
  return props.question?.content?.story
})

const targetWord = computed(() => {
  return props.question?.content?.target_word
})

/**
 * 生成单词的常见变体形式（复数、过去式、现在分词等）
 * 返回包含原词和所有变体的数组
 */
const generateWordVariants = (word: string): string[] => {
  word = word.toLowerCase()
  const variants = new Set<string>([word])
  const lastChar = word.charAt(word.length - 1)
  const secondLastChar = word.charAt(word.length - 2)
  variants.add(word + 's')
  if (/(?:s|x|z|ch|sh)$/.test(word)) {
    variants.add(word + 'es')
  }
  if (word.length > 1 && word.endsWith('y') && !'aeiou'.includes(secondLastChar)) {
    variants.add(word.slice(0, -1) + 'ies')
  }
  if (word.endsWith('f')) {
    variants.add(word.slice(0, -1) + 'ves')
  }
  if (word.endsWith('fe')) {
    variants.add(word.slice(0, -2) + 'ves')
  }
  variants.add(word + 'ed')
  if (word.endsWith('e')) {
    variants.add(word + 'd')
  }
  if (word.length > 1 && word.endsWith('y') && !'aeiou'.includes(secondLastChar)) {
    variants.add(word.slice(0, -1) + 'ied')
  }
  if (word.length >= 2 && !'aeiouwy'.includes(lastChar) && 'aeiou'.includes(secondLastChar)) {
    variants.add(word + lastChar + 'ed')
  }
  variants.add(word + 'ing')
  if (word.endsWith('e') && !word.endsWith('ee')) {
    variants.add(word.slice(0, -1) + 'ing')
  }
  if (word.length >= 2 && !'aeiouwy'.includes(lastChar) && 'aeiou'.includes(secondLastChar)) {
    variants.add(word + lastChar + 'ing')
  }
  variants.add(word + 'er')
  variants.add(word + 'est')
  if (word.endsWith('e')) {
    variants.add(word + 'r')
    variants.add(word + 'st')
  }
  if (word.length > 1 && word.endsWith('y') && !'aeiou'.includes(secondLastChar)) {
    variants.add(word.slice(0, -1) + 'ier')
    variants.add(word.slice(0, -1) + 'iest')
  }
  variants.add(word + 'ly')
  if (word.length > 1 && word.endsWith('y') && !'aeiou'.includes(secondLastChar)) {
    variants.add(word.slice(0, -1) + 'ily')
  }
  return Array.from(variants)
}

const highlightedStory = computed(() => {
  if (!story.value || !targetWord.value) return story.value || ''

  const variants = generateWordVariants(targetWord.value)
  variants.sort((a, b) => b.length - a.length)
  const escapedVariants = variants.map((v) => v.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const regex = new RegExp(`\\b(${escapedVariants.join('|')})\\b`, 'gi')
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
const isInCooldown = ref(false)

let cooldownTimer: number | null = null

// 处理选项点击
const handleOptionClick = (option: string) => {
  if (isAnswered.value || isInCooldown.value) return

  selectedOption.value = option
  const isCorrect = option === correct_option.value

  if (isCorrect) {
    // 答对：显示绿色背景和解析
    isAnswered.value = true
    showExplanation.value = true
    emit('isCorrect', true)
  } else {
    // 答错：显示红色背景，2秒后恢复
    if (cooldownTimer) {
      clearTimeout(cooldownTimer)
    }
    isInCooldown.value = true
    cooldownTimer = window.setTimeout(() => {
      selectedOption.value = null
      isInCooldown.value = false
      cooldownTimer = null
    }, 2000)
    emit('isCorrect', false)
  }
}

const handleContinue = () => {
  emit('continue')
}

onBeforeUnmount(() => {
  if (cooldownTimer) {
    clearTimeout(cooldownTimer)
    cooldownTimer = null
  }
})

// 获取按钮样式类
const getButtonClass = (option: string) => {
  if (selectedOption.value !== option) return ''

  const isCorrect = option === correct_option.value
  return isCorrect
    ? 'bg-green-500 hover:bg-green-500 text-white'
    : 'bg-red-500 hover:bg-red-500 text-white'
}
</script>
