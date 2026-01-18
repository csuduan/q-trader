import axios, { type AxiosResponse, type AxiosInstance } from 'axios'
import { ElMessage } from 'element-plus'

// 定义响应类型
export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}

const api: AxiosInstance = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json'
  }
})

// 响应拦截器 - 自动解包 data
api.interceptors.response.use(
  async (response: AxiosResponse<ApiResponse<any>>) => {
    const res = response.data
    if (res.code === 0) {
      return res.data as any
    } else {
      const error = new Error(res.message || '请求失败')
      console.error('API Error:', error)
      throw error
    }
  },
  async (error) => {
    console.error('Network Error:', error)
    if (error.response) {
      if (error.response.status === 500) {
        ElMessage.error('无法连接服务端')
        throw new Error('无法连接服务端')
      }
      if (error.response.data) {
        const errData = error.response.data as ApiResponse<any>
        throw new Error(errData.message || '请求失败')
      }
    }
    throw new Error('网络请求失败')
  }
)

export default api
