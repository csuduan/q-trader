import api from './request'
import type { Order, ManualOrderRequest } from '@/types'

/**
 * 委托单 API
 */
export const orderApi = {
  /**
   * 获取委托单列表
   */
  getOrders: async (status?: string): Promise<Order[]> => {
    return api.get<Order[]>('/order', { params: { status } })
  },

  /**
   * 获取指定委托单详情
   */
  getOrderById: async (orderId: string): Promise<Order> => {
    return api.get<Order>(`/order/${orderId}`)
  },

  /**
   * 手动报单
   */
  createOrder: async (order: ManualOrderRequest): Promise<{ order_id: string }> => {
    return api.post<{ order_id: string }>('/order', order)
  },

  /**
   * 撤销委托单
   */
  cancelOrder: async (orderId: string): Promise<{ order_id: string }> => {
    return api.delete<{ order_id: string }>(`/order/${orderId}`)
  },

  /**
   * 批量撤销委托单
   */
  cancelBatchOrders: async (orderIds: string[]): Promise<{ success_count: number; total: number; failed_orders: string[] }> => {
    return api.post<{ success_count: number; total: number; failed_orders: string[] }>('/order/cancel-batch', { order_ids: orderIds })
  }
}
