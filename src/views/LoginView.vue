<script setup lang="ts">
import { ref } from 'vue'
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

const mode = ref<'login' | 'register'>('login')
</script>

<template>
  <div class="flex items-center justify-center h-screen w-screen">
    <Card class="flex flex-col min-w-[350px] max-w-[450px] w-2/3">
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
            <Input id="username" placeholder="username" />
            <Label for="password">密码</Label>
            <Input id="password" placeholder="password" />
            <!-- 注册多一个确认密码输入框 -->
            <div v-if="mode === 'register'" class="flex flex-col space-y-4">
              <Label for="confirm">确认密码</Label>
              <Input id="confirm" placeholder="confirm password" />
            </div>
          </div>
        </form>
      </CardContent>
      <CardFooter class="flex flex-none justify-center">
        <Button variant="outline" class="w-2/5 text-1xl cursor-pointer">
          {{ mode === 'login' ? '登&nbsp;&nbsp;录' : '注&nbsp;&nbsp;册' }}
        </Button>
      </CardFooter>
    </Card>
  </div>
</template>
