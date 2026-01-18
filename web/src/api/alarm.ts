import request from './request'
import type { Alarm, AlarmStats } from '@/types'

export const alarmApi = {
  getTodayAlarms(): Promise<Alarm[]> {
    return request.get('/alarm/list')
  },

  getAlarmStats(): Promise<AlarmStats> {
    return request.get('/alarm/stats')
  },

  confirmAlarm(alarmId: number): Promise<Alarm> {
    return request.post(`/alarm/confirm/${alarmId}`)
  }
}
