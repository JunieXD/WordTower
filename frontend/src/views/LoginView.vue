<script setup lang="ts">
import { ref } from 'vue'
import request from '@/utils/request'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useNotificationStore } from '@/stores/notification'
import { useUserProfileStore } from '@/stores/userProfile'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const notificationStore = useNotificationStore()
const userProfileStore = useUserProfileStore()

const mode = ref<'login' | 'register'>('login')
const username = ref('test')
const password = ref('123456')
const confirm = ref('')
const showRefreshTip = ref(false)
const isSubmitting = ref(false)

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

// 登录函数
const login = async () => {
  try {
    const res = await request.post('/api/auth/login', {
      username: username.value,
      password: password.value,
    })
    if (res.data.success) {
      // 登录成功后先确认登录态，避免路由守卫因资料未就绪将用户重新打回登录页
      let profile = null
      for (let i = 0; i < 3; i++) {
        profile = await userProfileStore.getProfile(true)
        if (profile) break
        await sleep(150)
      }
      if (!profile) {
        notificationStore.addNotification({
          title: '登录失败',
          description: '登录状态校验失败，请重试',
          variant: 'destructive',
          duration: 4000,
        })
        return
      }

      notificationStore.addNotification({
        title: '登录成功',
        description: '您已成功登录。',
        variant: 'default',
        duration: 2000,
      })
      const rawRedirect = route.query.redirect
      const redirect = Array.isArray(rawRedirect) ? rawRedirect[0] : rawRedirect
      await router.replace(redirect || '/home')
    } else {
      notificationStore.addNotification({
        title: '登录失败',
        description: res.data.message,
        variant: 'destructive',
        duration: 4000,
      })
    }
  } catch (error) {
    let errorMessage = '未知错误'
    if (error instanceof Error) errorMessage = error.message
    else errorMessage = String(error)
    notificationStore.addNotification({
        title: '登录失败',
        description: errorMessage,
        variant: 'destructive',
        duration: 4000,
      })
  }
}

// 注册函数
const register = async () => {
  if (password.value !== confirm.value) {
    notificationStore.addNotification({
      title: '注册失败',
      description: '两次密码不一致',
      variant: 'destructive',
      duration: 4000,
    })
    return
  }
  try {
    const res = await request.post('/api/auth/register', {
      username: username.value,
      password: password.value,
    })
    if (res.data.success) {
      notificationStore.addNotification({
        title: '注册成功',
        description: '您已成功注册。',
        variant: 'default',
        duration: 2000,
      })
      mode.value = 'login'
    } else {
      notificationStore.addNotification({
        title: '注册失败',
        description: res.data.message,
        variant: 'destructive',
        duration: 4000,
      })
    }
  }
  catch (error) {
    let errorMessage = '未知错误'
    if (error instanceof Error) errorMessage = error.message
    else errorMessage = String(error)
    notificationStore.addNotification({
        title: '登录失败',
        description: errorMessage,
        variant: 'destructive',
        duration: 4000,
      })
  }
}

// 提交按钮逻辑
const handleSubmit = async () => {
  if (isSubmitting.value) return

  isSubmitting.value = true
  try {
    if (mode.value === 'login') {
      showRefreshTip.value = true
      await login()
    } else {
      showRefreshTip.value = false
      await register()
    }
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="flex flex-col items-center justify-center h-screen w-screen">
    <div class="space-y-4 min-w-[350px] max-w-[400px] w-2/3">
      <h1
        class="text-center text-5xl font-bold text-transparent bg-clip-text bg-linear-to-br from-blue-500 via-purple-500 to-pink-500"
      >
        Word Tower
      </h1>
      <div
        class="h-1 w-[280px] bg-linear-to-br from-blue-500 to-purple-500 mx-auto rounded-full"
      ></div>
    </div>
    <Card class="flex flex-col min-w-[350px] max-w-[400px] w-2/3">
      <CardHeader class="flex-none gap-5">
        <CardTitle class="flex justify-center">
          <Button
            :variant="mode === 'login' ? 'default' : 'outline'"
            class="text-1xl mx-4 cursor-pointer"
            :disabled="isSubmitting"
            @click="mode = 'login'"
          >
            登 录
          </Button>
          <Button
            :variant="mode === 'register' ? 'default' : 'outline'"
            class="text-1xl mx-4 cursor-pointer"
            :disabled="isSubmitting"
            @click="mode = 'register'"
          >
            注 册
          </Button>
        </CardTitle>
        <CardDescription class="tracking-wider flex flex-col gap-2">
          <div>{{ mode === 'login' ? '请使用用户名和密码登录。' : '请填写信息完成注册。' }}</div>
          <div>测试用户名：test，密码：123456</div>
        </CardDescription>
      </CardHeader>
      <CardContent class="grow content-center">
        <form>
          <div class="flex flex-col gap-y-4">
            <Label for="username">用户名</Label>
            <Input v-model="username" placeholder="username" :disabled="isSubmitting" />
            <Label for="password">密码</Label>
            <Input
              v-model="password"
              placeholder="password"
              type="password"
              :disabled="isSubmitting"
              @keyup.enter.prevent="handleSubmit"
            />
            <p v-if="password.length > 0 && password.length < 6" class="text-sm text-red-500">
              密码少于6位
            </p>
            <!-- 注册多一个确认密码输入框 -->
            <template v-if="mode === 'register'">
              <Label for="confirm">确认密码</Label>
              <Input
                v-model="confirm"
                placeholder="confirm password"
                type="password"
                :disabled="isSubmitting"
                @keyup.enter.prevent="handleSubmit"
              />
              <p v-if="confirm.length > 0 && confirm !== password" class="text-sm text-red-500">
                两次密码不一致
              </p>
            </template>
          </div>
        </form>
      </CardContent>
      <CardFooter class="flex-col flex-none justify-center gap-4">
        <Button
          @click="handleSubmit"
          variant="outline"
          class="w-2/5 text-1xl"
          :loading="isSubmitting"
        >
          {{ mode === 'login' ? '登&nbsp;&nbsp;录' : '注&nbsp;&nbsp;册' }}
        </Button>
        <div v-if="showRefreshTip && mode === 'login'" class="text-red-500 text-sm">如登录成功但未跳转请刷新页面</div>
      </CardFooter>
    </Card>
  </div>
</template>
