import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import HistoryView from '@/views/HistoryView.vue'
import request from '@/utils/request'

const pushMock = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}))

vi.mock('@/utils/request', () => ({
  default: {
    get: vi.fn(),
  },
}))

describe('HistoryView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    pushMock.mockReset()
    vi.mocked(request.get).mockResolvedValue({
      data: {
        success: true,
        data: [
          {
            run_ref: 'tower-7',
            run_id: 7,
            mode: 'tower',
            status: 'in_progress',
            day_key: null,
            started_at: new Date().toISOString(),
            ended_at: null,
            highest_floor: 3,
            current_floor: 3,
            total_exp: 20,
            total_coins: 10,
            question_count: 4,
            last_hp: null,
          },
        ],
      },
    })
  })

  it('renders history runs and navigates to detail page', async () => {
    const wrapper = mount(HistoryView)

    await flushPromises()

    expect(vi.mocked(request.get)).toHaveBeenCalledWith('/api/history/runs')
    expect(wrapper.text()).toContain('第 1 次闯塔')
    expect(wrapper.text()).toContain('普通闯塔')
    expect(wrapper.text()).toContain('进行中')
    expect(wrapper.text()).toContain('题目数：4')

    await wrapper.get('button[type="button"]').trigger('click')

    expect(pushMock).toHaveBeenCalledWith({ name: 'history-detail', params: { runId: 'tower-7' } })
  })
})
