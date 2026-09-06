<template>
  <div class="dashboard">
    <div class="container">
      <h1>📊 财务 Dashboard</h1>

      <div v-if="financeStore.loadError" class="status-banner warning">
        服务端数据加载失败，当前回退到浏览器本地缓存：{{ financeStore.loadError }}
      </div>
      <div v-else-if="financeStore.isLoading" class="status-banner loading">
        正在加载服务端持久化数据...
      </div>

      <div v-if="financeStore.latestImportJob" class="import-job-card section" data-testid="latest-import-job-card">
        <div class="import-job-header">
          <div>
            <h2>🧾 最近一次导入</h2>
            <p class="import-job-file">{{ financeStore.latestImportJob.filename }}</p>
          </div>
          <span
            class="import-job-badge"
            :class="statusTone(financeStore.latestImportJob.status)"
            data-testid="latest-import-job-status"
          >
            {{ statusLabel(financeStore.latestImportJob.status) }}
          </span>
        </div>

        <div class="import-job-meta">
          <span>来源：{{ sourceLabel(financeStore.latestImportJob.source) }}</span>
          <span>总笔数：{{ financeStore.latestImportJob.total_transactions }}</span>
          <span>已入库：{{ financeStore.latestImportJob.persisted_count }}</span>
          <span>待审核：{{ financeStore.latestImportJob.review_required_count }}</span>
        </div>

        <p v-if="financeStore.latestImportJob.updated_at" class="import-job-updated">
          更新时间：{{ formatJobTime(financeStore.latestImportJob.updated_at) }}
        </p>

        <p v-if="financeStore.latestImportJob.error_message" class="import-job-error">
          失败原因：{{ financeStore.latestImportJob.error_message }}
        </p>

        <div v-if="financeStore.latestImportJob.status === 'REVIEW_REQUIRED'" class="import-job-actions">
          <router-link to="/review" class="btn btn-review">去处理待审核交易 →</router-link>
        </div>
      </div>

      <SummaryCards
        :total-income="financeStore.totalIncome"
        :total-expense="financeStore.totalExpense"
        :balance="financeStore.balance"
      />

      <div class="ai-card section">
        <div class="ai-header" @click="handleGetAiDiagnosis">
          <h2>✨ AI 深度财务诊断</h2>
          <button class="btn-ai" :disabled="isAiLoading || financeStore.filteredTransactions.length === 0">
            {{ isAiLoading ? '🧠 AI 疯狂计算中...' : '💡 一键获取分析建议' }}
          </button>
        </div>
        <div v-if="aiResult || isAiLoading" class="ai-content">
          <div v-if="isAiLoading" class="loading-text">正在分析你的收支数据，请稍候...</div>
          <div v-else class="markdown-body" v-html="aiResult"></div>
        </div>
      </div>

      <div class="section">
        <h2>📈 支出构成</h2>
        <div class="chart-area">
          <ExpenseChart :data="financeStore.filteredExpensesByCategory" />
          <CategoryList :categories="financeStore.filteredExpensesByCategory" />
        </div>
      </div>

      <div class="section">
        <h2>📝 近期交易</h2>
        <MonthFilter
          :model-value="financeStore.selectedMonth"
          :options="financeStore.availableMonths"
          @update:model-value="handleMonthChange"
        />
        <TransactionList :transactions="financeStore.filteredTransactions" />
      </div>

      <div class="nav">
        <router-link to="/" class="btn">← 返回上传</router-link>
        <button class="btn btn-danger" @click="handleClear">🧹 清空本地缓存</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useFinanceStore } from '@/stores/finance'
import { useRouter } from 'vue-router'
import { fetchAiDiagnosis } from '@/utils/api'

import SummaryCards from '@/components/SummaryCards.vue'
import ExpenseChart from '@/components/ExpenseChart.vue'
import CategoryList from '@/components/CategoryList.vue'
import TransactionList from '@/components/TransactionList.vue'
import MonthFilter from '@/components/MonthFilter.vue'

const financeStore = useFinanceStore()
const router = useRouter()

const isAiLoading = ref(false)
const aiResult = ref('')

const sourceLabelMap = {
  alipay: '支付宝',
  wechat: '微信',
  ccb: '建设银行',
  other: '其他',
}

const statusLabelMap = {
  PENDING: '待处理',
  RUNNING: '进行中',
  SUCCEEDED: '已完成',
  FAILED: '失败',
  REVIEW_REQUIRED: '待审核',
}

function sourceLabel(source) {
  return sourceLabelMap[source] || source || '未知'
}

function statusLabel(status) {
  return statusLabelMap[status] || status || '未知状态'
}

function statusTone(status) {
  if (status === 'SUCCEEDED') return 'success'
  if (status === 'FAILED') return 'danger'
  if (status === 'REVIEW_REQUIRED') return 'warning'
  return 'neutral'
}

function formatJobTime(value) {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    hour12: false,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function handleGetAiDiagnosis() {
  if (isAiLoading.value || financeStore.filteredTransactions.length === 0) return

  isAiLoading.value = true
  aiResult.value = ''

  try {
    const res = await fetchAiDiagnosis(financeStore.aiPromptData)
    aiResult.value = res.result
  } catch (err) {
    aiResult.value = `<p style="color: red;">获取诊断失败: ${err.message}</p>`
  } finally {
    isAiLoading.value = false
  }
}

async function handleMonthChange(month) {
  if (!month) {
    financeStore.selectedMonth = ''
    return
  }

  await financeStore.loadMonthData(month)
}

onMounted(async () => {
  await financeStore.initialize(financeStore.selectedMonth)
})

function handleClear() {
  if (confirm('确定要清空当前浏览器中的本地缓存吗？这不会删除服务器中的持久化账单数据。')) {
    financeStore.clear()
    router.push('/')
  }
}
</script>

<style scoped>
.dashboard {
  min-height: 100vh;
  padding: 2rem;
  background: #f5f5f5;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
}

h1 {
  margin-bottom: 1.5rem;
  color: #333;
}

.status-banner {
  margin-bottom: 1rem;
  padding: 0.9rem 1rem;
  border-radius: 10px;
  font-size: 0.95rem;
}

.status-banner.loading {
  background: #eff6ff;
  color: #1d4ed8;
  border: 1px solid #bfdbfe;
}

.status-banner.warning {
  background: #fff7ed;
  color: #c2410c;
  border: 1px solid #fdba74;
}

.section {
  background: white;
  padding: 1.5rem;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-bottom: 1.5rem;
}

.section h2 {
  margin-bottom: 1rem;
  font-size: 1.2rem;
  color: #333;
}

.chart-area {
  display: flex;
  gap: 2rem;
  align-items: center;
}

.btn {
  display: inline-block;
  padding: 0.75rem 1.5rem;
  background: #667eea;
  color: white;
  text-decoration: none;
  border-radius: 8px;
  margin-top: 1rem;
  margin-right: 1rem;
  transition: background 0.2s;
  border: none;
  cursor: pointer;
  font-size: 1rem;
}

.btn:hover { background: #5a6fd6; }
.btn-danger { background: #ff4d4f; }
.btn-danger:hover { background: #ff7875; }

.ai-card {
  background: linear-gradient(135deg, #f8faff 0%, #edf2fe 100%);
  border-left: 5px solid #667eea;
}

.ai-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.ai-header h2 {
  margin-bottom: 0;
  color: #4a5568;
}

.btn-ai {
  padding: 0.6rem 1.2rem;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 6px rgba(102, 126, 234, 0.2);
}

.btn-ai:hover:not(:disabled) {
  background: #5a6fd6;
  transform: translateY(-2px);
  box-shadow: 0 6px 12px rgba(102, 126, 234, 0.3);
}

.btn-ai:disabled {
  background: #a0aec0;
  cursor: not-allowed;
  box-shadow: none;
}

.ai-content {
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px dashed #cbd5e0;
  color: #2d3748;
  line-height: 1.6;
}

.loading-text {
  color: #667eea;
  font-weight: bold;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.5; }
  100% { opacity: 1; }
}

.import-job-card {
  border-left: 5px solid #0f766e;
  background: linear-gradient(135deg, #f0fdfa 0%, #f8fafc 100%);
}

.import-job-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.import-job-file {
  margin: 0.35rem 0 0;
  color: #475569;
  word-break: break-all;
}

.import-job-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1rem;
  margin-top: 1rem;
  color: #334155;
  font-size: 0.95rem;
}

.import-job-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0.4rem 0.8rem;
  font-size: 0.9rem;
  font-weight: 700;
  white-space: nowrap;
}

.import-job-badge.success {
  background: #dcfce7;
  color: #166534;
}

.import-job-badge.warning {
  background: #fef3c7;
  color: #92400e;
}

.import-job-badge.danger {
  background: #fee2e2;
  color: #b91c1c;
}

.import-job-badge.neutral {
  background: #e2e8f0;
  color: #334155;
}

.import-job-updated,
.import-job-error {
  margin-top: 0.9rem;
  margin-bottom: 0;
}

.import-job-updated {
  color: #64748b;
}

.import-job-error {
  color: #b91c1c;
  font-weight: 600;
}

.import-job-actions {
  margin-top: 1rem;
}

.btn-review {
  margin-top: 0;
  background: #0f766e;
}

.btn-review:hover {
  background: #0d5f59;
}
</style>
