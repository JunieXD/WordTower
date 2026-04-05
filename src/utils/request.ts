import axios, { AxiosError } from 'axios'

const envBaseURL = import.meta.env.VITE_API_BASE_URL?.trim()
const isLocalHost =
  typeof window !== 'undefined' && ['localhost', '127.0.0.1'].includes(window.location.hostname)

// 优先使用环境变量；未配置时本地走后端直连，生产走同源
const baseURL = envBaseURL || (isLocalHost ? 'http://localhost:8000' : '')

const request = axios.create({
  baseURL,
  timeout: 5000,
  withCredentials: true,
  validateStatus: function (status) {
    return status < 600 // 允许错误状态码进入 .then() 成功回调
  },
})

// 请求拦截器
request.interceptors.request.use((config) => {
  return config
})

// 响应拦截器
request.interceptors.response.use(
  (res) => {
    return res
  },
  async (err: AxiosError) => {
    return Promise.reject(err)
  },
)

export default request
