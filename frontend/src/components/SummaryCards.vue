<template>
  <div class="summary-cards">
    <div class="card income">
      <span class="label">收入</span>
      <span class="value">¥{{ totalIncome.toLocaleString() }}</span>
    </div>
    <div class="card expense">
      <span class="label">支出</span>
      <span class="value">¥{{ totalExpense.toLocaleString() }}</span>
    </div>
    <div class="card balance" :class="{ negative: balance < 0 }">
      <span class="label">结余</span>
      <span class="value">¥{{ balance.toLocaleString() }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  totalIncome: {
    type: Number,
    required: true
  },
  totalExpense: {
    type: Number,
    required: true
  },
  balance: {
    type: Number,
    required: true
  }
})
</script>

<style scoped>
.summary-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  margin-bottom: 2rem;
}

.card {
  background: white;
  padding: 1.5rem;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.card.income .value { color: #52c41a; }
.card.expense .value { color: #ff4d4f; }
.card.balance .value { color: #1890ff; }
.card.balance.negative .value { color: #ff4d4f; }

.card .label {
  font-size: 0.9rem;
  color: #666;
}

.card .value {
  font-size: 1.8rem;
  font-weight: bold;
}
</style>