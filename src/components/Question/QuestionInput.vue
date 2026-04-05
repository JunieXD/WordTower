<template>
  <!-- 题干区域 -->
  <Card class="p-4 gap-2">
    <p class="text-md">请使用单词 {{ targetWord }} 翻译下面的句子：</p>
    <p v-if="chineseSentence" class="text-md text-gray-700 mt-2">
      {{ chineseSentence }}
    </p>
  </Card>

  <!-- 输入与提交区域 -->
  <Card class="p-4 gap-4">
    <Textarea
      v-model="userAnswer"
      placeholder="在这里输入你的英文句子..."
      :disabled="isSubmitting || isAnswered"
    />
    <p v-if="errorMessage" class="text-sm text-red-500">
      {{ errorMessage }}
    </p>
    <Button
      class="self-start mt-2"
      variant="outline"
      :disabled="isSubmitting || isAnswered || !userAnswer.trim()"
      @click="handleSubmit"
    >
      {{ isSubmitting ? '提交中...' : isAnswered ? '已提交' : '提交答案' }}
    </Button>
  </Card>

  <!-- 结果解析区域：无论是否正确都展示 -->
  <Card
    v-if="checkResult"
    class="p-4 gap-2"
    :class="checkResult.is_correct ? 'bg-green-50' : 'bg-yellow-50'"
  >
    <p class="text-sm font-semibold mb-1">
      {{ checkResult.is_correct ? '✓ 回答不错！' : '✗ 回答有待改进。' }} 得分：{{
        checkResult.score
      }}
      / 100
    </p>
    <p v-if="checkResult.feedback" class="text-md">解析：{{ checkResult.feedback }}</p>
    <p v-if="referenceAnswer" class="text-md">参考答案：{{ referenceAnswer }}</p>
    <p v-if="displayBetterTranslation" class="text-md">建议改写：{{ displayBetterTranslation }}</p>
    <Button class="self-start mt-2" variant="outline" @click="handleContinue">继续</Button>
  </Card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useCombatStore } from '@/stores/combat'

const props = defineProps({
  question: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['isCorrect', 'continue'])

const combatStore = useCombatStore()

// 题目内容相关
const targetWord = computed(() => props.question?.content?.target_word ?? '')
const chineseSentence = computed(() => props.question?.content?.chinese_sentence ?? '')
const referenceAnswer = computed(() => props.question?.content?.reference_answer ?? '')

// 用户作答与状态
const userAnswer = ref('')
const isSubmitting = ref(false)
const isAnswered = ref(false)
const errorMessage = ref('')

interface CheckResult {
  is_correct: boolean
  score: number
  feedback: string
  better_translation: string
}

const checkResult = ref<CheckResult | null>(null)

// better_translation 是对用户答案的润色建议，不是出题时的标准参考答案。
const displayBetterTranslation = computed(() => {
  const betterTranslation = checkResult.value?.better_translation?.trim() ?? ''
  const originalReference = referenceAnswer.value.trim()
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

// 提交答案并向后端请求批改
const handleSubmit = async () => {
  if (!userAnswer.value.trim() || isSubmitting.value || isAnswered.value) return

  isSubmitting.value = true
  errorMessage.value = ''
  try {
    const payload = {
      target_word: targetWord.value,
      chinese_sentence: chineseSentence.value,
      user_input: userAnswer.value.trim(),
    }
    const raw = await combatStore.checkKeywordTranslation(payload)
    // 这里约定后端返回的数据一定在 res.data.data 中，
    // store 已经帮我们取出了 data，因此直接使用 raw。
    checkResult.value = {
      is_correct: raw.is_correct,
      score: Number(raw.score ?? 0),
      feedback: raw.feedback ?? '',
      better_translation: raw.better_translation ?? '',
    }
    isAnswered.value = true
    emit('isCorrect', raw.is_correct)
  } catch (error) {
    console.error('检查答案失败:', error)
    errorMessage.value = '检查答案失败，请稍后重试'
  } finally {
    isSubmitting.value = false
  }
}
</script>
