import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/utils/request'
import { useNotificationStore } from '@/stores/notification'

export interface Library {
  id: number
  name: string
  description: string
  creator_id: number
  visibility: 'public' | 'private'
  created_at: string
  word_count: number
  updated_at: string
}

export const useLibraryStore = defineStore('library', () => {
  const libraries = ref<Library[]>([])

  async function fetchLibraries() {
    try {
      const res = await request.get('/api/library/get_libraries')
      libraries.value = res.data.data as Library[]
      libraries.value.sort((a, b) => a.id - b.id)
    } catch (error) {
      console.error('获取词库失败:', error)
      libraries.value = []
    }
  }

  async function getLibraries(forceRefresh = false) {
    if (forceRefresh || !libraries.value.length) {
      await fetchLibraries()
    } else {
      fetchLibraries()
    }
    return libraries.value
  }

  async function createLibrary(name: string, description: string) {
    const notificationStore = useNotificationStore()
    const res = await request.post('/api/library/create_library', {
      name: name,
      description: description,
    })
    if (res.data.success) {
      notificationStore.addNotification({
        variant: 'default',
        title: '成功',
        description: res.data.message,
        duration: 2000,
      })
      await getLibraries(true)
    } else {
      notificationStore.addNotification({
        variant: 'destructive',
        title: '失败',
        description: res.data.message,
        duration: 4000,
      })
    }
  }

  return {
    libraries,
    fetchLibraries,
    getLibraries,
    createLibrary,
  }
})
