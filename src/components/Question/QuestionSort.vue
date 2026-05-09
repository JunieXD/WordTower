<template>
  <Card class="p-4 gap-2">
    <p class="text-md mb-2">请将下面的单词按正确顺序填入文章中的空格。</p>
    <p class="text-md text-gray-800" v-html="renderedClozeText"></p>
  </Card>

  <Card class="p-4 gap-4">
    <p class="text-md">点击下面的单词，按照第 1 空、第 2 空……的顺序依次选择。</p>

    <div class="flex flex-wrap gap-2">
      <span
        v-for="(word, index) in selectedWords"
        :key="index"
        class="px-2 py-1 rounded bg-blue-50 text-blue-700 text-sm border border-blue-200"
      >
        {{ index + 1 }}. {{ word }}
      </span>
      <span v-if="selectedWords.length === 0" class="text-sm text-gray-500">还没有选择任何单词</span>
    </div>

    <div class="flex flex-wrap gap-2">
      <Button
        v-for="(word, index) in shuffledOptions"
        :key="index"
        size="sm"
        variant="outline"
        class="px-3 py-1"
        :disabled="isAnswered || isOptionUsed(index) || isSubmitting"
        @click="handleOptionClick(index)"
      >
        {{ word }}
      </Button>
    </div>

    <div class="flex flex-wrap items-center gap-3 mt-2">
      <Button
        variant="outline"
        size="sm"
        :disabled="isAnswered || isSubmitting || selectedOptionIndices.length === 0"
        @click="handleReset"
      >
        重置选择
      </Button>
      <Button
        variant="outline"
        size="sm"
        :disabled="isAnswered || isSubmitting || selectedOptionIndices.length !== expectedSequenceLength"
        @click="handleSubmit"
      >
        提交答案
      </Button>
      <p v-if="errorMessage" class="text-sm text-red-500">{{ errorMessage }}</p>
    </div>
  </Card>

  <Card
    v-if="isAnswered"
    class="p-4 gap-2"
    :class="displayedIsCorrect ? 'bg-green-50' : 'bg-yellow-50'"
  >
    <p class="text-sm font-semibold mb-1">
      {{ displayedIsCorrect ? '✓ 答案正确！' : '✗ 答案有误。' }}
    </p>
    <p v-if="displayedTranslation" class="text-md">中文译文：{{ displayedTranslation }}</p>
    <p v-if="displayedIsCorrect === false" class="text-md mt-1">
      正确英文：
      <span v-html="correctFilledText"></span>
    </p>
    <Button class="self-start mt-2" variant="outline" :disabled="isSubmitting" @click="handleContinue">
      {{ isSubmitting ? '下一题准备中...' : '继续' }}
    </Button>
  </Card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import type { QuestionContent1 } from '@/stores/combat'

const props = defineProps({
  question: {
    type: Object,
    required: true,
  },
  evaluationMode: {
    type: String,
    default: 'client',
  },
  answerResult: {
    type: Object,
    default: null,
  },
  isSubmitting: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['isCorrect', 'continue', 'submit'])

const content = computed<QuestionContent1 | null>(() => (props.question?.content as QuestionContent1) ?? null)
const questionKey = computed(() => props.question?.id ?? props.question?.question_id ?? null)

const clozeText = computed(() => content.value?.cloze_text ?? '')
const shuffledOptions = computed(() => content.value?.shuffled_options ?? [])
const correctSequence = computed(() => content.value?.correct_sequence ?? [])
const chineseTranslation = computed(() => content.value?.chinese_translation ?? '')
const expectedSequenceLength = computed(() => {
  if (props.evaluationMode === 'server') {
    return shuffledOptions.value.length
  }
  return correctSequence.value.length
})

const selectedOptionIndices = ref<number[]>([])
const isAnswered = ref(false)
const isCorrect = ref<boolean | null>(null)
const errorMessage = ref('')

const displayedResult = computed(() => {
  if (props.evaluationMode === 'server') {
    return props.answerResult as
      | {
          is_correct: boolean
          detail?: {
            correct_sequence?: string[]
            chinese_translation?: string
          }
        }
      | null
  }

  return isCorrect.value === null
    ? null
    : {
        is_correct: isCorrect.value,
        detail: {
          correct_sequence: correctSequence.value,
          chinese_translation: chineseTranslation.value,
        },
      }
})

const displayedIsCorrect = computed(() => displayedResult.value?.is_correct ?? null)
const displayedTranslation = computed(() => displayedResult.value?.detail?.chinese_translation ?? chineseTranslation.value)

const selectedWords = computed(() => selectedOptionIndices.value.map((idx) => shuffledOptions.value[idx] ?? ''))

const isOptionUsed = (index: number) => selectedOptionIndices.value.includes(index)

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

const correctFilledText = computed(() => {
  if (!clozeText.value) return ''

  const displayCorrectSequence = displayedResult.value?.detail?.correct_sequence ?? correctSequence.value
  const regex = /____\[(\d+)]____/g
  return clozeText.value.replace(regex, (match, indexStr) => {
    const idx = Number(indexStr) - 1
    const word = displayCorrectSequence[idx]
    if (!word) return match
    return `<span class="px-1 border-b border-dashed border-green-600">${word}</span>`
  })
})

const handleOptionClick = (index: number) => {
  if (isAnswered.value || props.isSubmitting) return
  if (isOptionUsed(index)) return
  if (selectedOptionIndices.value.length >= expectedSequenceLength.value) return

  selectedOptionIndices.value.push(index)
  errorMessage.value = ''
}

const handleReset = () => {
  if (isAnswered.value || props.isSubmitting) return
  selectedOptionIndices.value = []
  errorMessage.value = ''
}

const handleSubmit = () => {
  if (isAnswered.value || props.isSubmitting) return

  if (selectedOptionIndices.value.length !== expectedSequenceLength.value) {
    errorMessage.value = '请先按顺序选完所有单词。'
    return
  }

  const userSequence = selectedOptionIndices.value.map((idx) => shuffledOptions.value[idx] ?? '')

  if (props.evaluationMode === 'server') {
    emit('submit', {
      selected_sequence: userSequence,
    })
    return
  }

  const correct = userSequence.every((word, i) => word === (correctSequence.value[i] ?? ''))
  isCorrect.value = correct
  isAnswered.value = true
  emit('isCorrect', {
    isCorrect: correct,
    answerDetail: {
      selected_sequence: userSequence,
      selected_indices: [...selectedOptionIndices.value],
      correct_sequence: [...correctSequence.value],
      shuffled_options: [...shuffledOptions.value],
    },
  })
}

const handleContinue = () => {
  emit('continue')
}

watch(
  () => questionKey.value,
  () => {
    selectedOptionIndices.value = []
    isAnswered.value = false
    isCorrect.value = null
    errorMessage.value = ''
  },
)

watch(
  () => props.answerResult,
  (value) => {
    if (props.evaluationMode !== 'server' || !value) return
    isAnswered.value = true
  },
  { immediate: true },
)
</script>
