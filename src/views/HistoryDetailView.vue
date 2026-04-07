<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  useHistoryStore,
  type HistoryQuestion,
  type HistoryRunMode,
  type HistoryRunStatus,
} from '@/stores/history'

const route = useRoute()
const historyStore = useHistoryStore()

const detail = computed(() => historyStore.currentRunDetail)

const sortedQuestions = computed(() => {
  const questions = detail.value?.questions ?? []
  return [...questions].sort((left, right) => {
    const leftAnsweredAt = left.first_answer?.answered_at
    const rightAnsweredAt = right.first_answer?.answered_at

    if (leftAnsweredAt && rightAnsweredAt) {
      return new Date(rightAnsweredAt).getTime() - new Date(leftAnsweredAt).getTime()
    }
    if (leftAnsweredAt) {
      return -1
    }
    if (rightAnsweredAt) {
      return 1
    }
    return right.order_index - left.order_index
  })
})

const statusLabelMap: Record<HistoryRunStatus, string> = {
  in_progress: '进行中',
  completed: '已完成',
  failed: '已结束',
}

const statusClassMap: Record<HistoryRunStatus, string> = {
  in_progress: 'bg-blue-50 text-blue-700',
  completed: 'bg-emerald-50 text-emerald-700',
  failed: 'bg-amber-50 text-amber-700',
}

const modeLabelMap: Record<HistoryRunMode, string> = {
  tower: '普通闯塔',
  daily_challenge: '每日挑战',
}

const modeClassMap: Record<HistoryRunMode, string> = {
  tower: 'bg-slate-100 text-slate-700',
  daily_challenge: 'bg-violet-50 text-violet-700',
}

const questionTypeLabelMap: Record<string, string> = {
  context_guess: '语境猜词',
  cloze_test: '完形填空',
  keyword_translation: '关键词翻译',
}

const formatDateTime = (value: string | null | undefined) => {
  if (!value) return '未记录'
  return new Date(value).toLocaleString()
}

const getRunRef = () => {
  const value = route.params.runId
  if (Array.isArray(value)) {
    return value[0] ?? ''
  }
  return typeof value === 'string' ? value : ''
}

const loadDetail = async () => {
  const runRef = getRunRef()
  if (!runRef) return
  if (historyStore.runs.length === 0) {
    await historyStore.fetchRuns()
  }
  await historyStore.fetchRunDetail(runRef)
}

const runSequenceNumber = computed(() => {
  const runRef = detail.value?.run.run_ref
  if (!runRef || detail.value?.run.mode !== 'tower') {
    return null
  }
  return historyStore.getRunSequenceNumber(runRef)
})

const detailTitle = computed(() => {
  if (!detail.value) return '记录详情'
  if (detail.value.run.mode === 'daily_challenge') {
    return detail.value.run.day_key ? `每日挑战 · ${detail.value.run.day_key}` : '每日挑战详情'
  }
  return runSequenceNumber.value ? `第 ${runSequenceNumber.value} 次闯塔` : '闯塔记录详情'
})

const readAnswerDetail = (question: HistoryQuestion) => question.first_answer?.answer_detail ?? {}

const asString = (value: unknown) => (typeof value === 'string' ? value : '')

const asStringArray = (value: unknown) =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []

const renderAnswerSummary = (question: HistoryQuestion) => {
  const answerDetail = readAnswerDetail(question)
  switch (question.question_type) {
    case 'context_guess': {
      const selectedOption = asString(answerDetail.selected_option)
      const selectedText = asString(answerDetail.selected_text)
      return selectedOption ? `首次选择：${selectedOption}${selectedText ? ` - ${selectedText}` : ''}` : '首次作答内容未记录'
    }
    case 'cloze_test': {
      const selectedSequence = asStringArray(answerDetail.selected_sequence)
      return selectedSequence.length > 0 ? `首次填写：${selectedSequence.join(' / ')}` : '首次作答内容未记录'
    }
    case 'keyword_translation': {
      const userInput = asString(answerDetail.user_input)
      return userInput ? `首次输入：${userInput}` : '首次作答内容未记录'
    }
    default:
      return '首次作答内容未记录'
  }
}

onMounted(loadDetail)

watch(
  () => route.params.runId,
  () => {
    loadDetail()
  },
)
</script>

<template>
  <div class="flex h-full flex-col overflow-y-auto p-6">
    <div class="mx-auto flex w-full max-w-3xl flex-col gap-4">
      <Card v-if="historyStore.isLoadingDetail">
        <CardContent class="py-6 text-sm text-muted-foreground">正在加载记录详情...</CardContent>
      </Card>

      <template v-else-if="detail">
        <Card>
          <CardHeader class="gap-3">
            <div class="flex flex-wrap items-center gap-3">
              <CardTitle class="text-xl">
                {{ detailTitle }}
              </CardTitle>
              <span
                class="rounded-full px-2.5 py-1 text-xs font-medium"
                :class="modeClassMap[detail.run.mode]"
              >
                {{ modeLabelMap[detail.run.mode] }}
              </span>
              <span
                class="rounded-full px-2.5 py-1 text-xs font-medium"
                :class="statusClassMap[detail.run.status]"
              >
                {{ statusLabelMap[detail.run.status] }}
              </span>
            </div>
          </CardHeader>
          <CardContent class="grid gap-3 text-sm text-muted-foreground md:grid-cols-2">
            <div>开始时间：{{ formatDateTime(detail.run.started_at) }}</div>
            <div>结束时间：{{ formatDateTime(detail.run.ended_at) }}</div>
            <div>最高层数：第 {{ detail.run.highest_floor }} 层</div>
            <div v-if="detail.run.current_floor">当前层数：第 {{ detail.run.current_floor }} 层</div>
            <div v-if="detail.run.day_key">挑战日期：{{ detail.run.day_key }}</div>
            <div v-if="detail.run.mode === 'tower'">累计经验：{{ detail.run.total_exp }}</div>
            <div v-if="detail.run.mode === 'tower'">累计金币：{{ detail.run.total_coins }}</div>
            <div>题目数：{{ detail.questions.length }}</div>
            <div>结束血量：{{ detail.run.last_hp ?? '未记录' }}</div>
          </CardContent>
        </Card>

        <Card v-if="detail.questions.length === 0">
          <CardContent class="py-6 text-sm text-muted-foreground">
            这条历史记录里暂时还没有可展示的题目作答。
          </CardContent>
        </Card>

        <Card v-for="question in sortedQuestions" :key="question.question_id">
          <CardHeader class="gap-2">
            <div class="flex flex-wrap items-center gap-2">
              <CardTitle class="text-base">
                第 {{ question.order_index }} 题（第 {{ question.floor }} 层）
              </CardTitle>
              <span class="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                {{ questionTypeLabelMap[question.question_type ?? ''] ?? (question.question_type || '未知题型') }}
              </span>
            </div>
          </CardHeader>
          <CardContent class="space-y-4 text-sm">
            <div class="space-y-2">
              <div class="font-medium">题目详情</div>
              <template v-if="question.question_type === 'context_guess'">
                <p>{{ question.content?.story }}</p>
                <p>目标单词：{{ question.content?.target_word }}</p>
                <p>正确选项：{{ question.content?.correct_option }}</p>
                <p>解析：{{ question.content?.explanation }}</p>
              </template>
              <template v-else-if="question.question_type === 'cloze_test'">
                <p>{{ question.content?.cloze_text }}</p>
                <p>备选单词：{{ (question.content?.shuffled_options as string[] | undefined)?.join(' / ') || '未记录' }}</p>
                <p>中文译文：{{ question.content?.chinese_translation }}</p>
              </template>
              <template v-else-if="question.question_type === 'keyword_translation'">
                <p>目标单词：{{ question.content?.target_word }}</p>
                <p>题目句子：{{ question.content?.chinese_sentence }}</p>
                <p>参考答案：{{ question.content?.reference_answer }}</p>
              </template>
            </div>

            <div class="space-y-2 border-t pt-4">
              <div class="font-medium">第一次作答</div>
              <template v-if="question.first_answer">
                <p>
                  作答结果：
                  {{ question.first_answer.correct === true ? '正确' : question.first_answer.correct === false ? '错误' : '未记录' }}
                </p>
                <p>{{ renderAnswerSummary(question) }}</p>
                <p>作答时间：{{ formatDateTime(question.first_answer.answered_at) }}</p>
                <p v-if="question.first_answer.rating !== null">评分：{{ question.first_answer.rating }}</p>
                <p v-if="question.first_answer.report">反馈：{{ question.first_answer.report }}</p>
              </template>
              <p v-else class="text-muted-foreground">没有找到这道题的首次作答记录。</p>
            </div>
          </CardContent>
        </Card>
      </template>

      <Card v-else>
        <CardContent class="py-6 text-sm text-muted-foreground">历史记录不存在或加载失败。</CardContent>
      </Card>
    </div>
  </div>
</template>
