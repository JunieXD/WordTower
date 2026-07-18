import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/utils/request'

export interface UserProfile {
  id: number
  nickname: string | null
  username: string
  email: string | null
  avatar_url: string | null
  exp: number
  coins: number
  created_at: string
  last_login: string
  status: string
  max_hp: number
  attack: number
  crit_rate: number
  role: string
  max_floor: number
}

export const useUserProfileStore = defineStore('userProfile', () => {
  // 用户资料状态
  const profile = ref<UserProfile | null>(null)

  /**
   * 从后端获取用户资料并更新响应式状态
   * 返回的数据会立即更新 profile.value，视图会自动更新显示最新数据
   */
  async function fetchProfile() {
    try {
      const res = await request.get('/api/auth/profile')
      if (res.data.success && res.data.data) {
        profile.value = res.data.data
      }
    } catch (error) {
      console.error('获取用户信息失败:', error)
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
      fetchProfile()
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
    fetchProfile,
    getProfile,
    clearProfile,
    updateProfile,
  }
})
