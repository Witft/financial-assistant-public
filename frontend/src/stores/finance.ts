import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { getTransactions, clearTransactions, saveTransactions } from '@/utils/storage'
import { normalizeCategoryLabel } from '@/utils/category'
import {
  fetchAgentMonths,
  fetchAgentTransactions,
  fetchLatestImportJob,
  fetchMonthlySummary,
  submitTransactionCorrection,
} from '@/utils/api'
import type { ImportJob, MonthlySummary, Transaction } from '@/types/finance'

export const useFinanceStore = defineStore('finance', () => {
  function normalizeTransactionCategories(items: Transaction[]): Transaction[] {
    return items.map(t => ({
      ...t,
      category: normalizeCategoryLabel(t.category),
    }))
  }

  function buildAvailableMonths(items: Transaction[]) {
    return Array.from(new Set(items.map(item => item.date.slice(0, 7)))).sort()
  }

  function applyTransactions(items: Transaction[]) {
    const normalized = normalizeTransactionCategories(items || [])
    transactions.value = normalized
    return normalized
  }

  function refresh() {
    const localTransactions = applyTransactions(getTransactions() || [])
    availableMonths.value = buildAvailableMonths(localTransactions)
    if (!selectedMonth.value && availableMonths.value.length > 0) {
      selectedMonth.value = availableMonths.value[availableMonths.value.length - 1]
    }
    summary.value = null
  }

  function fallbackToLocalCache(preferredMonth = '') {
    refresh()
    if (preferredMonth) {
      selectedMonth.value = preferredMonth
    }
    loadError.value = ''
  }

  const transactions = ref<Transaction[]>([])
  const selectedMonth = ref('')
  const availableMonths = ref<string[]>([])
  const summary = ref<MonthlySummary | null>(null)
  const isLoading = ref(false)
  const loadError = ref('')
  const correctionError = ref('')
  const latestImportJob = ref<ImportJob | null>(null)

  refresh()

  const pendingReviews = computed(() => {
    return transactions.value.filter(
      t => t.requires_human_review === true || t.category === 'other' || t.category === '其他'
    )
  })

  const filteredTransactions = computed(() => {
    if (!selectedMonth.value) return transactions.value
    return transactions.value.filter(t => t.date.startsWith(selectedMonth.value))
  })

  const totalIncome = computed(() => {
    if (summary.value && selectedMonth.value) {
      return summary.value.income
    }

    return filteredTransactions.value
      .filter(t => t.type === 'income')
      .reduce((sum, t) => sum + Math.abs(t.amount), 0)
  })

  const totalExpense = computed(() => {
    if (summary.value && selectedMonth.value) {
      return summary.value.expense
    }

    return filteredTransactions.value
      .filter(t => t.type === 'expense')
      .reduce((sum, t) => sum + Math.abs(t.amount), 0)
  })

  const balance = computed(() => {
    if (summary.value && selectedMonth.value) {
      return summary.value.balance
    }
    return totalIncome.value - totalExpense.value
  })

  const filteredExpensesByCategory = computed(() => {
    const map: Record<string, number> = {}
    filteredTransactions.value
      .filter(t => t.type === 'expense')
      .forEach(t => {
        if (!map[t.category]) map[t.category] = 0
        map[t.category] += Math.abs(t.amount)
      })

    const total = Object.values(map).reduce((s, v) => s + v, 0)
    const COLORS = [
      '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4',
      '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F',
      '#BB8FCE', '#85C1E9', '#F8B500', '#6BCB77',
    ]
    return Object.entries(map)
      .map(([name, value], index) => ({
        name,
        value,
        color: COLORS[index % COLORS.length],
        pct: total > 0 ? Math.round((value / total) * 100) : 0,
      }))
      .sort((a, b) => b.value - a.value)
  })

  const aiPromptData = computed(() => {
    const topExpenses = [...filteredTransactions.value]
      .filter(t => t.type === 'expense')
      .sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount))
      .slice(0, 3)
      .map(t => ({
        date: t.date,
        category: t.category,
        amount: Math.abs(t.amount).toFixed(2),
        desc: t.description || '无明细',
      }))

    const topCategories = filteredExpensesByCategory.value
      .slice(0, 3)
      .map(c => ({
        name: c.name,
        amount: c.value.toFixed(2),
        pct: `${c.pct}%`,
      }))

    return {
      month: selectedMonth.value || '全部历史',
      summary: {
        income: totalIncome.value.toFixed(2),
        expense: totalExpense.value.toFixed(2),
        balance: balance.value.toFixed(2),
      },
      top_categories: topCategories,
      top_expenses: topExpenses,
    }
  })

  async function loadMonthData(month: string) {
    if (!month) {
      selectedMonth.value = ''
      summary.value = null
      transactions.value = []
      return
    }

    isLoading.value = true
    loadError.value = ''

    try {
      const [summaryPayload, monthTransactions] = await Promise.all([
        fetchMonthlySummary(month),
        fetchAgentTransactions(month),
      ])

      selectedMonth.value = month
      summary.value = summaryPayload.summary
      const normalized = applyTransactions(monthTransactions)
      saveTransactions(normalized)

      if (!availableMonths.value.includes(month)) {
        availableMonths.value = [...availableMonths.value, month].sort()
      }
    } catch (error) {
      loadError.value = error instanceof Error ? error.message : '加载服务端财务数据失败'
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function refreshLatestImportJob() {
    try {
      latestImportJob.value = await fetchLatestImportJob()
    } catch (error) {
      console.warn('Failed to load latest import job:', error)
      latestImportJob.value = null
    }
  }

  async function initialize(preferredMonth = '') {
    isLoading.value = true
    loadError.value = ''

    try {
      const months = await fetchAgentMonths()
      availableMonths.value = months
      await refreshLatestImportJob()

      const targetMonth = preferredMonth || selectedMonth.value || months[months.length - 1] || ''
      if (!targetMonth) {
        selectedMonth.value = ''
        summary.value = null
        transactions.value = []
        return
      }

      await loadMonthData(targetMonth)
    } catch (error) {
      console.warn('Falling back to local transaction cache:', error)
      latestImportJob.value = null
      fallbackToLocalCache(preferredMonth)
    } finally {
      isLoading.value = false
    }
  }

  function clear() {
    clearTransactions()
    transactions.value = []
    availableMonths.value = []
    selectedMonth.value = ''
    summary.value = null
    loadError.value = ''
    correctionError.value = ''
    latestImportJob.value = null
  }

  async function updateTransactionCategory(id: string, category: string) {
    const transaction = transactions.value.find(t => t.id === id)
    if (!transaction) return

    correctionError.value = ''

    const previousCategory = transaction.category
    const previousRequiresHumanReview = transaction.requires_human_review

    transaction.category = category
    transaction.requires_human_review = false
    saveTransactions(transactions.value)

    try {
      await submitTransactionCorrection({
        transactionId: id,
        description: transaction.description,
        category,
        jobId: transaction.import_job_id,
      })
    } catch (err) {
      transaction.category = previousCategory
      transaction.requires_human_review = previousRequiresHumanReview
      saveTransactions(transactions.value)
      correctionError.value = err instanceof Error ? err.message : '保存交易分类失败，请重试'
      console.error('Failed to persist transaction category:', err)
      throw err
    }
  }

  return {
    transactions,
    selectedMonth,
    availableMonths,
    summary,
    isLoading,
    loadError,
    pendingReviews,
    filteredTransactions,
    totalIncome,
    totalExpense,
    balance,
    filteredExpensesByCategory,
    aiPromptData,
    correctionError,
    latestImportJob,
    refresh,
    initialize,
    loadMonthData,
    refreshLatestImportJob,
    clear,
    updateTransactionCategory,
  }
})
