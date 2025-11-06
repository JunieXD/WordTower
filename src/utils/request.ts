import axios from 'axios'

const request = axios.create({
  baseURL: 'http://localhost:8080',
  timeout: 5000,
})

// 请求拦截器（可自动加 token）
request.interceptors.request.use((config) => {
  const auth_token = localStorage.getItem('auth_token')
  if (auth_token) {
    config.headers.Authorization = `Bearer ${auth_token}`
  }
  return config
})

// 响应拦截器
request.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      alert('登录已过期，请重新登录')
      localStorage.removeItem('auth_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

export default request
