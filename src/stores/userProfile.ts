import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/utils/request'

export interface UserProfile {
  id: number
  nickname: string | null
  username: string
  email: string | null
  avatarUrl: string | null
  exp: number
  coins: number
  createdAt: string
  lastLogin: string
  status: string
  maxHp: number
  attack: number
  critRate: number
  role: string
  maxFloor: number
}

export const useUserProfileStore = defineStore('userProfile', () => {
  // 用户资料状态
  const profile = ref<UserProfile | null>(null)
  const loading = ref(false)

  /**
   * 从后端获取用户资料并更新响应式状态
   * 返回的数据会立即更新 profile.value，视图会自动更新显示最新数据
   */
  async function fetchProfile() {
    loading.value = true
    try {
      const res = await request.get('/api/auth/profile')
      if (res.status === 200 && res.data) {
        profile.value = res.data
        return res.data
      }
      return null
    } catch (error) {
      console.error('获取用户信息失败:', error)
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * 获取用户资料
   * - 如果强制刷新或没有缓存：直接等待后端数据返回
   */
  async function getProfile(forceRefresh = false) {
    if (forceRefresh || !profile.value) {
      await fetchProfile()
    } else {
      fetchProfile().catch((error) => {
        console.error('后台更新用户资料失败:', error)
      })
    }
    return profile.value
  }

  /**
   * 清除用户资料（登出时调用）
   */
  function clearProfile() {
    profile.value = null
  }

  /**
   * 更新用户资料（部分更新）
   */
  function updateProfile(updates: Partial<UserProfile>) {
    if (profile.value) {
      const updatedProfile = { ...profile.value, ...updates }
      profile.value = updatedProfile
    }
  }

  return {
    profile,
    loading,
    fetchProfile,
    getProfile,
    clearProfile,
    updateProfile,
  }
})
