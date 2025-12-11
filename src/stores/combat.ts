import { defineStore } from 'pinia'
import request from '@/utils/request'
import { ref } from 'vue'

export interface CombatInfo {
  level_id: number
  current_floor: number
  player_hp: number
  player_max_hp: number
  player_attack: number
  enemy_hp: number
  enemy_max_hp: number
  enemy_attack: number
}

export interface QuestionOptions {
  A: string
  B: string
  C: string
  D: string
}

export interface QuestionContent0 {
  target_word: string
  story: string
  options: QuestionOptions
  correct_option: string
  explanation: string
}

export interface QuestionContent1 {
  cloze_text: string
  shuffled_options: string[]
  correct_sequence: string[]
  chinese_translation: string
}

export interface QuestionContent2 {
  target_word: string
  chinese_sentence: string
  reference_answer: string
}

export type QuestionType = 'context_guess' | 'cloze_test' | 'keyword_translation'

export interface Question {
  id: number
  type: QuestionType
  content: QuestionContent0 | QuestionContent1 | QuestionContent2
}

// 关键词翻译 / 句子批改结果
export interface QuestionCheckResult {
  is_correct: boolean
  score: number
  feedback: string
  better_translation: string
}

export interface CheckoutInfo {
  max_floor: number
  total_exp: number
  total_coins: number
}

export const useCombatStore = defineStore('combat', () => {
  const combatInfo = ref<CombatInfo | null>(null)
  const currentQuestion = ref<Question | null>(null)
  const checkoutInfo = ref<CheckoutInfo | null>(null)

  async function fetchQuestion() {
    currentQuestion.value = null
    const questionRes = await request.get('/api/question/get', { timeout: 30000 })
    currentQuestion.value = questionRes.data.data as Question
  }

  async function fetchCheckoutInfo() {
    const res = await request.get('/api/combat/checkout')
    checkoutInfo.value = res.data.data as CheckoutInfo
  }

  // 检查关键词翻译 / 句子翻译题的答案
  async function checkKeywordTranslation(payload: {
    target_word: string
    chinese_sentence: string
    user_input: string
  }): Promise<QuestionCheckResult> {
    const res = await request.post('/api/question/check', payload, { timeout: 30000 })
    return res.data.data as QuestionCheckResult
  }

  async function answerQuestion(questionId: number, isCorrect: boolean) {
    await request.post(`/api/question/answer/${questionId}`, {
      level_id: combatInfo.value?.level_id,
      is_correct: isCorrect,
    })
  }

  async function StartCombat() {
    const res = await request.post('/api/combat/start')
    combatInfo.value = res.data.data as CombatInfo
  }

  // 计算本次挑战获得的经验和金币（根据层数）
  function calculateRewards() {
    const floor = combatInfo.value?.current_floor ?? 1
    return {
      exp: floor * 10,
      coins: floor * 5,
    }
  }

  // 完成一次挑战（击败怪物），累加经验和金币，继续下一层
  async function CompleteCombat() {
    const rewards = calculateRewards()

    const res = await request.post('/api/combat/end', {
      next: true,
      end_hp: combatInfo.value?.player_hp,
      exp_gained: rewards.exp,
      coins_gained: rewards.coins,
    })

    if (combatInfo.value && res.data.data?.level_id) {
      combatInfo.value.level_id = res.data.data.level_id
    }
  }

  // 结束闯塔（玩家死亡）
  async function EndCombat() {
    await request.post('/api/combat/end', {
      next: false,
      end_hp: combatInfo.value?.player_hp,
      exp_gained: 0,
      coins_gained: 0,
    })

    await fetchCheckoutInfo()

    // 清理状态
    combatInfo.value = null
    currentQuestion.value = null
  }

  async function clearCheckout() {
    checkoutInfo.value = null
  }

  async function ratingQuestion(questionId: number, rating: number) {
    await request.post(`/api/question/rating/${questionId}`, { rating })
  }

  async function reportQuestion(questionId: number, report: string) {
    await request.post(`/api/question/report/${questionId}`, { report })
  }

  return {
    combatInfo,
    currentQuestion,
    checkoutInfo,
    StartCombat,
    fetchQuestion,
    checkKeywordTranslation,
    answerQuestion,
    CompleteCombat,
    EndCombat,
    fetchCheckoutInfo,
    clearCheckout,
    ratingQuestion,
    reportQuestion,
  }
})
