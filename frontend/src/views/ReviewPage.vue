<template>
  <div class="review" data-testid="review-page">
    <div class="review-header">
      <div>
        <h1>待审核交易列表</h1>
        <p>请为识别为“其他”或低置信度的交易选择合适分类。</p>
      </div>
      <button class="primary-button" data-testid="review-finish-button" @click="goToDashboard">
        完成审核并查看报告
      </button>
    </div>

    <div v-if="financeStore.correctionError" class="status-banner error" data-testid="review-error-banner">
      {{ financeStore.correctionError }}
    </div>
    <div v-if="financeStore.loadError" class="status-banner warning">
      服务端数据加载失败，当前回退到浏览器本地缓存：{{ financeStore.loadError }}
    </div>
    <div v-else-if="financeStore.isLoading" class="status-banner loading">
      正在加载待审核交易...
    </div>

    <div v-if="pendingReviews.length > 0" class="review-table-wrap" data-testid="review-table-wrap">
      <table class="review-table">
        <thead>
          <tr>
            <th>日期</th>
            <th>描述</th>
            <th>金额</th>
            <th>来源</th>
            <th>分类</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="transaction in pendingReviews"
            :key="transaction.id"
            :data-testid="`review-row-${transaction.id}`"
          >
            <td>{{ transaction.date }}</td>
            <td class="description">{{ transaction.description || '-' }}</td>
            <td :class="['amount', transaction.type]">
              {{ formatTransactionAmount(transaction.amount, transaction.type) }}
            </td>
            <td>{{ sourceLabelMap[transaction.source] || transaction.source }}</td>
            <td>
              <select
                class="category-select"
                :data-testid="`review-category-${transaction.id}`"
                :value="transaction.category"
                @change="handleCategoryChange(transaction.id, $event.target.value)"
              >
                <option
                  v-for="category in categoryOptions"
                  :key="category"
                  :value="category"
                >
                  {{ category }}
                </option>
              </select>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else class="empty-state" data-testid="review-empty-state">
      <h2>没有待审核交易</h2>
      <p>当前月份的交易都已经完成分类，可以直接查看报告。</p>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useFinanceStore } from '@/stores/finance'
import { formatTransactionAmount } from '@/utils/transactionAmount'

const router = useRouter()
const financeStore = useFinanceStore()

const pendingReviews = computed(() => financeStore.pendingReviews)
const categoryOptions = ['餐饮', '交通', '购物', '娱乐', '通讯', '住房', '医疗', '人情', '转账', '收入', '其他']
const sourceLabelMap = {
  wechat: '微信',
  alipay: '支付宝',
  ccb: '建行',
  other: '其他',
}

async function handleCategoryChange(id, category) {
  try {
    await financeStore.updateTransactionCategory(id, category)
  } catch {
    // error state is exposed via financeStore.correctionError banner
  }
}

function goToDashboard() {
  router.push('/dashboard')
}

onMounted(async () => {
  await financeStore.initialize(financeStore.selectedMonth)
})
</script>

<style scoped>
.review {
  min-height: 100vh;
  padding: 32px;
  background: #f5f7fb;
  color: #1f2937;
}

.review-header {
  max-width: 1100px;
  margin: 0 auto 24px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}

.review-header h1 {
  margin: 0 0 8px;
  font-size: 2rem;
}

.review-header p {
  margin: 0;
  color: #667085;
}

.status-banner {
  max-width: 1100px;
  margin: 0 auto 16px;
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

.status-banner.error {
  background: #fef2f2;
  color: #b42318;
  border: 1px solid #fda29b;
}

.primary-button {
  border: 0;
  border-radius: 8px;
  padding: 12px 18px;
  background: #2563eb;
  color: #ffffff;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s ease;
}

.primary-button:hover {
  background: #1d4ed8;
  transform: translateY(-1px);
}

.review-table-wrap {
  max-width: 1100px;
  margin: 0 auto;
  overflow-x: auto;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.review-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 760px;
}

.review-table th,
.review-table td {
  padding: 14px 16px;
  text-align: left;
  border-bottom: 1px solid #eef2f7;
  vertical-align: middle;
}

.review-table th {
  background: #f9fafb;
  color: #475467;
  font-size: 0.9rem;
  font-weight: 700;
}

.review-table tbody tr:last-child td {
  border-bottom: 0;
}

.description {
  max-width: 360px;
  color: #111827;
}

.amount {
  font-weight: 700;
  white-space: nowrap;
}

.amount.expense {
  color: #dc2626;
}

.amount.income {
  color: #16a34a;
}

.amount.transfer {
  color: #fa8c16;
}

.category-select {
  width: 140px;
  border: 1px solid #d0d5dd;
  border-radius: 8px;
  padding: 8px 10px;
  background: #ffffff;
  color: #111827;
  font-size: 0.95rem;
}

.empty-state {
  max-width: 1100px;
  margin: 0 auto;
  padding: 48px 24px;
  text-align: center;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.empty-state h2 {
  margin: 0 0 8px;
}

.empty-state p {
  margin: 0;
  color: #667085;
}

@media (max-width: 720px) {
  .review {
    padding: 20px;
  }

  .review-header {
    align-items: stretch;
    flex-direction: column;
  }

  .primary-button {
    width: 100%;
  }
}
</style>
