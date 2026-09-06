<template>
  <div class="upload-page">
    <div class="container">
      <h1 class="title">💰 财务助手</h1>
      <p class="subtitle">上传你的支付宝/微信账单，我来帮你分析</p>

      <div
        class="drop-zone"
        :class="{ 'drag-over': isDragOver }"
        @dragover.prevent="handleDragOver"
        @dragleave.prevent="handleDragLeave"
        @drop.prevent="handleDrop"
        @click="triggerFileInput"
      >
        <input
          ref="fileInput"
          type="file"
          accept=".csv,.txt,.xlsx,.xls"
          @change="handleFileSelect"
          style="display: none"
        />

        <div class="drop-zone-content">
          <span class="icon">📁</span>
          <p class="text">拖拽 CSV/Excel 文件到这里</p>
          <p class="sub-text">或点击选择文件</p>
        </div>
      </div>

      <div class="supported-files">
        <p>支持：支付宝 CSV / 微信 CSV 或 Excel(.xlsx)</p>
      </div>

      <div v-if="hasExistingData" class="existing-data">
        <p>检测到已有持久化账单数据，是否直接查看 Dashboard？</p>
        <button @click="goToDashboard" class="btn-secondary">查看 Dashboard →</button>
      </div>

      <div v-if="status" class="status" :class="status.type">
        {{ status.message }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { saveTransactions, getTransactions } from '@/utils/storage'
import { useFinanceStore } from '@/stores/finance'
import { fetchAgentMonths, fetchParsedTransactions } from '@/utils/api'

const router = useRouter()
const financeStore = useFinanceStore()
const fileInput = ref(null)
const isDragOver = ref(false)
const status = ref(null)
const hasExistingData = ref(false)

onMounted(async () => {
  try {
    const months = await fetchAgentMonths()
    hasExistingData.value = months.length > 0
  } catch {
    const data = getTransactions()
    hasExistingData.value = data && data.length > 0
  }
})

function handleDragOver() {
  isDragOver.value = true
}

function handleDragLeave() {
  isDragOver.value = false
}

function handleDrop(event) {
  isDragOver.value = false
  const files = event.dataTransfer.files
  if (files.length > 0) {
    processFile(files[0])
  }
}

function triggerFileInput() {
  fileInput.value.click()
}

function handleFileSelect(event) {
  const files = event.target.files
  if (files.length > 0) {
    processFile(files[0])
  }
}

async function processFile(file) {
  status.value = { type: 'loading', message: '正在上传并解析文件...' }

  try {
    const { transactions, message } = await fetchParsedTransactions(file)
    saveTransactions(transactions)

    const importedMonth = transactions[0]?.date?.slice(0, 7) || ''
    await financeStore.initialize(importedMonth)

    status.value = { type: 'success', message: message || `成功解析 ${transactions.length} 条记录！` }
    hasExistingData.value = true

    setTimeout(() => {
      if (financeStore.pendingReviews.length > 0) {
        router.push('/review')
      } else {
        router.push('/dashboard')
      }
    }, 1500)
  } catch (error) {
    console.error('解析错误:', error)
    status.value = { type: 'error', message: error.message || '文件解析失败' }
  }
}

function goToDashboard() {
  router.push('/dashboard')
}
</script>

<style scoped>
.upload-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.container {
  max-width: 500px;
  width: 100%;
  text-align: center;
}

.title {
  color: white;
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
}

.subtitle {
  color: rgba(255, 255, 255, 0.8);
  margin-bottom: 2rem;
}

.drop-zone {
  background: white;
  border: 3px dashed #ddd;
  border-radius: 16px;
  padding: 3rem 2rem;
  cursor: pointer;
  transition: all 0.3s ease;
}

.drop-zone:hover,
.drop-zone.drag-over {
  border-color: #667eea;
  background: #f8f9ff;
  transform: scale(1.02);
}

.drop-zone-content .icon {
  font-size: 3rem;
  display: block;
  margin-bottom: 1rem;
}

.drop-zone-content .text {
  font-size: 1.2rem;
  color: #333;
  margin-bottom: 0.5rem;
}

.drop-zone-content .sub-text {
  color: #999;
  font-size: 0.9rem;
}

.supported-files {
  margin-top: 1.5rem;
  color: rgba(255, 255, 255, 0.7);
}

.existing-data {
  margin-top: 2rem;
  padding: 1.5rem;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  color: white;
}

.btn-secondary {
  margin-top: 1rem;
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 8px;
  background: white;
  color: #667eea;
  font-weight: 600;
  cursor: pointer;
}

.status {
  margin-top: 1.5rem;
  padding: 1rem;
  border-radius: 8px;
  font-weight: 500;
}

.status.loading {
  background: rgba(255, 255, 255, 0.2);
  color: white;
}

.status.success {
  background: rgba(82, 196, 26, 0.18);
  color: white;
  border: 1px solid rgba(82, 196, 26, 0.35);
}

.status.error {
  background: rgba(255, 77, 79, 0.18);
  color: white;
  border: 1px solid rgba(255, 77, 79, 0.35);
}
</style>
