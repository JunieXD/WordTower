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
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const store = useNotificationStore()

const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const confirm = ref('')

// 登录函数
const login = async () => {
  const res = await request.post('/api/auth/login', {
    username: username.value,
    passwordHash: password.value,
  })
  if (res.data.code === 0) {
    localStorage.setItem('auth_token', res.data.data)
    store.addNotification({
      title: '登录成功',
      description: '您已成功登录。',
      variant: 'default',
      duration: 2000,
    })
    // 从 URL 查询参数获取 redirect
    const redirect = route.query.redirect || '/'
    router.push(redirect as string)
  } else {
    store.addNotification({
      title: '登录失败',
      description: res.data.msg,
      variant: 'destructive',
      duration: 4000,
    })
  }
}

// 注册函数
const register = async () => {
  if (password.value !== confirm.value) {
    store.addNotification({
      title: '注册失败',
      description: '两次密码不一致',
      variant: 'destructive',
      duration: 4000,
    })
    return
  }
  const res = await request.post('/api/auth/register', {
    username: username.value,
    passwordHash: password.value,
  })
  if (res.data.code === 0) {
    store.addNotification({
      title: '注册成功',
      description: '您已成功注册。',
      variant: 'default',
      duration: 2000,
    })
    mode.value = 'login'
  } else {
    store.addNotification({
      title: '注册失败',
      description: res.data.msg,
      variant: 'destructive',
      duration: 4000,
    })
  }
}

// 提交按钮逻辑
const handleSubmit = () => {
  if (mode.value === 'login') login()
  else register()
}
</script>

<template>
  <div class="flex items-center justify-center h-screen w-screen">
    <Card class="flex flex-col min-w-[350px] max-w-[400px] w-2/3">
      <CardHeader class="flex-none gap-5">
        <CardTitle class="flex justify-center">
          <Button
            :variant="mode === 'login' ? 'default' : 'outline'"
            class="text-1xl mx-4 cursor-pointer"
            @click="mode = 'login'"
          >
            登 录
          </Button>
          <Button
            :variant="mode === 'register' ? 'default' : 'outline'"
            class="text-1xl mx-4 cursor-pointer"
            @click="mode = 'register'"
          >
            注 册
          </Button>
        </CardTitle>
        <CardDescription class="tracking-wider">
          {{ mode === 'login' ? '请使用用户名和密码登录。' : '请填写信息完成注册。' }}
        </CardDescription>
      </CardHeader>
      <CardContent class="grow content-center">
        <form>
          <div class="flex flex-col space-y-4">
            <Label for="username">用户名</Label>
            <Input v-model="username" placeholder="username" />
            <Label for="password">密码</Label>
            <Input
              v-model="password"
              placeholder="password"
              type="password"
              @keyup.enter.prevent="handleSubmit"
            />
            <!-- 注册多一个确认密码输入框 -->
            <div v-if="mode === 'register'" class="flex flex-col space-y-4">
              <Label for="confirm">确认密码</Label>
              <Input
                v-model="confirm"
                placeholder="confirm password"
                type="password"
                @keyup.enter.prevent="handleSubmit"
              />
            </div>
          </div>
        </form>
      </CardContent>
      <CardFooter class="flex flex-none justify-center">
        <Button @click="handleSubmit" variant="outline" class="w-2/5 text-1xl cursor-pointer">
          {{ mode === 'login' ? '登&nbsp;&nbsp;录' : '注&nbsp;&nbsp;册' }}
        </Button>
      </CardFooter>
    </Card>
  </div>
</template>
