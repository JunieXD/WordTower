<template>
  <div
    class="min-h-screen flex items-center justify-center bg-linear-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 px-4"
  >
    <div class="text-center space-y-8 max-w-md w-full">
      <!-- 404 数字 -->
      <div class="space-y-4">
        <h1
          class="text-9xl font-bold text-transparent bg-clip-text bg-linear-to-br from-blue-500 via-purple-500 to-pink-500"
        >
          404
        </h1>
        <div
          class="h-1 w-24 bg-linear-to-br from-blue-500 to-purple-500 mx-auto rounded-full"
        ></div>
      </div>

      <!-- 错误信息 -->
      <div class="space-y-3">
        <h2 class="text-2xl font-semibold text-gray-800 dark:text-gray-200">页面未找到</h2>
        <p class="text-gray-600 dark:text-gray-400 text-lg">抱歉，您要找的页面不存在。</p>
      </div>

      <!-- 返回首页按钮 -->
      <RouterLink
        to="/"
        class="inline-flex items-center justify-center px-6 py-3 bg-linear-to-br from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white font-medium rounded-lg shadow-lg hover:shadow-xl transform hover:scale-105 transition-all duration-200 ease-in-out"
      >
        <span>返回首页</span>
        <svg class="ml-2 w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M13 7l5 5m0 0l-5 5m5-5H6"
          />
        </svg>
      </RouterLink>
    </div>
  </div>
</template>
