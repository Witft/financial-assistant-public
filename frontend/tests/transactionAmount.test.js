import { describe, expect, it } from 'vitest'
import { formatTransactionAmount } from '../src/utils/transactionAmount'

describe('formatTransactionAmount', () => {
  it('formats expense by type even when amount is positive', () => {
    expect(formatTransactionAmount(23.5, 'expense')).toBe('-¥23.50')
  })

  it('formats income with plus prefix', () => {
    expect(formatTransactionAmount(88, 'income')).toBe('+¥88.00')
  })

  it('formats transfer without sign', () => {
    expect(formatTransactionAmount(50, 'transfer')).toBe('¥50.00')
  })
})
