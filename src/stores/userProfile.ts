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
}

const STORAGE_KEY = 'user_profile'

export const useUserProfileStore = defineStore('userProfile', () => {
  // 从 localStorage 恢复缓存的用户资料
  const loadCachedProfile = (): UserProfile | null => {
    try {
      const cached = localStorage.getItem(STORAGE_KEY)
      if (cached) {
        return JSON.parse(cached) as UserProfile
      }
    } catch (error) {
      console.error('读取缓存的用户资料失败:', error)
    }
    return null
  }

  // 用户资料状态（优先使用缓存）
  const profile = ref<UserProfile | null>(loadCachedProfile())
  const loading = ref(false)

  /**
   * 保存用户资料到 localStorage 并更新响应式状态
   * 注意：这会立即更新 profile.value，Vue 会自动更新所有使用它的视图
   */
  function saveProfileToCache(profileData: UserProfile) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(profileData))
      // 更新响应式状态，这会触发 Vue 自动更新视图
      profile.value = profileData
    } catch (error) {
      console.error('保存用户资料到缓存失败:', error)
    }
  }

  /**
   * 从后端获取用户资料并更新缓存和响应式状态
   * 返回的数据会立即更新 profile.value，视图会自动更新显示最新数据
   */
  async function fetchProfile() {
    loading.value = true
    try {
      const res = await request.get('/api/auth/profile')
      if (res.data.code === 0) {
        // 保存到缓存并更新 profile.value，视图会自动更新显示后端返回的最新数据
        saveProfileToCache(res.data.data)
        return res.data.data
      }
    } catch (error) {
      console.error('获取用户信息失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  /**
   * 获取用户资料
   * - 如果有缓存：先显示缓存（快速响应），然后在后台从后端获取最新数据
   * - 当后端数据返回时，会自动更新 profile.value，视图会自动更新显示最新数据
   * - 如果强制刷新或没有缓存：直接等待后端数据返回
   */
  async function getProfile(forceRefresh = false) {
    // 如果强制刷新或没有缓存，则等待后端数据返回
    if (forceRefresh || !profile.value) {
      await fetchProfile()
    } else {
      // 有缓存时，先显示缓存（快速响应），然后在后台获取最新数据
      // fetchProfile 会更新 profile.value，视图会自动更新显示后端返回的最新数据
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
    localStorage.removeItem(STORAGE_KEY)
  }

  /**
   * 更新用户资料（部分更新）
   */
  function updateProfile(updates: Partial<UserProfile>) {
    if (profile.value) {
      const updatedProfile = { ...profile.value, ...updates }
      saveProfileToCache(updatedProfile)
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
