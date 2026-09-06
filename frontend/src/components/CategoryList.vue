<template>
  <div class="category-list">
    <div
      v-for="item in categories"
      :key="item.name"
      class="category-item"
    >
      <span class="category-dot" :style="{ background: item.color }"></span>
      <span class="category-name">{{ item.name }}</span>
      <span class="category-amount">¥{{ item.value.toLocaleString() }}</span>
      <span class="category-pct">{{ item.pct }}%</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  categories: {
    type: Array,
    required: true
  }
})
</script>

<style scoped>
.category-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  max-height: 320px;
  overflow-y: auto;
}

.category-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.5rem 0.75rem;
  background: #fafafa;
  border-radius: 8px;
}

.category-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.category-name {
  flex: 1;
  color: #333;
  font-size: 0.9rem;
}

.category-amount {
  font-weight: bold;
  color: #ff4d4f;
  font-size: 0.9rem;
}

.category-pct {
  color: #999;
  font-size: 0.8rem;
  width: 40px;
  text-align: right;
}
</style>