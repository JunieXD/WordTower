import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AxiosError, type AxiosRequestConfig } from 'axios'
import request from '../request'
import {
  cancelPendingActions,
  clearPendingActions,
  reliableRequest,
  requestRecovery,
} from '../reliableRequest'

vi.mock('../request', () => ({ default: vi.fn() }))
const send = vi.mocked(request)
const sent = (index: number) => send.mock.calls[index]![0] as unknown as AxiosRequestConfig
const success = { status: 200, data: { success: true, data: { id: 1 } }, headers: {} }
const config = { method: 'post', url: '/api/question/check', data: { user_input: 'My answer' } }

describe('retry-safe requests', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    clearPendingActions()
    send.mockReset()
  })
  afterEach(() => {
    clearPendingActions()
    vi.useRealTimers()
  })

  it('merges double-clicks into one request', async () => {
    send.mockResolvedValue(success)
    const first = reliableRequest(config)
    const second = reliableRequest(config)
    expect(first).toBe(second)
    await first
    expect(send).toHaveBeenCalledTimes(1)
  })

  it('retries a lost response with the original ID and unchanged input', async () => {
    send
      .mockRejectedValueOnce(new AxiosError('timeout', 'ECONNABORTED'))
      .mockResolvedValueOnce(success)
    const result = reliableRequest(config)
    await vi.advanceTimersByTimeAsync(1000)
    await expect(result).resolves.toEqual(success)
    expect(sent(0).headers!['Idempotency-Key']).toBe(sent(1).headers!['Idempotency-Key'])
    expect(sent(1).data).toEqual(config.data)
    expect(requestRecovery.value).toBe('')
  })

  it('shows a countdown and only retries a rate limit once', async () => {
    send.mockResolvedValue({
      status: 429,
      data: { message: '请稍等' },
      headers: { 'retry-after': '3' },
    })
    const result = reliableRequest(config)
    const assertion = expect(result).rejects.toThrow('请稍等')
    await vi.advanceTimersByTimeAsync(0)
    expect(requestRecovery.value).toContain('3 秒')
    await vi.advanceTimersByTimeAsync(3000)
    await assertion
    expect(send).toHaveBeenCalledTimes(2)
  })

  it('confirms an in-flight result without creating a new action', async () => {
    send
      .mockResolvedValueOnce({ status: 425, data: {}, headers: { 'retry-after': '2' } })
      .mockResolvedValueOnce(success)
    const result = reliableRequest(config)
    await vi.advanceTimersByTimeAsync(2000)
    await result
    expect(sent(0).headers!['Idempotency-Key']).toBe(sent(1).headers!['Idempotency-Key'])
  })

  it('retains the ID after a server error for a manual retry', async () => {
    send
      .mockResolvedValueOnce({ status: 503, data: { message: '稍后重试' }, headers: {} })
      .mockResolvedValueOnce(success)
    await expect(reliableRequest(config)).rejects.toThrow('稍后重试')
    await reliableRequest(config)
    expect(sent(0).headers!['Idempotency-Key']).toBe(sent(1).headers!['Idempotency-Key'])
  })

  it('cancels obsolete retry timers when leaving the page', async () => {
    send.mockResolvedValue({ status: 429, data: {}, headers: { 'retry-after': '3' } })
    const result = reliableRequest(config)
    const assertion = expect(result).rejects.toThrow()
    await vi.advanceTimersByTimeAsync(0)
    cancelPendingActions()
    await assertion
    await vi.advanceTimersByTimeAsync(10000)
    expect(send).toHaveBeenCalledTimes(1)
    expect(requestRecovery.value).toBe('')
  })
})
