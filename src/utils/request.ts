import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notification'
import axios, { AxiosError } from 'axios'

const request = axios.create({
  baseURL: 'http://localhost:8080',
  timeout: 5000,
})

// 请求拦截器（可自动加 token）
request.interceptors.request.use((config) => {
  const authStore = useAuthStore()
  if (!authStore.token) {
    authStore.initToken()
  }

  if (authStore.token) {
    config.headers.Authorization = `Bearer ${authStore.token}`
  }
  return config
})

// 响应拦截器
request.interceptors.response.use(
  (res) => res,
  async (err: AxiosError) => {
    const authStore = useAuthStore()
    const notificationStore = useNotificationStore()
    if (err.response?.status === 401) {
      authStore.clearToken()
      notificationStore.addNotification({
        title: '登录已过期',
        description: '登录已过期，请重新登录',
        variant: 'destructive',
        duration: 4000,
      })
      setTimeout(() => {
        window.location.href = '/login'
      }, 2000)
    }
    return Promise.reject(err)
  },
)

export default request
