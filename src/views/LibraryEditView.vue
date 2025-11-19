<template>
  <div class="flex flex-col p-8 h-screen overflow-y-auto">
    <div class="max-w-4xl mx-auto w-full space-y-6 pb-8">
      <!-- 页面标题 -->
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold">编辑词库</h1>
          <p class="text-sm text-gray-500 mt-1">修改词库信息和管理单词</p>
        </div>
        <Button variant="outline" @click="router.back()">返回</Button>
      </div>

      <!-- 基本信息 -->
      <Card class="gap-4">
        <CardHeader>
          <CardTitle>基本信息</CardTitle>
        </CardHeader>
        <CardContent class="space-y-4">
          <div class="space-y-2">
            <Label for="name">词库名称*</Label>
            <Input id="name" v-model="libraryName" placeholder="请输入词库名称" />
          </div>
          <div class="space-y-2">
            <Label for="description">描述</Label>
            <Textarea id="description" v-model="libraryDescription" placeholder="请输入词库描述" />
          </div>
        </CardContent>
      </Card>

      <!-- 单词管理 -->
      <Card>
        <CardHeader>
          <CardTitle>单词管理</CardTitle>
          <p class="text-sm text-gray-500">已选择 {{ selectedWords.size }} 个单词</p>
        </CardHeader>
        <CardContent class="space-y-4">
          <!-- 切换选择方式 -->
          <div class="flex gap-2 border-b">
            <Button
              :variant="selectMode === 'search' ? 'default' : 'outline'"
              @click="selectMode = 'search'"
              class="rounded-b-none"
            >
              搜索选择
            </Button>
            <Button
              :variant="selectMode === 'batch' ? 'default' : 'outline'"
              @click="selectMode = 'batch'"
              class="rounded-b-none"
            >
              批量添加
            </Button>
          </div>

          <!-- 搜索模式 -->
          <div v-if="selectMode === 'search'" class="space-y-4">
            <div class="flex gap-2">
              <Input
                v-model="searchQuery"
                placeholder="输入单词进行搜索..."
                @input="handleSearchDebounced"
              />
              <Button @click="handleSearch" :disabled="isSearching">
                {{ isSearching ? '搜索中...' : '搜索' }}
              </Button>
            </div>

            <!-- 搜索结果 -->
            <div
              v-if="searchResults.length > 0"
              class="border rounded-lg px-4 py-2 max-h-48 overflow-y-auto"
            >
              <div class="space-y-2">
                <div
                  v-for="word in searchResults"
                  :key="word.id"
                  class="flex items-center justify-between py-1 hover:bg-gray-50 rounded"
                >
                  <div class="flex-1">
                    <div class="font-medium">{{ word.text }}</div>
                    <div class="text-sm text-gray-500">{{ word.meaning }}</div>
                  </div>
                  <Button
                    size="sm"
                    :variant="selectedWords.has(word.id) ? 'default' : 'outline'"
                    @click="toggleWord(word.id)"
                  >
                    {{ selectedWords.has(word.id) ? '已选择' : '选择' }}
                  </Button>
                </div>
              </div>
            </div>
            <div v-else-if="searchQuery && !isSearching" class="text-center text-gray-500 py-4">
              没有找到匹配的单词
            </div>
          </div>

          <!-- 批量添加模式 -->
          <div v-if="selectMode === 'batch'" class="space-y-4">
            <div class="space-y-2">
              <Label for="batch-input">粘贴单词列表（每行一个单词）</Label>
              <Textarea
                id="batch-input"
                v-model="batchInput"
                placeholder="例如：&#10;apple&#10;banana&#10;orange"
                rows="10"
              />
            </div>
            <Button @click="handleBatchAdd" :disabled="!batchInput.trim() || isProcessing">
              {{ isProcessing ? '处理中...' : '识别并添加' }}
            </Button>

            <!-- 批量添加结果 -->
            <div v-if="batchResult" class="space-y-2">
              <div class="p-4 bg-green-50 border border-green-200 rounded-lg">
                <p class="text-sm text-green-800">
                  成功识别 {{ batchResult.recognizedCount }} 个单词，无法识别
                  {{ batchResult.unrecognizedCount }} 个
                </p>
              </div>
              <div v-if="batchResult.unrecognizedWords.length > 0" class="text-sm text-gray-600">
                <p class="font-medium mb-1">无法识别的单词：</p>
                <p class="text-red-600">{{ batchResult.unrecognizedWords.join(', ') }}</p>
              </div>
            </div>
          </div>

          <!-- 已选择的单词列表（优化版） -->
          <div v-if="selectedWords.size > 0" class="space-y-2">
            <div class="flex items-center justify-between">
              <Label>已选择的单词（{{ selectedWords.size }} 个）</Label>
              <div class="flex gap-2">
                <Button variant="outline" size="sm" @click="showAllSelectedWords = true">
                  查看全部
                </Button>
                <AlertDialog>
                  <AlertDialogTrigger as-child>
                    <Button variant="outline" size="sm">清空</Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>确认清空</AlertDialogTitle>
                      <AlertDialogDescription>
                        确定要清空所有已选择的单词吗？当前已选择 {{ selectedWords.size }} 个单词。
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>取消</AlertDialogCancel>
                      <AlertDialogAction @click="clearSelectedWords">确认清空</AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </div>
            <!-- 只显示前10个作为预览 -->
            <div class="border rounded-lg p-4">
              <div class="flex flex-wrap gap-2">
                <Badge
                  v-for="wordId in previewSelectedWords"
                  :key="wordId"
                  variant="secondary"
                  class="cursor-pointer hover:bg-gray-300"
                  @click="toggleWord(wordId)"
                >
                  {{ getWordById(wordId)?.text || wordId }}
                  <span class="ml-1">×</span>
                </Badge>
                <Badge
                  v-if="selectedWords.size > 10"
                  variant="outline"
                  class="cursor-pointer hover:bg-gray-100"
                  @click="showAllSelectedWords = true"
                >
                  还有 {{ selectedWords.size - 10 }} 个...
                </Badge>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- 操作按钮 -->
      <div class="flex justify-between gap-4">
        <AlertDialog>
          <AlertDialogTrigger as-child>
            <Button variant="destructive">删除词库</Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>确认删除</AlertDialogTitle>
              <AlertDialogDescription>
                确定要删除词库"{{ libraryName }}"吗？此操作无法撤销。
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>取消</AlertDialogCancel>
              <AlertDialogAction @click="handleDelete">确认删除</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        <div class="flex gap-4">
          <Button variant="outline" @click="router.back()">取消</Button>
          <Button @click="handleSave" :disabled="!libraryName.trim() || isSaving">
            {{ isSaving ? '保存中...' : '保存' }}
          </Button>
        </div>
      </div>
    </div>

    <!-- 查看全部已选择单词的对话框 -->
    <Dialog v-model:open="showAllSelectedWords">
      <DialogContent class="max-w-3xl max-h-[60vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>已选择的单词（{{ filteredSelectedWordsList.length }} 个）</DialogTitle>
        </DialogHeader>
        <div class="flex-1 overflow-hidden flex flex-col space-y-4">
          <!-- 搜索框 -->
          <div class="flex gap-2">
            <Input v-model="selectedWordsFilter" placeholder="搜索已选择的单词..." class="flex-1" />
            <AlertDialog>
              <AlertDialogTrigger as-child>
                <Button variant="outline" size="sm">清空全部</Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>确认清空</AlertDialogTitle>
                  <AlertDialogDescription>
                    确定要清空所有已选择的单词吗？当前已选择 {{ selectedWords.size }} 个单词。
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>取消</AlertDialogCancel>
                  <AlertDialogAction @click="clearSelectedWords">确认清空</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>

          <!-- 单词列表 -->
          <div class="flex-1 overflow-y-auto border rounded-lg">
            <Table v-if="filteredSelectedWordsList.length > 0">
              <TableHeader class="bg-gray-50 sticky top-0">
                <TableRow>
                  <TableHead class="text-center font-medium w-32">单词</TableHead>
                  <TableHead class="text-center font-medium">释义</TableHead>
                  <TableHead class="text-center font-medium w-24">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-for="wordId in filteredSelectedWordsList" :key="wordId">
                  <TableCell class="text-center font-medium w-32">
                    {{ getWordById(wordId)?.text || '-' }}
                  </TableCell>
                  <TableCell
                    class="text-sm text-gray-600 wrap-break-word whitespace-normal max-w-md"
                  >
                    {{ getWordById(wordId)?.meaning || '-' }}
                  </TableCell>
                  <TableCell class="text-center w-24">
                    <Button
                      variant="ghost"
                      size="sm"
                      @click="toggleWord(wordId)"
                      class="text-red-600 hover:text-red-700 hover:bg-red-50"
                    >
                      删除
                    </Button>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
            <div v-else class="text-center py-8 text-gray-500">
              {{ selectedWordsFilter ? '没有找到匹配的单词' : '暂无已选择的单词' }}
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="showAllSelectedWords = false">关闭</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { useLibraryStore, type Word } from '@/stores/library'
import { useNotificationStore } from '@/stores/notification'

const router = useRouter()
const route = useRoute()
const libraryStore = useLibraryStore()
const notificationStore = useNotificationStore()

// 获取词库ID
const libraryId = ref<number>(Number(route.params.id))

// 基本信息
const libraryName = ref('')
const libraryDescription = ref('')

// 单词选择
const selectMode = ref<'search' | 'batch'>('search')
const selectedWords = ref<Set<number>>(new Set())

// 搜索模式
const searchQuery = ref('')
const searchResults = ref<Word[]>([])
const isSearching = ref(false)
let searchDebounceTimer: number | null = null

// 批量添加模式
const batchInput = ref('')
const batchResult = ref<{
  recognizedCount: number
  unrecognizedCount: number
  unrecognizedWords: string[]
} | null>(null)
const isProcessing = ref(false)

// 保存状态
const isSaving = ref(false)

// 单词缓存（用于显示已选择的单词）
const wordCache = ref<Map<number, Word>>(new Map())

// 查看全部已选择单词的对话框
const showAllSelectedWords = ref(false)
const selectedWordsFilter = ref('')

// 加载词库详情
async function loadLibraryDetails() {
  try {
    const details = await libraryStore.getLibraryDetails(libraryId.value)
    libraryName.value = details.name
    libraryDescription.value = details.description || ''
    // 加载已选择的单词
    details.words.forEach((word: Word) => {
      selectedWords.value.add(word.id)
      wordCache.value.set(word.id, word)
    })
  } catch {
    notificationStore.addNotification({
      title: '加载失败',
      description: '无法加载词库详情',
      variant: 'destructive',
      duration: 3000,
    })
  }
}

// 搜索单词
async function handleSearch() {
  if (!searchQuery.value.trim()) {
    searchResults.value = []
    return
  }

  isSearching.value = true
  try {
    const results = await libraryStore.searchWords(searchQuery.value)
    searchResults.value = results
    // 缓存搜索结果
    results.forEach((word: Word) => {
      wordCache.value.set(word.id, word)
    })
  } catch {
    notificationStore.addNotification({
      title: '搜索失败',
      description: '搜索单词时出错',
      variant: 'destructive',
      duration: 3000,
    })
  } finally {
    isSearching.value = false
  }
}

// 防抖搜索 - 输入停止300ms后才执行搜索
function handleSearchDebounced() {
  // 清除之前的计时器
  if (searchDebounceTimer !== null) {
    clearTimeout(searchDebounceTimer)
  }

  // 如果搜索框为空，立即清空结果
  if (!searchQuery.value.trim()) {
    searchResults.value = []
    return
  }

  // 设置新的计时器，300ms后执行搜索
  searchDebounceTimer = window.setTimeout(() => {
    handleSearch()
  }, 300)
}

// 切换单词选择状态
function toggleWord(wordId: number) {
  if (selectedWords.value.has(wordId)) {
    selectedWords.value.delete(wordId)
  } else {
    selectedWords.value.add(wordId)
  }
}

// 批量添加单词
async function handleBatchAdd() {
  const words = batchInput.value
    .split('\n')
    .map((w) => w.trim())
    .filter((w) => w.length > 0)

  if (words.length === 0) return

  isProcessing.value = true
  try {
    const result = await libraryStore.batchRecognizeWords(words)
    batchResult.value = result

    // 添加识别成功的单词到选择列表
    result.recognizedWords.forEach((word: Word) => {
      selectedWords.value.add(word.id)
      wordCache.value.set(word.id, word)
    })

    // 清空输入框
    if (result.recognizedCount > 0) {
      batchInput.value = ''
    }

    notificationStore.addNotification({
      title: '处理完成',
      description: `成功识别 ${result.recognizedCount} 个单词`,
      variant: 'default',
      duration: 3000,
    })
  } catch {
    notificationStore.addNotification({
      title: '处理失败',
      description: '批量添加单词时出错',
      variant: 'destructive',
      duration: 3000,
    })
  } finally {
    isProcessing.value = false
  }
}

// 获取单词信息
function getWordById(wordId: number) {
  return wordCache.value.get(wordId)
}

// 获取预览的已选择单词（前10个）
const previewSelectedWords = computed(() => {
  return Array.from(selectedWords.value).slice(0, 10)
})

// 获取过滤后的已选择单词列表
const filteredSelectedWordsList = computed(() => {
  const wordIds = Array.from(selectedWords.value)
  if (!selectedWordsFilter.value.trim()) {
    return wordIds
  }
  const filter = selectedWordsFilter.value.toLowerCase()
  return wordIds.filter((wordId) => {
    const word = getWordById(wordId)
    if (!word) return false
    return word.text.toLowerCase().includes(filter) || word.meaning?.toLowerCase().includes(filter)
  })
})

// 清空已选择的单词
function clearSelectedWords() {
  selectedWords.value.clear()
  showAllSelectedWords.value = false
}

// 保存词库
async function handleSave() {
  if (!libraryName.value.trim()) {
    notificationStore.addNotification({
      title: '提示',
      description: '请输入词库名称',
      variant: 'destructive',
      duration: 2000,
    })
    return
  }

  isSaving.value = true
  const res = await libraryStore.updateLibrary(libraryId.value, {
    name: libraryName.value,
    description: libraryDescription.value,
    words_id: Array.from(selectedWords.value),
  })
  if (res) {
    notificationStore.addNotification({
      title: '保存成功',
      description: '词库已更新',
      variant: 'default',
      duration: 2000,
    })
    router.back()
  } else {
    notificationStore.addNotification({
      title: '保存失败',
      description: '保存词库时出错',
      variant: 'destructive',
      duration: 3000,
    })
  }
  isSaving.value = false
}

// 删除词库
async function handleDelete() {
  const res = await libraryStore.removeLibrary(libraryId.value)
  if (res.success) {
    notificationStore.addNotification({
      variant: 'default',
      title: '成功',
      description: res.message,
      duration: 2000,
    })
    router.push({ name: 'library' })
  } else {
    notificationStore.addNotification({
      variant: 'destructive',
      title: '失败',
      description: res.message,
      duration: 4000,
    })
  }
}

onMounted(() => {
  loadLibraryDetails()
})

// 组件卸载时清理计时器
onUnmounted(() => {
  if (searchDebounceTimer !== null) {
    clearTimeout(searchDebounceTimer)
  }
})
</script>
