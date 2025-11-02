<template>
  <n-layout has-sider>
    <!-- 侧边栏：仅桌面端显示 -->
    <n-layout-sider> sider </n-layout-sider>

    <!-- 主布局（Header + Content + Footer） -->
    <n-layout>
      <n-layout-header> header </n-layout-header>

      <n-layout-content>
        <router-view />
      </n-layout-content>

      <n-layout-footer> footer </n-layout-footer>
    </n-layout>
  </n-layout>
</template>

<style scoped></style>
