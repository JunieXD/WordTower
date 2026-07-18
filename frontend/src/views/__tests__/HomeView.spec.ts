import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import HomeView from '@/views/HomeView.vue'
import request from '@/utils/request'

vi.mock('@/utils/request', () => ({
  default: {
    get: vi.fn(),
  },
}))

describe('HomeView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(request.get).mockImplementation((url) => {
      if (url === '/api/auth/profile') {
        return Promise.resolve({
          data: {
            success: true,
            data: {
              id: 1,
              nickname: 'Junie',
              username: 'junie',
              email: null,
              avatar_url: null,
              exp: 100,
              coins: 50,
              created_at: new Date().toISOString(),
              last_login: new Date().toISOString(),
              status: 'active',
              max_hp: 100,
              attack: 10,
              crit_rate: 0,
              role: 'user',
              max_floor: 12,
            },
          },
        })
      }

      if (url === '/api/daily-challenge/overview') {
        return Promise.resolve({
          data: {
            success: true,
            data: {
              day_key: '2026-04-06',
              opens_at: new Date().toISOString(),
              closes_at: new Date(Date.now() + 60_000).toISOString(),
              seconds_until_reset: 3600,
              user_status: 'ended',
              today_best_floor: 9,
              active_run: null,
              leaderboard: [],
              current_user_rank: null,
              current_user_entry: null,
            },
          },
        })
      }

      return Promise.resolve({
        data: {
          success: true,
          data: null,
        },
      })
    })
  })

  it('shows the ended daily challenge state on the home page', async () => {
    const wrapper = mount(HomeView, {
      global: {
        stubs: {
          RouterLink: true,
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('每日挑战')
    expect(wrapper.text()).toContain('第 9 层')
    expect(wrapper.text()).toContain('今日已结束，明早 6 点刷新')
  })
})
