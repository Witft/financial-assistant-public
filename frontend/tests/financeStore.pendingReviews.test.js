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

function createTransaction(overrides = {}) {
  return {
    id: 'tx-default',
    date: '2026-04-01',
    amount: 23.5,
    category: '其他',
    description: '测试商户',
    source: 'alipay',
    type: 'expense',
    ...overrides,
  }
}

describe('financeStore.pendingReviews', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    storageMocks.transactions = []
    vi.clearAllMocks()
  })

  it('includes transactions categorized as 其他 or other', () => {
    storageMocks.transactions = [
      createTransaction({ id: 'cn-other', category: '其他' }),
      createTransaction({ id: 'en-other', category: 'other' }),
      createTransaction({ id: 'dining', category: '餐饮' }),
    ]

    const store = useFinanceStore()

    expect(store.pendingReviews.map(tx => tx.id)).toEqual(['cn-other', 'en-other'])
  })

  it('excludes transactions that already have a concrete category', () => {
    storageMocks.transactions = [
      createTransaction({ id: 'dining', category: '餐饮' }),
      createTransaction({ id: 'shopping', category: '购物' }),
      createTransaction({ id: 'income', category: '收入', type: 'income', amount: 88 }),
    ]

    const store = useFinanceStore()

    expect(store.pendingReviews).toEqual([])
  })

  it('removes a transaction from pendingReviews after manual recategorization and persists the update', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    })

    storageMocks.transactions = [
      createTransaction({ id: 'review-1', category: '其他', description: '星巴克' }),
      createTransaction({ id: 'review-2', category: 'other', description: '未知商户' }),
    ]

    const store = useFinanceStore()

    expect(store.pendingReviews.map(tx => tx.id)).toEqual(['review-1', 'review-2'])

    await store.updateTransactionCategory('review-1', '餐饮')

    expect(store.pendingReviews.map(tx => tx.id)).toEqual(['review-2'])
    expect(store.correctionError).toBe('')
    expect(storageMocks.saveTransactions).toHaveBeenCalledTimes(1)
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/transactions/correct', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ transaction_id: 'review-1', description: '星巴克', category: 'dining' }),
    }))
    expect(storageMocks.saveTransactions).toHaveBeenCalledWith(expect.arrayContaining([
      expect.objectContaining({ id: 'review-1', category: '餐饮' }),
      expect.objectContaining({ id: 'review-2', category: '其他' }),
    ]))
  })

  it('rolls back the optimistic update and exposes a correction error when persistence fails', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: async () => ({ detail: '保存失败，请稍后重试' }),
    })

    storageMocks.transactions = [
      createTransaction({ id: 'review-1', category: '其他', description: '星巴克', requires_human_review: true }),
    ]

    const store = useFinanceStore()

    await expect(store.updateTransactionCategory('review-1', '餐饮')).rejects.toThrow('保存失败，请稍后重试')

    expect(store.pendingReviews.map(tx => tx.id)).toEqual(['review-1'])
    expect(store.transactions.find(tx => tx.id === 'review-1')).toEqual(
      expect.objectContaining({ category: '其他', requires_human_review: true })
    )
    expect(store.correctionError).toBe('保存失败，请稍后重试')
    expect(storageMocks.saveTransactions).toHaveBeenCalledTimes(2)
    expect(storageMocks.saveTransactions).toHaveBeenNthCalledWith(2, expect.arrayContaining([
      expect.objectContaining({ id: 'review-1', category: '其他', requires_human_review: true }),
    ]))
  })
})
