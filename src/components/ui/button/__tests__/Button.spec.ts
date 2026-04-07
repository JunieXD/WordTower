import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { Button } from '@/components/ui/button'

describe('Button', () => {
  it('renders loading state feedback', () => {
    const wrapper = mount(Button, {
      props: {
        loading: true,
      },
      slots: {
        default: '登录',
      },
    })

    expect(wrapper.attributes('aria-busy')).toBe('true')
    expect(wrapper.attributes('disabled')).toBeDefined()
    expect(wrapper.find('.animate-spin').exists()).toBe(true)
    expect(wrapper.text()).toContain('登录')
  })
})
