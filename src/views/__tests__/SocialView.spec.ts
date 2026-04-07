import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import SocialView from '@/views/SocialView.vue'
import request from '@/utils/request'

const pushMock = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => ({
    query: {},
  }),
  useRouter: () => ({
    push: pushMock,
    replace: vi.fn(),
  }),
}))

vi.mock('@/utils/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('SocialView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    pushMock.mockReset()
    vi.mocked(request.get).mockImplementation((url, config) => {
      if (url === '/api/social/friends') {
        return Promise.resolve({
          data: {
            success: true,
            data: [
              {
                relation_id: 1,
                friend: {
                  id: 2,
                  username: 'bob',
                  nickname: '学习搭子',
                  avatar_url: null,
                  exp: 230,
                  level: 2,
                  max_floor: 8,
                  social_status: 'online',
                  last_online_at: new Date().toISOString(),
                },
                unread_count: 3,
                last_message: {
                  id: 7,
                  sender_id: 2,
                  recipient_id: 1,
                  content: '一起刷塔吗',
                  created_at: new Date().toISOString(),
                  read_at: null,
                },
              },
            ],
          },
        })
      }

      if (url === '/api/social/requests') {
        return Promise.resolve({
          data: {
            success: true,
            data: [
              {
                request_id: 5,
                created_at: new Date().toISOString(),
                requester: {
                  id: 3,
                  username: 'carol',
                  nickname: '夜行者',
                  avatar_url: null,
                  exp: 120,
                  level: 1,
                  max_floor: 4,
                  social_status: 'offline',
                  last_online_at: null,
                },
              },
            ],
          },
        })
      }

      if (url === '/api/social/unread-summary') {
        return Promise.resolve({
          data: {
            success: true,
            data: { total: 3 },
          },
        })
      }

      if (url === '/api/social/search') {
        return Promise.resolve({
          data: {
            success: true,
            data: [
              {
                user: {
                  id: 4,
                  username: 'eve',
                  nickname: '新朋友',
                  avatar_url: null,
                  exp: 50,
                  level: 0,
                  max_floor: 1,
                  social_status: 'offline',
                  last_online_at: null,
                },
                relation_status: 'none',
                request_id: null,
              },
            ],
          },
        })
      }

      return Promise.resolve({
        data: {
          success: true,
          data: config?.params?.q ? [] : { total: 0 },
        },
      })
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
  })

  it('renders requests, conversations, and unread badge from social APIs', async () => {
    const wrapper = mount(SocialView)

    await flushPromises()

    expect(wrapper.text()).toContain('好友申请')
    expect(wrapper.text()).toContain('夜行者')
    expect(wrapper.text()).toContain('学习搭子')
    expect(wrapper.text()).toContain('一起刷塔吗')
    expect(wrapper.text()).toContain('3')

    wrapper.unmount()
  })

  it('searches global users after debounce', async () => {
    const wrapper = mount(SocialView)
    await flushPromises()

    await wrapper.get('input').setValue('eve')
    await vi.advanceTimersByTimeAsync(300)
    await flushPromises()

    expect(vi.mocked(request.get)).toHaveBeenCalledWith('/api/social/search', {
      params: { q: 'eve' },
    })
    expect(wrapper.text()).toContain('新朋友')

    wrapper.unmount()
  })
})
