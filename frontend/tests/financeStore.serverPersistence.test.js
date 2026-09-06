import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useFinanceStore } from '../src/stores/finance'

const storageMocks = vi.hoisted(() => ({
  transactions: [],
  clearTransactions: vi.fn(),
  saveTransactions: vi.fn(),
}))

const apiMocks = vi.hoisted(() => ({
  fetchAgentMonths: vi.fn(),
  fetchMonthlySummary: vi.fn(),
  fetchAgentTransactions: vi.fn(),
}))

vi.mock('@/utils/storage', () => ({
  getTransactions: () => storageMocks.transactions,
  clearTransactions: storageMocks.clearTransactions,
  saveTransactions: storageMocks.saveTransactions,
}))

vi.mock('@/utils/api', async importOriginal => {
  const actual = await importOriginal()
  return {
    ...actual,
    fetchAgentMonths: apiMocks.fetchAgentMonths,
    fetchMonthlySummary: apiMocks.fetchMonthlySummary,
    fetchAgentTransactions: apiMocks.fetchAgentTransactions,
  }
})

describe('financeStore server-backed dashboard flow', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    storageMocks.transactions = []
    vi.clearAllMocks()
  })

  it('initializes from persisted backend data and prefers latest month', async () => {
    apiMocks.fetchAgentMonths.mockResolvedValue(['2026-03', '2026-05'])
    apiMocks.fetchMonthlySummary.mockResolvedValue({
      month: '2026-05',
      summary: {
        income: 10000,
        expense: 259,
        transfer: 0,
        balance: 9741,
        transaction_count: 5,
      },
      category_expenses: [],
    })
    apiMocks.fetchAgentTransactions.mockResolvedValue([
      {
        id: 'tx_1',
        date: '2026-05-01',
        amount: -39,
        category: '餐饮',
        description: '麦当劳',
        source: 'alipay',
        type: 'expense',
        requires_human_review: false,
      },
      {
        id: 'tx_2',
        date: '2026-05-02',
        amount: 10000,
        category: '其他',
        description: '工资',
        source: 'wechat',
        type: 'income',
        requires_human_review: true,
      },
    ])

    const store = useFinanceStore()
    await store.initialize()

    expect(store.availableMonths).toEqual(['2026-03', '2026-05'])
    expect(store.selectedMonth).toBe('2026-05')
    expect(store.totalIncome).toBe(10000)
    expect(store.totalExpense).toBe(259)
    expect(store.balance).toBe(9741)
    expect(store.pendingReviews.map(tx => tx.id)).toEqual(['tx_2'])
    expect(storageMocks.saveTransactions).toHaveBeenCalledWith(expect.arrayContaining([
      expect.objectContaining({ id: 'tx_1', category: '餐饮' }),
      expect.objectContaining({ id: 'tx_2', category: '其他' }),
    ]))
  })

  it('falls back to local cache when backend months API is unavailable', async () => {
    storageMocks.transactions = [
      {
        id: 'local_1',
        date: '2026-04-03',
        amount: -18,
        category: '其他',
        description: '本地缓存交易',
        source: 'alipay',
        type: 'expense',
        requires_human_review: true,
      },
    ]
    apiMocks.fetchAgentMonths.mockRejectedValue(new Error('503 service unavailable'))

    const store = useFinanceStore()
    await store.initialize('2026-04')

    expect(store.selectedMonth).toBe('2026-04')
    expect(store.filteredTransactions).toEqual([
      expect.objectContaining({ id: 'local_1', category: '其他' }),
    ])
    expect(store.pendingReviews.map(tx => tx.id)).toEqual(['local_1'])
    expect(store.loadError).toBe('')
  })
})
