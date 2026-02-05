<template>
  <div class="strategy-details">
    <el-page-header @back="goBack" :title="`策略详情 - ${strategyId}`" class="header" />

    <el-skeleton v-if="loading" :rows="6" animated />

    <template v-else>
      <!-- 策略基本信息及操作 -->
      <el-card shadow="hover" class="section">
        <template #header>
          <span>基本信息</span>
        </template>
        <el-descriptions :column="3" border v-if="strategy">
          <el-descriptions-item label="策略ID">{{ strategy.strategy_id }}</el-descriptions-item>
          <el-descriptions-item label="合约">{{ strategy.params?.symbol || strategy.config?.symbol || '-' }}</el-descriptions-item>
          <el-descriptions-item label="启用开关">
            <el-switch
              v-model="strategy.enabled"
              @change="handleToggleEnabled"
              :loading="actionLoading"
              active-text="已启用"
              inactive-text="已禁用"
            />
          </el-descriptions-item>
          <el-descriptions-item label="开仓状态">
            <el-tag :type="strategy.opening_paused ? 'danger' : 'success'" size="small">
              {{ strategy.opening_paused ? '已暂停' : '正常' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="平仓状态">
            <el-tag :type="strategy.closing_paused ? 'danger' : 'success'" size="small">
              {{ strategy.closing_paused ? '已暂停' : '正常' }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <div class="action-buttons" v-if="strategy">
          <el-space wrap>
            <el-button
              v-if="!strategy.opening_paused"
              @click="handlePauseOpening"
              :loading="actionLoading"
            >
              暂停开仓
            </el-button>
            <el-button
              v-else
              type="success"
              @click="handleResumeOpening"
              :loading="actionLoading"
            >
              恢复开仓
            </el-button>
            <el-button
              v-if="!strategy.closing_paused"
              @click="handlePauseClosing"
              :loading="actionLoading"
            >
              暂停平仓
            </el-button>
            <el-button
              v-else
              type="success"
              @click="handleResumeClosing"
              :loading="actionLoading"
            >
              恢复平仓
            </el-button>
          </el-space>
        </div>
      </el-card>

    <!-- 策略参数设置 -->
    <el-card shadow="hover" class="section">
      <template #header>
        <span>参数设置</span>
      </template>
      <el-form :model="paramsForm" label-width="140px" v-if="strategy">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="合约代码">
              <el-input v-model="paramsForm.symbol" placeholder="如: IM2603" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="时间类型">
              <el-select v-model="paramsForm.bar" placeholder="选择时间类型">
                <el-option label="1分钟" value="M1" />
                <el-option label="5分钟" value="M5" />
                <el-option label="15分钟" value="M15" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="目标手数">
              <el-input-number v-model="paramsForm.volume_per_trade" :min="1" :max="100" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="最大持仓">
              <el-input-number v-model="paramsForm.max_position" :min="1" :max="100" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="止盈率">
              <el-input-number v-model="paramsForm.take_profit_pct" :min="0" :max="1" :step="0.001" :precision="4" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="止损率">
              <el-input-number v-model="paramsForm.stop_loss_pct" :min="0" :max="1" :step="0.001" :precision="4" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="强平时间">
              <el-time-picker
                v-model="forceExitTimeValue"
                format="HH:mm:ss"
                value-format="HH:mm:ss"
                placeholder="选择时间"
                @change="handleForceExitTimeChange"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- RSI 策略特定参数 -->
        <template v-if="isRsiStrategy">
          <el-divider content-position="left">RSI 策略参数</el-divider>
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="RSI 周期">
                <el-input-number v-model="paramsForm.rsi_n" :min="2" :max="100" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="短 K 线周期">
                <el-input-number v-model="paramsForm.short_k" :min="1" :max="60" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="长 K 线周期">
                <el-input-number v-model="paramsForm.long_k" :min="1" :max="120" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="长 RSI 阈值">
                <el-input-number v-model="paramsForm.long_threshold" :min="0" :max="100" :step="0.1" :precision="1" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="短 RSI 阈值">
                <el-input-number v-model="paramsForm.short_threshold" :min="0" :max="100" :step="0.1" :precision="1" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="信号方向阈值">
                <el-input-number v-model="paramsForm.dir_thr" :min="0" :max="1" :step="0.1" :precision="1" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="使用外部信号">
                <el-switch v-model="paramsForm.use_signal" />
              </el-form-item>
            </el-col>
          </el-row>
        </template>

        <el-form-item>
          <el-button type="primary" @click="handleSaveParams" :loading="saveLoading">保存参数</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 策略信号设置 -->
    <el-card shadow="hover" class="section">
      <template #header>
        <span>信号设置</span>
      </template>
      <el-form :model="signalForm" label-width="140px" v-if="strategy">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="信号方向">
              <el-radio-group v-model="signalForm.side">
                <el-radio :label="0">无信号</el-radio>
                <el-radio :label="1">多头</el-radio>
                <el-radio :label="-1">空头</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="入场价格" v-if="signalForm.side !== 0">
              <el-input-number v-model="signalForm.entry_price" :min="0" :step="0.1" :precision="2" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="目标手数" v-if="signalForm.side !== 0">
              <el-input-number v-model="signalForm.entry_volume" :min="1" :max="100" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-divider content-position="left">当前持仓状态</el-divider>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="持仓手数">
              <el-input-number v-model="signalForm.pos_volume" :min="0" :max="100" disabled />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="持仓均价">
              <el-input-number v-model="signalForm.pos_price" :min="0" :step="0.1" :precision="2" disabled />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item>
          <el-button type="primary" @click="handleSaveSignal" :loading="saveLoading">保存信号</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 报单指令历史 -->
    <el-card shadow="hover" class="section">
      <template #header>
        <div class="card-header">
          <span>报单指令历史</span>
          <el-radio-group v-model="orderCmdFilter" @change="loadOrderCmds" size="small">
            <el-radio-button label="all">全部</el-radio-button>
            <el-radio-button label="active">进行中</el-radio-button>
            <el-radio-button label="finished">已完成</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <el-table :data="orderCmds" stripe v-loading="orderCmdsLoading" table-layout="auto">
        <el-table-column prop="cmd_id" label="指令ID" width="200" />
        <el-table-column prop="symbol" label="合约" width="120" />
        <el-table-column label="方向" width="80">
          <template #default="{ row }">
            <el-tag :type="row.direction === 'BUY' ? 'danger' : 'primary'" size="small">
              {{ row.direction === 'BUY' ? '买' : '卖' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="开平" width="80">
          <template #default="{ row }">
            <el-tag size="small">{{ getOffsetText(row.offset) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="volume" label="目标手数" width="100" />
        <el-table-column prop="filled_volume" label="已成交" width="100" />
        <el-table-column prop="filled_price" label="成交均价" width="100">
          <template #default="{ row }">{{ row.filled_price?.toFixed(2) || '-' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useStore } from '@/stores'
import { strategyApi } from '@/api'

const router = useRouter()
const route = useRoute()
const store = useStore()

const strategyId = route.params.strategyId as string
const strategy = ref<any>(null)
const loading = ref(false)
const actionLoading = ref(false)
const saveLoading = ref(false)

const paramsForm = ref<any>({
  symbol: '',
  bar: 'M1',
  volume_per_trade: 1,
  max_position: 5,
  take_profit_pct: 0.015,
  stop_loss_pct: 0.015,
  slippage: 0,
  force_exit_time: '14:55:00',
  rsi_n: 5,
  short_k: 5,
  long_k: 15,
  long_threshold: 50,
  short_threshold: 55,
  dir_thr: 0,
  use_signal: true
})

const signalForm = ref<any>({
  side: 0,
  entry_price: 0,
  entry_volume: 1,
  pos_volume: 0,
  pos_price: null
})

const forceExitTimeValue = ref('')

const orderCmds = ref<any[]>([])
const orderCmdsLoading = ref(false)
const orderCmdFilter = ref<'all' | 'active' | 'finished'>('all')

const isRsiStrategy = computed(() => {
  return strategyId.toLowerCase().includes('rsi') || false
})

function goBack() {
  router.push('/strategy')
}

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

function getOffsetText(offset: string | undefined): string {
  const map: Record<string, string> = {
    'OPEN': '开',
    'CLOSE': '平',
    'CLOSETODAY': '平今'
  }
  return map[offset || ''] || offset || '-'
}

function getStatusType(status: string | undefined): string {
  const map: Record<string, string> = {
    'PENDING': 'info',
    'RUNNING': 'primary',
    'FINISHED': 'success'
  }
  return map[status || ''] || 'info'
}

function getStatusText(status: string | undefined): string {
  const map: Record<string, string> = {
    'PENDING': '待执行',
    'RUNNING': '执行中',
    'FINISHED': '已完成'
  }
  return map[status || ''] || status || '-'
}

async function loadStrategy() {
  loading.value = true
  try {
    strategy.value = await strategyApi.getStrategy(strategyId, store.selectedAccountId || undefined)
    // 初始化参数表单
    const params = strategy.value.params || {}
    paramsForm.value = {
      symbol: params.symbol || strategy.value.config?.symbol || '',
      bar: params.bar || 'M1',
      volume_per_trade: params.volume_per_trade || 1,
      max_position: params.max_position || 5,
      take_profit_pct: params.take_profit_pct || 0.015,
      stop_loss_pct: params.stop_loss_pct || 0.015,
      slippage: params.slippage || 0,
      force_exit_time: params.force_exit_time || '14:55:00',
      rsi_n: params.rsi_n || 5,
      short_k: params.short_k || 5,
      long_k: params.long_k || 15,
      long_threshold: params.long_threshold || 50,
      short_threshold: params.short_threshold || 55,
      dir_thr: params.dir_thr || 0,
      use_signal: params.use_signal !== undefined ? params.use_signal : true
    }
    forceExitTimeValue.value = paramsForm.value.force_exit_time || '14:55:00'

    // 初始化信号表单
    const signal = strategy.value.signal || {}
    signalForm.value = {
      side: signal.side || 0,
      entry_price: signal.entry_price || 0,
      entry_volume: signal.entry_volume || paramsForm.value.volume_per_trade,
      pos_volume: signal.pos_volume || 0,
      pos_price: signal.pos_price || null
    }
  } catch (error: any) {
    ElMessage.error(`加载策略失败: ${error.message}`)
    strategy.value = null  // 确保为 null，v-if="strategy" 会阻止渲染
  } finally {
    loading.value = false
  }
}

async function loadOrderCmds() {
  orderCmdsLoading.value = true
  try {
    const status = orderCmdFilter.value === 'all' ? undefined : orderCmdFilter.value
    orderCmds.value = await strategyApi.getStrategyOrderCmds(strategyId, { status }, store.selectedAccountId || undefined)
  } catch (error: any) {
    ElMessage.error(`加载报单指令失败: ${error.message}`)
  } finally {
    orderCmdsLoading.value = false
  }
}

async function handleToggleEnabled(enabled: boolean) {
  actionLoading.value = true
  try {
    if (enabled) {
      await strategyApi.enableStrategy(strategyId, store.selectedAccountId || undefined)
      ElMessage.success('策略已启用')
    } else {
      await strategyApi.disableStrategy(strategyId, store.selectedAccountId || undefined)
      ElMessage.success('策略已禁用')
    }
    await loadStrategy()
  } catch (error: any) {
    ElMessage.error(`操作失败: ${error.message}`)
  } finally {
    actionLoading.value = false
  }
}

async function handlePauseOpening() {
  actionLoading.value = true
  try {
    await strategyApi.pauseStrategyOpening(strategyId, store.selectedAccountId || undefined)
    ElMessage.success('暂停开仓成功')
    await loadStrategy()
  } catch (error: any) {
    ElMessage.error(`暂停开仓失败: ${error.message}`)
  } finally {
    actionLoading.value = false
  }
}

async function handleResumeOpening() {
  actionLoading.value = true
  try {
    await strategyApi.resumeStrategyOpening(strategyId, store.selectedAccountId || undefined)
    ElMessage.success('恢复开仓成功')
    await loadStrategy()
  } catch (error: any) {
    ElMessage.error(`恢复开仓失败: ${error.message}`)
  } finally {
    actionLoading.value = false
  }
}

async function handlePauseClosing() {
  actionLoading.value = true
  try {
    await strategyApi.pauseStrategyClosing(strategyId, store.selectedAccountId || undefined)
    ElMessage.success('暂停平仓成功')
    await loadStrategy()
  } catch (error: any) {
    ElMessage.error(`暂停平仓失败: ${error.message}`)
  } finally {
    actionLoading.value = false
  }
}

async function handleResumeClosing() {
  actionLoading.value = true
  try {
    await strategyApi.resumeStrategyClosing(strategyId, store.selectedAccountId || undefined)
    ElMessage.success('恢复平仓成功')
    await loadStrategy()
  } catch (error: any) {
    ElMessage.error(`恢复平仓失败: ${error.message}`)
  } finally {
    actionLoading.value = false
  }
}

function handleForceExitTimeChange(value: string) {
  paramsForm.value.force_exit_time = value
}

async function handleSaveParams() {
  saveLoading.value = true
  try {
    await strategyApi.updateStrategy(strategyId, paramsForm.value, store.selectedAccountId || undefined)
    ElMessage.success('参数保存成功')
    await loadStrategy()
  } catch (error: any) {
    ElMessage.error(`保存参数失败: ${error.message}`)
  } finally {
    saveLoading.value = false
  }
}

async function handleSaveSignal() {
  saveLoading.value = true
  try {
    await strategyApi.updateStrategySignal(strategyId, signalForm.value, store.selectedAccountId || undefined)
    ElMessage.success('信号保存成功')
    await loadStrategy()
  } catch (error: any) {
    ElMessage.error(`保存信号失败: ${error.message}`)
  } finally {
    saveLoading.value = false
  }
}

onMounted(async () => {
  await loadStrategy()
  await loadOrderCmds()
})
</script>

<style scoped>
.strategy-details {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.header {
  margin-bottom: 20px;
}

.header :deep(.el-page-header__title) {
  color: #409eff;
}

.header :deep(.el-page-header__content) {
  color: #409eff;
}

.header :deep(.el-icon) {
  color: #409eff;
}

.section {
  margin-bottom: 20px;
}

.action-buttons {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--el-border-color);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
