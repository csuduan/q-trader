<template>
  <div class="strategy">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>策略管理</span>
          <el-space>
            <el-button type="success" @click="handleStartAll" :loading="loading">
              <el-icon><VideoPlay /></el-icon>
              启动
            </el-button>
            <el-button type="warning" @click="handleStopAll" :loading="loading">
              <el-icon><VideoPause /></el-icon>
              停止
            </el-button>
            <el-button type="primary" @click="handleReplayAll" :loading="replayAllLoading">
              <el-icon><VideoPlay /></el-icon>
              回播
            </el-button>
            <el-button @click="loadStrategies" :loading="loading">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </el-space>
        </div>
      </template>

      <el-table :data="strategies" stripe v-loading="loading" table-layout="auto">
        <el-table-column prop="strategy_id" label="策略ID" width="140" fixed />
        <el-table-column prop="config.symbol" label="合约" width="120" />
        <el-table-column prop="config.bar" label="时间类型" width="100">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.config.bar || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="运行状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.active ? 'success' : 'info'" size="small">
              {{ row.active ? '运行中' : '已停止' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="信号" width="100">
          <template #default="{ row }">
            <el-tooltip v-if="row.signal && row.signal.side !== 0" placement="left" :show-after="200">
              <template #content>
                <div class="signal-detail">
                  <div>方向: <span :class="row.signal.side > 0 ? 'text-long' : 'text-short'">{{ row.signal.side > 0 ? '多头' : '空头' }}</span></div>
                  <div v-if="row.signal.entry_price">入场价: {{ row.signal.entry_price.toFixed(2) }}</div>
                  <div v-if="row.signal.entry_time">入场时间: {{ formatDateTime(row.signal.entry_time) }}</div>
                  <div v-if="row.signal.entry_volume">目标手数: {{ row.signal.entry_volume }}</div>
                  <div v-if="row.signal.pos_volume">持仓手数: {{ row.signal.pos_volume }}</div>
                  <div v-if="row.signal.pos_price">持仓均价: {{ row.signal.pos_price.toFixed(2) }}</div>
                  <div v-if="row.signal.exit_time" class="exit-info">
                    <div>退出价: {{ row.signal.exit_price?.toFixed(2) || '-' }}</div>
                    <div>退出时间: {{ formatDateTime(row.signal.exit_time) }}</div>
                    <div>退出原因: {{ getExitReasonText(row.signal.exit_reason) }}</div>
                  </div>
                </div>
              </template>
              <el-tag :type="row.signal.side > 0 ? 'danger' : 'primary'" size="small">
                {{ row.signal.side > 0 ? '多' : '空' }}
              </el-tag>
            </el-tooltip>
            <el-tag v-else type="info" size="small">无</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="交易状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getTradingStatusType(row.trading_status)" size="small">
              {{ row.trading_status || '无' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="!row.active"
              type="success"
              size="small"
              @click="handleStartStrategy(row.strategy_id)"
            >
              启动
            </el-button>
            <el-button
              v-else
              type="warning"
              size="small"
              @click="handleStopStrategy(row.strategy_id)"
            >
              停止
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="strategies.length === 0" description="暂无策略" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useStore } from '@/stores'
import { strategyApi } from '@/api'

interface StrategyRes {
  strategy_id: string
  active: boolean
  enabled: boolean
  inited: boolean
  config: Record<string, any>
  params: Record<string, any>
  signal: SignalData
  trading_status: string
}

interface SignalData {
  side: number
  entry_price: number
  entry_time: string
  entry_volume: number
  exit_price: number
  exit_time: string | null
  exit_reason: string
  pos_volume: number
  pos_price: number | null
}

const store = useStore()
const loading = ref(false)
const strategies = ref<StrategyRes[]>([])
const replayAllLoading = ref(false)

function formatDateTime(dateStr: string | undefined): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function getExitReasonText(reason: string | undefined): string {
  const reasonMap: Record<string, string> = {
    'TP': '止盈',
    'SL': '止损',
    'FORCE': '强制平仓'
  }
  return reasonMap[reason || ''] || reason || '-'
}

function getTradingStatusType(status: string | undefined): string {
  const typeMap: Record<string, string> = {
    '无': 'info',
    '开仓中': 'primary',
    '平仓中': 'warning',
    '持仓': 'success'
  }
  return typeMap[status || ''] || 'info'
}

async function loadStrategies() {
  loading.value = true
  try {
    strategies.value = await strategyApi.getStrategies(store.selectedAccountId || undefined)
  } catch (error: any) {
    ElMessage.error(`加载策略失败: ${error.message}`)
  } finally {
    loading.value = false
  }
}

async function handleStartStrategy(strategyId: string) {
  try {
    await strategyApi.startStrategy(strategyId, store.selectedAccountId || undefined)
    ElMessage.success(`策略 ${strategyId} 已启动`)
    await loadStrategies()
  } catch (error: any) {
    ElMessage.error(`启动策略失败: ${error.message}`)
  }
}

async function handleStopStrategy(strategyId: string) {
  try {
    await strategyApi.stopStrategy(strategyId, store.selectedAccountId || undefined)
    ElMessage.success(`策略 ${strategyId} 已停止`)
    await loadStrategies()
  } catch (error: any) {
    ElMessage.error(`停止策略失败: ${error.message}`)
  }
}

async function handleStartAll() {
  try {
    await strategyApi.startAllStrategies(store.selectedAccountId || undefined)
    ElMessage.success('所有策略已启动')
    await loadStrategies()
  } catch (error: any) {
    ElMessage.error(`启动策略失败: ${error.message}`)
  }
}

async function handleStopAll() {
  try {
    await strategyApi.stopAllStrategies(store.selectedAccountId || undefined)
    ElMessage.success('所有策略已停止')
    await loadStrategies()
  } catch (error: any) {
    ElMessage.error(`停止策略失败: ${error.message}`)
  }
}

async function handleReplayAll() {
  // 弹出确认对话框
  try {
    await ElMessageBox.confirm(
      '当前只支持bar回播，回播会重置策略，并从当前交易日的初始bar开始推送。是否继续？',
      '确认回播全部策略',
      {
        confirmButtonText: '确认回播',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    // 用户取消
    return
  }

  replayAllLoading.value = true
  try {
    const result = await strategyApi.replayAllStrategies(store.selectedAccountId || undefined)
    ElMessage.success(`回播完成，共回播 ${result.replayed_count} 个策略`)
    await loadStrategies()
  } catch (error: any) {
    ElMessage.error(`回播策略失败: ${error.message}`)
  } finally {
    replayAllLoading.value = false
  }
}

onMounted(async () => {
  loadStrategies()
})
</script>

<style scoped>
.strategy {
  padding: 0;
  width: 100%;
}

.el-table {
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.signal-detail {
  font-size: 12px;
  line-height: 1.8;
  min-width: 150px;
}

.signal-detail > div {
  display: block;
}

.signal-detail .exit-info {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--el-border-color);
}

.text-long {
  color: var(--el-color-danger);
  font-weight: 500;
}

.text-short {
  color: var(--el-color-primary);
  font-weight: 500;
}
</style>
