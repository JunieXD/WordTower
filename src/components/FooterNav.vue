<template>
  <nav
    class="fixed bottom-0 left-0 right-0 bg-white border-t flex justify-around items-center h-16 text-gray-600"
  >
    <RouterLink to="/home" custom v-slot="{ navigate, isExactActive }">
      <button
        @click="navigate"
        :class="['flex flex-col items-center', isExactActive ? 'text-blue-600' : 'text-gray-600']"
      >
        <Icon icon="mdi:home-variant-outline" class="size-8" />
        <span class="text-xs">首页</span>
      </button>
    </RouterLink>
    <RouterLink to="/library" custom v-slot="{ navigate, isExactActive }">
      <button
        @click="navigate"
        :class="['flex flex-col items-center', isExactActive ? 'text-blue-600' : 'text-gray-600']"
      >
        <Icon icon="mdi:bookshelf" class="size-8" />
        <span class="text-xs">词库</span>
      </button>
    </RouterLink>
    <RouterLink to="/profile" custom v-slot="{ navigate, isExactActive }">
      <button
        @click="navigate"
        :class="['flex flex-col items-center', isExactActive ? 'text-blue-600' : 'text-gray-600']"
      >
        <Icon icon="mdi:account" class="size-8" />
        <span class="text-xs">我的</span>
      </button>
    </RouterLink>
  </nav>
</template>
