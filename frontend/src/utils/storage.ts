import type { Transaction } from '@/types/finance'

/**
 * localStorage 存储工具
 */

const STORAGE_KEY = 'financial_assistant_transactions'

/**
 * 保存交易数据
 */
export function saveTransactions(transactions: Transaction[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(transactions))
  } catch (e) {
    console.error('保存数据失败:', e)
    throw new Error('数据保存失败', { cause: e })
  }
}

/**
 * 获取交易数据
 */
export function getTransactions(): Transaction[] {
  try {
    const data = localStorage.getItem(STORAGE_KEY)
    return data ? (JSON.parse(data) as Transaction[]) : []
  } catch (e) {
    console.error('读取数据失败:', e)
    return []
  }
}

/**
 * 清除交易数据
 */
export function clearTransactions(): void {
  localStorage.removeItem(STORAGE_KEY)
}

/**
 * 获取指定月份的数据
 */
export function getTransactionsByMonth(month: string): Transaction[] {
  const all = getTransactions()
  return all.filter(t => t.date.startsWith(month))
}

/**
 * 获取最新数据，按日期排序
 */
export function getLatestTransactions(limit = 10): Transaction[] {
  const all = getTransactions()
  return all
    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
    .slice(0, limit)
}

