<template>
  <div class="chart-wrapper">
    <v-chart :option="chartOption" autoresize style="height: 320px" />
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: {
    type: Array,
    required: true
  }
})

const COLORS = [
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4',
  '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F',
  '#BB8FCE', '#85C1E9', '#F8B500', '#6BCB77'
]

const chartOption = computed(() => {
  return {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: ¥{c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: { color: '#666', fontSize: 12 }
    },
    color: COLORS,
    series: [
      {
        name: '支出构成',
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['35%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 6,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: false
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            fontWeight: 'bold'
          }
        },
        data: props.data.map((d, i) => ({ 
          ...d, 
          itemStyle: { color: COLORS[i % COLORS.length] } 
        }))
      }
    ]
  }
})
</script>

<style scoped>
.chart-wrapper {
  flex: 0 0 320px;
  height: 320px;
}
</style>