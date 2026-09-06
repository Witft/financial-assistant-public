<template>
  <div class="transaction-list">
    <div
      v-for="t in transactions"
      :key="t.id"
      class="transaction-item"
      :class="[t.type]"
    >
      <span class="t-date">{{ t.date }}</span>
      <span class="t-desc">{{ t.description }}</span>
      <span class="t-category">{{ t.category || '未分类' }}</span>
      <span class="t-amount">{{ formatTransactionAmount(t.amount, t.type) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Transaction } from '@/types/finance'
import { formatTransactionAmount } from '@/utils/transactionAmount'

defineProps<{
  transactions: Transaction[]
}>()
</script>

<style scoped>
.transaction-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 400px;
  overflow-y: auto;
}

.transaction-item {
  display: grid;
  grid-template-columns: 100px 1fr 96px auto;
  gap: 1rem;
  padding: 0.75rem;
  background: #fafafa;
  border-radius: 8px;
  align-items: center;
}

.transaction-item.income .t-amount { color: #52c41a; }
.transaction-item.expense .t-amount { color: #ff4d4f; }
.transaction-item.transfer .t-amount { color: #fa8c16; }

.t-date { color: #999; font-size: 0.9rem; }
.t-desc { color: #333; }
.t-category {
  justify-self: start;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  background: #f0f5ff;
  color: #2f54eb;
  font-size: 0.8rem;
  font-weight: 600;
  white-space: nowrap;
}
.t-amount { font-weight: bold; }
</style>
