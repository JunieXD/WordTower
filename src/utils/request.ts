import axios, { AxiosError } from 'axios'

const request = axios.create({
  baseURL: '',
  timeout: 5000,
  withCredentials: true,
  validateStatus: function (status) {
    return status < 500 // 允许 4xx 状态码进入 .then() 成功回调
  },
})

// 请求拦截器
request.interceptors.request.use((config) => {
  // console.log('发送请求：', config)
  return config
})

// 响应拦截器
request.interceptors.response.use(
  (res) => {
    // console.log('收到响应：', res)
    return res
  },
  async (err: AxiosError) => {
    // console.log('收到错误：', err.response)
    return Promise.reject(err)
  },
)

export default request
