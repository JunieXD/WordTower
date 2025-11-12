<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { X, Download } from 'lucide-vue-next'

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

const showPrompt = ref(false)
const deferredPrompt = ref<BeforeInstallPromptEvent | null>(null)
const isInstalled = ref(false)
const DISMISS_STORAGE_KEY = 'pwa-install-dismissed'
const DISMISS_DURATION = 24 * 60 * 60 * 1000 // 24 小时

const shouldShowPrompt = () => {
  if (isInstalled.value) {
    return false
  }
  const dismissed = localStorage.getItem(DISMISS_STORAGE_KEY)
  if (dismissed) {
    const dismissedTime = parseInt(dismissed, 10)
    if (!Number.isNaN(dismissedTime) && Date.now() - dismissedTime < DISMISS_DURATION) {
      return false
    }
  }
  return true
}

onMounted(() => {
  // 检测是否已经安装
  if (window.matchMedia('(display-mode: standalone)').matches) {
    isInstalled.value = true
    return
  }

  // 监听 beforeinstallprompt 事件
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault()
    deferredPrompt.value = e as BeforeInstallPromptEvent
    if (shouldShowPrompt()) {
      showPrompt.value = true
    }
  })

  // 监听应用安装事件
  window.addEventListener('appinstalled', () => {
    showPrompt.value = false
    isInstalled.value = true
    deferredPrompt.value = null
  })
})

const handleInstall = async () => {
  if (!deferredPrompt.value) return

  // 显示安装提示
  await deferredPrompt.value.prompt()

  // 等待用户选择
  const { outcome } = await deferredPrompt.value.userChoice

  if (outcome === 'accepted') {
    showPrompt.value = false
    isInstalled.value = true
  }

  deferredPrompt.value = null
}

const handleDismiss = () => {
  showPrompt.value = false
  deferredPrompt.value = null
  // 将提示状态保存到 localStorage，避免频繁显示
  localStorage.setItem(DISMISS_STORAGE_KEY, Date.now().toString())
}

// 检查是否在24小时内已经关闭过提示
onMounted(() => {
  showPrompt.value = shouldShowPrompt()
})
</script>

<template>
  <Transition name="fade">
    <div
      v-if="showPrompt && !isInstalled"
      class="fixed bottom-4 left-4 right-4 z-50 max-w-md mx-auto pointer-events-auto"
    >
      <Card class="shadow-lg">
        <CardHeader class="pb-3">
          <div class="flex items-center justify-between">
            <CardTitle class="text-lg flex items-center gap-2">
              <Download class="h-5 w-5" />
              安装 Word Tower
            </CardTitle>
            <button
              @click="handleDismiss"
              class="p-1 opacity-70 transition-opacity hover:opacity-100 rounded-sm"
              aria-label="关闭"
            >
              <X class="h-4 w-4" />
            </button>
          </div>
        </CardHeader>
        <CardContent>
          <CardDescription class="mb-4">
            将 Word Tower 安装到您的设备上，享受更快的访问速度。
          </CardDescription>
          <div class="flex gap-2">
            <Button @click="handleInstall" class="flex-1"> 立即安装 </Button>
            <Button variant="outline" @click="handleDismiss"> 稍后 </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  </Transition>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition:
    opacity 0.3s ease,
    transform 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
</style>
