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
      :disabled="isAnswered || isSubmitting"
    >
      <p class="text-md">{{ props.question?.content?.options?.[option] }}</p>
    </Button>
  </Card>
  <Card
    v-if="showExplanation"
    class="p-4 gap-2"
    :class="displayedResult?.is_correct ? 'bg-green-50' : 'bg-yellow-50'"
  >
    <p class="text-sm font-semibold text-green-800 mb-2">
      {{ displayedResult?.is_correct ? '✓ 回答正确！解析：' : '✗ 回答有误。解析：' }}
    </p>
    <p class="text-md">{{ displayedExplanation }}</p>
    <p v-if="displayedCorrectText" class="text-md text-gray-700">正确答案：{{ displayedCorrectText }}</p>
    <Button class="self-start mt-2" variant="outline" :disabled="isSubmitting" @click="handleContinue">
      继续
    </Button>
  </Card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

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

const story = computed(() => props.question?.content?.story)
const targetWord = computed(() => props.question?.content?.target_word)
const questionKey = computed(() => props.question?.id ?? props.question?.question_id ?? null)

const storyTargetForms = computed<string[]>(() => {
  const forms = props.question?.content?.story_target_forms
  if (Array.isArray(forms) && forms.length > 0) {
    return forms.filter((form): form is string => typeof form === 'string' && form.trim().length > 0)
  }
  if (targetWord.value) {
    return inferHighlightForms(targetWord.value, story.value ?? '')
  }
  return []
})

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const normalizeWord = (value: string) => value.trim().toLowerCase()

const buildCandidateForms = (baseWord: string) => {
  const normalized = normalizeWord(baseWord)
  if (!normalized) return []

  const forms = new Set<string>([normalized])

  if (normalized.endsWith('y') && normalized.length > 1) {
    forms.add(`${normalized.slice(0, -1)}ies`)
    forms.add(`${normalized.slice(0, -1)}ied`)
  } else {
    forms.add(`${normalized}s`)
    forms.add(`${normalized}ed`)
  }

  if (normalized.endsWith('e')) {
    forms.add(`${normalized}d`)
    forms.add(`${normalized.slice(0, -1)}ing`)
  } else {
    forms.add(`${normalized}ing`)
  }

  if (
    normalized.length >= 3 &&
    !/[aeiou]$/.test(normalized) &&
    /[aeiou][^aeiouywx]$/.test(normalized)
  ) {
    const last = normalized.slice(-1)
    forms.add(`${normalized}${last}ed`)
    forms.add(`${normalized}${last}ing`)
  }

  return [...forms]
}

const inferHighlightForms = (baseWord: string, currentStory: string) => {
  const storyText = currentStory || ''
  const candidates = buildCandidateForms(baseWord)
  if (!storyText || candidates.length === 0) return [baseWord]

  const matched = candidates.filter((candidate) => {
    const regex = new RegExp(`\\b${escapeRegExp(candidate)}\\b`, 'i')
    return regex.test(storyText)
  })

  return matched.length > 0 ? matched : [baseWord]
}

const highlightedStory = computed(() => {
  if (!story.value) return story.value || ''

  const forms = [...storyTargetForms.value]
  if (forms.length === 0) return story.value

  forms.sort((a, b) => b.length - a.length)
  const escapedForms = forms.map((form) => escapeRegExp(form))
  const regex = new RegExp(`\\b(${escapedForms.join('|')})\\b`, 'gi')
  return story.value.replace(regex, '<strong class="underline">$1</strong>')
})

const correctOption = computed(() => props.question?.content?.correct_option)
const explanation = computed(() => props.question?.content?.explanation)
const options = ['A', 'B', 'C', 'D'] as const

const selectedOption = ref<string | null>(null)
const isAnswered = ref(false)
const showExplanation = ref(false)

const displayedResult = computed(() => {
  if (props.evaluationMode === 'server') {
    return props.answerResult as
      | {
          is_correct: boolean
          detail?: {
            explanation?: string
            correct_text?: string
            correct_option?: string
          }
        }
      | null
  }

  if (!selectedOption.value) return null

  return {
    is_correct: selectedOption.value === correctOption.value,
    detail: {
      explanation: explanation.value,
      correct_text: props.question?.content?.options?.[correctOption.value ?? ''] ?? '',
      correct_option: correctOption.value ?? '',
    },
  }
})

const displayedExplanation = computed(() => displayedResult.value?.detail?.explanation ?? '')
const displayedCorrectText = computed(() => displayedResult.value?.detail?.correct_text ?? '')

const handleOptionClick = (option: string) => {
  if (isAnswered.value || props.isSubmitting) return

  selectedOption.value = option

  if (props.evaluationMode === 'server') {
    emit('submit', { selected_option: option })
    return
  }

  const isCorrect = option === correctOption.value
  const answerDetail = {
    selected_option: option,
    selected_text: props.question?.content?.options?.[option] ?? '',
    correct_option: correctOption.value ?? '',
    correct_text: props.question?.content?.options?.[correctOption.value ?? ''] ?? '',
  }

  if (isCorrect) {
    isAnswered.value = true
    showExplanation.value = true
    emit('isCorrect', { isCorrect: true, answerDetail })
  } else {
    isAnswered.value = true
    showExplanation.value = true
    emit('isCorrect', { isCorrect: false, answerDetail })
  }
}

const handleContinue = () => {
  emit('continue')
}

watch(
  () => questionKey.value,
  () => {
    selectedOption.value = null
    isAnswered.value = false
    showExplanation.value = false
  },
)

watch(
  () => props.answerResult,
  (value) => {
    if (props.evaluationMode !== 'server' || !value) return
    const detail = (value as { detail?: Record<string, unknown> }).detail ?? {}
    selectedOption.value =
      typeof detail.selected_option === 'string' && detail.selected_option.trim()
        ? detail.selected_option
        : selectedOption.value
    isAnswered.value = true
    showExplanation.value = true
  },
  { immediate: true },
)

const getButtonClass = (option: string) => {
  if (props.evaluationMode === 'server') {
    if (!displayedResult.value) {
      return selectedOption.value === option ? 'bg-slate-100' : ''
    }

    const serverCorrectOption = displayedResult.value.detail?.correct_option
    if (option === serverCorrectOption) {
      return 'bg-green-500 hover:bg-green-500 text-white'
    }
    if (selectedOption.value === option) {
      return 'bg-red-500 hover:bg-red-500 text-white'
    }
    return ''
  }

  if (!selectedOption.value) return ''

  if (option === correctOption.value) {
    return 'bg-green-500 hover:bg-green-500 text-white'
  }
  if (selectedOption.value === option) {
    return 'bg-red-500 hover:bg-red-500 text-white'
  }
  return ''
}
</script>
