import dungeonBackground from '@/assets/background/dungeon.jpg'
import playerIdleAnimationSrc from '@/assets/character/Elf/Idle.gif'
import playerWalkAnimationSrc from '@/assets/character/Elf/Walk.gif'
import playerAttackAnimationSrc from '@/assets/character/Elf/Attack.gif'
import playerHurtAnimationSrc from '@/assets/character/Elf/Hurt.gif'
import playerDeathAnimationSrc from '@/assets/character/Elf/Death.gif'
import enemyIdleAnimationSrc from '@/assets/character/DemonKin/Idle.gif'
import enemyWalkAnimationSrc from '@/assets/character/DemonKin/Walk.gif'
import enemyAttackAnimationSrc from '@/assets/character/DemonKin/Attack.gif'
import enemyHurtAnimationSrc from '@/assets/character/DemonKin/Hurt.gif'
import enemyDeathAnimationSrc from '@/assets/character/DemonKin/Death.gif'

const criticalBattleAssets = [
  dungeonBackground,
  playerIdleAnimationSrc,
  playerWalkAnimationSrc,
  playerAttackAnimationSrc,
  playerHurtAnimationSrc,
  playerDeathAnimationSrc,
  enemyIdleAnimationSrc,
  enemyWalkAnimationSrc,
  enemyAttackAnimationSrc,
  enemyHurtAnimationSrc,
  enemyDeathAnimationSrc,
]

const routeWarmups = [
  () => import('@/components/battle/BattleContainer.vue'),
  () => import('@/views/CombatView.vue'),
  () => import('@/views/DailyChallengeView.vue'),
  () => import('@/layouts/CombatLayout.vue'),
]

let hasStartedHomeAssetPreload = false

function shouldSkipAggressivePreload() {
  if (typeof navigator === 'undefined') return false

  const connection = (
    navigator as Navigator & {
      connection?: {
        saveData?: boolean
        effectiveType?: string
      }
    }
  ).connection

  if (!connection) return false
  if (connection.saveData) return true

  return connection.effectiveType === 'slow-2g' || connection.effectiveType === '2g'
}

function preloadImageAsset(src: string) {
  return new Promise<void>((resolve) => {
    const image = new Image()
    image.onload = () => resolve()
    image.onerror = () => resolve()
    image.src = src
  })
}

function scheduleWhenIdle(task: () => void) {
  const idleWindow = window as Window & {
    requestIdleCallback?: (callback: () => void) => number
  }

  if (typeof idleWindow.requestIdleCallback === 'function') {
    idleWindow.requestIdleCallback(task)
    return
  }

  window.setTimeout(task, 0)
}

function warmupRouteChunks() {
  for (const loadChunk of routeWarmups) {
    void loadChunk().catch(() => undefined)
  }
}

function preloadCriticalAssets() {
  for (const asset of criticalBattleAssets) {
    void preloadImageAsset(asset)
  }
}

export function preloadHomeCriticalAssets() {
  if (hasStartedHomeAssetPreload || typeof window === 'undefined') return

  hasStartedHomeAssetPreload = true

  scheduleWhenIdle(() => {
    warmupRouteChunks()

    if (!shouldSkipAggressivePreload()) {
      preloadCriticalAssets()
    }
  })
}
