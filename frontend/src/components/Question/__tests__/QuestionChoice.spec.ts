import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import QuestionChoice from '@/components/Question/QuestionChoice.vue'

describe('QuestionChoice', () => {
  it('highlights inferred inflected forms when storyTargetForms is missing', () => {
    const wrapper = mount(QuestionChoice, {
      props: {
        question: {
          id: 1,
          type: 'context_guess',
          content: {
            target_word: 'kick',
            story:
              'Last Saturday, Tom went to the park with his little sister. Tom wanted to play, so he kicked it hard.',
            options: {
              A: '踢',
              B: '拿',
              C: '放',
              D: '看',
            },
            correct_option: 'A',
            explanation: '这里表示踢球。',
          },
        },
      },
    })

    expect(wrapper.html()).toContain('<strong class="underline">kicked</strong>')
  })

  it('locks the question and shows explanation after the first wrong answer', async () => {
    const wrapper = mount(QuestionChoice, {
      props: {
        question: {
          id: 2,
          type: 'context_guess',
          content: {
            target_word: 'canal',
            story: 'We walked along a wide canal.',
            options: {
              A: '管',
              B: '沟渠',
              C: '开运河',
              D: '水道',
            },
            correct_option: 'D',
            explanation: '这里表示水道。',
          },
        },
      },
    })

    await wrapper.get('button').trigger('click')

    expect(wrapper.text()).toContain('✗ 回答有误。解析：')
    expect(wrapper.text()).toContain('正确答案：水道')
    const optionButtons = wrapper.findAll('button').slice(0, 4)
    expect(optionButtons).toHaveLength(4)
    expect(optionButtons[0]?.classes()).toContain('bg-red-500')
    expect(optionButtons[3]?.classes()).toContain('bg-green-500')
    optionButtons.slice(1).forEach((button) => {
      expect(button.attributes('disabled')).toBeDefined()
    })
  })
})
