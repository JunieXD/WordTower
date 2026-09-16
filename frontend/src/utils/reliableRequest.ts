import { ref } from 'vue'
import axios, { type AxiosRequestConfig, type AxiosResponse } from 'axios'
import request from './request'

// Transient status only: answers stay in their original component/store.
export const requestRecovery = ref('')
const pending = new Map<string, { id: string; expires: number }>()
const inflight = new Map<string, Promise<AxiosResponse>>()
let generation = 0
let activeController = new AbortController()

export function cancelPendingActions() {
  generation++
  activeController.abort()
  activeController = new AbortController()
  inflight.clear()
  requestRecovery.value = ''
}

export function clearPendingActions() {
  cancelPendingActions()
  pending.clear()
}

function wait(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(new axios.CanceledError())
    const cancel = () => {
      clearTimeout(timer)
      reject(new axios.CanceledError())
    }
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', cancel)
      resolve()
    }, milliseconds)
    signal.addEventListener('abort', cancel, { once: true })
  })
}

function makeId(): string {
  // randomUUID is unavailable on some HTTP LAN development origins.
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  return Array.from(bytes, (value) => value.toString(16).padStart(2, '0')).join('')
}

/** Only use for endpoints that implement server-side replay protection. */
export function reliableRequest(config: AxiosRequestConfig): Promise<AxiosResponse> {
  const key = JSON.stringify([config.method ?? 'get', config.url, config.data ?? null])
  const running = inflight.get(key)
  if (running) return running
  const now = Date.now()
  for (const [entryKey, entry] of pending) {
    if (entry.expires <= now) pending.delete(entryKey)
  }
  let entry = pending.get(key)
  if (!entry) {
    entry = { id: makeId(), expires: now + 24 * 60 * 60 * 1000 }
    pending.set(key, entry)
  }
  const id = entry.id
  const currentGeneration = generation
  const signal = activeController.signal
  const task = (async () => {
    let networkRetries = 0
    let rateRetries = 0
    const deadline = Date.now() + 60_000
    try {
      while (true) {
        let response: AxiosResponse
        try {
          response = await request({
            ...config,
            timeout: config.timeout ?? 30_000,
            signal,
            headers: { ...config.headers, 'Idempotency-Key': id },
          })
        } catch (error) {
          if (axios.isCancel(error) || signal.aborted) throw error
          if (networkRetries++ >= 1 || Date.now() >= deadline) {
            throw new Error('网络连接不稳定，当前内容已保留，请点击重试确认结果。')
          }
          requestRecovery.value = '网络连接不稳定，正在确认上次操作的结果…'
          await wait(1000, signal)
          continue
        }
        if (response.status < 400 && response.data?.success !== false) {
          pending.delete(key)
          return response
        }
        const retryable = response.status === 429 || response.status === 425
        const delay = Math.max(
          1,
          Math.min(
            60,
            Number(response.headers['retry-after'] ?? response.data?.details?.retry_after ?? 2) ||
              2,
          ),
        )
        if (
          retryable &&
          Date.now() + delay * 1000 < deadline &&
          (response.status === 425 || rateRetries++ < 1)
        ) {
          for (let seconds = Math.ceil(delay); seconds > 0; seconds--) {
            requestRecovery.value =
              response.status === 425
                ? `上次操作仍在处理中，${seconds} 秒后确认结果…`
                : `请求有些密集，${seconds} 秒后自动继续，当前内容会保留。`
            await wait(1000, signal)
          }
          continue
        }
        // Keep the ID on ambiguous/server errors so a manual retry is safe too.
        if (response.status >= 400 && response.status < 500 && !retryable) pending.delete(key)
        throw new Error(response.data?.message || '暂时未能完成，当前内容已保留，请稍后重试。')
      }
    } finally {
      if (generation === currentGeneration) {
        inflight.delete(key)
        requestRecovery.value = ''
      }
    }
  })()
  inflight.set(key, task)
  return task
}
