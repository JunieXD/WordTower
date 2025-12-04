import { defineStore } from 'pinia'
import request from '@/utils/request'
import { ref } from 'vue'

export interface CombatInfo {
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
  current_floor: number
  exp_gained: number
  coins_gained: number
}

export const useCombatStore = defineStore('combat', () => {
  const combatInfo = ref<CombatInfo | null>(null)
  const currentQuestion = ref<Question | null>(null)
  const checkoutInfo = ref<CheckoutInfo | null>(null)

  // 累计获得的经验和金币（本次闯塔）
  const totalExp = ref(0)
  const totalCoins = ref(0)

  async function fetchQuestion() {
    currentQuestion.value = null
    const questionRes = await request.post('/api/question/generate', {}, { timeout: 15000 })
    currentQuestion.value = questionRes.data.data as Question
  }

  // 检查关键词翻译 / 句子翻译题的答案
  async function checkKeywordTranslation(payload: {
    target_word: string
    chinese_sentence: string
    user_input: string
  }): Promise<QuestionCheckResult> {
    const res = await request.post('/api/question/check', payload, { timeout: 15000 })
    return res.data.data as QuestionCheckResult
  }

  async function answerQuestion(questionId: number, isCorrect: boolean) {
    await request.post(`/api/question/answer/${questionId}`, {
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
    totalExp.value += rewards.exp
    totalCoins.value += rewards.coins

    await request.post('/api/combat/end', {
      next: true,
      end_hp: combatInfo.value?.player_hp,
      exp_gained: rewards.exp,
      coins_gained: rewards.coins,
    })
  }

  // 结束闯塔（玩家死亡）
  async function EndCombat() {
    // 保存结算信息
    checkoutInfo.value = {
      current_floor: combatInfo.value?.current_floor ?? 0,
      exp_gained: totalExp.value,
      coins_gained: totalCoins.value,
    }

    await request.post('/api/combat/end', {
      next: false,
      end_hp: combatInfo.value?.player_hp,
      exp_gained: 0,
      coins_gained: 0,
    })

    // 清理状态
    combatInfo.value = null
    currentQuestion.value = null
    totalExp.value = 0
    totalCoins.value = 0
  }

  function clearCheckout() {
    checkoutInfo.value = null
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
    clearCheckout,
  }
})
