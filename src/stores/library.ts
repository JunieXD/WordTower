import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/utils/request'

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

  return {
    libraries,
    fetchLibraries,
    getLibraries,
  }
})
