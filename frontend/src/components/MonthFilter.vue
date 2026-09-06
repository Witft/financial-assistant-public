<template>
  <div class="filter-row">
    <select :value="modelValue" @change="$emit('update:modelValue', $event.target.value)">
      <option v-for="month in normalizedOptions" :key="month" :value="month">
        {{ month }}
      </option>
    </select>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: {
    type: String,
    default: '',
  },
  options: {
    type: Array,
    default: () => [],
  },
})

defineEmits(['update:modelValue'])

const normalizedOptions = computed(() => Array.isArray(props.options) ? props.options : [])
</script>

<style scoped>
.filter-row {
  margin-bottom: 1rem;
}

.filter-row select {
  padding: 0.5rem 1rem;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 0.9rem;
  color: #333;
  background: white;
  cursor: pointer;
}
</style>
