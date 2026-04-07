<template>
  <Card class="p-4 gap-2">
    <p class="text-md">请使用单词 {{ targetWord }} 翻译下面的句子：</p>
    <p v-if="chineseSentence" class="text-md text-gray-700 mt-2">{{ chineseSentence }}</p>
  </Card>

  <Card class="p-4 gap-4">
    <Textarea
      v-model="userAnswer"
      placeholder="在这里输入你的英文句子..."
      :disabled="isSubmitting || isAnswered"
    />
    <p v-if="errorMessage" class="text-sm text-red-500">{{ errorMessage }}</p>
    <Button
      class="self-start mt-2"
      variant="outline"
      :disabled="isSubmitting || isAnswered || !userAnswer.trim()"
      @click="handleSubmit"
    >
      {{ isSubmitting ? '提交中...' : isAnswered ? '已提交' : '提交答案' }}
    </Button>
  </Card>

  <Card
    v-if="displayedCheckResult"
    class="p-4 gap-2"
    :class="displayedCheckResult.is_correct ? 'bg-green-50' : 'bg-yellow-50'"
  >
    <p class="text-sm font-semibold mb-1">
      {{ displayedCheckResult.is_correct ? '✓ 回答不错！' : '✗ 回答有待改进。' }} 得分：{{
        displayedCheckResult.score
      }}
      / 100
    </p>
    <p v-if="displayedCheckResult.feedback" class="text-md">解析：{{ displayedCheckResult.feedback }}</p>
    <p v-if="displayedReferenceAnswer" class="text-md">参考答案：{{ displayedReferenceAnswer }}</p>
    <p v-if="displayBetterTranslation" class="text-md">建议改写：{{ displayBetterTranslation }}</p>
    <Button class="self-start mt-2" variant="outline" :disabled="isSubmitting" @click="handleContinue">
      继续
    </Button>
  </Card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { useCombatStore } from '@/stores/combat'

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

const combatStore = useCombatStore()

const targetWord = computed(() => props.question?.content?.target_word ?? '')
const chineseSentence = computed(() => props.question?.content?.chinese_sentence ?? '')
const referenceAnswer = computed(() => props.question?.content?.reference_answer ?? '')
const questionKey = computed(() => props.question?.id ?? props.question?.question_id ?? null)

const userAnswer = ref('')
const isAnswered = ref(false)
const errorMessage = ref('')

interface CheckResult {
  is_correct: boolean
  score: number
  feedback: string
  better_translation: string
}

const checkResult = ref<CheckResult | null>(null)

const displayedCheckResult = computed<CheckResult | null>(() => {
  if (props.evaluationMode === 'server' && props.answerResult) {
    const result = props.answerResult as { is_correct?: boolean; detail?: Record<string, unknown> }
    const detail = result.detail ?? {}
    return {
      is_correct: Boolean(result.is_correct),
      score: Number(detail.score ?? 0),
      feedback: String(detail.feedback ?? ''),
      better_translation: String(detail.better_translation ?? ''),
    }
  }
  return checkResult.value
})

const displayedReferenceAnswer = computed(() => {
  if (props.evaluationMode === 'server' && props.answerResult) {
    const detail = (props.answerResult as { detail?: Record<string, unknown> }).detail ?? {}
    return String(detail.reference_answer ?? '')
  }
  return referenceAnswer.value
})

const displayBetterTranslation = computed(() => {
  const betterTranslation = displayedCheckResult.value?.better_translation?.trim() ?? ''
  const originalReference = displayedReferenceAnswer.value.trim()
  if (!betterTranslation) {
    return ''
  }
  if (betterTranslation === originalReference) {
    return ''
  }
  return betterTranslation
})

const handleContinue = () => {
  emit('continue')
}

const handleSubmit = async () => {
  if (!userAnswer.value.trim() || props.isSubmitting || isAnswered.value) return

  if (props.evaluationMode === 'server') {
    emit('submit', { user_input: userAnswer.value.trim() })
    return
  }

  errorMessage.value = ''
  try {
    const payload = {
      target_word: targetWord.value,
      chinese_sentence: chineseSentence.value,
      user_input: userAnswer.value.trim(),
    }
    const raw = await combatStore.checkKeywordTranslation(payload)
    checkResult.value = {
      is_correct: raw.is_correct,
      score: Number(raw.score ?? 0),
      feedback: raw.feedback ?? '',
      better_translation: raw.better_translation ?? '',
    }
    isAnswered.value = true
    emit('isCorrect', {
      isCorrect: raw.is_correct,
      answerDetail: {
        user_input: userAnswer.value.trim(),
        score: Number(raw.score ?? 0),
        feedback: raw.feedback ?? '',
        better_translation: raw.better_translation ?? '',
        reference_answer: referenceAnswer.value,
      },
    })
  } catch (error) {
    console.error('检查答案失败:', error)
    errorMessage.value = '检查答案失败，请稍后重试'
  }
}

watch(
  () => questionKey.value,
  () => {
    userAnswer.value = ''
    isAnswered.value = false
    errorMessage.value = ''
    checkResult.value = null
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
