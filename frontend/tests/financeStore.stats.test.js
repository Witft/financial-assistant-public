import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useFinanceStore } from '../src/stores/finance'

const storageMocks = vi.hoisted(() => ({
  transactions: [],
  clearTransactions: vi.fn(),
  saveTransactions: vi.fn(),
}))

vi.mock('@/utils/storage', () => ({
  getTransactions: () => storageMocks.transactions,
  clearTransactions: storageMocks.clearTransactions,
  saveTransactions: storageMocks.saveTransactions,
}))

function createTransaction(amount, type) {
  return { id: Math.random().toString(), date: '2026-04-01', category: '测试', amount, type }
}

describe('financeStore.stats (Dashboard计算逻辑)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    storageMocks.transactions = []
    vi.clearAllMocks()
  })

  it('正确计算 totalIncome, totalExpense 和 balance，且忽略 transfer', () => {
    storageMocks.transactions = [
        createTransaction(-100, 'expense'),
        createTransaction(50, 'expense'), // 退款等情况
        createTransaction(500, 'income'),
        createTransaction(-200, 'transfer')
    ]

    const store = useFinanceStore()

    expect(store.totalExpense).toBe(150)
    expect(store.totalIncome).toBe(500)
    expect(store.balance).toBe(350)
  })
})
