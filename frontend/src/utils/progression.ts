export const LEVEL_BASE_EXP = 100
export const LEVEL_GROWTH_EXP = 20

export interface LevelInfo {
  level: number
  currentLevelExp: number
  nextLevelNeedExp: number
  progressPercent: number
}

export function getLevelInfo(totalExp: number): LevelInfo {
  let exp = Math.max(0, Math.floor(totalExp))
  let level = 0
  let need = LEVEL_BASE_EXP

  while (exp >= need) {
    exp -= need
    level += 1
    need = LEVEL_BASE_EXP + LEVEL_GROWTH_EXP * level
  }

  const progressPercent = need > 0 ? (exp / need) * 100 : 0

  return {
    level,
    currentLevelExp: exp,
    nextLevelNeedExp: need,
    progressPercent,
  }
}
