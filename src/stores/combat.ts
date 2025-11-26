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

export const useCombatStore = defineStore('combat', () => {
  const combatInfo = ref<CombatInfo | null>(null)
  const currentQuestion = ref<Question | null>(null)
  async function initCombatInfo() {
    const res = await request.get('/api/combat/combat_info')
    combatInfo.value = res.data.data as CombatInfo
    const questionRes = await request.post(
      `/api/question/generate/${combatInfo.value?.current_floor}`,
    )
    currentQuestion.value = questionRes.data.data as Question
  }

  return {
    combatInfo,
    currentQuestion,
    initCombatInfo,
  }
})
