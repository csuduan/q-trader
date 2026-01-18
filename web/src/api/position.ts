import api from './request'
import type { Position } from '@/types'

/**
 * 持仓相关 API
 */
export const positionApi = {
  /**
   * 获取持仓列表
   */
  getPositions: async (): Promise<Position[]> => {
    return api.get<Position[]>('/position')
  },

  /**
   * 获取指定合约持仓
   */
  getPositionBySymbol: async (symbol: string): Promise<Position[]> => {
    return api.get<Position[]>(`/position/${symbol}`)
  },

  /**
   * 平仓
   */
  closePosition: async (data: {
    symbol: string
    direction: string
    offset: string
    volume: number
    price?: number
  }): Promise<{ order_id: string }> => {
    return api.post<{ order_id: string }>('/position/close', data)
  },

  /**
   * 批量平仓
   */
  closeBatchPositions: async (positions: Array<{
    symbol: string
    direction: string
    offset: string
    volume: number
    price?: number
  }>): Promise<{ success_count: number; total: number; failed_orders: any[] }> => {
    return api.post<{ success_count: number; total: number; failed_orders: any[] }>('/position/close-batch', { positions })
  }
}
