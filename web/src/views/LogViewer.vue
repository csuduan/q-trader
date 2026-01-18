<template>
  <div class="log-viewer">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>系统日志 - {{ today }}</span>
          <el-space>
            <el-button
              @click="toggleMonitoring"
              :type="logMonitoringEnabled ? 'danger' : 'primary'"
              :loading="monitoringLoading"
            >
              <el-icon><VideoPlay v-if="!logMonitoringEnabled" /><VideoPause v-else /></el-icon>
              {{ logMonitoringEnabled ? '停止监听' : '开始监听' }}
            </el-button>
            <el-button @click="toggleAutoScroll" :type="autoScroll ? 'primary' : 'default'">
              <el-icon><BottomRight /></el-icon>
              {{ autoScroll ? '自动滚动' : '停止滚动' }}
            </el-button>
            <el-button @click="clearLogs" type="danger">
              <el-icon><Delete /></el-icon>
              清空显示
            </el-button>
            <el-button @click="loadHistory" :loading="loading">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </el-space>
        </div>
      </template>

      <el-row :gutter="20" class="mb-4">
        <el-col :span="8">
          <el-select v-model="levelFilter" placeholder="选择日志级别" clearable style="width: 100%">
            <el-option label="全部" value="" />
            <el-option label="DEBUG" value="DEBUG" />
            <el-option label="INFO" value="INFO" />
            <el-option label="WARNING" value="WARNING" />
            <el-option label="ERROR" value="ERROR" />
            <el-option label="CRITICAL" value="CRITICAL" />
          </el-select>
        </el-col>
        <el-col :span="16">
          <el-input
            v-model="searchText"
            placeholder="搜索日志内容"
            clearable
            @clear="clearSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
      </el-row>

      <div ref="logContainer" class="log-container">
        <div
          v-for="(log, index) in filteredLogs"
          :key="index"
          :class="['log-entry', `log-${(log.level || '').toLowerCase()}`]"
        >
          <div class="log-header">
            <span class="log-time">{{ log.timestamp }}</span>
            <el-tag v-if="log.level" :type="getLevelType(log.level) || undefined" size="small">{{ log.level }}</el-tag>
          <el-tag v-else type="info" size="small">UNKNOWN</el-tag>
          </div>
          <div class="log-source">
            {{ log.logger }}:{{ log.function }}:{{ log.line }}
          </div>
          <div class="log-message">{{ log.message }}</div>
        </div>
        <div v-if="filteredLogs.length === 0" class="empty-logs">
          <el-empty description="暂无日志数据" />
        </div>
      </div>

      <div class="log-footer">
        <el-space>
          <span>显示: {{ filteredLogs?.length || 0 }} 条</span>
          <span>缓冲: {{ logs?.length || 0 }} / {{ maxLogs }} 条</span>
        </el-space>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { VideoPlay, VideoPause } from '@element-plus/icons-vue'
import { logApi, systemApi } from '@/api'
import wsManager from '@/ws'
import type { LogEntry } from '@/types'

const logs = ref<LogEntry[]>([])
const maxLogs = 1000
const autoScroll = ref(true)
const levelFilter = ref('')
const searchText = ref('')
const loading = ref(false)
const logContainer = ref<HTMLElement>()
const isUserScrolled = ref(false)
const logMonitoringEnabled = ref(false)
const monitoringLoading = ref(false)

const today = new Date().toLocaleDateString('zh-CN')

const filteredLogs = computed(() => {
  if (!logs.value || !Array.isArray(logs.value)) {
    return []
  }

  let result = logs.value

  if (levelFilter.value) {
    result = result.filter(log => log && log.level === levelFilter.value)
  }

  if (searchText.value) {
    const search = searchText.value.toLowerCase()
    result = result.filter(log =>
      log &&
      ((log.message || '').toLowerCase().includes(search) ||
      (log.logger || '').toLowerCase().includes(search))
    )
  }

  return result
})

function getLevelType(level: string): '' | 'success' | 'warning' | 'danger' | 'info' {
  const types: Record<string, '' | 'success' | 'warning' | 'danger' | 'info'> = {
    'DEBUG': 'info',
    'INFO': '',
    'WARNING': 'warning',
    'ERROR': 'danger',
    'CRITICAL': 'danger'
  }
  return types[level] ?? ''
}

function shouldShow(log: LogEntry): boolean {
  if (levelFilter.value && log.level !== levelFilter.value) {
    return false
  }

  if (searchText.value) {
    const search = searchText.value.toLowerCase()
    if (!(log.message || '').toLowerCase().includes(search) &&
        !(log.logger || '').toLowerCase().includes(search)) {
      return false
    }
  }

  return true
}

async function handleNewLog(entry: LogEntry) {
  if (!entry) return

  logs.value.push(entry)

  if (logs.value.length > maxLogs) {
    logs.value = logs.value.slice(-maxLogs)
  }

  if (autoScroll.value && shouldShow(entry) && !isUserScrolled.value) {
    await nextTick()
    scrollToBottom()
  }
}

async function toggleMonitoring() {
  monitoringLoading.value = true
  try {
    if (logMonitoringEnabled.value) {
      await systemApi.stopLogMonitoring()
      wsManager.unsubscribeLogs()
      logMonitoringEnabled.value = false
      ElMessage.success('日志监听已停止')
    } else {
      await systemApi.startLogMonitoring()
      wsManager.subscribeLogs()
      logMonitoringEnabled.value = true
      ElMessage.success('日志监听已启动')
    }
  } catch (error: any) {
    ElMessage.error(`操作失败: ${error.message}`)
  } finally {
    monitoringLoading.value = false
  }
}

async function loadLogMonitoringStatus() {
  try {
    const status = await systemApi.getLogMonitoringStatus()
    logMonitoringEnabled.value = status.enabled
  } catch (error: any) {
    console.error(`加载日志监控状态失败: ${error.message}`)
  }
}

function toggleAutoScroll() {
  autoScroll.value = !autoScroll.value
  if (autoScroll.value) {
    isUserScrolled.value = false
    scrollToBottom()
  }
}

function clearLogs() {
  logs.value = []
  ElMessage.success('日志显示已清空')
}

function clearSearch() {
  searchText.value = ''
}

async function loadHistory() {
  loading.value = true
  try {
    const history = await logApi.getLogHistory(0, 100)
    logs.value = [...history].reverse()
    isUserScrolled.value = false
    if (autoScroll.value) {
      await nextTick()
      scrollToBottom()
    }
  } catch (error: any) {
    ElMessage.error(`加载历史日志失败: ${error.message}`)
  } finally {
    loading.value = false
  }
}

function scrollToBottom() {
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}

function handleScroll() {
  if (logContainer.value) {
    const container = logContainer.value
    const isAtBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 50

    if (!isAtBottom && autoScroll.value) {
      isUserScrolled.value = true
    }

    if (isAtBottom) {
      isUserScrolled.value = false
    }
  }
}

let unsubscribeLogUpdate: (() => void) | null = null

onMounted(async () => {
  unsubscribeLogUpdate = wsManager.onLogUpdate(handleNewLog)
  await loadLogMonitoringStatus()
  await loadHistory()

  if (logContainer.value) {
    logContainer.value.addEventListener('scroll', handleScroll)
  }
})

onUnmounted(() => {
  if (logMonitoringEnabled.value) {
    wsManager.unsubscribeLogs()
  }
  if (unsubscribeLogUpdate) {
    unsubscribeLogUpdate()
  }

  if (logContainer.value) {
    logContainer.value.removeEventListener('scroll', handleScroll)
  }
})
</script>

<style scoped>
.log-viewer {
  height: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.mb-4 {
  margin-bottom: 16px;
}

.log-container {
  height: 800px;
  overflow-y: auto;
  background-color: #1e1e1e;
  border-radius: 4px;
  padding: 10px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
}

.log-entry {
  padding: 8px;
  margin-bottom: 4px;
  border-left: 3px solid transparent;
  background-color: #2d2d2d;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.log-entry:hover {
  background-color: #3d3d3d;
}

.log-debug {
  border-left-color: #909399;
}

.log-info {
  border-left-color: #409eff;
}

.log-warning {
  border-left-color: #e6a23c;
}

.log-error,
.log-critical {
  border-left-color: #f56c6c;
}

.log-header {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  flex-shrink: 0;
  padding-top: 2px;
}

.log-time {
  color: #909399;
  font-size: 12px;
  white-space: nowrap;
}

.log-source {
  color: #67c23a;
  font-size: 12px;
  flex-shrink: 0;
  white-space: nowrap;
}

.log-message {
  color: #d4d4d4;
  flex: 1;
  white-space: normal;
  word-wrap: break-word;
  word-break: break-word;
  line-height: 1.5;
  text-align: left;
  min-width: 0;
}

.empty-logs {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
}

.log-footer {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #e6e6e6;
  font-size: 12px;
  color: #909399;
}
</style>
