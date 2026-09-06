import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchParsedTransactions } from '../src/utils/api'

const file = new File(['mock'], 'bill.csv', { type: 'text/csv' })

function mockFetchJson(data, ok = true) {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok,
    json: async () => data,
    text: async () => JSON.stringify(data),
    status: ok ? 200 : 500,
    statusText: ok ? 'OK' : 'Internal Server Error',
  })
}

describe('fetchParsedTransactions', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('preserves amount and type while mapping category to Chinese', async () => {
    mockFetchJson({
      success: true,
      transactions: [
        {
          id: 'tx_1',
          date: '2026-04-01',
          amount: 23.5,
          category: 'other',
          description: '测试商户',
          source: 'alipay',
          type: 'expense',
        },
      ],
    })

    const result = await fetchParsedTransactions(file)

    expect(result.transactions).toHaveLength(1)
    expect(result.transactions[0]).toMatchObject({
      amount: 23.5,
      type: 'expense',
      category: '其他',
    })
  })

  it('maps known backend category codes to Chinese labels used by the UI', async () => {
    mockFetchJson({
      success: true,
      transactions: [
        {
          id: 'tx_1',
          date: '2026-04-01',
          amount: 23.5,
          category: 'dining',
          description: '测试商户',
          source: 'alipay',
          type: 'expense',
        },
        {
          id: 'tx_2',
          date: '2026-04-01',
          amount: 23.5,
          category: 'healthcare',
          description: '测试商户',
          source: 'alipay',
          type: 'expense',
        },
        {
          id: 'tx_3',
          date: '2026-04-01',
          amount: 23.5,
          category: 'other',
          description: '测试商户',
          source: 'alipay',
          type: 'expense',
        },
      ],
    })

    const result = await fetchParsedTransactions(file)

    expect(result.transactions).toHaveLength(3)
    expect(result.transactions.map(tx => tx.category)).toEqual(['餐饮', '医疗', '其他'])
  })

  it('normalizes structured category objects from parse API before passing data to dashboard', async () => {
    mockFetchJson({
      success: true,
      transactions: [
        {
          id: 'tx_structured_category',
          date: '2026-04-01',
          amount: -23.5,
          category: {
            category: '餐饮',
            confidence: 0.9,
            reason: '包含咖啡关键词',
            requires_human_review: false,
          },
          description: '星巴克',
          source: 'alipay',
          type: 'expense',
        },
      ],
    })

    const result = await fetchParsedTransactions(file)

    expect(result.transactions[0].category).toBe('餐饮')
  })

  it('preserves parse API message so upload page can show persistence status', async () => {
    mockFetchJson({
      success: true,
      message: '成功解析 1 笔交易；未配置 DATABASE_URL，当前未写入数据库',
      transactions: [
        {
          id: 'tx_1',
          date: '2026-04-01',
          amount: -23.5,
          category: 'other',
          description: '测试商户',
          source: 'alipay',
          type: 'expense',
        },
      ],
    })

    const result = await fetchParsedTransactions(file)

    expect(result.message).toBe('成功解析 1 笔交易；未配置 DATABASE_URL，当前未写入数据库')
  })

  it('throws when parse API returns invalid transaction payload', async () => {
    mockFetchJson({
      success: true,
      transactions: null,
    })

    await expect(fetchParsedTransactions(file)).rejects.toThrow('解析返回格式错误')
  })
})
