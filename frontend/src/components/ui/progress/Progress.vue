<script setup lang="ts">
import type { ProgressRootProps } from 'reka-ui'
import type { HTMLAttributes } from 'vue'
import { reactiveOmit } from '@vueuse/core'
import { ProgressIndicator, ProgressRoot } from 'reka-ui'
import { cn } from '@/lib/utils'
import { computed } from 'vue'

const props = withDefaults(
  defineProps<
    ProgressRootProps & {
      class?: HTMLAttributes['class']
      label?: string
      showLabel?: boolean
    }
  >(),
  {
    modelValue: 0,
    showLabel: true,
  },
)

const delegatedProps = reactiveOmit(props, 'class', 'label', 'showLabel')

const displayLabel = computed(() => {
  if (props.label !== undefined) {
    return props.label
  }
  return props.showLabel ? `${Math.round(props.modelValue ?? 0)}%` : ''
})
</script>

<template>
  <ProgressRoot
    data-slot="progress"
    v-bind="delegatedProps"
    :class="cn('bg-primary/20 relative h-3 w-full overflow-hidden rounded-full', props.class)"
  >
    <ProgressIndicator
      data-slot="progress-indicator"
      class="bg-primary h-full w-full flex-1 transition-all"
      :style="`transform: translateX(-${100 - (props.modelValue ?? 0)}%);`"
    />
    <span
      v-if="displayLabel"
      class="absolute inset-0 flex items-center justify-center text-xs font-medium text-primary-foreground z-1 pointer-events-none"
    >
      {{ displayLabel }}
    </span>
  </ProgressRoot>
</template>
