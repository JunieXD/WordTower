import type {
  AnswerDetail,
  QuestionContent0,
  QuestionContent1,
  QuestionContent2,
  QuestionType,
} from '@/stores/combat'

export type BattleEvaluationMode = 'client' | 'server'

export interface BattleRenderableQuestion {
  id?: number
  question_id?: number
  type: QuestionType
  content: QuestionContent0 | QuestionContent1 | QuestionContent2
}

export interface BattleSubmitPayload {
  selected_option?: string
  selected_sequence?: string[]
  user_input?: string
  is_correct?: boolean
  answer_detail?: AnswerDetail
}

export type BattleAnswerEvent = boolean | { isCorrect: boolean; answerDetail?: AnswerDetail }

export interface BattleContainerHandle {
  enterBattlefield: () => void
  respawnPlayer: () => void
  respawnEnemy: () => void
  cancelActiveAnimation: () => void
  playPlayerAttack: (options: { nextEnemyHp: number; enemyDies: boolean }) => Promise<void>
  playEnemyAttack: (options: { nextPlayerHp: number; playerDies: boolean }) => Promise<void>
}
