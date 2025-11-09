import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  // token 状态
  const token = ref<string | null>(localStorage.getItem('auth_token'))

  // 计算属性：是否已登录
  const isAuthenticated = computed(() => !!token.value)

  /**
   * 设置 token（登录时调用）
   */
  function setToken(newToken: string) {
    token.value = newToken
    localStorage.setItem('auth_token', newToken)
  }

  /**
   * 清除 token（登出时调用）
   */
  function clearToken() {
    token.value = null
    localStorage.removeItem('auth_token')
  }

  /**
   * 初始化 token（从 localStorage 恢复）
   */
  function initToken() {
    const storedToken = localStorage.getItem('auth_token')
    if (storedToken) {
      token.value = storedToken
    }
  }

  return {
    token,
    isAuthenticated,
    setToken,
    clearToken,
    initToken,
  }
})
