import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchAgentMonths, fetchAgentTransactions, fetchMonthlySummary } from '../src/utils/api'

function mockFetchJson(data, ok = true) {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok,
    json: async () => data,
    text: async () => JSON.stringify(data),
    status: ok ? 200 : 500,
    statusText: ok ? 'OK' : 'Internal Server Error',
  })
}

describe('agent persistence APIs', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('fetchAgentMonths returns server months list', async () => {
    mockFetchJson({ success: true, months: ['2026-03', '2026-04', '2026-05'] })

    const months = await fetchAgentMonths()

    expect(months).toEqual(['2026-03', '2026-04', '2026-05'])
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/agent/months')
  })

  it('fetchMonthlySummary normalizes backend category codes for UI', async () => {
    mockFetchJson({
      success: true,
      month: '2026-05',
      summary: {
        income: 10000,
        expense: 259,
        transfer: 0,
        balance: 9741,
        transaction_count: 5,
      },
      category_expenses: [
        { category: 'dining', amount: 59, transaction_count: 2 },
        { category: 'transportation', amount: 20, transaction_count: 1 },
      ],
    })

    const result = await fetchMonthlySummary('2026-05')

    expect(result.summary.expense).toBe(259)
    expect(result.category_expenses).toEqual([
      { category: '餐饮', amount: 59, transaction_count: 2 },
      { category: '交通', amount: 20, transaction_count: 1 },
    ])
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/agent/monthly-summary?month=2026-05')
  })

  it('fetchAgentTransactions maps persisted transactions into frontend shape', async () => {
    mockFetchJson({
      success: true,
      count: 2,
      transactions: [
        {
          id: 'tx_1',
          date: '2026-05-01',
          amount: -39,
          category: 'dining',
          description: '麦当劳',
          source: 'alipay',
          type: 'expense',
          requires_human_review: false,
        },
        {
          id: 'tx_2',
          date: '2026-05-02',
          amount: 10000,
          category: 'other',
          description: '工资',
          source: 'wechat',
          type: 'income',
          requires_human_review: true,
        },
      ],
    })

    const transactions = await fetchAgentTransactions('2026-05')

    expect(transactions).toEqual([
      expect.objectContaining({ id: 'tx_1', category: '餐饮', amount: -39, type: 'expense' }),
      expect.objectContaining({ id: 'tx_2', category: '其他', requires_human_review: true, type: 'income' }),
    ])
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/agent/transactions?month=2026-05&limit=200')
  })
})
