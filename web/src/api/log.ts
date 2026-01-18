import request from './request'
import type { LogEntry } from '@/types'

export async function getLogHistory(offset: number = 0, limit: number = 1000): Promise<LogEntry[]> {
  const response: any = await request.get('/logs/history', {
    params: { offset, limit }
  })
  return (response.lines || []) as LogEntry[]
}
