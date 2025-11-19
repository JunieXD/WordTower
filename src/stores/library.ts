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
  selected: boolean
  priority: number
}

export interface Word {
  id: number
  text: string
  meaning: string
  phonetic?: string
}

export interface LibraryDetails extends Library {
  words: Word[]
}

export interface BatchRecognizeResult {
  recognizedCount: number
  unrecognizedCount: number
  recognizedWords: Word[]
  unrecognizedWords: string[]
}

export const useLibraryStore = defineStore('library', () => {
  const libraries = ref<Library[]>([])

  async function fetchLibraries() {
    try {
      const res = await request.get('/api/library/get_libraries')
      libraries.value = res.data.data as Library[]

      // 分离已选择和未选择的词库
      const selected = libraries.value.filter((lib) => lib.selected)
      const unselected = libraries.value.filter((lib) => !lib.selected)

      // 已选择的按 priority 排序，未选择的按 id 排序
      selected.sort((a, b) => a.priority - b.priority)
      unselected.sort((a, b) => a.id - b.id)

      // 合并：已选择的在前，未选择的在后
      libraries.value = [...selected, ...unselected]
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
    const res = await request.post('/api/library/create_library', {
      name: name,
      description: description,
    })
    if (res.data.success) {
      await getLibraries(true)
    }
    return { success: res.data.success, message: res.data.message }
  }

  async function toggleLibrary(libraryId: number) {
    const res = await request.post(`/api/library/toggle_user_library_select/${libraryId}`)
    if (res.data.success) {
      await getLibraries(true)
    }
    return { success: res.data.success, message: res.data.message }
  }

  async function getLibraryDetails(libraryId: number): Promise<LibraryDetails> {
    const res = await request.get(`/api/library/get_library_details/${libraryId}`)
    if (res.data.success) {
      return res.data.data as LibraryDetails
    } else {
      throw new Error(res.data.message || '获取词库详情失败')
    }
  }

  async function searchWords(query: string): Promise<Word[]> {
    try {
      const res = await request.get('/api/word/search', {
        params: { q: query },
      })
      if (res.data.success) {
        return res.data.data as Word[]
      } else {
        return []
      }
    } catch (error) {
      console.error('搜索单词失败:', error)
      return []
    }
  }

  async function batchRecognizeWords(words: string[]): Promise<BatchRecognizeResult> {
    const res = await request.post('/api/word/batch_recognize', { words })
    if (res.data.success) {
      return res.data.data as BatchRecognizeResult
    } else {
      throw new Error(res.data.message || '批量识别单词失败')
    }
  }

  async function updateLibrary(
    libraryId: number,
    data: { name: string; description: string; words_id: number[] },
  ) {
    const res = await request.put(`/api/library/update_library/${libraryId}`, data)
    if (res.data.success) {
      await getLibraries(true)
      return true
    } else {
      return false
    }
  }

  async function removeLibrary(libraryId: number) {
    const res = await request.delete(`/api/library/remove_library/${libraryId}`)
    if (res.data.success) {
      await getLibraries(true)
    }
    return {
      success: res.data.success,
      message: res.data.message || (res.data.success ? '删除词库成功' : '删除词库失败'),
    }
  }

  async function batchUpdateLibraryPriorities(
    priorities: Array<{ library_id: number; priority: number }>,
  ) {
    const res = await request.put('/api/library/batch_update_library_priorities', { priorities })
    return { success: res.data.success, message: res.data.message }
  }

  return {
    libraries,
    fetchLibraries,
    getLibraries,
    createLibrary,
    toggleLibrary,
    getLibraryDetails,
    searchWords,
    batchRecognizeWords,
    updateLibrary,
    removeLibrary,
    batchUpdateLibraryPriorities,
  }
})
